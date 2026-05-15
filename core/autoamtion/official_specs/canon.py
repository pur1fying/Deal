from __future__ import annotations

from core.autoamtion.official_specs.common import BrandScrapeConfig, CameraSpec, scrape_brand


CONFIG = BrandScrapeConfig(
    brand="Canon",
    product_urls=(
        "https://www.canon-europe.com/cameras/eos-r5-mark-ii/specifications/",
        "https://www.canon-europe.com/cameras/eos-r6-mark-ii/specifications/",
        "https://www.canon-europe.com/cameras/eos-r3/specifications/",
    ),
    start_urls=(
        "https://www.canon-europe.com/cameras/",
        "https://www.usa.canon.com/shop/cameras/mirrorless-cameras",
        "https://www.usa.canon.com/shop/cameras/dslr-cameras",
    ),
    allowed_domains=("canon-europe.com", "usa.canon.com"),
    include_patterns=(
        r"/cameras/eos-.*/specifications/",
        r"/shop/p/",
        r"/cameras/",
    ),
    exclude_patterns=(
        r"/shop/cameras/",
        r"/lenses/",
        r"/printers/",
        r"/accessories/",
        r"/support/",
    ),
    max_pages=30,
)


def scrape(max_pages: int | None = None) -> list[CameraSpec]:
    config = CONFIG if max_pages is None else BrandScrapeConfig(**{**CONFIG.__dict__, "max_pages": max_pages})
    return scrape_brand(config)
