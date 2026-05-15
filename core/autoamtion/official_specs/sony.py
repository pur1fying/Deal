from __future__ import annotations

from core.autoamtion.official_specs.common import BrandScrapeConfig, CameraSpec, scrape_brand


CONFIG = BrandScrapeConfig(
    brand="Sony",
    product_urls=(
        "https://www.sony.com/electronics/support/e-mount-body-ilce-7-series/ilce-7rm5/specifications",
        "https://www.sony.com/electronics/support/e-mount-body-ilce-7-series/ilce-7m4/specifications",
        "https://www.sony.com/electronics/support/e-mount-body-ilce-1-series/ilce-1m2/specifications",
    ),
    start_urls=(
        "https://electronics.sony.com/imaging/interchangeable-lens-cameras/c/interchangeable-lens-cameras",
        "https://electronics.sony.com/imaging/compact-cameras/c/compact-cameras",
    ),
    allowed_domains=("electronics.sony.com",),
    include_patterns=(
        r"/imaging/.*/p/",
    ),
    exclude_patterns=(
        r"/accessories/",
        r"/lenses/",
        r"/c/interchangeable-lens-cameras$",
        r"/c/compact-cameras$",
    ),
    max_pages=30,
)


def scrape(max_pages: int | None = None) -> list[CameraSpec]:
    config = CONFIG if max_pages is None else BrandScrapeConfig(**{**CONFIG.__dict__, "max_pages": max_pages})
    return scrape_brand(config)
