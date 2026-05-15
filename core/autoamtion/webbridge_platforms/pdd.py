from core.autoamtion.webbridge_common import WebBridgePlatformAutomation


class PddWebBridgeAutomation(WebBridgePlatformAutomation):
    platform = "pdd"
    base_url = "https://mobile.yangkeduo.com/"
    search_url = "https://mobile.yangkeduo.com/search_result.html?search_key={query}"
    search_input_selector = "input"
    search_button_selector = "button"
    item_selector = "[class*=goods], [class*=item], a[href*='goods']"
    title_selector = "[class*=title], [class*=name], span"
    price_selector = "[class*=price], [class*=Price]"
    next_page_selector = "a, button"
