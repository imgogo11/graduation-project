# 作用:
# - 这是演示型电商爬虫模块，负责访问 Web Scraper 测试站点，提取商品列表信息，
#   并把抓取结果写成 CSV 与 manifest。
# 关联文件:
# - 被 backend/scripts/crawl_demo_ecommerce.py 导入并作为实际业务实现调用。
# - 依赖 backend/app/data_sources/contracts.py 提供的 DatasetArtifact、ImportManifest、
#   SourceType、now_utc_iso 和 write_manifest。
# - 依赖 beautifulsoup4 与 requests 完成 HTML 解析和网络请求。
#
from __future__ import annotations

from collections import deque
from pathlib import Path
import re
import time
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests

from .contracts import DatasetArtifact, ImportManifest, SourceType, now_utc_iso, write_manifest

DEMO_SITE_URL = "https://webscraper.io/test-sites/e-commerce/static"
USER_AGENT = "graduation-project-demo-crawler/1.0"


def _load_bs4():
    try:
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError(
            "beautifulsoup4 is not installed. Run `pip install -r backend/requirements.txt` first."
        ) from exc
    return BeautifulSoup


def _build_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    return session


def _request_with_retry(
    session: requests.Session,
    url: str,
    retries: int,
    sleep_seconds: float,
    timeout: float,
) -> str:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            time.sleep(sleep_seconds)
            return response.text
        except Exception as exc:  # pragma: no cover
            last_error = exc
            if attempt < retries:
                time.sleep(sleep_seconds)
    raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error


def _infer_category(soup, fallback: str) -> str:
    active = soup.select_one("ul.breadcrumb li.active")
    if active:
        return active.get_text(" ", strip=True)
    return fallback or "unknown"


def _resolve_category_url(
    session: requests.Session,
    start_url: str,
    category: str,
    retries: int,
    sleep_seconds: float,
    timeout: float,
) -> str:
    if not category:
        return start_url

    BeautifulSoup = _load_bs4()
    html = _request_with_retry(session, start_url, retries, sleep_seconds, timeout)
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.select("a"):
        text = anchor.get_text(" ", strip=True).lower()
        href = anchor.get("href")
        if href and category.lower() in text:
            return urljoin(start_url, href)
    raise ValueError(f"Could not resolve category '{category}' from {start_url}")


def _extract_products_from_listing(html: str, page_url: str, fallback_category: str) -> list[dict[str, object]]:
    BeautifulSoup = _load_bs4()
    soup = BeautifulSoup(html, "html.parser")
    page_category = _infer_category(soup, fallback_category)
    rows: list[dict[str, object]] = []

    for card in soup.select("div.thumbnail"):
        link = card.select_one("a.title")
        price_node = card.select_one("h4.price")
        desc_node = card.select_one("p.description")
        review_node = card.select_one("div.ratings p.pull-right")
        href = link.get("href") if link else None
        if not href or not link or not price_node:
            continue

        review_text = review_node.get_text(" ", strip=True) if review_node else "0 reviews"
        match = re.search(r"(\d+)", review_text)
        review_count = int(match.group(1)) if match else 0

        rows.append(
            {
                "source_url": urljoin(page_url, href),
                "category": page_category,
                "title": link.get("title") or link.get_text(" ", strip=True),
                "price": float(price_node.get_text(strip=True).replace("$", "")),
                "description": desc_node.get_text(" ", strip=True) if desc_node else "",
                "review_count": review_count,
            }
        )

    return rows


def _extract_pagination_urls(html: str, page_url: str) -> list[str]:
    BeautifulSoup = _load_bs4()
    soup = BeautifulSoup(html, "html.parser")
    urls: list[str] = []
    for anchor in soup.select("ul.pagination a"):
        href = anchor.get("href")
        if href:
            urls.append(urljoin(page_url, href))
    return urls


def _same_origin(url_a: str, url_b: str) -> bool:
    parsed_a = urlparse(url_a)
    parsed_b = urlparse(url_b)
    return parsed_a.scheme == parsed_b.scheme and parsed_a.netloc == parsed_b.netloc


def crawl_demo_site(
    start_url: str,
    category: str,
    max_pages: int,
    sleep_seconds: float,
    out_path: Path,
    retries: int = 3,
    timeout: float = 20.0,
) -> tuple[Path, Path]:
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    session = _build_session()
    start_listing_url = _resolve_category_url(session, start_url, category, retries, sleep_seconds, timeout)

    existing = pd.DataFrame()
    known_urls: set[str] = set()
    if out_path.exists():
        existing = pd.read_csv(out_path)
        if "source_url" in existing.columns:
            known_urls = set(existing["source_url"].dropna().astype(str))

    queue: deque[str] = deque([start_listing_url])
    seen_pages: set[str] = set()
    rows: list[dict[str, object]] = []

    while queue and len(seen_pages) < max_pages:
        page_url = queue.popleft()
        if page_url in seen_pages:
            continue
        if not _same_origin(start_url, page_url):
            continue

        html = _request_with_retry(session, page_url, retries, sleep_seconds, timeout)
        seen_pages.add(page_url)

        for row in _extract_products_from_listing(html, page_url, category):
            source_url = str(row["source_url"])
            if source_url not in known_urls:
                rows.append(row)
                known_urls.add(source_url)

        for candidate in _extract_pagination_urls(html, page_url):
            if candidate not in seen_pages:
                queue.append(candidate)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    new_frame = pd.DataFrame(rows, columns=["source_url", "category", "title", "price", "description", "review_count"])
    combined = pd.concat([existing, new_frame], ignore_index=True) if not existing.empty else new_frame
    if not combined.empty:
        combined = combined.drop_duplicates(subset=["source_url"]).reset_index(drop=True)
    combined.to_csv(out_path, index=False, encoding="utf-8-sig")

    manifest = ImportManifest(
        dataset_name="webscraper_demo_products",
        source_type=SourceType.CRAWL,
        source_name="webscraper.test.site",
        source_uri=start_url,
        created_at=now_utc_iso(),
        record_count=len(combined),
        columns=list(combined.columns),
        artifacts=[
            DatasetArtifact(
                name="products",
                path=str(out_path),
                rows=len(combined),
                columns=list(combined.columns),
            )
        ],
        metadata={
            "category": category or "all",
            "max_pages": max_pages,
            "sleep_seconds": sleep_seconds,
            "pages_visited": sorted(seen_pages),
        },
    )
    manifest_path = write_manifest(manifest, out_path.with_name("webscraper_demo_manifest.json"))
    return out_path, manifest_path
