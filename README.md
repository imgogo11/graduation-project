# Graduation Project

当前仓库已经整理为“全仓库一个 Python 虚拟环境”的工作方式，默认使用根目录 `.venv/`、`uv` 和 `pyproject.toml` 管理 Python 依赖。

## 当前已落地

- Python 项目级依赖入口：`pyproject.toml`
- Python 版本入口：`.python-version`，默认 `3.13`
- 虚拟环境约定：根目录 `.venv/`
- `backend/requirements*.txt` 兼容层
- 环境基线文档与安装建议
- 数据源策略文档
- 运行配置模板：`.env.template`
- A 股日线抓取脚本（AkShare）
- Olist 数据集校验脚本
- 电商模拟数据生成脚本
- 演示型电商爬虫脚本（Web Scraper test site）
- 环境检查脚本

## 推荐顺序

1. 创建项目虚拟环境：

   ```powershell
   uv venv .venv --python 3.13
   ```

2. 安装默认依赖：

   ```powershell
   uv sync
   ```

3. 如需扩展数据源依赖：

   ```powershell
   uv sync --extra data-sources
   ```

4. 检查当前项目环境：

   ```powershell
   uv run python backend/scripts/check_environment.py
   ```

5. 如需同步兼容层 requirements 文件：

   ```powershell
   uv run python backend/scripts/export_requirements.py
   ```

6. 校验手动下载的 Olist 数据集：

   ```powershell
   uv run python backend/scripts/inspect_olist_dataset.py --dataset-dir data/raw/ecommerce/olist
   ```

7. 生成电商模拟数据：

   ```powershell
   uv run python backend/scripts/generate_ecommerce_synthetic.py --order-count 100000
   ```

8. 拉取 A 股日线快照：

   ```powershell
   uv run python backend/scripts/fetch_stock_akshare.py --symbols 000001 600519 300750
   ```

9. 运行演示爬虫：

   ```powershell
   uv run python backend/scripts/crawl_demo_ecommerce.py --category computers --max-pages 3
   ```

## 关键文档

- `docs/python-environment.md`
- `docs/environment-baseline.md`
- `docs/data-source-strategy.md`

## 说明

- 根目录 `version-description.txt` 用于保留本机环境检查记录。
- 真正的项目运行配置模板为 `.env.template`，实际启用时再复制为 `.env`。
- `backend/requirements.txt` 与 `backend/requirements-optional.txt` 现在是兼容文件，主维护入口已经转到 `pyproject.toml`。
- `data/` 目录仍然用于原始数据和处理结果落盘，且默认被 Git 忽略。
