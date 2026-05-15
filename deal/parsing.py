from __future__ import annotations

import re

from deal.models import ProductConfig


PRICE_RE = re.compile(r"(?:¥|￥|RMB|CNY)?\s*([0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]{1,2})?")
EFFECTIVE_HINTS = ("到手", "券后", "补贴", "预估", "立减", "优惠后")


def parse_price(text: str | None) -> float | None:
    if not text:
        return None
    normalized = text.replace("，", ",").replace("－", "-").replace("—", "-")
    matches = PRICE_RE.findall(normalized)
    if not matches:
        return None
    values = [float(match.replace(",", "")) for match in matches]
    if "-" in normalized or "起" in normalized or "区间" in normalized:
        return min(values)
    return values[0]


def parse_list_and_effective_price(price_text: str | None, effective_text: str | None = None) -> tuple[float | None, float | None]:
    list_price = parse_price(price_text)
    effective_price = parse_price(effective_text)
    if effective_price is None and price_text and any(hint in price_text for hint in EFFECTIVE_HINTS):
        effective_price = list_price
        list_price = None
    return list_price, effective_price


def title_matches(product: ProductConfig, title: str) -> bool:
    normalized_title = title.casefold()
    excluded = [word for word in product.exclude_words if word.casefold() in normalized_title]
    if excluded:
        return False
    candidates = [product.brand, product.model, *product.keywords]
    return any(candidate.casefold() in normalized_title for candidate in candidates if candidate)
