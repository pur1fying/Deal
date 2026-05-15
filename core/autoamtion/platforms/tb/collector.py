from core.autoamtion.platforms.common import PlatformAutomation


class TbAutomation(PlatformAutomation):
    platform = "tb"
    search_url = "https://s.taobao.com/search?q={query}"
    item_selectors = ["[class*=item]", "[data-index]", "a[href*='item.taobao.com']"]
