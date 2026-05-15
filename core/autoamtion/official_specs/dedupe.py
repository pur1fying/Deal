from __future__ import annotations

import argparse
import json
import re
import textwrap
from collections import defaultdict
from pathlib import Path
from typing import Any


BRAND_ORDER = {
    "Fujifilm": 0,
    "Canon": 1,
    "Sony": 2,
    "Hasselblad": 3,
    "Nikon": 4,
}

BRAND_ROW_COLORS = {
    "Fujifilm": "#e3f2ea",
    "Canon": "#fde4e4",
    "Sony": "#e4eefc",
    "Hasselblad": "#f4ecd8",
    "Nikon": "#fff6bf",
}


def dedupe_result_file(
    result_path: Path | str,
    output_path: Path | str | None = None,
) -> dict[str, Any]:
    result = json.loads(Path(result_path).read_text(encoding="utf-8"))
    items = result.get("items", [])
    deduped_items = dedupe_items(items)
    output = Path(output_path) if output_path else Path(result_path).with_name("result_deduped.json")
    deduped = {
        **{key: value for key, value in result.items() if key != "items"},
        "total": len(deduped_items),
        "items": deduped_items,
        "source_total": len(items),
        "deduped": True,
        "dedupe_removed": len(items) - len(deduped_items),
        "result_path": str(output),
    }
    output.write_text(json.dumps(deduped, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return deduped


def dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        groups[(str(item.get("brand") or ""), normalize_model(str(item.get("model") or "")))].append(item)

    merged: list[dict[str, Any]] = []
    for (_brand, _model_key), group in groups.items():
        if not _model_key:
            merged.extend(sanitize_item(item) for item in group)
            continue
        merged.append(merge_group(group))
    return sorted(
        merged,
        key=lambda item: (
            BRAND_ORDER.get(str(item.get("brand") or ""), 99),
            normalize_model(str(item.get("model") or "")),
            str(item.get("source_url") or ""),
        ),
    )


def normalize_model(model: str) -> str:
    value = model.strip().lower()
    value = re.sub(r"\|.*", "", value)
    value = re.sub(r"\s+-\s+(filmmaking|professional|classic style|pocket size).*", "", value)
    value = re.sub(r"\b(camera|cameras|mirrorless|digital|interchangeable lens|hybrid|body only)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", "", value)
    return value


def merge_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    primary = max(group, key=item_score)
    merged = dict(primary)
    for key in [
        "sensor_format",
        "megapixels",
        "official_price_text",
        "official_price",
        "original_price_text",
        "original_price",
        "price_currency",
        "captured_at",
    ]:
        merged[key] = first_non_empty([primary.get(key), *[item.get(key) for item in group]])
    for key in ["video_formats"]:
        merged[key] = union_list(item.get(key) for item in group)
    merged["video_modes"] = union_video_modes(group)
    merged.pop("video_resolution", None)
    merged.pop("video_frame_rates", None)
    source_urls = union_list([[item.get("source_url")] for item in group])
    merged["source_url"] = primary.get("source_url") or (source_urls[0] if source_urls else None)
    merged["merged_source_urls"] = source_urls
    merged["duplicate_count"] = len(group)
    return merged


def sanitize_item(item: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(item)
    sanitized["video_modes"] = normalize_video_modes_from_item(item)
    sanitized.pop("video_resolution", None)
    sanitized.pop("video_frame_rates", None)
    return sanitized


def item_score(item: dict[str, Any]) -> float:
    score = 0.0
    for key in ["sensor_format", "megapixels", "official_price_text", "official_price", "original_price_text"]:
        if item.get(key) not in (None, "", []):
            score += 8
    score += min(len(normalize_video_modes_from_item(item)), 10)
    score += min(len(item.get("video_formats") or []), 10)
    url = str(item.get("source_url") or "").lower()
    if "specification" in url or "specifications" in url:
        score += 12
    if any(part in url for part in ["/shop/", "accessories", "firmware", "lenses"]):
        score -= 15
    model = str(item.get("model") or "").lower()
    if model in {"logo, back to home page", "electronics", "store"}:
        score -= 20
    return score


def first_non_empty(values: list[Any]) -> Any:
    for value in values:
        if value not in (None, "", []):
            return value
    return None


def union_list(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for values_item in values:
        for value in values_item or []:
            if value in (None, ""):
                continue
            text = str(value)
            if text not in seen:
                seen.add(text)
                result.append(text)
    return result


def union_video_modes(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        for mode in normalize_video_modes_from_item(item):
            key = (mode["resolution"].upper(), mode["fps"].lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(mode)
    return result


def normalize_video_modes_from_item(item: dict[str, Any]) -> list[dict[str, str]]:
    modes: list[dict[str, str]] = []
    for value in item.get("video_modes") or []:
        mode = parse_video_mode(value)
        if mode:
            modes.append(mode)
    legacy_resolutions = [str(value).strip() for value in item.get("video_resolution") or [] if str(value).strip()]
    legacy_rates = [str(value).strip() for value in item.get("video_frame_rates") or [] if str(value).strip()]
    for resolution in legacy_resolutions:
        if legacy_rates:
            for fps in legacy_rates:
                modes.append({"resolution": normalize_resolution(resolution), "fps": normalize_fps(fps)})
        else:
            modes.append({"resolution": normalize_resolution(resolution), "fps": ""})
    return unique_video_modes(modes)


def unique_video_modes(modes: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for mode in modes:
        resolution = str(mode.get("resolution") or "").strip()
        fps = str(mode.get("fps") or "").strip()
        if not resolution and not fps:
            continue
        key = (resolution.upper(), fps.lower())
        if key in seen:
            continue
        seen.add(key)
        result.append({"resolution": resolution, "fps": fps})
    return result


def parse_video_mode(value: Any) -> dict[str, str] | None:
    if isinstance(value, dict):
        resolution = normalize_resolution(str(value.get("resolution") or ""))
        fps = normalize_fps(str(value.get("fps") or ""))
        if resolution or fps:
            return {"resolution": resolution, "fps": fps}
        return None
    text = str(value or "").strip()
    if not text:
        return None
    match = re.search(
        r"(?P<resolution>\b(?:8K|6\.2K|6K|5\.8K|5\.7K|5\.4K|4K|2K)\b|"
        r"\b(?:7680|6240|6000|4096|3840|1920)\s*x\s*(?:4320|4160|3160|2160|1080)\b)"
        r".*?"
        r"(?P<fps>[1-9][0-9]{1,2}(?:\.[0-9]+)?\s*(?:fps|p)\b)",
        text,
        re.IGNORECASE,
    )
    if match:
        return {
            "resolution": normalize_resolution(match.group("resolution")),
            "fps": normalize_fps(match.group("fps")),
        }
    return {"resolution": normalize_resolution(text), "fps": ""}


def normalize_resolution(value: str) -> str:
    return re.sub(r"\s+", "", value.strip().upper())


def normalize_fps(value: str) -> str:
    match = re.search(r"([1-9][0-9]{1,2}(?:\.[0-9]+)?)", value)
    if not match:
        return value.strip()
    return f"{float(match.group(1)):g}p"


def compact_video_modes(item: dict[str, Any], limit: int) -> str:
    values = [
        " ".join(part for part in [mode["resolution"], mode["fps"]] if part)
        for mode in normalize_video_modes_from_item(item)
    ]
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", +{len(values) - limit}"


def draw_deduped_table(
    items: list[dict[str, Any]],
    output_path: Path | str,
    *,
    source_label: str = "",
    title: str = "Camera Official Specs - Deduped Record Table",
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = [
        ("#", 0.035, "center"),
        ("Brand", 0.075, "left"),
        ("Model", 0.16, "left"),
        ("Dup", 0.04, "right"),
        ("Sensor", 0.075, "left"),
        ("MP", 0.055, "right"),
        ("Official", 0.08, "right"),
        ("Original", 0.075, "right"),
        ("Video Modes", 0.205, "left"),
        ("Formats", 0.085, "left"),
        ("URL", 0.095, "left"),
    ]
    total_width = sum(width for _, width, _ in columns)
    columns = [(name, width / total_width, align) for name, width, align in columns]
    rows = [table_row(index, item) for index, item in enumerate(items, start=1)]
    char_budgets = [3, 9, 24, 3, 10, 7, 10, 10, 30, 15, 18]
    wrapped_rows = [
        [wrap_cell(value, char_budgets[index]) for index, value in enumerate(row)]
        for row in rows
    ]
    row_heights = [
        0.32 + 0.16 * (max(cell.count("\n") + 1 for cell in row) - 1)
        for row in wrapped_rows
    ]
    title_h = 1.05
    header_h = 0.58
    footer_h = 0.36
    fig_w = 18
    fig_h = title_h + header_h + sum(row_heights) + footer_h
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=160)
    fig.patch.set_facecolor("#f6f7fb")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, fig_h)
    ax.axis("off")

    ax.text(0.5, fig_h - 0.38, title, ha="center", va="center", fontsize=17, fontweight="bold", color="#111827")
    ax.text(0.5, fig_h - 0.77, f"{source_label} | unique rows: {len(items)}", ha="center", va="center", fontsize=8.8, color="#4b5563")

    x_positions = [0]
    for _, width, _ in columns:
        x_positions.append(x_positions[-1] + width)
    y = fig_h - title_h - header_h
    for col_index, (name, width, _align) in enumerate(columns):
        x0 = x_positions[col_index]
        ax.add_patch(Rectangle((x0, y), width, header_h, facecolor="#172033", edgecolor="#ffffff", linewidth=0.7))
        ax.text(x0 + width / 2, y + header_h / 2, name, ha="center", va="center", fontsize=8.3, fontweight="bold", color="#ffffff")

    current_y = y
    for row_index, row in enumerate(wrapped_rows):
        item = items[row_index]
        row_h = row_heights[row_index]
        current_y -= row_h
        bg = BRAND_ROW_COLORS.get(str(item.get("brand") or ""), "#ffffff")
        for col_index, (_name, width, align) in enumerate(columns):
            x0 = x_positions[col_index]
            ax.add_patch(Rectangle((x0, current_y), width, row_h, facecolor=bg, edgecolor="#a7b3c4", linewidth=0.42))
            pad = 0.0035
            if align == "center":
                tx = x0 + width / 2
            elif align == "right":
                tx = x0 + width - pad
            else:
                tx = x0 + pad
            fs = 5.9 if col_index in {8, 9, 10} else 6.4
            fw = "bold" if col_index in {1, 2} else "normal"
            ax.text(tx, current_y + row_h / 2, row[col_index], ha=align, va="center", fontsize=fs, fontweight=fw, color="#111827", linespacing=1.04)

    ax.text(0.0, 0.12, "Dup = number of duplicate raw rows merged into this record. Brand rows use fixed background colors.", ha="left", va="bottom", fontsize=7.8, color="#4b5563")
    fig.savefig(output, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return output


def table_row(index: int, item: dict[str, Any]) -> list[str]:
    return [
        str(index),
        str(item.get("brand") or ""),
        str(item.get("model") or ""),
        str(item.get("duplicate_count") or 1),
        str(item.get("sensor_format") or ""),
        str(item.get("megapixels") or ""),
        str(item.get("official_price_text") or ""),
        str(item.get("original_price_text") or ""),
        compact_video_modes(item, 8),
        compact_list(item.get("video_formats"), 5),
        short_url(item.get("source_url")),
    ]


def compact_list(values: Any, limit: int) -> str:
    items = [str(value).strip() for value in values or [] if str(value).strip()]
    if len(items) <= limit:
        return ", ".join(items)
    return ", ".join(items[:limit]) + f", +{len(items) - limit}"


def short_url(value: Any) -> str:
    url = str(value or "").replace("https://", "").replace("http://", "")
    url = re.sub(r"/$", "", url)
    return url


def wrap_cell(value: Any, width: int) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if not text:
        return ""
    return "\n".join(textwrap.wrap(text, width=max(5, width), break_long_words=True, break_on_hyphens=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--input", default="result.json")
    parser.add_argument("--output-json", default="result_deduped.json")
    parser.add_argument("--output-image", default="charts/cam_spec_full_table_deduped.png")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    source = run_dir / args.input
    output_json = run_dir / args.output_json
    deduped = dedupe_result_file(source, output_json)
    image_path = draw_deduped_table(
        deduped["items"],
        run_dir / args.output_image,
        source_label=f"Source: {source}",
    )
    print(f"wrote {deduped['total']} unique rows to {output_json}")
    print(f"removed {deduped['dedupe_removed']} duplicate rows")
    print(f"wrote table image to {image_path}")


if __name__ == "__main__":
    main()
