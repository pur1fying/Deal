from core.autoamtion.webbridge_common import WebBridgePlatformAutomation


class TbWebBridgeAutomation(WebBridgePlatformAutomation):
    platform = "tb"
    base_url = "https://www.taobao.com/"
    search_url = "https://s.taobao.com/search?q={query}"
    search_input_selector = "input[name='q'], input[type='search'], input[type='text']"
    search_button_selector = "button[type='submit'], .btn-search, [class*=search]"
    item_selector = "[class*=item], [data-index], a[href*='item.taobao.com']"
    title_selector = "[class*=title], [class*=Title], a, span"
    price_selector = "[class*=price], [class*=Price]"
    next_page_selector = ".next, a[aria-label*=下一页], a, button"
