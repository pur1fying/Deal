from core.autoamtion.platforms.common import PlatformAutomation


class PddAutomation(PlatformAutomation):
    platform = "pdd"
    search_url = "https://mobile.yangkeduo.com/search_result.html?search_key={query}"
    item_selectors = ["[class*=goods]", "[class*=item]", "a[href*='goods']"]
