from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from deal.io import read_json, write_json
from deal.models import ProductConfig


DEFAULT_CONFIG: dict[str, Any] = {
    "task": "run",
    "output_dir": "output",
    "products_file": "config/products.json",
    "run_id": None,
    "output_layout": {
        "date_format": "%Y-%m-%d",
        "run_id_format": "%H%M%S",
        "log_dir": "log",
        "platforms": ["tb", "jd", "pdd", "goofish"],
    },
    "collector": {
        "max_items": 20,
        "wait_seconds": 6,
    },
    "summary": {
        "run_dir": None,
    },
    "plot": {
        "run_dir": None,
    },
    "webbridge_search": {
        "use_current_tab": True,
        "session_name": "goofish-camera-search",
        "search": {
            "max_pages_per_keyword": 3,
            "max_items_per_keyword": 80,
        },
        "human_like_interaction": {
            "typing": {
                "char_delay_ms": [120, 420],
                "word_delay_ms": [250, 900],
                "after_input_delay_ms": [600, 1600],
            },
            "scrolling": {
                "scroll_step_px": [280, 760],
                "scroll_delay_ms": [900, 2400],
                "pause_after_items": [5, 9],
                "long_pause_ms": [2500, 6500],
                "max_scroll_rounds_per_page": 12,
            },
            "navigation_wait_ms": [2500, 6000],
        },
        "extraction": {
            "save_item_screenshot": True,
        },
    },
    "cam_spec": {
        "task_name": "cam_spec",
        "result_file": "result.json",
        "merge": True,
        "dedupe": True,
        "draw_table": True,
        "dedupe_result_file": "result_deduped.json",
        "table_image_file": "charts/cam_spec_full_table_deduped.png",
        "brands": ["fujifilm", "canon", "sony", "hasselblad", "nikon"],
        "max_workers": 5,
        "max_pages_per_brand": None,
    },
}
DEFAULT_PRODUCTS: dict[str, Any] = {
    "products": [
        {
            "brand": "Sony",
            "model": "A7M4",
            "keywords": ["Sony A7M4", "\u7d22\u5c3c A7M4"],
            "exclude_words": ["\u8d34\u819c", "\u4fdd\u62a4\u5957", "\u7535\u6c60", "\u5145\u7535\u5668"],
            "platform_keywords": {
                "tb": ["\u7d22\u5c3c A7M4 \u76f8\u673a"],
                "jd": ["\u7d22\u5c3c A7M4 \u76f8\u673a"],
                "pdd": ["\u7d22\u5c3c A7M4 \u76f8\u673a"],
                "goofish": ["\u7d22\u5c3c A7M4 \u76f8\u673a"],
            },
        },
        {
            "brand": "Canon",
            "model": "R6 Mark II",
            "keywords": ["Canon R6 Mark II", "\u4f73\u80fd R6 Mark II"],
            "exclude_words": ["\u8d34\u819c", "\u4fdd\u62a4\u5957", "\u7535\u6c60", "\u5145\u7535\u5668"],
        },
    ]
}


def merge_with_defaults(current: Any, default: Any) -> Any:
    if isinstance(default, dict) and not isinstance(current, dict):
        return deepcopy(default)
    if isinstance(current, dict) and isinstance(default, dict):
        merged: dict[str, Any] = {}
        for key, default_value in default.items():
            if key in current:
                merged[key] = merge_with_defaults(current[key], default_value)
            else:
                merged[key] = deepcopy(default_value)
        return merged
    return current


@dataclass
class ConfigSet:
    config_dir: Path = Path("config")
    config_name: str = "config.json"
    products_name: str = "products.json"

    def __post_init__(self) -> None:
        self.config_dir = Path(self.config_dir)
        self.config_path = self.config_dir / self.config_name
        self.products_path = self.config_dir / self.products_name
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.ensure_files()
        self.config: dict[str, Any] = {}
        self.reload()

    def ensure_files(self) -> None:
        if not self.config_path.exists():
            write_json(self.config_path, DEFAULT_CONFIG)
        else:
            self._update_config_file()
        if not self.products_path.exists():
            write_json(self.products_path, DEFAULT_PRODUCTS)

    def _update_config_file(self) -> None:
        try:
            current = read_json(self.config_path)
            updated = merge_with_defaults(current, DEFAULT_CONFIG)
            write_json(self.config_path, updated)
        except Exception:
            write_json(self.config_path, merge_with_defaults({}, DEFAULT_CONFIG))

    def reload(self) -> None:
        self.config = read_json(self.config_path)

    def get(self, key: str, default: Any = None) -> Any:
        self.reload()
        value: Any = self.config
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value

    def set(self, key: str, value: Any) -> None:
        self.reload()
        target = self.config
        parts = key.split(".")
        for part in parts[:-1]:
            next_value = target.setdefault(part, {})
            if not isinstance(next_value, dict):
                next_value = {}
                target[part] = next_value
            target = next_value
        target[parts[-1]] = value
        self.save()

    def save(self) -> None:
        write_json(self.config_path, merge_with_defaults(self.config, DEFAULT_CONFIG))


def check_config(config_dir: Path = Path("config"), config_name: str = "config.json") -> ConfigSet:
    return ConfigSet(config_dir, config_name=config_name)


def load_products(path: Path) -> list[ProductConfig]:
    data = read_json(path)
    products = data.get("products", data) if isinstance(data, dict) else data
    if not isinstance(products, list):
        raise ValueError("products config must contain a list or an object with a 'products' list")
    return [ProductConfig.from_dict(item) for item in products]

