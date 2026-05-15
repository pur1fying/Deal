from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar
from urllib.parse import quote_plus

from core.webbridge import WebBridgeClient, WebBridgeError
from deal.io import write_json
from deal.models import ProductConfig, RunPaths


BLOCK_MARKERS = ("验证码", "安全验证", "滑块", "captcha", "verify", "risk", "异常访问")


@dataclass(frozen=True)
class InteractionConfig:
    char_delay_ms: tuple[int, int] = (120, 420)
    word_delay_ms: tuple[int, int] = (250, 900)
    after_input_delay_ms: tuple[int, int] = (600, 1600)
    navigation_wait_ms: tuple[int, int] = (2500, 6000)
    scroll_step_px: tuple[int, int] = (280, 760)
    scroll_delay_ms: tuple[int, int] = (900, 2400)
    pause_after_items: tuple[int, int] = (5, 9)
    long_pause_ms: tuple[int, int] = (2500, 6500)
    max_scroll_rounds_per_page: int = 12

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "InteractionConfig":
        root = config.get("human_like_interaction", {})
        typing = root.get("typing", {})
        scrolling = root.get("scrolling", {})
        return cls(
            char_delay_ms=as_range(typing.get("char_delay_ms"), cls.char_delay_ms),
            word_delay_ms=as_range(typing.get("word_delay_ms"), cls.word_delay_ms),
            after_input_delay_ms=as_range(typing.get("after_input_delay_ms"), cls.after_input_delay_ms),
            navigation_wait_ms=as_range(root.get("navigation_wait_ms"), cls.navigation_wait_ms),
            scroll_step_px=as_range(scrolling.get("scroll_step_px"), cls.scroll_step_px),
            scroll_delay_ms=as_range(scrolling.get("scroll_delay_ms"), cls.scroll_delay_ms),
            pause_after_items=as_range(scrolling.get("pause_after_items"), cls.pause_after_items),
            long_pause_ms=as_range(scrolling.get("long_pause_ms"), cls.long_pause_ms),
            max_scroll_rounds_per_page=int(scrolling.get("max_scroll_rounds_per_page", 12)),
        )

    def sleep_navigation(self) -> None:
        sleep_ms(self.navigation_wait_ms)

    def sleep_after_input(self) -> None:
        sleep_ms(self.after_input_delay_ms)

    def sleep_scroll(self) -> None:
        sleep_ms(self.scroll_delay_ms)

    def sleep_long_pause(self) -> None:
        sleep_ms(self.long_pause_ms)


@dataclass
class WebBridgePlatformAutomation:
    client: WebBridgeClient
    paths: RunPaths
    config: dict[str, Any]
    interaction: InteractionConfig

    platform: ClassVar[str] = ""
    base_url: ClassVar[str] = ""
    search_url: ClassVar[str] = ""
    search_input_selector: ClassVar[str] = "input"
    search_button_selector: ClassVar[str | None] = None
    item_selector: ClassVar[str] = "a"
    title_selector: ClassVar[str] = ""
    price_selector: ClassVar[str] = ""
    next_page_selector: ClassVar[str] = "a[aria-label*=下一页], a[aria-label*=Next], button[aria-label*=下一页], button[aria-label*=Next]"

    def collect(self, products: list[ProductConfig]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        max_pages = int(self.search_config.get("max_pages_per_keyword", 1))
        max_items = int(self.search_config.get("max_items_per_keyword", 20))
        screenshot_index = 1
        for product in products:
            for keyword in product.search_terms(self.platform):
                self.search(keyword)
                for page_index in range(1, max_pages + 1):
                    self.stop_if_blocked()
                    self.browse_page()
                    page_items = self.extract_items(product, keyword, page_index)
                    for item in page_items:
                        if len([x for x in items if x["keyword"] == keyword]) >= max_items:
                            break
                        screenshot_path = self.paths.platform_screenshot_path(self.platform, screenshot_index)
                        selector = item.pop("_screenshot_selector", "")
                        if selector and self.extraction_config.get("save_item_screenshot", True):
                            try:
                                self.client.screenshot(screenshot_path, selector=selector)
                                item["screenshot_path"] = str(screenshot_path)
                            except WebBridgeError:
                                item["screenshot_path"] = None
                        else:
                            item["screenshot_path"] = None
                        items.append(item)
                        screenshot_index += 1
                    if page_index >= max_pages or not self.next_page():
                        break
        write_json(self.paths.platform_result_json(self.platform), items)
        return items

    @property
    def search_config(self) -> dict[str, Any]:
        return self.config.get("search", {})

    @property
    def extraction_config(self) -> dict[str, Any]:
        return self.config.get("extraction", {})

    def search(self, keyword: str) -> None:
        try:
            if self.config.get("use_current_tab"):
                self.client.find_tab(self.base_url, active=True)
            else:
                self.client.navigate(self.base_url, new_tab=True, group_title=self.platform)
        except WebBridgeError:
            self.client.navigate(self.base_url, new_tab=True, group_title=self.platform)
        self.interaction.sleep_navigation()
        if self.search_input_selector:
            try:
                self.client.type_like_human(
                    self.search_input_selector,
                    keyword,
                    char_delay_ms=self.interaction.char_delay_ms,
                    word_delay_ms=self.interaction.word_delay_ms,
                )
                self.interaction.sleep_after_input()
                if self.search_button_selector:
                    self.client.mouse_click(self.search_button_selector)
                else:
                    self.client.send_keys("Enter")
            except WebBridgeError:
                self.client.navigate(self.search_url.format(query=quote_plus(keyword)), new_tab=False)
        else:
            self.client.navigate(self.search_url.format(query=quote_plus(keyword)), new_tab=False)
        self.interaction.sleep_navigation()

    def browse_page(self) -> None:
        pause_after = random.randint(*self.interaction.pause_after_items)
        for round_index in range(self.interaction.max_scroll_rounds_per_page):
            self.client.scroll_by(random.randint(*self.interaction.scroll_step_px))
            if (round_index + 1) % pause_after == 0:
                self.interaction.sleep_long_pause()
            else:
                self.interaction.sleep_scroll()

    def next_page(self) -> bool:
        script = f"""
(() => {{
  const selector = {json.dumps(self.next_page_selector)};
  const candidates = [...document.querySelectorAll(selector)]
    .filter(el => !el.disabled && el.getAttribute('aria-disabled') !== 'true');
  const next = candidates.find(el => /下一页|下页|Next|›|>/i.test((el.innerText || el.getAttribute('aria-label') || '').trim()));
  if (!next) return false;
  next.scrollIntoView({{ block: 'center', inline: 'center' }});
  next.setAttribute('data-deal-next-page', '1');
  return true;
}})()
"""
        if not self.client.evaluate(script):
            return False
        try:
            self.client.mouse_click('[data-deal-next-page="1"]')
        except WebBridgeError:
            self.client.click('[data-deal-next-page="1"]')
        self.interaction.sleep_navigation()
        return True

    def extract_items(self, product: ProductConfig, keyword: str, page_index: int) -> list[dict[str, Any]]:
        script = self.extract_script(product, keyword, page_index)
        data = self.client.evaluate_json(script)
        return data if isinstance(data, list) else []

    def extract_script(self, product: ProductConfig, keyword: str, page_index: int) -> str:
        return f"""
(() => {{
  const itemSelector = {json.dumps(self.item_selector)};
  const titleSelector = {json.dumps(self.title_selector)};
  const priceSelector = {json.dumps(self.price_selector)};
  const nodes = [...document.querySelectorAll(itemSelector)].slice(0, 80);
  const textOf = (node, selector) => {{
    if (!selector) return '';
    const found = node.querySelector(selector);
    return found ? found.innerText.trim() : '';
  }};
  const hrefOf = (node) => {{
    const link = node.matches('a[href]') ? node : node.querySelector('a[href]');
    return link ? link.href : null;
  }};
  const compact = (value) => (value || '').replace(/\\s+/g, ' ').trim();
  return JSON.stringify(nodes.map((node, index) => {{
    const cardId = `${{Date.now()}}-${{index + 1}}`;
    node.setAttribute('data-deal-card-id', cardId);
    const rawText = node.innerText || '';
    const title = compact(textOf(node, titleSelector) || rawText.split('\\n').find(Boolean) || '');
    const priceText = compact(textOf(node, priceSelector) || (rawText.match(/¥\\s*[\\d.]+\\s*万?/) || [''])[0]);
    return {{
      captured_at: {json.dumps(datetime.now().isoformat(timespec="seconds"))},
      site: {json.dumps(self.platform)},
      platform: {json.dumps(self.platform)},
      brand: {json.dumps(product.brand)},
      model: {json.dumps(product.model)},
      keyword: {json.dumps(keyword)},
      title,
      full_content: rawText,
      price_text: priceText,
      price_yuan: null,
      location: null,
      seller_name: null,
      shop_name: null,
      seller_credit: null,
      sold_count: null,
      on_sale_count: null,
      want_count: null,
      condition: null,
      raw_url: hrefOf(node),
      screenshot_path: null,
      page_index: {page_index},
      rank_on_page: index + 1,
      raw_card_text: rawText,
      _screenshot_selector: `[data-deal-card-id="${{cardId}}"]`
    }};
  }}).filter(item => item.title));
}})()
"""

    def stop_if_blocked(self) -> None:
        text = self.client.evaluate("(document.body.innerText || '').slice(0, 2000)")
        if isinstance(text, str) and any(marker.lower() in text.lower() for marker in BLOCK_MARKERS):
            raise WebBridgeError(f"{self.platform} appears blocked by login/captcha/risk verification")


def as_range(value: Any, default: tuple[int, int]) -> tuple[int, int]:
    if isinstance(value, list | tuple) and len(value) == 2:
        return (int(value[0]), int(value[1]))
    return default


def sleep_ms(value: tuple[int, int]) -> None:
    time.sleep(random.randint(*value) / 1000)
