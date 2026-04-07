# 作用:
# - 这是演示型电商爬虫的命令行入口，负责解析分类、分页和输出路径等参数，
#   并触发示例站点商品列表抓取。
# 关联文件:
# - 直接导入 backend/scripts/_bootstrap.py，用来准备 backend 的导入路径。
# - 直接调用 backend/app/data_sources/demo_crawler.py 中的 DEMO_SITE_URL 和 crawl_demo_site。
# - 生成的 CSV 和 manifest 由 backend/app/data_sources/contracts.py 的契约结构约束。
#
from __future__ import annotations

import argparse
from pathlib import Path

from _bootstrap import ensure_backend_on_path

_, REPO_ROOT = ensure_backend_on_path()

from app.data_sources.demo_crawler import DEMO_SITE_URL, crawl_demo_site


def main() -> int:
    parser = argparse.ArgumentParser(description="Crawl the Web Scraper demo e-commerce site.")
    parser.add_argument("--start-url", default=DEMO_SITE_URL, help="Listing entry URL")
    parser.add_argument("--category", default="", help="Category text to resolve from the entry page")
    parser.add_argument("--max-pages", type=int, default=3, help="Maximum number of listing pages to crawl")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Delay between HTTP requests")
    parser.add_argument(
        "--out-path",
        default=str(REPO_ROOT / "data" / "raw" / "ecommerce" / "webscraper_demo" / "products.csv"),
        help="CSV output path",
    )
    args = parser.parse_args()

    csv_path, manifest_path = crawl_demo_site(
        start_url=args.start_url,
        category=args.category,
        max_pages=args.max_pages,
        sleep_seconds=args.sleep_seconds,
        out_path=Path(args.out_path),
    )
    print(f"Crawl output written to: {csv_path}")
    print(f"Manifest written to: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
