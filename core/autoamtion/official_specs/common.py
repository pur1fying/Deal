from __future__ import annotations

import html
import re
import time
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from core.logger import logger
from core.webbridge import WebBridgeClient


@dataclass
class CameraSpec:
    brand: str
    model: str
    source_url: str
    sensor_format: str | None = None
    megapixels: str | None = None
    official_price_text: str | None = None
    official_price: float | None = None
    original_price_text: str | None = None
    original_price: float | None = None
    price_currency: str | None = None
    video_formats: list[str] = field(default_factory=list)
    video_modes: list[dict[str, str]] = field(default_factory=list)
    raw_text: str | None = None
    captured_at: str | None = None
    parse_error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class BrandScrapeConfig:
    brand: str
    start_urls: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    include_patterns: tuple[str, ...]
    exclude_patterns: tuple[str, ...] = ()
    product_urls: tuple[str, ...] = ()
    max_pages: int = 20
    browse_delay_seconds: float = 0.8


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._title_depth = 0
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if lowered == "title":
            self._title_depth += 1
        if lowered in {"br", "p", "li", "tr", "th", "td", "h1", "h2", "h3", "div"}:
            self.text_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if lowered == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = html.unescape(data).strip()
        if not text:
            return
        if self._title_depth:
            self.title_parts.append(text)
        self.text_parts.append(text)

    @property
    def title(self) -> str:
        return compact_text(" ".join(self.title_parts))

    @property
    def text(self) -> str:
        return compact_text("\n".join(self.text_parts))


def read_page(client: WebBridgeClient, url: str, delay_seconds: float = 2.0) -> dict:
    logger.info(f"Opening camera spec page: {url}")
    client.navigate_reuse_tab(url, group_title="official-specs")
    time.sleep(delay_seconds)
    expand_current_page(client)
    time.sleep(min(delay_seconds, 1.0))
    code = """
(() => JSON.stringify({
  url: location.href,
  title: document.title || '',
  text: document.body ? document.body.innerText : '',
  links: [...document.querySelectorAll('a[href]')].map(a => a.href)
}))()
"""
    data = client.evaluate_json(code)
    if not isinstance(data, dict):
        raise RuntimeError(f"failed to read page via WebBridge: {url}")
    return data


def expand_current_page(client: WebBridgeClient) -> None:
    code = """
(() => {
  const labels = /spec|technical|details|expand|show more|view more|see all specs/i;
  const nodes = [...document.querySelectorAll('button,[role="button"],summary,[aria-expanded="false"]')];
  let clicked = 0;
  for (const node of nodes) {
    const text = `${node.innerText || ''} ${node.getAttribute('aria-label') || ''}`.trim();
    if (labels.test(text) || node.getAttribute('aria-expanded') === 'false') {
      node.click();
      clicked += 1;
    }
    if (clicked >= 20) break;
  }
  return clicked;
})()
"""
    try:
        client.evaluate(code)
    except Exception:
        return


def discover_product_urls(client: WebBridgeClient, config: BrandScrapeConfig) -> list[str]:
    logger.attr(f"discover camera urls: {config.brand}")
    discovered: list[str] = []
    seen: set[str] = set()
    for product_url in config.product_urls:
        url = normalize_url(product_url)
        if url not in seen:
            seen.add(url)
            discovered.append(url)
            logger.info(f"Use configured {config.brand} product URL: {url}")
            if len(discovered) >= config.max_pages:
                return discovered
    for start_url in config.start_urls:
        try:
            page = read_page(client, start_url, config.browse_delay_seconds)
        except Exception:
            logger.warning(f"Failed to read {config.brand} start page: {start_url}")
            continue
        for href in page.get("links", []):
            url = normalize_url(urljoin(start_url, href))
            if url in seen or not is_allowed_url(url, config):
                continue
            seen.add(url)
            discovered.append(url)
            logger.info(f"Discovered {config.brand} product URL: {url}")
            if len(discovered) >= config.max_pages:
                return discovered
        time.sleep(config.browse_delay_seconds)
    return discovered


def scrape_brand(config: BrandScrapeConfig) -> list[CameraSpec]:
    logger.attr(f"start camera brand: {config.brand}")
    client = WebBridgeClient(session=f"official-specs-{config.brand.lower()}")
    specs: list[CameraSpec] = []
    try:
        try:
            client.close_session()
        except Exception:
            pass
        urls = discover_product_urls(client, config)
        logger.info(f"{config.brand}: {len(urls)} product page(s) queued")
        for url in urls:
            try:
                page = read_page(client, url, config.browse_delay_seconds)
                spec = parse_camera_text(
                    config.brand,
                    str(page.get("url") or url),
                    str(page.get("title") or ""),
                    str(page.get("text") or ""),
                )
                specs.append(spec)
                logger.info(
                    f"{config.brand}: parsed {spec.model} "
                    f"(sensor={spec.sensor_format}, megapixels={spec.megapixels})"
                )
            except Exception as exc:
                logger.error(f"{config.brand}: failed to parse {url}: {exc}")
                specs.append(CameraSpec(
                    brand=config.brand,
                    model=model_from_url(url),
                    source_url=url,
                    parse_error=f"{type(exc).__name__}: {exc}",
                ))
            time.sleep(config.browse_delay_seconds)
        logger.attr(f"finish camera brand: {config.brand}, items={len(specs)}")
        return specs
    finally:
        close_webbridge_session(client, config.brand)


def parse_camera_text(brand: str, url: str, title: str, text: str) -> CameraSpec:
    text = compact_text(text)
    model = extract_model(title, text, brand) or model_from_url(url)
    price = extract_official_price(text)
    return CameraSpec(
        brand=brand,
        model=model,
        source_url=url,
        sensor_format=extract_sensor_format(text),
        megapixels=extract_megapixels(text),
        official_price_text=price["official_price_text"],
        official_price=price["official_price"],
        original_price_text=price["original_price_text"],
        original_price=price["original_price"],
        price_currency=price["price_currency"],
        video_formats=extract_video_formats(text),
        video_modes=extract_video_modes(text),
        raw_text=text[:12000],
        captured_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def close_webbridge_session(client: WebBridgeClient, brand: str) -> None:
    for attempt in range(2):
        try:
            result = client.close_session()
            logger.info(f"{brand}: WebBridge session closed ({result})")
            return
        except Exception as exc:
            if attempt == 1:
                logger.warning(f"{brand}: failed to close WebBridge session: {exc}")
            time.sleep(0.5)


def parse_camera_page(brand: str, url: str, page: str) -> CameraSpec:
    extractor = TextExtractor()
    extractor.feed(page)
    return parse_camera_text(brand, url, extractor.title, extractor.text)


def is_allowed_url(url: str, config: BrandScrapeConfig) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if not any(host.endswith(domain) for domain in config.allowed_domains):
        return False
    if any(re.search(pattern, url, re.IGNORECASE) for pattern in config.exclude_patterns):
        return False
    return any(re.search(pattern, path, re.IGNORECASE) for pattern in config.include_patterns)


def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed._replace(fragment="", query="").geturl().rstrip("/")


def compact_text(value: str) -> str:
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_model(title: str, text: str, brand: str) -> str | None:
    candidates = [title] + text.splitlines()[:20]
    brand_pattern = re.escape(brand)
    for value in candidates:
        cleaned = re.sub(r"\s+", " ", value).strip(" -|")
        if not cleaned:
            continue
        cleaned = re.sub(brand_pattern, "", cleaned, flags=re.IGNORECASE).strip(" -|")
        cleaned = re.sub(r"(camera|cameras|mirrorless|digital|official|specifications|specs).*", "", cleaned, flags=re.I).strip(" -|")
        if 2 <= len(cleaned) <= 80 and re.search(r"[A-Za-z0-9]", cleaned):
            return cleaned
    return None


def model_from_url(url: str) -> str:
    slug = urlparse(url).path.strip("/").split("/")[-1]
    slug = re.sub(r"[-_]+", " ", slug)
    return slug.strip() or url


def extract_sensor_format(text: str) -> str | None:
    patterns = [
        r"(medium format)",
        r"(full[- ]frame|35mm full[- ]frame)",
        r"(APS[- ]C|APS-C)",
        r"(micro four thirds|four thirds|4/3)",
        r"(1-inch|1 inch|type 1\.0)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return normalize_sensor(match.group(1))
    return None


def normalize_sensor(value: str) -> str:
    lowered = value.lower()
    if "medium" in lowered:
        return "Medium Format"
    if "full" in lowered or "35mm" in lowered:
        return "Full Frame"
    if "aps" in lowered:
        return "APS-C"
    if "four" in lowered or "4/3" in lowered:
        return "Micro Four Thirds"
    if "1" in lowered:
        return "1-inch"
    return value


def extract_megapixels(text: str) -> str | None:
    lines = text.splitlines()
    effective_blocks: list[str] = []
    generic_blocks: list[str] = []
    for index, line in enumerate(lines):
        lowered = line.lower()
        previous = lines[index - 1].lower() if index else ""
        nearby = " ".join(lines[max(0, index - 1):index + 2]).lower()
        if "effective" in lowered and ("pixel" in lowered or "megapixel" in lowered):
            effective_blocks.append(" ".join(lines[index:index + 3]))
        elif "mp" in lowered and "compare" not in lowered:
            generic_blocks.append(line)
        elif ("number of pixels" in lowered or "megapixel" in lowered or "million pixels" in lowered) and "total" not in nearby:
            if "larger" in lowered or "based on" in previous:
                continue
            generic_blocks.append(" ".join(lines[index:index + 2]))

    patterns = [
        r"([0-9]+(?:\.[0-9]+)?)\s*MP\b",
        r"([0-9]+(?:\.[0-9]+)?)\s*[- ]?\s*(?:effective\s+)?megapixels?",
        r"([0-9]+(?:\.[0-9]+)?)\s*million pixels",
        r"([0-9]+(?:\.[0-9]+)?)\s*millions pixels",
        r"([0-9]+(?:\.[0-9]+)?)\s*million\b",
    ]
    for block in effective_blocks + generic_blocks:
        value = first_megapixel_match(block, patterns)
        if value is not None:
            return value
    return first_megapixel_match(text, patterns)


def first_megapixel_match(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        matches = [float(item) for item in re.findall(pattern, text, re.IGNORECASE)]
        matches = [item for item in matches if 5 <= item <= 200]
        if matches:
            return f"{matches[0]:g} MP"
    return None


def extract_official_price(text: str) -> dict:
    result = {
        "official_price_text": None,
        "official_price": None,
        "original_price_text": None,
        "original_price": None,
        "price_currency": None,
    }
    sale_match = re.search(r"Sale Price\s*(\$|USD)\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", text, re.IGNORECASE)
    original_match = re.search(r"Original Price\s*(\$|USD)\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", text, re.IGNORECASE)
    generic_match = re.search(r"(?<!/)(\$|USD)\s*([0-9][0-9,]*(?:\.[0-9]{2})?)", text, re.IGNORECASE)

    current = sale_match or generic_match
    if current:
        result["official_price_text"] = normalize_price_text(current.group(1), current.group(2))
        result["official_price"] = parse_price_number(current.group(2))
        result["price_currency"] = normalize_currency(current.group(1))
    if original_match:
        result["original_price_text"] = normalize_price_text(original_match.group(1), original_match.group(2))
        result["original_price"] = parse_price_number(original_match.group(2))
        result["price_currency"] = result["price_currency"] or normalize_currency(original_match.group(1))
    return result


def normalize_price_text(symbol: str, amount: str) -> str:
    currency = normalize_currency(symbol)
    prefix = "$" if currency == "USD" else symbol.strip()
    return f"{prefix}{amount}"


def normalize_currency(value: str) -> str:
    return "USD" if value.strip().upper() in {"$", "USD"} else value.strip().upper()


def parse_price_number(value: str) -> float | None:
    try:
        return float(value.replace(",", ""))
    except ValueError:
        return None


def extract_video_formats(text: str) -> list[str]:
    candidates = ("H.264", "H.265", "HEVC", "MPEG-4", "ProRes", "RAW", "XAVC", "AVC", "MOV", "MP4")
    found = []
    for candidate in candidates:
        if re.search(re.escape(candidate), text, re.IGNORECASE):
            found.append(candidate)
    return sorted(set(found), key=found.index)


def extract_video_modes(text: str) -> list[dict[str, str]]:
    modes: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    resolution_pattern = re.compile(
        r"\b(?:8K|6\.2K|6K|5\.8K|5\.7K|5\.4K|4K|2K)\b|"
        r"\b(?:7680|6240|6000|4096|3840|1920)\s*x\s*(?:4320|4160|3160|2160|1080)\b",
        re.IGNORECASE,
    )
    frame_pattern = re.compile(
        r"\b[1-9][0-9]{1,2}(?:\.[0-9]+)?\s*(?:fps|FPS|p)\b|"
        r"/\s*[1-9][0-9]{1,2}(?:\.[0-9]+)?\s*p\b",
        re.IGNORECASE,
    )
    for line in text.splitlines():
        resolutions = [normalize_video_resolution(item.group(0)) for item in resolution_pattern.finditer(line)]
        frames = [normalize_frame_rate(item.group(0)) for item in frame_pattern.finditer(line)]
        if not resolutions or not frames:
            continue
        for resolution in resolutions:
            for frame in frames:
                key = (resolution, frame)
                if key in seen:
                    continue
                seen.add(key)
                modes.append({"resolution": resolution, "fps": frame})
    return modes


def normalize_video_resolution(value: str) -> str:
    return re.sub(r"\s+", "", value.upper())


def normalize_frame_rate(value: str) -> str:
    match = re.search(r"([1-9][0-9]{1,2}(?:\.[0-9]+)?)", value)
    if not match:
        return value.strip()
    return f"{float(match.group(1)):g}p"
