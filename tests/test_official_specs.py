from core.autoamtion.official_specs.common import parse_camera_page
from core.autoamtion.official_specs.dedupe import dedupe_items, dedupe_result_file
from core.autoamtion.official_specs.runner import camera_video_label, collect_official_specs
from deal.config import ConfigSet
from deal.io import read_json, write_json


def test_parse_camera_page_extracts_core_specs():
    html = """
    <html><head><title>Canon EOS R6 Mark II Specifications</title></head>
    <body>
      <h1>EOS R6 Mark II</h1>
      <table>
        <tr><th>Image Sensor</th><td>Full-frame CMOS sensor</td></tr>
        <tr><th>Pixels</th><td>Approx. 24.2 megapixels</td></tr>
        <tr><th>Movie</th><td>4K 60p, Full HD, MP4, H.264, H.265</td></tr>
      </table>
    </body></html>
    """

    spec = parse_camera_page("Canon", "https://example.test/eos-r6-mark-ii", html)

    assert spec.model == "EOS R6 Mark II"
    assert spec.sensor_format == "Full Frame"
    assert spec.megapixels == "24.2 MP"
    assert {"resolution": "4K", "fps": "60p"} in spec.video_modes
    assert "H.264" in spec.video_formats
    assert "video_resolution" not in spec.to_dict()
    assert "video_frame_rates" not in spec.to_dict()


def test_parse_camera_page_extracts_price_and_video_rates():
    html = """
    <html><head><title>Sony Alpha 1 Specifications</title></head>
    <body>
      <h1>Alpha 1</h1>
      <p>Full-frame camera 50.1MP, 30FPS, 4K/120p/8K/30p.</p>
      <p>Sale Price $6,199.99 Original Price $6,499.99</p>
    </body></html>
    """

    spec = parse_camera_page("Sony", "https://example.test/alpha-1", html)

    assert spec.official_price_text == "$6,199.99"
    assert spec.official_price == 6199.99
    assert spec.original_price_text == "$6,499.99"
    assert spec.original_price == 6499.99
    assert spec.price_currency == "USD"
    assert {"resolution": "4K", "fps": "120p"} in spec.video_modes
    assert {"resolution": "8K", "fps": "30p"} in spec.video_modes
    assert "video_resolution" not in spec.to_dict()
    assert "video_frame_rates" not in spec.to_dict()


def test_collect_official_specs_merges_brand_outputs(tmp_path, monkeypatch):
    from core.autoamtion.official_specs import runner
    from core.autoamtion.official_specs.common import CameraSpec

    monkeypatch.setitem(
        runner.BRAND_SCRAPERS,
        "canon",
        lambda max_pages=None: [CameraSpec(brand="Canon", model="R6", source_url="https://example.test/r6")],
    )
    monkeypatch.setitem(
        runner.BRAND_SCRAPERS,
        "sony",
        lambda max_pages=None: [CameraSpec(brand="Sony", model="A7", source_url="https://example.test/a7")],
    )

    output = tmp_path / "cameras.json"
    result = collect_official_specs(output, brands=["canon", "sony"], max_workers=2, max_pages_per_brand=1)

    assert result["total"] == 2
    assert "by_brand" not in result
    assert output.exists()
    assert "by_brand" not in read_json(output)
    assert (tmp_path / "canon.json").exists()
    assert (tmp_path / "sony.json").exists()


def test_collect_official_specs_can_skip_merged_result(tmp_path, monkeypatch):
    from core.autoamtion.official_specs import runner
    from core.autoamtion.official_specs.common import CameraSpec

    monkeypatch.setitem(
        runner.BRAND_SCRAPERS,
        "canon",
        lambda max_pages=None: [CameraSpec(brand="Canon", model="R6", source_url="https://example.test/r6")],
    )

    output_dir = tmp_path / "official_specs"
    result = collect_official_specs(output_dir, brands=["canon"], max_workers=1, merge=False)

    assert result["total"] == 1
    assert result["result_path"] is None
    assert not (output_dir / "result.json").exists()
    assert (output_dir / "canon.json").exists()


def test_cam_spec_config_uses_run_directory_and_merge_flag(tmp_path, monkeypatch):
    from deal import runner as deal_runner

    config_dir = tmp_path / "config"
    write_json(config_dir / "parse_camera_spec.json", {
        "task": "cam_spec",
        "output_dir": str(tmp_path / "output"),
        "run_id": "spec-run",
        "cam_spec": {
            "task_name": "cam_spec",
            "result_file": "result.json",
            "merge": False,
            "brands": ["canon"],
            "max_workers": 1,
            "max_pages_per_brand": 1,
        },
    })
    captured = {}

    def fake_collect(output_path, **kwargs):
        captured["output_path"] = output_path
        captured.update(kwargs)
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "canon.json").write_text("[]\n", encoding="utf-8")
        return {
            "total": 1,
            "items": [],
            "output_dir": str(output_path),
            "result_path": None,
            "errors": {},
        }

    monkeypatch.setattr(deal_runner, "ensure_webbridge_ready", lambda: {"version": "test", "extension_version": "test"})
    monkeypatch.setattr(deal_runner, "collect_official_specs", fake_collect)

    expected_date = deal_runner.datetime.now().strftime("%Y-%m-%d")
    output_dir = deal_runner.run_configured_task(ConfigSet(config_dir, config_name="parse_camera_spec.json"))

    assert output_dir == tmp_path / "output" / expected_date / "cam_spec" / "spec-run"
    assert captured["merge"] is False
    assert captured["result_filename"] == "result.json"
    assert (output_dir / "canon.json").exists()
    log = read_json(tmp_path / "output" / expected_date / "cam_spec" / "spec-run" / "log" / "cam_spec_run.json")
    assert log["merge"] is False
    run_log = tmp_path / "output" / expected_date / "cam_spec" / "spec-run" / "log" / "run.log"
    assert "<<< checking webbridge >>>" in run_log.read_text(encoding="utf-8")


def test_cam_spec_run_id_auto_increments_from_001(tmp_path, monkeypatch):
    from deal import runner as deal_runner

    config_dir = tmp_path / "config"
    write_json(config_dir / "parse_camera_spec.json", {
        "task": "cam_spec",
        "output_dir": str(tmp_path / "output"),
        "cam_spec": {
            "merge": False,
            "brands": ["canon"],
            "max_workers": 1,
            "max_pages_per_brand": 1,
        },
    })

    def fake_collect(output_path, **kwargs):
        output_path.mkdir(parents=True, exist_ok=True)
        (output_path / "canon.json").write_text("[]\n", encoding="utf-8")
        return {
            "total": 0,
            "items": [],
            "output_dir": str(output_path),
            "result_path": None,
            "errors": {},
        }

    monkeypatch.setattr(deal_runner, "ensure_webbridge_ready", lambda: {"version": "test", "extension_version": "test"})
    monkeypatch.setattr(deal_runner, "collect_official_specs", fake_collect)

    config = ConfigSet(config_dir, config_name="parse_camera_spec.json")
    first = deal_runner.run_configured_task(config)
    second = deal_runner.run_configured_task(config)
    expected_date = deal_runner.datetime.now().strftime("%Y-%m-%d")

    assert first == tmp_path / "output" / expected_date / "cam_spec" / "001"
    assert second == tmp_path / "output" / expected_date / "cam_spec" / "002"


def test_cam_spec_config_can_dedupe_and_draw_table(tmp_path, monkeypatch):
    from deal import runner as deal_runner

    config_dir = tmp_path / "config"
    write_json(config_dir / "parse_camera_spec.json", {
        "task": "cam_spec",
        "output_dir": str(tmp_path / "output"),
        "run_id": "draw-run",
        "cam_spec": {
            "merge": True,
            "dedupe": True,
            "draw_table": True,
            "brands": ["canon"],
            "max_workers": 1,
            "max_pages_per_brand": 1,
        },
    })

    def fake_collect(output_path, **kwargs):
        output_path.mkdir(parents=True, exist_ok=True)
        result_path = output_path / kwargs["result_filename"]
        write_json(result_path, {
            "brands": ["canon"],
            "total": 2,
            "items": [
                {"brand": "Canon", "model": "R6", "source_url": "https://example.test/r6"},
                {"brand": "Canon", "model": "R6", "source_url": "https://example.test/r6/specs"},
            ],
            "errors": {},
            "output_dir": str(output_path),
            "result_path": str(result_path),
        })
        return {
            "total": 2,
            "items": read_json(result_path)["items"],
            "output_dir": str(output_path),
            "result_path": str(result_path),
            "errors": {},
        }

    def fake_draw_table(items, output_path, **kwargs):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("table image placeholder", encoding="utf-8")
        return output_path

    monkeypatch.setattr(deal_runner, "ensure_webbridge_ready", lambda: {"version": "test", "extension_version": "test"})
    monkeypatch.setattr(deal_runner, "collect_official_specs", fake_collect)
    monkeypatch.setattr(deal_runner, "draw_deduped_table", fake_draw_table)

    output_dir = deal_runner.run_configured_task(ConfigSet(config_dir, config_name="parse_camera_spec.json"))

    assert (output_dir / "result_deduped.json").exists()
    assert (output_dir / "charts" / "cam_spec_full_table_deduped.png").exists()
    log = read_json(output_dir / "log" / "cam_spec_run.json")
    assert log["dedupe"] is True
    assert log["draw_table"] is True
    assert log["deduped_items"] == 1
    assert log["deduped_result_path"].endswith("result_deduped.json")
    assert log["table_image_path"].endswith("cam_spec_full_table_deduped.png")


def test_dedupe_items_merges_same_brand_and_model():
    items = [
        {
            "brand": "Fujifilm",
            "model": "GFX100 II",
            "source_url": "https://example.test/gfx100-ii",
            "megapixels": "102 MP",
            "video_modes": [{"resolution": "4K", "fps": "60p"}],
            "video_formats": ["RAW"],
        },
        {
            "brand": "Fujifilm",
            "model": "GFX100 II - Filmmaking",
            "source_url": "https://example.test/gfx100-ii/specifications",
            "sensor_format": "Medium Format",
            "video_resolution": ["8K"],
            "video_frame_rates": ["30p"],
        },
        {
            "brand": "Sony",
            "model": "Alpha 1",
            "source_url": "https://example.test/alpha-1",
        },
    ]

    deduped = dedupe_items(items)
    gfx = next(item for item in deduped if item["brand"] == "Fujifilm")

    assert len(deduped) == 2
    assert gfx["duplicate_count"] == 2
    assert gfx["sensor_format"] == "Medium Format"
    assert gfx["megapixels"] == "102 MP"
    assert gfx["video_modes"] == [
        {"resolution": "4K", "fps": "60p"},
        {"resolution": "8K", "fps": "30p"},
    ]
    assert "video_resolution" not in gfx
    assert "video_frame_rates" not in gfx
    assert len(gfx["merged_source_urls"]) == 2


def test_camera_video_label_formats_video_mode_objects():
    item = {
        "video_modes": [
            {"resolution": "6.2K", "fps": "29.97p"},
            {"resolution": "4K", "fps": "59.94p"},
        ]
    }

    assert camera_video_label(item) == "6.2K 29.97p, 4K 59.94p"


def test_dedupe_result_file_writes_new_json(tmp_path):
    source = tmp_path / "result.json"
    write_json(source, {
        "brands": ["fujifilm"],
        "total": 2,
        "items": [
            {"brand": "Fujifilm", "model": "X-T5", "source_url": "https://example.test/x-t5"},
            {
                "brand": "Fujifilm",
                "model": "X-T5",
                "source_url": "https://example.test/x-t5/specifications",
                "video_resolution": ["6.2K"],
                "video_frame_rates": ["30p"],
            },
        ],
    })

    result = dedupe_result_file(source)

    assert result["total"] == 1
    assert result["source_total"] == 2
    assert result["dedupe_removed"] == 1
    assert result["items"][0]["video_modes"] == [{"resolution": "6.2K", "fps": "30p"}]
    assert "video_resolution" not in result["items"][0]
    assert "video_frame_rates" not in result["items"][0]
    assert (tmp_path / "result_deduped.json").exists()
