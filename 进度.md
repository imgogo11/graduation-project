# 项目进度

更新时间：2026-04-07

## 说明


以下内容默认不计入“正式项目框架”：
- `.git/`
- `.venv/`
- `.uv-cache/`
- 各目录下的 `__pycache__/`、`.pyc`
- `backend/.tmp-tests/` 以及测试运行产生的临时目录

## 当前总体判断

当前项目已经从“只有数据脚本”推进到“数据库优先的后端 MVP”阶段，真实完成度明显高于之前版本的 `进度.md`。

当前已落地的主线：
- Python 环境管理已统一到根目录 `pyproject.toml + .venv + uv`。
- 数据采集 / 校验 / 生成链路已完成，包含股票、Olist、电商合成数据、演示爬虫和统一 manifest 契约。
- 后端已完成最小 FastAPI 应用、SQLAlchemy ORM、仓储层、导入服务层、只读查询接口。
- Alembic 初始迁移、PostgreSQL 最小 Docker Compose 配置已落地。
- `data/raw/` 与 `data/processed/` 中已经有真实数据与测试产物，不再只是空目录。
- 后端测试已覆盖 manifest 契约、合成数据、数据库主链路。

当前仍未完成的主线：
- `frontend/` 仍为空，前端尚未开始。
- `algo-engine/` 仍为空，C++ 算法引擎 / PyBind11 绑定尚未开始。
- 鉴权、用户系统、Redis、任务调度、报表导出、性能实验平台都还未落地。
- `deploy/` 目前只有最小 PostgreSQL 配置，Nginx、完整多服务编排尚未实现。
- `docs/` 目前以环境与数据源文档为主，设计文档、API 文档、实验报告、论文提纲还未补全。

## 当前已验证状态

本次已实际验证：
- `uv run python backend/scripts/check_environment.py` 可运行。
- 核心命令与核心 Python 包可用：`fastapi`、`sqlalchemy`、`pandas`、`akshare`、`pybind11`、`alembic`、`psycopg`、`uvicorn` 等均正常。
- 可选包 `tushare`、`scrapy` 仍未安装。
- `uv run python -m unittest discover backend/tests -v` 已通过 5 个测试。

测试通过范围：
- `test_contracts.py`
- `test_ecommerce_synthetic.py`
- `test_database_pipeline.py`

说明：
- 当前数据库主链路已通过 SQLite 集成测试验证。
- PostgreSQL 容器编排与 Alembic 已经存在，但本次没有额外执行一次真实 PostgreSQL 容器联调。

## 当前真实项目框架

```text
graduation-project/
├─ frontend/                                      前端目录占位；当前为空，未开始。
├─ backend/                                       后端主工程；已形成“数据接入 + 数据库存储 + 最小 API”主链路。
│  ├─ app/                                        应用主包；当前已具备 api/core/models/repositories/schemas/services/data_sources。
│  │  ├─ __init__.py                              包初始化文件；已完成。
│  │  ├─ main.py                                  FastAPI 入口；已可挂载最小 API。
│  │  ├─ api/                                     接口层；已完成统一路由和 4 组接口。
│  │  │  ├─ __init__.py                           API 包初始化；已完成。
│  │  │  ├─ router.py                             总路由注册；已完成。
│  │  │  └─ routes/                               具体接口目录；已落地健康检查、导入、股票、电商接口。
│  │  │     ├─ __init__.py                        routes 包初始化；已完成。
│  │  │     ├─ health.py                          健康检查接口；已完成。
│  │  │     ├─ imports.py                         导入接口；已支持 stock / olist / synthetic 三类导入。
│  │  │     ├─ stocks.py                          股票只读查询接口；已完成基础查询。
│  │  │     └─ commerce.py                        电商订单 / 商品只读查询接口；已完成基础查询。
│  │  ├─ core/                                    基础设施层；已完成配置与数据库连接管理。
│  │  │  ├─ __init__.py                           core 包初始化；已完成。
│  │  │  ├─ config.py                             Settings 配置模块；已接入 `.env` / 环境变量。
│  │  │  └─ database.py                           SQLAlchemy Engine / Session / 建表工具；已完成。
│  │  ├─ data_sources/                            数据源核心逻辑；已完成，是当前最成熟模块之一。
│  │  │  ├─ __init__.py                           数据源公共导出；已完成。
│  │  │  ├─ contracts.py                          manifest / artifact 契约定义；已完成。
│  │  │  ├─ stock.py                              AkShare 股票抓取与标准化；已完成。
│  │  │  ├─ olist.py                              Olist 数据集校验与 manifest 输出；已完成。
│  │  │  ├─ ecommerce_synthetic.py                合成电商数据生成与落盘；已完成。
│  │  │  └─ demo_crawler.py                       演示电商站爬虫；已完成。
│  │  ├─ models/                                  ORM 模型层；已完成数据库核心表定义。
│  │  │  ├─ __init__.py                           模型统一导出；已完成。
│  │  │  ├─ base.py                               Declarative Base 与 UTC 工具；已完成。
│  │  │  └─ entities.py                           导入记录、股票、电商业务表实体；已完成。
│  │  ├─ repositories/                            仓储层；已完成 imports / stocks / commerce 基础仓储。
│  │  │  ├─ __init__.py                           仓储包初始化；已完成。
│  │  │  ├─ imports.py                            导入记录仓储；已完成。
│  │  │  ├─ stocks.py                             股票仓储；已完成。
│  │  │  └─ commerce.py                           电商查询仓储；已完成。
│  │  ├─ schemas/                                 Pydantic 模型层；已完成基础请求 / 响应模型。
│  │  │  ├─ __init__.py                           schema 包初始化；已完成。
│  │  │  └─ api.py                                Health / Import / Stock / Commerce 响应模型；已完成。
│  │  └─ services/                                服务层；已完成导入服务主逻辑。
│  │     ├─ __init__.py                           服务包初始化；已完成。
│  │     └─ imports.py                            manifest 驱动的数据导入服务；已完成。
│  ├─ scripts/                                    命令行脚本层；已形成完整的数据准备与导入工具链。
│  │  ├─ _bootstrap.py                            脚本导入路径引导；已完成。
│  │  ├─ check_environment.py                     环境检查脚本；已完成。
│  │  ├─ crawl_demo_ecommerce.py                  演示爬虫运行入口；已完成。
│  │  ├─ export_requirements.py                   requirements 导出脚本；已完成。
│  │  ├─ fetch_stock_akshare.py                   股票抓取脚本入口；已完成。
│  │  ├─ generate_ecommerce_synthetic.py          合成电商数据生成入口；已完成。
│  │  ├─ import_data.py                           数据库导入脚本入口；已完成。
│  │  └─ inspect_olist_dataset.py                 Olist 校验脚本入口；已完成。
│  ├─ tests/                                      测试目录；已覆盖契约、合成数据、数据库主链路。
│  │  ├─ test_contracts.py                        manifest 契约测试；已通过。
│  │  ├─ test_ecommerce_synthetic.py              合成数据测试；已通过。
│  │  └─ test_database_pipeline.py                SQLite 下数据库主链路集成测试；已通过。
│  ├─ alembic/                                    数据库迁移目录；已具备最小迁移能力。
│  │  ├─ env.py                                   Alembic 环境入口；已完成。
│  │  ├─ script.py.mako                           Alembic 模板文件；已存在。
│  │  └─ versions/
│  │     └─ 20260407_01_initial_schema.py         初始 schema 迁移；已完成。
│  ├─ alembic.ini                                 Alembic 配置文件；已完成。
│  ├─ requirements.txt                            核心依赖兼容导出文件；已可用。
│  └─ requirements-optional.txt                   可选依赖兼容导出文件；已可用。
├─ algo-engine/                                   C++ 算法引擎目录；当前为空，占位未开始。
├─ data/                                          数据目录；已具备真实 raw / processed 数据。
│  ├─ raw/                                        原始数据目录；已不再是空目录。
│  │  ├─ stocks/
│  │  │  └─ akshare/                              AkShare 股票快照目录；已有 000001 / 600519 / 300750 的 CSV 和 manifest。
│  │  └─ ecommerce/
│  │     ├─ olist/                                Olist 原始数据集目录；已有 CSV 文件和 dataset manifest。
│  │     └─ webscraper_demo/                      演示爬虫输出目录；已有 `products.csv` 和 manifest。
│  └─ processed/                                  处理后数据目录；已具备正式生成数据和测试产物。
│     ├─ ecommerce/
│     │  └─ synthetic/                            合成电商数据正式输出目录；已有 9 张表 CSV 和 manifest。
│     └─ test_artifacts/                          测试产物目录；已有 contracts / synthetic / database_pipeline / debug_case 等验证产物。
├─ deploy/                                        部署目录；当前只完成最小 PostgreSQL 编排。
│  ├─ docker-compose.yml                          Docker Compose 配置；当前只启动 postgres。
│  └─ env/
│     └─ postgres.env.template                    Postgres 环境变量模板；已完成。
├─ docs/                                          文档目录；当前以环境与数据源文档为主。
│  ├─ environment-baseline.md                     环境基线说明；已完成。
│  ├─ python-environment.md                       Python 环境管理说明；已完成。
│  └─ data-source-strategy.md                     数据源策略说明；已完成。
├─ pre-tasks/                                     前期方案草稿目录；保存多版本任务规划文档。
│  ├─ tasks-gemini3.1-high.md                     规划草稿；已存在。
│  ├─ tasks-geminipro-web.md                      规划草稿；已存在。
│  ├─ tasks-gpt-web.md                            规划草稿；已存在。
│  ├─ tasks-gpt5.3-codex.md                       规划草稿；已存在。
│  ├─ tasks-opus4.6.md                            规划草稿；已存在。
│  └─ tasks-sonnet4.6-perplexity.md               规划草稿；已存在。
├─ .env.template                                  运行时配置模板；已扩展到数据库 / API / 数据目录配置。
├─ .gitignore                                     Git 忽略规则；已存在。
├─ .python-version                                Python 版本入口；当前为 3.13。
├─ pyproject.toml                                 Python 依赖主入口；已成为当前工程标准入口。
├─ uv.lock                                        uv 锁文件；已生成。
├─ README.md                                      项目总览与启动说明；已更新到数据库优先后端工作流。
├─ require.md                                     Windows 环境安装说明；已完成文档。
├─ tasks.md                                       项目总体规划文档；当前仍作为目标蓝图。
├─ ToDoList                                       简短待办记录；内容较早，尚未同步到当前进展。
├─ version-description.txt                        本机工具与版本检查记录；已存在。
├─ 数据库 + 算法模块协同工作说明.md              架构说明文档；描述数据库与算法模块协同思路，偏方案层。
└─ 进度.md                                        当前进度文档；本次已按真实框架更新。
```

## 当前完成情况总结

### 1. 已完成

- Python 环境方案已经稳定，`pyproject.toml`、`.env.template`、`uv.lock`、兼容 `requirements` 均已落地。
- 数据准备链路已经完成：
  - AkShare 股票抓取
  - Olist 数据集校验
  - 合成电商数据生成
  - 演示电商爬虫
  - manifest 契约统一
- 数据库层已经完成第一阶段：
  - SQLAlchemy Engine / Session 管理
  - ORM 实体定义
  - Alembic 初始迁移
  - 导入记录表与业务表结构
- 后端接口层已经完成第一阶段：
  - `GET /api/health`
  - `GET /api/imports/runs`
  - `POST /api/imports/stocks/akshare`
  - `POST /api/imports/ecommerce/olist`
  - `POST /api/imports/ecommerce/synthetic`
  - `GET /api/stocks/daily-prices`
  - `GET /api/commerce/orders`
  - `GET /api/commerce/products`
- 数据目录已经有真实内容：
  - 原始股票数据
  - Olist 原始数据
  - 演示爬虫结果
  - 合成电商正式输出
  - 多类测试产物

### 2. 部分完成

- `deploy/` 已有最小 PostgreSQL Compose，但还不是完整部署方案。
- `docs/` 已有环境与数据源文档，但系统设计、API 文档、实验报告、论文提纲还没补齐。
- 后端当前已经形成 MVP，但仍偏“导入 + 查询 + 验证”阶段，尚未进入完整业务系统阶段。

### 3. 尚未开始或基本未开始

- `frontend/` 前端工程
- `algo-engine/` C++ 算法引擎
- PyBind11 真正的算法绑定集成
- 用户、鉴权、角色权限
- Redis、任务调度、异步任务
- 报表导出、实验平台、性能对比模块
- 完整容器化编排与 Nginx

## 一句话结论

当前项目的真实状态已经是“数据库优先的后端 MVP 已基本搭好，数据采集 / 导入 / 查询 / 迁移 / 测试链路已经成立”，而不是之前 `进度.md` 里写的“只有数据脚本、后端分层尚未开始”。
