from deal.io import write_json
from deal.plotting import plot_history


def test_plot_history_writes_png(tmp_path):
    run = tmp_path / "2026-05-15" / "100000"
    write_json(run / "normalized" / "products.json", [
        {
            "brand": "Sony",
            "model": "A7M4",
            "platform": "jd",
            "title": "Sony A7M4",
            "url": "https://example.test",
            "list_price": 12100,
            "effective_price": 12000,
            "currency": "CNY",
            "source_keyword": "Sony A7M4",
            "captured_at": "2026-05-15T10:00:00",
        }
    ])

    written = plot_history(tmp_path, run / "charts")

    assert len(written) == 1
    assert written[0].exists()
    assert written[0].suffix == ".png"
