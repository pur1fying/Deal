from __future__ import annotations

from core.autoamtion.official_specs.common import BrandScrapeConfig, CameraSpec, scrape_brand


CONFIG = BrandScrapeConfig(
    brand="Hasselblad",
    product_urls=(
        "https://www.hasselblad.com/x-system/x2d-ii-100c/",
        "https://www.hasselblad.com/x-system/x2d-100c/",
        "https://www.hasselblad.com/v-system/907x-cfv-100c/",
    ),
    start_urls=(
        "https://www.hasselblad.com/x-system/",
        "https://www.hasselblad.com/cameras/",
    ),
    allowed_domains=("hasselblad.com",),
    include_patterns=(
        r"/x-system/",
        r"/cameras/",
        r"/907x",
        r"/x2d",
    ),
    exclude_patterns=(
        r"/lenses/",
        r"/accessories/",
        r"/support/",
    ),
    max_pages=20,
)


def scrape(max_pages: int | None = None) -> list[CameraSpec]:
    config = CONFIG if max_pages is None else BrandScrapeConfig(**{**CONFIG.__dict__, "max_pages": max_pages})
    return scrape_brand(config)
