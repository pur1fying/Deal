from datetime import datetime
from pathlib import Path

from core.autoamtion.webbridge_common import InteractionConfig
from core.autoamtion.webbridge_platforms.goofish import GoofishWebBridgeAutomation
from deal.io import read_json
from deal.models import ProductConfig, RunPaths


class FakeWebBridgeClient:
    def __init__(self):
        self.actions = []

    def find_tab(self, url, active=True):
        self.actions.append(("find_tab", url, active))
        return {"success": True}

    def navigate(self, url, new_tab=True, group_title=None):
        self.actions.append(("navigate", url, new_tab, group_title))
        return {"success": True}

    def type_like_human(self, selector, text, **kwargs):
        self.actions.append(("type_like_human", selector, text))

    def send_keys(self, keys, repeat=1):
        self.actions.append(("send_keys", keys, repeat))

    def mouse_click(self, selector):
        self.actions.append(("mouse_click", selector))

    def scroll_by(self, pixels):
        self.actions.append(("scroll_by", pixels))

    def evaluate(self, code):
        if "data-deal-next-page" in code:
            return False
        return ""

    def evaluate_json(self, code):
        return [
            {
                "captured_at": "2026-05-15T10:00:00",
                "site": "goofish",
                "platform": "goofish",
                "brand": "Canon",
                "model": "R6",
                "keyword": "佳能R6相机",
                "title": "佳能 R6 机身",
                "full_content": "佳能 R6 机身\n¥10000",
                "price_text": "¥10000",
                "price_yuan": None,
                "location": None,
                "seller_name": None,
                "shop_name": None,
                "seller_credit": None,
                "sold_count": None,
                "on_sale_count": None,
                "want_count": None,
                "condition": None,
                "raw_url": "https://www.goofish.com/item?id=1",
                "screenshot_path": None,
                "page_index": 1,
                "rank_on_page": 1,
                "raw_card_text": "佳能 R6 机身\n¥10000",
                "_screenshot_selector": "[data-deal-card-id='1']",
            }
        ]

    def screenshot(self, path, selector=None, image_format="png"):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return path


def test_webbridge_goofish_collect_writes_result_and_screenshot(tmp_path):
    paths = RunPaths.create(tmp_path / "output", datetime(2026, 5, 15, 10, 0, 0), run_id="webbridge")
    client = FakeWebBridgeClient()
    automation = GoofishWebBridgeAutomation(
        client=client,
        paths=paths,
        config={
            "use_current_tab": True,
            "search": {"max_pages_per_keyword": 1, "max_items_per_keyword": 1},
            "extraction": {"save_item_screenshot": True},
            "human_like_interaction": {
                "scrolling": {"max_scroll_rounds_per_page": 0},
            },
        },
        interaction=InteractionConfig(max_scroll_rounds_per_page=0),
    )

    items = automation.collect([
        ProductConfig(brand="Canon", model="R6", keywords=["佳能R6相机"]),
    ])

    assert len(items) == 1
    screenshot = Path(items[0]["screenshot_path"])
    assert screenshot.parts[-4:] == ("result", "goofish", "screenshot", "00000001.png")
    assert screenshot.exists()
    assert read_json(paths.platform_result_json("goofish"))[0]["title"] == "佳能 R6 机身"
    assert ("type_like_human", "input", "佳能R6相机") in client.actions
