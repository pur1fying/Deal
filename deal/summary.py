from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deal.io import read_json, write_json


@dataclass(frozen=True)
class PreviousRun:
    date: str
    run_id: str
    path: Path


def item_key(item: dict[str, Any]) -> tuple[str, str, str]:
    return (str(item["brand"]), str(item["model"]), str(item["platform"]))


def best_price(item: dict[str, Any]) -> float | None:
    price = item.get("effective_price")
    if price is None:
        price = item.get("list_price")
    return float(price) if price is not None else None


def platform_min_prices(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        price = best_price(item)
        if price is None:
            continue
        key = "|".join(item_key(item))
        current = result.get(key)
        if current is None or price < current["min_price"]:
            result[key] = {
                "brand": item["brand"],
                "model": item["model"],
                "platform": item["platform"],
                "min_price": price,
                "price_type": "effective_price" if item.get("effective_price") is not None else "list_price",
                "title": item.get("title"),
                "url": item.get("url"),
                "captured_at": item.get("captured_at"),
            }
    return result


def find_previous_run(output_root: Path, current_run: Path) -> PreviousRun | None:
    current_date = current_run.parent.name
    candidates: list[PreviousRun] = []
    for date_dir in output_root.iterdir() if output_root.exists() else []:
        if not date_dir.is_dir() or date_dir.name >= current_date:
            continue
        for run_dir in date_dir.iterdir():
            normalized = run_dir / "normalized" / "products.json"
            if normalized.exists():
                candidates.append(PreviousRun(date_dir.name, run_dir.name, run_dir))
    return max(candidates, key=lambda run: (run.date, run.run_id), default=None)


def build_summary(run_dir: Path, output_root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    items = read_json(run_dir / "normalized" / "products.json")
    current_min = platform_min_prices(items)
    previous = find_previous_run(output_root, run_dir)
    previous_min: dict[str, dict[str, Any]] = {}
    if previous:
        previous_items = read_json(previous.path / "normalized" / "products.json")
        previous_min = platform_min_prices(previous_items)

    changes: dict[str, dict[str, Any]] = {}
    for key, current in current_min.items():
        previous_price = previous_min.get(key, {}).get("min_price")
        change_amount = None
        change_percent = None
        if previous_price:
            change_amount = round(current["min_price"] - previous_price, 2)
            change_percent = round(change_amount / previous_price * 100, 2)
        changes[key] = current | {
            "previous_price": previous_price,
            "previous_run": str(previous.path) if previous else None,
            "change_amount": change_amount,
            "change_percent": change_percent,
        }
    write_json(run_dir / "summary" / "platform_min_prices.json", current_min)
    write_json(run_dir / "summary" / "daily_changes.json", changes)
    return current_min, changes
