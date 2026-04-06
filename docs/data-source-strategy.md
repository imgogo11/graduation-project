# 数据源策略

## 主策略

当前 MVP 阶段遵循“先跑通主链路，再补充复杂来源”的原则：

- 股票主数据源：`AkShare stock_zh_a_hist`
- 电商主数据源：Kaggle `Olist Brazilian E-Commerce Public Dataset`
- 电商补充数据：本地模拟生成器
- 演示型爬虫：`Web Scraper` 官方测试站

## 为什么这样选

### 股票域

- A 股日线数据适合先走 `AkShare`，接入成本低，便于直接生成本地快照。
- Kaggle/HuggingFace 上的静态股票数据更适合做 `fixtures`，不适合作为后续周期更新主链路。
- 如果后面需要更稳定的批量日线接口或更多指标，再升级到 `Tushare daily`。

### 电商域

- Olist 数据集天然适合拆成 `orders / order_items / products / customers / sellers / payments / reviews` 多表。
- 本地模拟生成器负责补价格历史、订单扩容、用户行为时间序列，便于算法实验和压力测试。
- 真站爬取不进入主链路，避免把反爬、登录、代理和合规问题提前带进来。

## 来源类型约定

统一保留四种来源类型：

- `csv`
- `api`
- `synthetic`
- `crawl`

该约定已经落到 `backend/app/data_sources/contracts.py`，所有脚本都会把来源类型写入 manifest。

## 目录建议

推荐数据落盘结构：

```text
data/
├─ raw/
│  ├─ stocks/
│  │  └─ akshare/
│  └─ ecommerce/
│     ├─ olist/
│     └─ webscraper_demo/
└─ processed/
   └─ ecommerce/
      └─ synthetic/
```

## 已提供的脚本

### 1. 环境检查

```powershell
python backend/scripts/check_environment.py
```

### 2. Olist 数据集校验

手动下载 Kaggle 数据集到 `data/raw/ecommerce/olist` 后执行：

```powershell
python backend/scripts/inspect_olist_dataset.py --dataset-dir data/raw/ecommerce/olist
```

### 3. 电商模拟数据

```powershell
python backend/scripts/generate_ecommerce_synthetic.py --order-count 100000
```

### 4. A 股日线抓取

```powershell
python backend/scripts/fetch_stock_akshare.py --symbols 000001 600519 300750
```

### 5. 演示爬虫

```powershell
python backend/scripts/crawl_demo_ecommerce.py --category computers --max-pages 3
```

## Manifest 设计

每次采集、校验或生成数据后，脚本都会写一个 manifest，用于统一描述：

- 数据集名称
- 来源类型
- 来源名称
- 来源地址
- 生成时间
- 行数和字段
- 产物文件路径

这样后面接入 PostgreSQL 导入任务时，可以直接沿用这套元数据。
