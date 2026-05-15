from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from deal.io import read_json
from deal.summary import platform_min_prices


def collect_history(output_root: Path) -> dict[str, list[tuple[str, float]]]:
    series: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for normalized in sorted(output_root.glob("*/*/normalized/products.json")):
        run_dir = normalized.parents[1]
        run_label = f"{run_dir.parent.name} {run_dir.name}"
        for key, item in platform_min_prices(read_json(normalized)).items():
            series[key].append((run_label, item["min_price"]))
    return series


def plot_history(output_root: Path, charts_dir: Path) -> list[Path]:
    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required for plot/run.") from exc

    charts_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for key, values in collect_history(output_root).items():
        if not values:
            continue
        labels = [label for label, _ in values]
        prices = [price for _, price in values]
        plt.figure(figsize=(10, 4.8))
        plt.plot(labels, prices, marker="o")
        plt.title(key.replace("|", " / "))
        plt.xlabel("Run")
        plt.ylabel("CNY")
        plt.xticks(rotation=30, ha="right")
        plt.tight_layout()
        path = charts_dir / f"{safe_filename(key)}.png"
        plt.savefig(path)
        plt.close()
        written.append(path)
    return written


def safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)
