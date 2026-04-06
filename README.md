# Graduation Project

当前仓库已经补齐前期 MVP 所需的数据源与环境基线，目标是先把“股票数据 + 电商数据”的采集、验证、生成和演示链路跑通，再继续接入后端、数据库和算法模块。

## 当前已落地

- 环境基线文档与安装建议
- 数据源策略文档
- 根目录 `.env.template` 运行配置模板
- 统一数据来源契约：`csv | api | synthetic | crawl`
- A 股日线抓取脚本（AkShare）
- Olist 数据集校验脚本
- 电商模拟数据生成脚本
- 演示型电商爬虫脚本（Web Scraper test site）
- 环境检查脚本

## 推荐顺序

1. 安装 Python 依赖：

   ```powershell
   pip install -r backend/requirements.txt
   ```

2. 检查当前机器环境：

   ```powershell
   python backend/scripts/check_environment.py
   ```

3. 校验手动下载的 Olist 数据集：

   ```powershell
   python backend/scripts/inspect_olist_dataset.py --dataset-dir data/raw/ecommerce/olist
   ```

4. 生成电商模拟数据：

   ```powershell
   python backend/scripts/generate_ecommerce_synthetic.py --order-count 100000
   ```

5. 拉取 A 股日线快照：

   ```powershell
   python backend/scripts/fetch_stock_akshare.py --symbols 000001 600519 300750
   ```

6. 运行演示爬虫：

   ```powershell
   python backend/scripts/crawl_demo_ecommerce.py --category computers --max-pages 3
   ```

## 关键文档

- `docs/environment-baseline.md`
- `docs/data-source-strategy.md`

## 说明

- 根目录 `version-description.txt` 用于保留本机环境检查记录。
- 真正的项目运行配置模板为 `.env.template`，实际启用时再复制为 `.env`。
- `data/` 目录仍然用于原始数据和处理结果落盘，且默认被 Git 忽略。
