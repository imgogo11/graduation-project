# 项目进度

更新时间：2026-04-09

## 说明

本文件按仓库当前真实状态整理，不再沿用 `tasks.md` 里的理想目录树。
这里记录的是“项目现在实际上有什么、做到哪一步了”，因此会把已存在但尚未提交的目录也纳入“实时框架”。

以下内容默认不计入“正式源码框架”，但会在需要时单独说明：

- `.git/`
- `.venv/`
- `.uv-cache/`
- 各目录下的 `__pycache__/`、`.pyc`
- `backend/.tmp-tests/`
- `algo-engine/build/`
- 根目录 `build/`
- 测试和构建过程中自动生成的临时产物

## 当前总体判断

当前项目已经不再是“仅有数据导入雏形”的阶段，而是进入了：

`数据库优先后端 MVP + C++ 算法引擎最小可用联动`

更具体地说：

- 后端主链路已经具备：`FastAPI + SQLAlchemy + Alembic + 数据导入 + 查询接口`
- 股票算法链路已经打通：`数据库时序 -> Python bridge -> C++ 线段树 -> FastAPI 路由`
- `algo-engine/` 已不只是目录骨架，而是已有可编译、可测试的最小实现
- 前端、完整部署、完整文档体系、benchmark 业务化接口仍明显未完成

## 本次实际核验结果

本次已重新核验当前项目状态：

- `uv run python backend/scripts/check_environment.py` 可运行
- 环境检查显示核心依赖已可用：`fastapi`、`sqlalchemy`、`pandas`、`akshare`、`pybind11`、`alembic`、`psycopg`、`uvicorn`
- 可选依赖 `tushare`、`scrapy` 仍未安装
- `uv run python -m unittest discover backend/tests -v` 通过 5 个后端测试
- `cmake -S algo-engine -B algo-engine/build` 配置成功
- `cmake --build algo-engine/build` 构建成功
- `ctest --test-dir algo-engine/build --output-on-failure` 通过 2 个算法引擎测试

当前已验证通过的测试范围：

- `backend/tests/test_contracts.py`
- `backend/tests/test_ecommerce_synthetic.py`
- `backend/tests/test_database_pipeline.py`
- `backend/tests/test_algo_stocks.py`
- `algo-engine/tests/unit/test_range_max_segment_tree.cpp`
- `algo-engine/tests/integration/test_python_binding.py`

## 当前实时框架

```text
graduation-project/
├─ .vscode/                                          本地 IDE 配置目录；当前只包含 CMake 工作区设置，不属于正式业务代码
│  └─ settings.json                                  指向 `algo-engine/` 的 CMake sourceDirectory；已存在
├─ frontend/                                         前端目录；当前仍为空，尚未开始
├─ backend/                                          后端主工程；已形成“数据准备 + 数据导入 + 查询接口 + 算法查询接口”主链路
│  ├─ app/                                           后端应用主包；已形成分层结构
│  │  ├─ __init__.py                                 包初始化；已完成
│  │  ├─ main.py                                     FastAPI 入口；已可启动最小后端
│  │  ├─ api/                                        API 层；正式业务路由已可用，benchmark 路由仍为占位
│  │  │  ├─ __init__.py                              包初始化；已完成
│  │  │  ├─ router.py                                总路由注册；当前已挂载 health/imports/stocks/commerce/algo-stocks
│  │  │  └─ routes/
│  │  │     ├─ __init__.py                           routes 包初始化；已完成
│  │  │     ├─ health.py                             健康检查接口；已完成
│  │  │     ├─ imports.py                            数据导入接口；已支持 stock / olist / synthetic manifest 导入
│  │  │     ├─ stocks.py                             股票只读查询接口；已完成
│  │  │     ├─ commerce.py                           电商只读查询接口；已完成
│  │  │     ├─ algo/
│  │  │     │  ├─ __init__.py                        算法接口子包；已存在
│  │  │     │  ├─ stocks.py                          股票算法接口；`/algo/stocks/range-max-amount` 已实现并挂到总路由
│  │  │     │  └─ commerce.py                        电商算法接口；当前仅空路由占位
│  │  │     └─ benchmark/
│  │  │        ├─ __init__.py                        benchmark 子包；已存在
│  │  │        ├─ stocks.py                          股票 benchmark 路由；当前仅空路由占位，未接入总路由
│  │  │        └─ commerce.py                        电商 benchmark 路由；当前仅空路由占位，未接入总路由
│  │  ├─ core/                                       基础设施层；配置和数据库能力已完成
│  │  │  ├─ __init__.py                              包初始化；已完成
│  │  │  ├─ config.py                                Settings 配置；已接入 `.env` 与环境变量
│  │  │  └─ database.py                              SQLAlchemy engine/session/建表工具；已完成
│  │  ├─ data_sources/                               数据源逻辑层；当前最成熟的部分之一
│  │  │  ├─ __init__.py                              公共导出；已完成
│  │  │  ├─ contracts.py                             manifest / artifact 契约定义；已完成并有测试
│  │  │  ├─ stock.py                                 AkShare 股票抓取与标准化；已完成
│  │  │  ├─ olist.py                                 Olist 校验与 manifest 输出；已完成
│  │  │  ├─ ecommerce_synthetic.py                   合成电商数据生成与落盘；已完成
│  │  │  └─ demo_crawler.py                          演示爬虫数据处理；已完成
│  │  ├─ engine_bridge/                              Python 与 C++ 算法引擎桥接层；已从空目录推进到“可调用”
│  │  │  ├─ __init__.py                              bridge 包初始化；已存在
│  │  │  ├─ loaders/
│  │  │  │  ├─ __init__.py                           loaders 子包；已存在
│  │  │  │  └─ stocks.py                             股票成交额序列装载/缩放/反缩放；已实现
│  │  │  └─ adapters/
│  │  │     ├─ __init__.py                           adapters 子包；已存在
│  │  │     └─ stocks.py                             动态加载 `algo_engine_py` 并执行区间最大值查询；已实现
│  │  ├─ models/                                     ORM 模型层；核心实体已完成
│  │  │  ├─ __init__.py                              模型统一导出；已完成
│  │  │  ├─ base.py                                  Declarative Base 与时间工具；已完成
│  │  │  └─ entities.py                              导入记录、股票、电商核心表；已完成
│  │  ├─ repositories/                               仓储层；已覆盖 imports/stocks/commerce
│  │  │  ├─ __init__.py                              包初始化；已完成
│  │  │  ├─ imports.py                               导入记录仓储；已完成
│  │  │  ├─ stocks.py                                股票仓储；已支持列表查询与算法用成交额时序读取
│  │  │  └─ commerce.py                              电商查询仓储；已完成
│  │  ├─ schemas/                                    Pydantic schema 层；已从基础 API schema 扩展到算法返回结构
│  │  │  ├─ __init__.py                              包初始化；已完成
│  │  │  ├─ api.py                                   health/import/stock/commerce schema；已完成
│  │  │  └─ algo.py                                  股票算法查询返回 schema；已实现
│  │  └─ services/                                   服务层；导入服务和算法服务都已落地
│  │     ├─ __init__.py                              包初始化；已完成
│  │     ├─ imports.py                               manifest 驱动的数据导入服务；已完成
│  │     └─ algo_stocks.py                           股票算法服务；已实现参数校验、日期切片和桥接调用
│  ├─ scripts/                                       命令行脚本层；数据准备工具链已成形
│  │  ├─ _bootstrap.py                               backend 导入路径引导；已完成
│  │  ├─ check_environment.py                        环境检查脚本；已完成并可运行
│  │  ├─ crawl_demo_ecommerce.py                     演示爬虫入口；已完成
│  │  ├─ export_requirements.py                      requirements 导出脚本；已完成
│  │  ├─ fetch_stock_akshare.py                      股票抓取入口；已完成
│  │  ├─ generate_ecommerce_synthetic.py             合成电商数据生成入口；已完成
│  │  ├─ import_data.py                              数据导入入口；已完成
│  │  └─ inspect_olist_dataset.py                    Olist 校验入口；已完成
│  ├─ tests/                                         后端测试目录；当前已覆盖契约、合成数据、数据库主链路、算法查询链路
│  │  ├─ test_contracts.py                           manifest 契约测试；已通过
│  │  ├─ test_ecommerce_synthetic.py                 合成数据测试；已通过
│  │  ├─ test_database_pipeline.py                   SQLite 数据导入/查询主链路测试；已通过
│  │  └─ test_algo_stocks.py                         股票算法接口与桥接链路测试；已通过
│  ├─ alembic/                                       数据库迁移目录；最小迁移能力已具备
│  │  ├─ env.py                                      Alembic 环境入口；已完成
│  │  ├─ script.py.mako                              Alembic 模板；已存在
│  │  └─ versions/
│  │     └─ 20260407_01_initial_schema.py            初始 schema 迁移；已完成
│  ├─ alembic.ini                                    Alembic 配置文件；已完成
│  ├─ requirements.txt                               核心依赖兼容导出文件；已可用
│  └─ requirements-optional.txt                      可选依赖导出文件；已可用
├─ algo-engine/                                      C++ 算法引擎目录；已从“空骨架”进入“最小可编译、可测试、可绑定”
│  ├─ README.md                                      说明文件；已存在，但内容仍偏“初始规划”，尚未完全同步当前实现
│  ├─ CMakeLists.txt                                 CMake 工程入口；已配置核心库、Python 绑定和测试
│  ├─ cmake/                                         预留 CMake 扩展目录；当前主要为占位
│  ├─ include/
│  │  └─ algo_engine/
│  │     └─ segment_tree/
│  │        └─ range_max_segment_tree.hpp            区间最大值线段树头文件；已实现
│  ├─ src/
│  │  └─ segment_tree/
│  │     └─ range_max_segment_tree.cpp               区间最大值线段树实现；已完成最小可用版本
│  ├─ bindings/
│  │  └─ python/
│  │     └─ module.cpp                               pybind11 绑定入口；已暴露 `RangeMaxSegmentTree`
│  ├─ tests/
│  │  ├─ unit/
│  │  │  └─ test_range_max_segment_tree.cpp          C++ 单元测试；已实现并通过
│  │  └─ integration/
│  │     └─ test_python_binding.py                   Python 绑定 smoke test；已实现并通过
│  ├─ benchmarks/
│  │  ├─ range_query/                                区间查询 benchmark 目录；当前仅 `.gitkeep`
│  │  └─ version_query/                              版本查询 benchmark 目录；当前仅 `.gitkeep`
│  └─ build/                                         本地构建产物目录；当前可生成 `.pyd` 与测试可执行文件，不计入正式源码框架
├─ data/                                             数据目录；已包含真实原始数据、合成数据和测试产物
│  ├─ raw/
│  │  ├─ stocks/
│  │  │  └─ akshare/                                 AkShare 股票快照目录；已有多只股票 CSV 与 manifest
│  │  └─ ecommerce/
│  │     ├─ olist/                                   Olist 原始数据目录；已有 CSV 与 dataset manifest
│  │     └─ webscraper_demo/                         演示爬虫结果目录；已有 `products.csv` 与 manifest
│  └─ processed/
│     ├─ ecommerce/
│     │  └─ synthetic/                               合成电商正式输出目录；已有多表 CSV 与 manifest
│     └─ test_artifacts/                             测试产物目录；已有 contracts/synthetic/database/algo_stocks 等产物
├─ deploy/                                           部署目录；当前只有最小 PostgreSQL 配置
│  ├─ docker-compose.yml                             Compose 配置；当前只覆盖 postgres
│  └─ env/
│     └─ postgres.env.template                       Postgres 环境变量模板；已完成
├─ docs/                                             文档目录；目前以环境与数据源文档为主
│  ├─ environment-baseline.md                        环境基线文档；已完成
│  ├─ python-environment.md                          Python 环境文档；已完成
│  └─ data-source-strategy.md                        数据源策略文档；已完成
├─ pre-tasks/                                        前期规划与草稿目录；保存早期任务拆解文档
├─ build/                                            根目录 CMake/CTest 生成目录；属于本地构建产物，不计入正式源码框架
├─ .env                                              本地运行配置；已存在，属于本地环境文件
├─ .env.template                                     运行时配置模板；已覆盖数据库/API/数据目录配置
├─ .gitignore                                        Git 忽略规则；已覆盖 Python、构建和测试产物
├─ .python-version                                   Python 版本入口；当前为 3.13
├─ pyproject.toml                                    Python 项目主入口；当前依赖管理标准入口
├─ uv.lock                                           uv 锁文件；已生成
├─ README.md                                         项目总览与启动说明；已覆盖数据库优先工作流
├─ require.md                                        Windows 环境安装说明；已存在
├─ tasks.md                                          项目蓝图文档；仍是目标设计，不等于当前实装结构
├─ ToDoList                                          简短待办记录；内容较早，未完全同步当前进度
├─ version-description.txt                           本机工具与版本记录；已存在
├─ 数据库 + 算法模块协同工作说明.md                  数据库与算法模块协同说明；已存在
└─ progress.md                                       当前进度文档；本次已按实时框架重写
```

## 完成度分层总结

### 已完成或已打通

- Python 环境、依赖管理、`.env` 配置模板
- 数据源契约、股票抓取、Olist 校验、合成电商数据生成、演示爬虫数据处理
- FastAPI + SQLAlchemy + Alembic 的最小后端工程
- 股票/电商查询接口
- manifest 驱动的数据导入服务
- 股票算法最小链路：数据库 -> Python bridge -> C++ -> API
- C++ 线段树最小实现、pybind11 绑定、单元测试、Python smoke test

### 部分完成

- `backend/app/api/routes/benchmark/` 已建目录，但仍是空路由占位
- `backend/app/api/routes/algo/commerce.py` 仍是空路由占位
- `algo-engine/benchmarks/` 只有目录骨架，还没有 benchmark 实现
- `deploy/` 目前只有 PostgreSQL Compose，未形成完整多服务部署方案
- `docs/` 只有环境和数据相关文档，缺少设计文档、API 文档、实验报告、论文提纲
- `algo-engine/README.md` 仍停留在“初始 scope”描述，尚未完全反映当前已实现内容

### 尚未开始或基本未开始

- `frontend/` 前端工程
- 电商算法实现与对应桥接
- benchmark 业务接口与性能对比输出
- Redis、任务调度、鉴权、用户体系
- 报表导出、实验平台、完整 Nginx/容器编排

## 一句话结论

当前项目的真实状态已经是：

`后端数据库主链路已可运行，股票算法最小链路已打通，algo-engine 已具备真实实现与测试；前端、完整部署和更大范围算法能力仍在后续阶段。`
