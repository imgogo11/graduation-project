# 融合 C++ 算法引擎的交易数据管理与分析系统设计与实现（C++-Powered Trading Data Analytics System）

## 项目简介

本项目当前聚焦一条明确主线：

- 用户注册与登录
- 用户上传 `CSV` / `XLSX` 历史交易数据
- 导入批次、清单与产物记录持久化
- 基于用户权限隔离的数据查询与管理
- 面向股票数据的一体化交易分析
- 基于 C++ 算法引擎的区间分析能力

早期的股票爬虫、电商演示数据、synthetic 数据与 benchmark 演示链路，已经退出当前主业务主线。

## 技术栈

- 前端：Vue 3 + TypeScript + Element Plus + ECharts
- 后端：FastAPI + SQLAlchemy + Alembic + Pandas
- 数据库：PostgreSQL
- 算法引擎：C++ + PyBind11

## 当前核心数据模型

- `users`
- `import_runs`
- `import_manifests`
- `import_artifacts`
- `trading_records`

## 支持的上传模板

```text
instrument_code,instrument_name,trade_date,open,high,low,close,volume,amount
```

- 支持文件格式：`.csv`、`.xlsx`
- 当前系统仅处理股票交易数据，上传模板标准列头为 `instrument_code`、`trade_date`、`open`、`high`、`low`、`close`、`volume`，可选列为 `instrument_name`、`amount`
- 数据集名称在“同一用户 + 未删除上传批次”范围内必须唯一；删除后名称可再次使用

## 当前主要能力

### 数据管理

- 用户注册、登录、鉴权
- 按用户隔离的导入批次管理
- 导入历史、导入统计、软删除
- 原始交易记录查询

### 数据分析

- 标的级交易摘要
- 数据质量分析
- 技术指标分析：MA / EMA / MACD / RSI / Bollinger / ATR
- 风险指标分析：区间收益率、波动率、最大回撤、上涨日占比等
- 异常检测：放量异常、收益率异常、振幅异常、突破前高/前低
- 横截面分析：多标的排序
- 相关性分析：当前批次内多标的收益率相关性矩阵
- 范围对比分析：支持同批次/跨批次、同标的/多标的、不同日期范围的一致性校验

### C++ 算法能力

- `GET /api/algo/trading/range-max-amount`
- `GET /api/algo/trading/range-kth-volume`
- `range-kth-volume` 同时支持精确解 `persistent_segment_tree` 与近似解 `t_digest`
- `t_digest` 在本项目中用于近似分位 / 近似第 K 大查询，不宣称任意区间严格 `O(1)` 或精确排名
- 当前已打通链路：数据库 -> Python bridge / Python t-digest -> FastAPI -> 前端

## 环境准备

### 1. 安装依赖

```powershell
uv venv .venv --python 3.13
uv sync
cd frontend
npm install
cd ..
```

### 2. 准备环境变量

```powershell
Copy-Item .env.template .env
Copy-Item .\frontend\.env.template .\frontend\.env
```

启动前请检查以下变量：

- `DATABASE_URL`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `UPLOAD_ROOT`
- `POSTGRES_PORT`（默认 `15432`）
- `frontend/.env` 中的 `VITE_BACKEND_TARGET`
- `frontend/.env` 中的 `VITE_DEV_HOST`
- `frontend/.env` 中的 `VITE_DEV_PORT`

### 3. 启动 PostgreSQL 并执行迁移

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

当前最新迁移已经清理旧业务表与历史遗留导入路径，系统只保留当前上传式交易数据主链路。
项目默认把 PostgreSQL 宿主端口设置为 `15432`，而不是常见的 `5432`，这是为了避开部分 Windows 环境对 `5432` 所在端口段的系统保留限制。

### 4. 启动后端与前端

后端：

```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --app-dir backend --host 127.0.0.1 --port 8200 --reload
```

前端：

```powershell
cd frontend
npm run dev
```

前端开发服务器默认运行在 `http://127.0.0.1:4173`。这里刻意避开了 `5173`，因为部分 Windows 环境会对该端口段做系统保留；如需局域网访问，可在 `frontend/.env` 中将 `VITE_DEV_HOST` 改为 `0.0.0.0`。

## 主要接口

### 鉴权与系统

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `GET /api/health`

### 导入与交易查询

- `GET /api/imports/runs`
- `GET /api/imports/stats`
- `POST /api/imports/trading`
- `DELETE /api/imports/runs/{run_id}`
- `GET /api/trading/instruments`
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
- `GET /api/trading/analysis/compare-runs`

### C++ 算法接口

- `GET /api/algo/trading/range-max-amount`
- `GET /api/algo/trading/range-kth-volume`

其中 `GET /api/algo/trading/range-kth-volume` 支持查询参数：

- `import_run_id`
- `instrument_code`
- `start_date`
- `end_date`
- `k`
- `method`

`method` 目前固定为：

- `persistent_segment_tree`：精确结果，返回命中的交易日期
- `t_digest`：近似结果，返回 `is_approx=true`、`approximation_note`，且不返回精确命中日期

## 常用脚本

初始化管理员账号：

```powershell
.\.venv\Scripts\python.exe backend/scripts/init_admin.py
```

从命令行导入本地交易文件：

```powershell
.\.venv\Scripts\python.exe backend/scripts/import_data.py --file-path .\frontend\public\trading_import_template.csv --dataset-name demo_run
```

导出兼容依赖：

```powershell
.\.venv\Scripts\python.exe backend/scripts/export_requirements.py
```

## 验证方式

后端：

```powershell
.\.venv\Scripts\python.exe backend/tests/test_database_pipeline.py
.\.venv\Scripts\python.exe backend/tests/test_algo_trading.py
.\.venv\Scripts\python.exe backend/tests/test_trading_analysis.py
```

前端：

```powershell
cd frontend
npm run build
```
