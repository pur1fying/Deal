from __future__ import annotations

from core.autoamtion.platforms import PLATFORM_AUTOMATIONS
from deal.io import write_json
from deal.models import PLATFORMS, NormalizedItem, ProductConfig, RawItem, RunPaths
from deal.parsing import parse_list_and_effective_price


def normalize_raw_items(raw_items: list[RawItem]):
    normalized = []
    for raw in raw_items:
        list_price, effective_price = parse_list_and_effective_price(raw.price_text, raw.effective_price_text)
        normalized.append(NormalizedItem.from_raw(raw, list_price, effective_price).to_dict())
    return normalized


async def collect_all(products: list[ProductConfig], paths: RunPaths, max_items: int, wait_seconds: int) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for collect/run. Install dependencies and run 'playwright install chrome'.") from exc

    normalized: list[dict] = []
    async with async_playwright() as playwright:
        for platform in PLATFORMS:
            automation = PLATFORM_AUTOMATIONS[platform](playwright, paths, max_items, wait_seconds)
            raw_items = await automation.collect(products)
            result_items = [item.to_dict() for item in raw_items]
            write_json(paths.raw / f"{platform}.json", result_items)
            write_json(paths.platform_result_json(platform), result_items)
            normalized.extend(normalize_raw_items(raw_items))
    write_json(paths.normalized / "products.json", normalized)
    return normalized
