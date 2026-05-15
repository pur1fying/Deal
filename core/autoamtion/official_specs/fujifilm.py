from __future__ import annotations

from core.autoamtion.official_specs.common import BrandScrapeConfig, CameraSpec, scrape_brand


CONFIG = BrandScrapeConfig(
    brand="Fujifilm",
    product_urls=(
        "https://fujifilm-x.com/en-us/products/cameras/x-t5/specifications/",
        "https://fujifilm-x.com/en-us/products/cameras/x-h2s/specifications/",
        "https://fujifilm-x.com/en-us/products/cameras/gfx100-ii/specifications/",
    ),
    start_urls=(
        "https://fujifilm-x.com/global/products/cameras/",
        "https://fujifilm-x.com/en-us/products/cameras/",
    ),
    allowed_domains=("fujifilm-x.com",),
    include_patterns=(
        r"/products/cameras/",
    ),
    exclude_patterns=(
        r"/products/cameras/$",
        r"/support/",
        r"/accessories/",
    ),
    max_pages=30,
)


def scrape(max_pages: int | None = None) -> list[CameraSpec]:
    config = CONFIG if max_pages is None else BrandScrapeConfig(**{**CONFIG.__dict__, "max_pages": max_pages})
    return scrape_brand(config)
