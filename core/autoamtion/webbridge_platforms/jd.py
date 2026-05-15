from core.autoamtion.webbridge_common import WebBridgePlatformAutomation


class JdWebBridgeAutomation(WebBridgePlatformAutomation):
    platform = "jd"
    base_url = "https://www.jd.com/"
    search_url = "https://search.jd.com/Search?keyword={query}&enc=utf-8"
    search_input_selector = "#key, input[name='keyword'], input[type='text']"
    search_button_selector = ".button, button[type='submit']"
    item_selector = ".gl-item, li[class*=item], a[href*='item.jd.com']"
    title_selector = ".p-name, [class*=title], em, a"
    price_selector = ".p-price, [class*=price]"
    next_page_selector = ".pn-next, a[aria-label*=下一页], a, button"
