from deal.config import ConfigSet
from deal.io import read_json, write_json


def test_config_files_are_created(tmp_path):
    config = ConfigSet(tmp_path / "config")

    assert config.config_path.exists()
    assert config.products_path.exists()
    assert config.get("task") == "run"
    assert config.get("collector.max_items") == 20


def test_config_recursive_update_adds_missing_and_removes_deprecated(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    write_json(config_dir / "config.json", {
        "task": "summary",
        "collector": {
            "max_items": 5,
            "old_nested": True,
        },
        "deprecated": "remove me",
    })

    config = ConfigSet(config_dir)
    data = read_json(config.config_path)

    assert data["task"] == "summary"
    assert data["collector"]["max_items"] == 5
    assert data["collector"]["wait_seconds"] == 6
    assert "old_nested" not in data["collector"]
    assert "deprecated" not in data
    assert data["products_file"] == "config/products.json"


def test_config_set_updates_nested_value(tmp_path):
    config = ConfigSet(tmp_path / "config")

    config.set("collector.wait_seconds", 2)

    assert ConfigSet(tmp_path / "config").get("collector.wait_seconds") == 2


def test_custom_config_writes_default_values(tmp_path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    write_json(config_dir / "parse_camera_spec.json", {
        "task": "cam_spec",
        "cam_spec": {"brands": ["canon"]},
    })

    config = ConfigSet(config_dir, config_name="parse_camera_spec.json")

    assert config.get("output_dir") == "output"
    assert config.get("cam_spec.task_name") == "cam_spec"
    written = read_json(config_dir / "parse_camera_spec.json")
    assert written["task"] == "cam_spec"
    assert written["output_dir"] == "output"
    assert written["cam_spec"]["brands"] == ["canon"]
    assert written["cam_spec"]["task_name"] == "cam_spec"
