# 股票交易数据管理与分析系统

本仓库是一个面向毕业设计的全栈系统，主题为：

**股票交易数据管理与分析系统的设计与实现**

系统围绕“用户上传股票交易数据，并在 Web 端完成数据管理、金融分析、快照与相关性分析、算法增强查询和风险雷达展示”这一条主线实现。当前项目已经不是早期实验骨架，而是具备前端页面、后端接口、PostgreSQL 持久化、C++/Python 混合算法模块、管理员后台和 benchmark 验证材料的可运行工程。

## 1. 核心能力

### 用户端

- 注册、登录、退出和登录态保持
- 上传 `CSV` / `XLSX` 股票交易文件
- 预览并确认列头映射，导入批次、文件产物和交易记录持久化
- 查看工作台、导入历史、交易样本和当前数据集摘要
- 使用统一筛选器同步批次、股票、日期范围、样本数等分析范围
- 在“金融分析”页面查看基础摘要、价格走势与技术信号、风险指标、异常检测、横截面对比
- 在“快照与相关性”页面查看数据质量、估值与基本面快照、相关性矩阵
- 在“算法雷达 / 风险雷达”页面查看五轴风险雷达、风险日历、风险事件列表、高风险股票画像
- 在“算法雷达 / 算法查询”页面查看区间最大成交额、区间第 K 大成交量、联合异常排名

### 管理员端

- 查看数据资产总览
- 管理普通用户：编辑用户名、重置密码、启用/禁用、删除无业务数据用户
- 查看调用记录与审计统计
- 查看导入批次、算法索引和运行监控状态

## 2. 技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Naive UI、ECharts
- 后端：FastAPI、SQLAlchemy 2、Pydantic 2、Alembic、Pandas、Uvicorn
- 数据库：PostgreSQL
- 算法模块：C++23、CMake、CTest、pybind11
- Python 环境：Python 3.13、uv、`.venv`
- 前端环境：Node.js 20+、npm
- Benchmark：Locust、Matplotlib、psutil

## 3. 页面与路由

### 用户端

| 页面 | 路由 | 说明 |
|---|---|---|
| 工作台 | `/workbench` | 导入趋势、当前数据集摘要、最近导入批次 |
| 数据集 | `/datasets` | 上传新数据集、导入历史、交易样本 |
| 金融分析 | `/analysis/market` | 基础摘要、价格走势与技术信号、风险指标、异常检测、横截面对比 |
| 快照与相关性 | `/analysis/governance` | 数据质量、估值与基本面快照、相关性矩阵 |
| 风险雷达 | `/algo-radar/risk` | 风险雷达、风险日历、风险事件列表、高风险股票画像 |
| 算法查询 | `/algo-radar/algorithms` | 区间算法结果、联合异常排名 |

兼容重定向：

- `/analysis` -> `/analysis/market`
- `/algo-radar` -> `/algo-radar/risk`
- `/overview` -> `/workbench`
- `/analysis-center` -> `/analysis/market`

### 管理员端

| 页面 | 路由 | 说明 |
|---|---|---|
| 数据资产总览 | `/admin/assets` | 数据、用户、批次、审计概览 |
| 用户管理 | `/admin/users` | 普通用户管理 |
| 用户调用记录 | `/admin/activity` | 审计日志与统计 |
| 运行监控 | `/admin/runs` | 导入批次和算法索引运行状态 |

兼容重定向：

- `/admin/overview` -> `/admin/assets`
- `/admin/health` -> `/admin/assets`
- `/system/users` -> `/admin/users`

## 4. 后端接口概览

所有业务接口默认挂载在 `/api` 下。

| 前缀 | 说明 |
|---|---|
| `/api/health` | 健康检查 |
| `/api/auth/*` | 注册、登录、当前用户 |
| `/api/admin/*` | 管理员资产、用户、审计、运行监控 |
| `/api/imports/*` | 导入预览、导入提交、导入历史、统计、软删除 |
| `/api/trading/*` | 股票列表、交易记录 |
| `/api/trading/analysis/*` | 摘要、质量、技术指标、风险、快照、异常、横截面、相关性 |
| `/api/algo/trading/*` | 区间最大成交额、区间第 K 大成交量、联合异常排名 |
| `/api/algo/indexes/*` | 算法索引状态与重建 |
| `/api/algo/risk-radar/*` | 风险雷达、事件、日历、股票画像、事件上下文 |

## 5. 目录结构

```text
graduation-project/
├─ backend/                  FastAPI 后端、Alembic 迁移、服务层、测试
├─ web/                      Vue 3 + Naive UI 前端
├─ algo-module/              C++ 算法模块与 pybind11 绑定
├─ benchmarks/               查询效率、第 K 大对比、平台质量 benchmark
├─ data/                     本地上传文件、处理后数据、测试数据
├─ deploy/                   PostgreSQL Docker Compose
├─ docs/                     环境、数据源、数据库图、论文草稿等材料
├─ scripts/dev/              本地启动脚本
├─ scripts/python/           数据获取、字段检查、验证脚本
├─ README.md                 项目说明
├─ require.md                数据契约与字段需求
├─ tasks.md                  任务总表
├─ progress.md               当前进度
├─ pyproject.toml            Python 依赖与 uv 配置
└─ .env.template             环境变量模板
```

## 6. 环境要求

- Python `3.13`
- Node.js `20+`
- npm
- uv
- Docker Desktop / Docker Compose
- CMake
- PostgreSQL，默认通过 `deploy/docker-compose.yml` 启动

默认本地端口：

- PostgreSQL：`15432`
- FastAPI：`8200`
- Vite：`4173`

## 7. 初始化

复制环境变量模板：

```powershell
Copy-Item .env.template .env
```

安装 Python 依赖：

```powershell
uv venv .venv --python 3.13
uv sync
```

安装前端依赖：

```powershell
npm.cmd --prefix web install
```

构建 C++ 算法模块：

```powershell
cmake -S algo-module -B algo-module/build "-DPython_EXECUTABLE=$(Resolve-Path .\.venv\Scripts\python.exe)" "-Dpybind11_DIR=$(uv run python -m pybind11 --cmakedir)"
cmake --build algo-module/build
```

启动数据库并迁移：

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
uv run python -m alembic -c backend/alembic.ini upgrade head
uv run python backend/scripts/init_admin.py
```

也可以参考：

- `run-scripts-full-setup.txt`
- `run-scripts-demo-start.txt`
- `scripts/dev/full-start.ps1`
- `scripts/dev/demo-start.ps1`

## 8. 日常启动

启动 PostgreSQL：

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
```

启动后端：

```powershell
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8200 --reload
```

启动前端：

```powershell
cd web
npm run dev
```

访问地址：

- 前端：`http://127.0.0.1:4173`
- 后端 OpenAPI：`http://127.0.0.1:8200/docs`

## 9. 数据导入

支持 `.csv` 和 `.xlsx`。导入页面支持列头预览和映射确认。

当前主表规范字段：

```text
stock_code,stock_name,trade_date,open,high,low,close,volume,amount,turnover,benchmark_close,pe_ttm,pb,roe,asset_liability_ratio,revenue_yoy,net_profit_yoy,valuation_as_of,fundamental_report_date
```

最小必需字段：

```text
stock_code,trade_date,open,high,low,close,volume
```

常用测试数据位于：

```text
data/processed/auto-generate/
```

其中 `manual_test_boundary_stocks_10x600_20220103_20240517.csv` 用于手动测试边界场景。

命令行导入：

```powershell
uv run python backend/scripts/import_data.py --file-path .\data\processed\auto-generate\manual_test_boundary_stocks_10x600_20220103_20240517.csv --dataset-name manual_test_boundary
```

如果 `.env` 已配置 `DEMO_IMPORT_FILE_PATH`、`DEMO_DATASET_PREFIX`、`DEMO_IMPORT_USERNAME`，也可以直接执行：

```powershell
uv run python backend/scripts/import_data.py
```

## 10. 测试与验证

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

前端类型检查：

```powershell
cd web
npm run typecheck
```

前端构建：

```powershell
cd web
npm run build
```

C++ 测试：

```powershell
ctest --test-dir algo-module/build --output-on-failure
```

Benchmark：

```powershell
python benchmarks/run_all.py --suite query_efficiency --sample all
python benchmarks/run_all.py --suite kth_comparison --sample all
python benchmarks/run_all.py --suite platform_quality --profile thesis
```

## 11. 当前注意事项

- `trading_records` 是当前唯一正式入库的交易主表。
- `benchmark_close`、估值快照和基本面字段已经是 `trading_records` 的可选列，上传文件提供并完成映射后可以入库。
- 这些增强列不是最小导入必需字段；普通 OHLCV 文件仍可导入，相关模块会按缺字段规则降级。
- 风险雷达索引是基于当前导入批次构建的运行期索引，不等同于用户筛选器内容。
- 停止 Uvicorn 开发服务时出现 `KeyboardInterrupt` / `CancelledError` 通常是 `Ctrl+C` 正常中断日志，不代表业务异常。
