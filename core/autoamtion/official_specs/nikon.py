from __future__ import annotations

from core.autoamtion.official_specs.common import BrandScrapeConfig, CameraSpec, scrape_brand


CONFIG = BrandScrapeConfig(
    brand="Nikon",
    product_urls=(
        "https://imaging.nikon.com/imaging/lineup/mirrorless/z_8/",
        "https://imaging.nikon.com/imaging/lineup/mirrorless/z6_3/",
        "https://imaging.nikon.com/imaging/lineup/mirrorless/z_f/",
    ),
    start_urls=(
        "https://imaging.nikon.com/imaging/lineup/mirrorless/",
        "https://imaging.nikon.com/imaging/lineup/dslr/",
    ),
    allowed_domains=("imaging.nikon.com",),
    include_patterns=(
        r"/p/",
        r"/cameras/",
    ),
    exclude_patterns=(
        r"/c/cameras/",
        r"/lenses/",
        r"/accessories/",
        r"/support/",
    ),
    max_pages=30,
)


def scrape(max_pages: int | None = None) -> list[CameraSpec]:
    config = CONFIG if max_pages is None else BrandScrapeConfig(**{**CONFIG.__dict__, "max_pages": max_pages})
    return scrape_brand(config)
