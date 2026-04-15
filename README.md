# 股票交易数据管理与分析系统的设计与实现（Design and Implementation of Stock Trading Data Management and Analysis System）

## 项目简介

本项目当前聚焦一条明确主线：

- 用户注册与登录
- 用户上传 `CSV` / `XLSX` 历史交易数据
- 导入批次、清单与产物记录持久化
- 基于用户权限隔离的数据查询与管理
- 面向股票数据的一体化交易分析
- 由 C++ 算法模块增强的区间分析、联合异常排序与风险雷达能力

早期的股票爬虫、电商演示数据和历史兼容壳已经退出当前主业务主线。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus + ECharts
- 后端：FastAPI + SQLAlchemy + Alembic + Pandas
- 数据库：PostgreSQL
- 算法模块：C++ + pybind11

## 当前核心数据模型

- `users`
- `import_runs`
- `import_manifests`
- `import_artifacts`
- `trading_records`

## 支持的上传模板

```text
stock_code,stock_name,trade_date,open,high,low,close,volume,amount
```

- 支持文件格式：`.csv`、`.xlsx`
- 当前系统仅处理股票交易数据
- 必填列：`stock_code`、`trade_date`、`open`、`high`、`low`、`close`、`volume`
- 可选列：`stock_name`、`amount`、`turnover`
- 上传链路只接受规范字段名本身，不再兼容 `instrument_*`、`code/symbol/ticker` 或中文别名表头
- 数据集名称在“同一用户 + 未删除上传批次”范围内必须唯一；删除后名称可再次使用

## 当前主要能力

### 数据管理

- 用户注册、登录、鉴权
- 按用户隔离的导入批次管理
- 导入历史、导入统计、软删除
- 原始交易记录查询
- 管理员普通用户管理：用户名编辑、密码重置、启用/禁用、无业务数据用户删除
- Web 前端采用 `Overview / Analysis Center / Algo Radar` 三页结构

### 数据分析

- 股票级交易摘要
- 数据质量分析
- 技术指标分析：MA / EMA / MACD / RSI / Bollinger / ATR
- 风险指标分析：区间收益率、波动率、最大回撤、上涨日占比等
- 异常检测：放量异常、收益率异常、振幅异常、突破前高/前低
- 横截面分析：多股票排序
- 相关性分析：当前批次内多股票收益率相关性矩阵
- 范围对比分析：通过 `compare-scopes` 支持同批次/跨批次、同股票/多股票、不同日期范围的一致性校验

### 算法与风险雷达

- `GET /api/algo/trading/range-max-amount`
- `GET /api/algo/trading/range-kth-volume`
- `GET /api/algo/trading/joint-anomaly-ranking`
- `GET /api/algo/indexes/status`
- `POST /api/algo/indexes/rebuild`
- `GET /api/algo/risk-radar/overview`
- `GET /api/algo/risk-radar/events`
- `GET /api/algo/risk-radar/stocks`
- `GET /api/algo/risk-radar/calendar`
- `GET /api/algo/risk-radar/event-context`

其中 `range-kth-volume` 同时支持：

- `persistent_segment_tree`：精确结果，返回命中的交易日期
- `t_digest`：近似结果，返回 `is_approx=true` 与 `approximation_note`

## 论文材料

- 毕业论文目录与写作提纲：[`docs/structure-codex.md`](docs/structure-codex.md)
- 论文正文草稿：[`docs/main-text.md`](docs/main-text.md)

## 环境准备

### 1. 安装依赖

```powershell
uv venv .venv --python 3.13
uv sync
uv sync --extra benchmark
cd web
npm install
cd ..
```

### 2. 准备环境变量

```powershell
Copy-Item .env.template .env
Copy-Item .\web\.env.template .\web\.env
```

启动前请检查以下变量：

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `UPLOAD_ROOT`
- `POSTGRES_PORT`，默认 `15432`
- `web/.env` 中的 `VITE_BACKEND_TARGET`
- `web/.env` 中的 `VITE_DEV_HOST`
- `web/.env` 中的 `VITE_DEV_PORT`

### 3. 启动 PostgreSQL 并执行迁移

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

### 4. 构建算法模块

```powershell
$pythonExe = (Resolve-Path .\.venv\Scripts\python.exe).Path
$pybind11CMakeDir = & $pythonExe -m pybind11 --cmakedir
cmake -S algo-module -B algo-module/build -DPython_EXECUTABLE="$pythonExe" -Dpybind11_DIR="$pybind11CMakeDir"
cmake --build algo-module/build
ctest --test-dir algo-module/build --output-on-failure
```

### 5. 启动后端与前端

后端：

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8200 --reload
```

前端：

```powershell
cd web
npm run dev
```

前端开发服务器默认运行在 `http://127.0.0.1:4173`。

## 主要接口

### 鉴权与系统

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/admin/users`
- `PATCH /api/admin/users/{user_id}`
- `POST /api/admin/users/{user_id}/disable`
- `POST /api/admin/users/{user_id}/enable`
- `DELETE /api/admin/users/{user_id}`
- `GET /api/health`

### 导入与交易查询

- `GET /api/imports/runs`
- `GET /api/imports/stats`
- `POST /api/imports/trading`
- `DELETE /api/imports/runs/{run_id}`
- `GET /api/trading/stocks`
- `GET /api/trading/records`

### 交易分析接口

- `GET /api/trading/analysis/summary`
- `GET /api/trading/analysis/quality`
- `GET /api/trading/analysis/indicators`
- `GET /api/trading/analysis/risk`
- `GET /api/trading/analysis/anomalies`
- `GET /api/trading/analysis/cross-section`
- `GET /api/trading/analysis/correlation`
- `GET /api/trading/analysis/compare-scopes`

## 常用脚本

初始化管理员账号：

```powershell
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

从命令行导入本地交易文件：

```powershell
.\.venv\Scripts\python.exe backend/scripts/import_data.py --file-path .\web\public\trading_import_template.csv --dataset-name demo_run
```

执行 live smoke：

```powershell
python backend/scripts/live_smoke.py --base-url http://127.0.0.1:8200 --username benchmark_runner --password benchmark-runner-123 --dataset-name platform_benchmark_dataset --admin-username admin --admin-password admin123456
```

## 验证方式

后端：

```powershell
.\.venv\Scripts\python.exe backend/tests/test_database_pipeline.py
.\.venv\Scripts\python.exe backend/tests/test_admin_users.py
.\.venv\Scripts\python.exe backend/tests/test_algo_trading.py
.\.venv\Scripts\python.exe backend/tests/test_tdigest_range_kth.py
.\.venv\Scripts\python.exe backend/tests/test_trading_analysis.py
.\.venv\Scripts\python.exe backend/tests/test_risk_radar.py
.\.venv\Scripts\python.exe benchmarks/tests/test_common.py
.\.venv\Scripts\python.exe benchmarks/tests/test_platform_quality.py
```

前端：

```powershell
cd web
npm run build
```

## 项目级 Benchmarks

- 官方 benchmark 入口统一为 `benchmarks/run_all.py`
- 查询效率套件：`query_efficiency`
- 第 K 大对比套件：`kth_comparison`
- 平台质量套件：`platform_quality`
- 每个 suite 都会把数值结果写入对应目录的 `results/`，把可视化图写入 `images/`

### 查询效率与第 K 大对比

```powershell
python benchmarks/run_all.py --suite query_efficiency --sample all
python benchmarks/run_all.py --suite kth_comparison --sample all
```

### 平台稳定性与安全性压测

推荐先通过公开注册接口创建普通用户 `benchmark_runner`，再用固定数据集 `data/fixtures/platform_benchmark_trading.csv` 导入平台压测批次。

示例：

```powershell
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8200/api/auth/register" -ContentType "application/json" -Body '{"username":"benchmark_runner","password":"benchmark-runner-123"}'
.\.venv\Scripts\python.exe backend/scripts/import_data.py --file-path .\data\fixtures\platform_benchmark_trading.csv --dataset-name platform_benchmark_dataset --username benchmark_runner
python backend/scripts/live_smoke.py --base-url http://127.0.0.1:8200 --username benchmark_runner --password benchmark-runner-123 --dataset-name platform_benchmark_dataset --admin-username admin --admin-password admin123456

$env:BENCHMARK_BASE_URL = "http://127.0.0.1:8200"
$env:BENCHMARK_USERNAME = "benchmark_runner"
$env:BENCHMARK_PASSWORD = "benchmark-runner-123"
$env:BENCHMARK_IMPORT_RUN_ID = "<导入后的 run id>"
$env:BENCHMARK_SAMPLE = "thesis"
python benchmarks/run_all.py --suite platform_quality --profile thesis
```
