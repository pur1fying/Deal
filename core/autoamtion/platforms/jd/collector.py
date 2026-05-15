from core.autoamtion.platforms.common import PlatformAutomation


class JdAutomation(PlatformAutomation):
    platform = "jd"
    search_url = "https://search.jd.com/Search?keyword={query}&enc=utf-8"
    item_selectors = [".gl-item", "li[class*=item]", "a[href*='item.jd.com']"]
