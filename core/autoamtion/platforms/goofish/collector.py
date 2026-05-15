from core.autoamtion.platforms.common import PlatformAutomation


class GoofishAutomation(PlatformAutomation):
    platform = "goofish"
    search_url = "https://www.goofish.com/search?q={query}"
    item_selectors = ["[class*=feeds-item]", "[class*=item]", "a[href*='item']"]
