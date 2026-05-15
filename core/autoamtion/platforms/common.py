from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus

from deal.models import ProductConfig, RawItem, RunPaths
from deal.parsing import title_matches


PRICE_SELECTORS = ["[class*=price]", "[class*=Price]", ".p-price", "[aria-label*=price]", "[aria-label*=\u4ef7\u683c]"]
TITLE_SELECTORS = ["[class*=title]", "[class*=Title]", ".p-name", "a", "span"]
BLOCK_MARKERS = (
    "login",
    "captcha",
    "verify",
    "\u767b\u5f55",
    "\u9a8c\u8bc1\u7801",
    "\u5b89\u5168\u9a8c\u8bc1",
    "\u6ed1\u5757",
)
EFFECTIVE_MARKERS = (
    "after coupon",
    "subsidy",
    "discount",
    "\u5230\u624b",
    "\u5238\u540e",
    "\u8865\u8d34",
    "\u4f18\u60e0\u540e",
)


class PlatformAutomation:
    platform: str
    search_url: str
    item_selectors: list[str]

    def __init__(self, playwright, paths: RunPaths, max_items: int, wait_seconds: int):
        self.playwright = playwright
        self.paths = paths
        self.max_items = max_items
        self.wait_seconds = wait_seconds

    async def collect(self, products: list[ProductConfig]) -> list[RawItem]:
        context = await self.launch_context()
        page = await context.new_page()
        raw_items: list[RawItem] = []
        try:
            for product in products:
                for keyword in product.search_terms(self.platform):
                    url = self.search_url.format(query=quote_plus(keyword))
                    await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                    await page.wait_for_timeout(self.wait_seconds * 1000)
                    if await self.looks_blocked(page):
                        print(f"[{self.platform}] Please handle login/captcha/region in Chrome, then press Enter here.")
                        input()
                        await page.wait_for_load_state("domcontentloaded")
                    try:
                        captured_at = datetime.now().isoformat(timespec="seconds")
                        raw_items.extend(await self.parse_items_from_page(page, product, keyword, captured_at))
                    except Exception as exc:
                        raw_items.append(await self.capture_parse_error(page, product, keyword, exc))
        finally:
            await context.close()
        return raw_items

    async def launch_context(self):
        user_data_dir = Path("config") / "profiles" / self.platform
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            channel="chrome",
            headless=False,
            viewport={"width": 1440, "height": 1000},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            accept_downloads=True,
        )

    async def looks_blocked(self, page) -> bool:
        text = (await page.locator("body").inner_text(timeout=5000)).lower()
        return any(marker in text for marker in BLOCK_MARKERS)

    async def parse_items_from_page(self, page, product: ProductConfig, keyword: str, captured_at: str) -> list[RawItem]:
        selector = ", ".join(self.item_selectors)
        locators = page.locator(selector)
        count = min(await locators.count(), self.max_items * 4)
        items: list[RawItem] = []
        seen: set[tuple[str, str | None]] = set()
        for index in range(count):
            node = locators.nth(index)
            text = await node.inner_text(timeout=3000)
            title = await first_inner_text(node, TITLE_SELECTORS) or first_line(text)
            if not title or not title_matches(product, title):
                continue
            price_text = await first_inner_text(node, PRICE_SELECTORS)
            href = await first_href(node)
            key = (title, href)
            if key in seen:
                continue
            seen.add(key)
            items.append(RawItem(
                brand=product.brand,
                model=product.model,
                platform=self.platform,
                source_keyword=keyword,
                title=title,
                url=href,
                price_text=price_text or text,
                effective_price_text=effective_text(text),
                full_content=text,
                page_index=1,
                rank_on_page=len(items) + 1,
                page_text=text,
                captured_at=captured_at,
            ))
            if len(items) >= self.max_items:
                break
        return items

    async def capture_parse_error(self, page, product: ProductConfig, keyword: str, exc: Exception) -> RawItem:
        screenshot = self.paths.platform_screenshot_path(self.platform, 1)
        html_path = self.paths.html / f"{self.platform}-{safe_name(product.model)}-{safe_name(keyword)}.html"
        await page.screenshot(path=str(screenshot), full_page=True)
        html_path.write_text(await page.content(), encoding="utf-8")
        return RawItem(
            brand=product.brand,
            model=product.model,
            platform=self.platform,
            source_keyword=keyword,
            title="",
            screenshot_path=str(screenshot),
            captured_at=datetime.now().isoformat(timespec="seconds"),
            parse_error=f"{type(exc).__name__}: {exc}",
        )


async def first_inner_text(locator, selectors: list[str]) -> str | None:
    for selector in selectors:
        child = locator.locator(selector).first
        if await child.count():
            value = (await child.inner_text(timeout=1000)).strip()
            if value:
                return value
    return None


async def first_href(locator) -> str | None:
    link = locator.locator("a[href]").first
    if not await link.count():
        return None
    return await link.get_attribute("href")


def first_line(text: str) -> str:
    return next((line.strip() for line in text.splitlines() if line.strip()), "")


def effective_text(text: str) -> str | None:
    for line in text.splitlines():
        lowered = line.lower()
        if any(marker in lowered for marker in EFFECTIVE_MARKERS):
            return line
    return None


def safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value)[:60]
