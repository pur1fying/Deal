from deal.models import ProductConfig
from deal.parsing import parse_list_and_effective_price, parse_price, title_matches


def test_parse_price_common_formats():
    assert parse_price("¥12,999") == 12999
    assert parse_price("到手价 10999") == 10999
    assert parse_price("券后 8999") == 8999
    assert parse_price("8999-10999") == 8999


def test_parse_effective_price_hint():
    assert parse_list_and_effective_price("到手价 10999", None) == (None, 10999)
    assert parse_list_and_effective_price("¥12,999", "券后 10999") == (12999, 10999)


def test_title_filtering_with_excludes():
    product = ProductConfig(
        brand="Sony",
        model="A7M4",
        keywords=["索尼 A7M4"],
        exclude_words=["贴膜", "保护套"],
    )
    assert title_matches(product, "索尼 A7M4 全画幅微单相机")
    assert not title_matches(product, "索尼 A7M4 贴膜")
    assert not title_matches(product, "佳能 R6 Mark II")
