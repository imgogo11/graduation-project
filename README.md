# 股票交易数据管理与分析系统

基于 `FastAPI + Vue 3 + PostgreSQL + C++/pybind11` 的毕业设计项目，围绕一条明确主线展开：

- 用户注册、登录与权限隔离
- 上传 `CSV` / `XLSX` 股票交易数据
- 导入批次、清单、产物与审计信息持久化
- 交易数据分析、异常检测与横截面对比
- 由 C++ 算法模块增强的区间查询、联合异常排序与风险雷达
- 面向管理员的健康检查、用户管理、运行监控与资产概览


## 1. 技术栈

- 前端：Vue 3、TypeScript、Vite、Naive UI、ECharts
- 后端：FastAPI、SQLAlchemy、Alembic、Pandas
- 数据库：PostgreSQL
- 算法模块：C++、CMake、pybind11
- 本地环境：`uv`、Node.js / npm、Docker Compose

## 2. 当前能力

### 用户侧

- 注册、登录、鉴权
- 上传交易文件并生成导入批次
- 查看导入历史、导入统计与交易明细
- 进行指标分析、风险分析、异常检测、相关性分析和范围对比
- 使用算法增强接口查看区间最大值、区间第 K 大、联合异常排序和风险雷达

### 管理员侧

- 系统概览
- 系统健康状态检查
- 普通用户管理：编辑用户名、重置密码、启用/禁用、删除无业务数据用户
- 用户调用记录与审计信息查看
- 数据资产总览
- 运行监控

## 3. 主要页面与路由

### 前端页面

- 用户端：`/workbench`、`/datasets`、`/analysis`、`/algo-radar`
- 管理端：`/admin/overview`、`/admin/health`、`/admin/users`、`/admin/activity`、`/admin/assets`、`/admin/runs`
- 鉴权页：`/login`、`/register`

### 后端接口前缀

- 鉴权：`/api/auth/*`
- 管理员：`/api/admin/*`
- 导入：`/api/imports/*`
- 交易查询：`/api/trading/*`
- 分析：`/api/trading/analysis/*`
- 算法增强：`/api/algo/*`
- 健康检查：`/api/health`

## 4. 目录结构

```text
graduation-project/
├─ backend/               FastAPI、SQLAlchemy、Alembic、测试
├─ web/                   Vue 3 前端
├─ algo-module/           C++ 算法模块与 pybind11 绑定
├─ benchmarks/            benchmark 套件
├─ deploy/                Docker Compose 与部署辅助文件
├─ scripts/dev/           本地开发辅助脚本
├─ data/                  本地数据、导入产物、测试产物
├─ .env.template          根目录运行配置模板
├─ pytest.ini             pytest 项目级配置
└─ pyproject.toml         Python 项目与 uv 依赖配置
```

## 5. 环境要求

- Python `3.13`
- Node.js `20+`
- npm
- `uv`
- Docker Desktop / Docker Compose
- CMake

## 6. 环境变量

根目录只保留一份运行配置：`.env`。

首次准备：

```powershell
Copy-Item .env.template .env
```

当前最关键的变量包括：

- `DATABASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `JWT_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- `BACKEND_HOST`
- `BACKEND_PORT`
- `VITE_DEV_HOST`
- `VITE_DEV_PORT`
- `VITE_BACKEND_TARGET`
- `DEMO_IMPORT_FILE_PATH`
- `DEMO_DATASET_PREFIX`
- `DEMO_IMPORT_USERNAME`

默认本地端口：

- PostgreSQL：`15432`
- FastAPI：`8200`
- Vite：`4173`

## 7. 安装依赖

### Python

```powershell
uv venv .venv --python 3.13
uv sync
```

### 前端

```powershell
npm.cmd --prefix web install
```

### 可选 benchmark 依赖

```powershell
uv sync --extra benchmark
```

## 8. 首次初始化

如果你希望按步骤手动完成初始化，可依次执行：

```powershell
Copy-Item .env.template .env
uv sync
npm.cmd --prefix web install
cmake -S algo-module -B algo-module/build "-DPython_EXECUTABLE=$(Resolve-Path .\.venv\Scripts\python.exe)" "-Dpybind11_DIR=$(uv run python -m pybind11 --cmakedir)"
cmake --build algo-module/build
docker compose -f deploy/docker-compose.yml up -d postgres
uv run python -m alembic -c backend/alembic.ini upgrade head
uv run python backend/scripts/init_admin.py
uv run python backend/scripts/import_data.py
```

如果你更喜欢看整理后的命令清单，也可以参考：

- [run-scripts-full-setup.txt](D:\graduation-project\run-scripts-full-setup.txt)
- [run-scripts-demo-start.txt](D:\graduation-project\run-scripts-demo-start.txt)

## 9. 日常启动

### 终端 1：启动数据库

```powershell
docker compose -f deploy/docker-compose.yml up -d postgres
```

### 终端 1：启动后端

```powershell
uv run uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8200 --reload
```

### 终端 2：启动前端

```powershell
cd web
npm run dev
```

访问地址：

- 前端：`http://127.0.0.1:4173`
- 后端 OpenAPI：`http://127.0.0.1:8200/docs`

## 10. 数据导入说明

默认示例文件位于：

```text
web/public/trading_import_template.csv
```

支持字段：

```text
stock_code,stock_name,trade_date,open,high,low,close,volume,amount
```

说明：

- 支持 `.csv` 与 `.xlsx`
- 必填列：`stock_code`、`trade_date`、`open`、`high`、`low`、`close`、`volume`
- 可选列：`stock_name`、`amount`、`turnover`
- 当前仅处理股票交易数据
- 上传链路使用规范英文列名，不再兼容历史别名和中文列头

## 11. 常用命令

### 初始化管理员

```powershell
uv run python backend/scripts/init_admin.py
```

### 导入本地交易文件

```powershell
uv run python backend/scripts/import_data.py --file-path .\web\public\trading_import_template.csv --dataset-name demo_run
```

如果 `.env` 已配置 `DEMO_IMPORT_FILE_PATH`、`DEMO_DATASET_PREFIX`、`DEMO_IMPORT_USERNAME`，也可以直接执行：

```powershell
uv run python backend/scripts/import_data.py
```

### 环境检查

```powershell
uv run python backend/scripts/check_environment.py
```

## 12. 测试与验证

### 后端测试

```powershell
.\.venv\Scripts\python.exe -m pytest
```

### 前端构建验证

```powershell
cd web
npm run build
```

## 13. Benchmark

统一入口：

```powershell
python benchmarks/run_all.py --suite <suite-name>
```

当前套件：

- `query_efficiency`
- `kth_comparison`
- `platform_quality`

示例：

```powershell
python benchmarks/run_all.py --suite query_efficiency --sample all
python benchmarks/run_all.py --suite kth_comparison --sample all
python benchmarks/run_all.py --suite platform_quality --profile thesis
```
