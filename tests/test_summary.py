from pathlib import Path

from deal.io import write_json
from deal.summary import build_summary, find_previous_run


def normalized_item(brand: str, model: str, platform: str, price: float, title: str = "item"):
    return {
        "brand": brand,
        "model": model,
        "platform": platform,
        "title": title,
        "url": "https://example.test/item",
        "list_price": price + 100,
        "effective_price": price,
        "currency": "CNY",
        "source_keyword": f"{brand} {model}",
        "captured_at": "2026-05-15T10:00:00",
    }


def write_run(output: Path, date: str, run_id: str, items: list[dict]) -> Path:
    run = output / date / run_id
    write_json(run / "normalized" / "products.json", items)
    (run / "summary").mkdir(parents=True, exist_ok=True)
    return run


def test_find_previous_run_uses_latest_prior_date(tmp_path):
    write_run(tmp_path, "2026-05-13", "230000", [normalized_item("Sony", "A7M4", "jd", 12000)])
    expected = write_run(tmp_path, "2026-05-14", "090000", [normalized_item("Sony", "A7M4", "jd", 11900)])
    current = write_run(tmp_path, "2026-05-15", "100000", [normalized_item("Sony", "A7M4", "jd", 11800)])

    previous = find_previous_run(tmp_path, current)

    assert previous is not None
    assert previous.path == expected


def test_build_summary_calculates_min_and_change(tmp_path):
    write_run(tmp_path, "2026-05-14", "090000", [
        normalized_item("Sony", "A7M4", "jd", 12000),
    ])
    current = write_run(tmp_path, "2026-05-15", "100000", [
        normalized_item("Sony", "A7M4", "jd", 11800, "cheap"),
        normalized_item("Sony", "A7M4", "jd", 12100, "expensive"),
    ])

    platform_min, changes = build_summary(current, tmp_path)

    key = "Sony|A7M4|jd"
    assert platform_min[key]["min_price"] == 11800
    assert changes[key]["previous_price"] == 12000
    assert changes[key]["change_amount"] == -200
    assert changes[key]["change_percent"] == -1.67
