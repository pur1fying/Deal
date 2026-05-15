from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from core.autoamtion.official_specs import canon, fujifilm, hasselblad, nikon, sony
from core.autoamtion.official_specs.common import CameraSpec
from core.logger import logger
from core.webbridge import ensure_webbridge_ready


BRAND_SCRAPERS: dict[str, Callable[[int | None], list[CameraSpec]]] = {
    "fujifilm": fujifilm.scrape,
    "canon": canon.scrape,
    "sony": sony.scrape,
    "hasselblad": hasselblad.scrape,
    "nikon": nikon.scrape,
}


def collect_official_specs(
    output_path: Path | str = "output/cam_spec/result.json",
    *,
    brands: list[str] | None = None,
    max_workers: int = 5,
    max_pages_per_brand: int | None = None,
    merge: bool = True,
    result_filename: str | None = None,
) -> dict:
    selected = brands or list(BRAND_SCRAPERS)
    logger.attr("camera specs crawl started")
    logger.info(
        "Camera specs config: "
        f"brands={selected}, max_workers={max_workers}, "
        f"max_pages_per_brand={max_pages_per_brand}, merge={merge}"
    )
    output_target = Path(output_path)
    if output_target.suffix.lower() == ".json":
        output_dir = output_target.parent
        merged_path = output_dir / (result_filename or output_target.name)
    else:
        output_dir = output_target
        merged_path = output_dir / (result_filename or "result.json")
    output_dir.mkdir(parents=True, exist_ok=True)
    if logger.log_file_path is None:
        logger.set_log_file(output_dir / "log" / "run.log")
    logger.info(f"Camera specs output directory: {output_dir}")
    by_brand: dict[str, list[dict]] = {}
    errors: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        logger.info(f"Submitting {len(selected)} camera brand task(s)")
        futures = {
            executor.submit(BRAND_SCRAPERS[brand], max_pages_per_brand): brand
            for brand in selected
        }
        for future in as_completed(futures):
            brand = futures[future]
            try:
                by_brand[brand] = [item.to_dict() for item in future.result()]
                logger.info(f"{brand}: collected {len(by_brand[brand])} camera spec item(s)")
            except Exception as exc:
                errors[brand] = f"{type(exc).__name__}: {exc}"
                by_brand[brand] = []
                logger.error(f"{brand}: crawler failed: {errors[brand]}")

    merged = {
        "brands": selected,
        "total": sum(len(items) for items in by_brand.values()),
        "items": [item for brand in selected for item in by_brand.get(brand, [])],
        "errors": errors,
        "merge": merge,
        "output_dir": str(output_dir),
        "result_path": str(merged_path) if merge else None,
    }
    if merge:
        merged_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info(f"Camera specs merged result written: {merged_path}")

    for brand, items in by_brand.items():
        brand_path = output_dir / f"{brand}.json"
        brand_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        logger.info(f"{brand}: brand result written: {brand_path}")

    logger.attr(f"camera specs crawl finished, total={merged['total']}")
    return merged


def print_camera_specs_table(items: list[dict[str, Any]]) -> None:
    if not items:
        logger.warning("No camera spec items to display")
        return
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
    except ModuleNotFoundError:
        print_plain_camera_specs_table(items)
        return

    table = Table(
        title=f"Camera Specs Crawl Results ({len(items)} items)",
        show_lines=False,
        box=box.SIMPLE_HEAVY,
    )
    table.add_column("#", justify="right", style="cyan", no_wrap=True)
    table.add_column("Brand", style="magenta", no_wrap=True, min_width=10)
    table.add_column("Model", style="white", min_width=20, max_width=36, overflow="fold")
    table.add_column("Sensor", style="green", no_wrap=True)
    table.add_column("MP", justify="right", style="green", no_wrap=True)
    table.add_column("Price", justify="right", style="yellow", no_wrap=True)
    table.add_column("Video", style="blue", min_width=22, max_width=48, overflow="fold")
    for index, item in enumerate(items, start=1):
        table.add_row(
            str(index),
            str(item.get("brand") or ""),
            str(item.get("model") or ""),
            str(item.get("sensor_format") or ""),
            str(item.get("megapixels") or ""),
            camera_price_label(item),
            camera_video_label(item),
        )
    Console(width=160).print(table)


def print_plain_camera_specs_table(items: list[dict[str, Any]]) -> None:
    headers = ("#", "Brand", "Model", "Sensor", "MP", "Price", "Video")
    rows = [
        (
            str(index),
            str(item.get("brand") or ""),
            str(item.get("model") or ""),
            str(item.get("sensor_format") or ""),
            str(item.get("megapixels") or ""),
            camera_price_label(item),
            camera_video_label(item),
        )
        for index, item in enumerate(items, start=1)
    ]
    widths = [
        min(max(len(row[column]) for row in [headers, *rows]), 40)
        for column in range(len(headers))
    ]
    print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value[:widths[index]].ljust(widths[index]) for index, value in enumerate(row)))


def camera_price_label(item: dict[str, Any]) -> str:
    current = item.get("official_price_text")
    original = item.get("original_price_text")
    if current and original and current != original:
        return f"{current} / orig {original}"
    return str(current or original or "")


def camera_video_label(item: dict[str, Any]) -> str:
    modes = [format_video_mode(value) for value in item.get("video_modes") or []]
    modes = [value for value in modes if value]
    if modes:
        return ", ".join(modes[:4])
    resolutions = [str(value) for value in item.get("video_resolution") or []]
    rates = [str(value) for value in item.get("video_frame_rates") or []]
    if resolutions and rates:
        return f"{', '.join(resolutions[:3])} @ {', '.join(rates[:3])}"
    if resolutions:
        return ", ".join(resolutions[:4])
    return ", ".join(rates[:4])


def format_video_mode(value: Any) -> str:
    if isinstance(value, dict):
        resolution = str(value.get("resolution") or "").strip()
        fps = str(value.get("fps") or "").strip()
        return " ".join(part for part in [resolution, fps] if part)
    return str(value or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/cam_spec")
    parser.add_argument("--brands", nargs="*", choices=sorted(BRAND_SCRAPERS), default=None)
    parser.add_argument("--max-workers", type=int, default=5)
    parser.add_argument("--max-pages-per-brand", type=int, default=None)
    parser.add_argument("--result-file", default="result.json")
    parser.add_argument("--no-merge", action="store_true")
    parser.add_argument("--skip-webbridge-check", action="store_true")
    args = parser.parse_args()
    if not args.skip_webbridge_check:
        logger.attr("checking webbridge")
        status = ensure_webbridge_ready()
        logger.info(f"webbridge ready (daemon={status.get('version')}, extension={status.get('extension_version')})")
    result = collect_official_specs(
        args.output,
        brands=args.brands,
        max_workers=args.max_workers,
        max_pages_per_brand=args.max_pages_per_brand,
        merge=not args.no_merge,
        result_filename=args.result_file,
    )
    print_camera_specs_table(result["items"])
    logger.info(f"wrote {result['total']} item(s) to {result['output_dir']}")


if __name__ == "__main__":
    main()
