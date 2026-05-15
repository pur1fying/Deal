from core.autoamtion.webbridge_common import WebBridgePlatformAutomation


class GoofishWebBridgeAutomation(WebBridgePlatformAutomation):
    platform = "goofish"
    base_url = "https://www.goofish.com/"
    search_url = "https://www.goofish.com/search?q={query}"
    search_input_selector = "input"
    search_button_selector = "button"
    item_selector = "[class*=feeds-item], [class*=item-card], a[href*='item']"
    title_selector = "[class*=title], [class*=desc], span"
    price_selector = "[class*=price], [class*=Price]"
    next_page_selector = "a, button"
