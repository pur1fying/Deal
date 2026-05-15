from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


PLATFORMS = ("tb", "jd", "pdd", "goofish")


@dataclass(frozen=True)
class ProductConfig:
    brand: str
    model: str
    keywords: list[str]
    exclude_words: list[str] = field(default_factory=list)
    platform_keywords: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductConfig":
        return cls(
            brand=str(data["brand"]),
            model=str(data["model"]),
            keywords=[str(item) for item in data.get("keywords", [])],
            exclude_words=[str(item) for item in data.get("exclude_words", [])],
            platform_keywords={
                str(platform): [str(item) for item in values]
                for platform, values in data.get("platform_keywords", {}).items()
            },
        )

    def search_terms(self, platform: str) -> list[str]:
        terms = self.platform_keywords.get(platform) or self.keywords
        if terms:
            return terms
        return [f"{self.brand} {self.model}"]


@dataclass
class RawItem:
    brand: str
    model: str
    platform: str
    source_keyword: str
    title: str
    url: str | None = None
    price_text: str | None = None
    effective_price_text: str | None = None
    full_content: str | None = None
    seller_name: str | None = None
    shop_name: str | None = None
    seller_credit: str | None = None
    sold_count: int | None = None
    on_sale_count: int | None = None
    want_count: int | None = None
    condition: str | None = None
    screenshot_path: str | None = None
    page_index: int | None = None
    rank_on_page: int | None = None
    page_text: str | None = None
    captured_at: str = ""
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class NormalizedItem:
    brand: str
    model: str
    platform: str
    title: str
    url: str | None
    list_price: float | None
    effective_price: float | None
    currency: str
    source_keyword: str
    captured_at: str
    parse_error: str | None = None

    @classmethod
    def from_raw(cls, raw: RawItem, list_price: float | None, effective_price: float | None) -> "NormalizedItem":
        return cls(
            brand=raw.brand,
            model=raw.model,
            platform=raw.platform,
            title=raw.title,
            url=raw.url,
            list_price=list_price,
            effective_price=effective_price,
            currency="CNY",
            source_keyword=raw.source_keyword,
            captured_at=raw.captured_at,
            parse_error=raw.parse_error,
        )

    def best_price(self) -> float | None:
        return self.effective_price if self.effective_price is not None else self.list_price

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RunPaths:
    root: Path
    raw: Path
    normalized: Path
    result: Path
    summary: Path
    charts: Path
    logs: Path
    screenshots: Path
    html: Path

    @classmethod
    def create(
        cls,
        output_root: Path,
        now: datetime,
        run_id: str | None = None,
        platforms: tuple[str, ...] = PLATFORMS,
        date_format: str = "%Y-%m-%d",
        run_id_format: str = "%H%M%S",
    ) -> "RunPaths":
        date_dir = output_root / now.strftime(date_format)
        run = run_id or next_incremental_run_id(date_dir)
        root = date_dir / run
        paths = cls(
            root=root,
            raw=root / "raw",
            normalized=root / "normalized",
            result=root / "result",
            summary=root / "summary",
            charts=root / "charts",
            logs=root / "log",
            screenshots=root / "screenshots",
            html=root / "html",
        )
        for path in asdict(paths).values():
            Path(path).mkdir(parents=True, exist_ok=True)
        for platform in platforms:
            paths.platform_result_dir(platform).mkdir(parents=True, exist_ok=True)
            paths.platform_screenshot_dir(platform).mkdir(parents=True, exist_ok=True)
        return paths

    def platform_result_dir(self, platform: str) -> Path:
        return self.result / platform

    def platform_result_json(self, platform: str) -> Path:
        return self.platform_result_dir(platform) / "result.json"

    def platform_screenshot_dir(self, platform: str) -> Path:
        return self.platform_result_dir(platform) / "screenshot"

    def platform_screenshot_path(self, platform: str, index: int) -> Path:
        return self.platform_screenshot_dir(platform) / f"{index:08d}.png"


def next_incremental_run_id(parent: Path) -> str:
    if not parent.exists():
        return "001"
    numbers = [
        int(path.name)
        for path in parent.iterdir()
        if path.is_dir() and path.name.isdigit()
    ]
    return f"{(max(numbers) + 1) if numbers else 1:03d}"
