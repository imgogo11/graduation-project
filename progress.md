# 项目进度

更新时间：2026-04-09

## 当前项目定位

当前仓库的主线已经不是早期的“股票抓取 + 电商演示 + benchmark 预留”组合方案，而是一个已经落地到可联调状态的：

`融合 C++ 算法引擎的交易数据管理与分析系统设计与实现（C++-Powered Trading Data Analytics System）`

当前真实业务链路为：

`用户注册/登录 -> 上传 CSV/XLSX 交易文件 -> 生成导入批次与产物记录 -> 查询交易数据 -> 调用 C++ 算法接口做区间最大成交额分析`

已经退出主链、只剩历史痕迹或文档痕迹的旧方向包括：

- 股票爬虫导入主链
- 电商演示数据导入主链
- synthetic 电商数据主链
- benchmark 业务接口主链

## 实时技术框架

### 前端

- Vue 3
- Vite 5
- TypeScript
- Vue Router 4
- Element Plus
- ECharts

### 后端

- FastAPI
- SQLAlchemy 2
- Pydantic 2
- Alembic
- Pandas
- Uvicorn

### 数据与运行环境

- PostgreSQL：主数据库
- SQLite：测试场景使用
- `uv`：Python 依赖与虚拟环境工作流
- `.venv`：本地 Python 运行环境
- `npm`：前端依赖与构建

### 鉴权与安全

- 自定义 Bearer Token / JWT 方案
- `PBKDF2-SHA256` 密码哈希
- 基于 `user / admin` 的最小权限区分

### 算法引擎

- C++23
- pybind11
- CMake
- CTest

## 当前实时项目骨架

```text
graduation-project/
├─ frontend/                         Vue 前端工程，已完成基础页面与联调
│  ├─ src/
│  │  ├─ api/                        前端 API 封装（auth / imports / health / trading）
│  │  ├─ components/                 AppShell、统计卡片、图表面板等组件
│  │  ├─ pages/                      Login / Register / Overview / Trading 页面
│  │  ├─ router/                     前端路由与登录守卫
│  │  ├─ stores/                     auth / runtime 状态管理
│  │  ├─ App.vue
│  │  └─ main.ts
│  ├─ public/
│  │  └─ trading_import_template.csv 上传模板
│  ├─ package.json
│  └─ vite.config.ts
├─ backend/                          FastAPI 后端主工程
│  ├─ app/
│  │  ├─ api/
│  │  │  ├─ deps.py                  当前用户与管理员依赖
│  │  │  ├─ router.py                总路由注册
│  │  │  └─ routes/
│  │  │     ├─ health.py             健康检查
│  │  │     ├─ auth.py               注册 / 登录 / 当前用户
│  │  │     ├─ imports.py            上传导入、导入历史、统计、软删除
│  │  │     ├─ trading.py            标的列表与交易记录查询
│  │  │     └─ algo/trading.py       区间最大成交额算法接口
│  │  ├─ core/
│  │  │  ├─ config.py                环境变量与运行配置
│  │  │  ├─ database.py              Engine / Session / 建表 / 连接检查
│  │  │  └─ security.py              密码哈希与 Token 编解码
│  │  ├─ engine_bridge/
│  │  │  ├─ adapters/trading.py      Python -> C++ 算法调用
│  │  │  └─ loaders/trading.py       成交额序列构建与缩放
│  │  ├─ models/
│  │  │  └─ entities.py              users / import_runs / trading_records 等 ORM
│  │  ├─ repositories/
│  │  │  ├─ users.py
│  │  │  ├─ imports.py
│  │  │  └─ trading.py
│  │  ├─ schemas/
│  │  │  ├─ auth.py
│  │  │  ├─ api.py
│  │  │  └─ trading.py
│  │  ├─ services/
│  │  │  ├─ auth.py
│  │  │  ├─ imports.py
│  │  │  └─ algo_trading.py
│  │  └─ main.py                     FastAPI 入口
│  ├─ alembic/
│  │  └─ versions/
│  │     ├─ 20260407_01_initial_schema.py
│  │     ├─ 20260409_01_unified_trading_system.py
│  │     └─ 20260409_02_cleanup_legacy_trading_sources.py
│  ├─ scripts/
│  │  ├─ check_environment.py
│  │  ├─ init_admin.py
│  │  ├─ import_data.py
│  │  └─ export_requirements.py
│  └─ tests/
│     ├─ test_database_pipeline.py
│     └─ test_algo_trading.py
├─ algo-engine/                      C++ 算法引擎与 Python 绑定
│  ├─ include/algo_engine/segment_tree/
│  │  └─ range_max_segment_tree.hpp
│  ├─ src/segment_tree/
│  │  └─ range_max_segment_tree.cpp
│  ├─ bindings/python/
│  │  └─ module.cpp
│  ├─ tests/
│  │  ├─ unit/test_range_max_segment_tree.cpp
│  │  └─ integration/test_python_binding.py
│  ├─ CMakeLists.txt
│  └─ build/                         本地已存在构建产物
├─ deploy/
│  └─ docker-compose.yml             当前仅提供 PostgreSQL 服务
├─ docs/
│  ├─ environment-baseline.md
│  ├─ python-environment.md
│  └─ data-source-strategy.md
├─ data/
│  ├─ uploads/                       用户上传文件落盘目录
│  └─ processed/test_artifacts/      后端与算法测试产物
├─ README.md
├─ pyproject.toml
└─ progress.md
```

## 已完成内容

### 1. 统一业务主线已经落地

- 项目主线已经统一到“用户上传交易文件”的单一路径
- 导入源只保留 `upload / user.upload`
- 迁移脚本已经显式清理旧业务表和旧导入记录

### 2. 后端主链已可用

- 已有可启动的 FastAPI 应用入口
- 已完成 `/api/health`
- 已完成 `/api/auth/register`
- 已完成 `/api/auth/login`
- 已完成 `/api/auth/me`
- 已完成 `/api/imports/runs`
- 已完成 `/api/imports/stats`
- 已完成 `/api/imports/trading`
- 已完成 `/api/imports/runs/{run_id}` 软删除
- 已完成 `/api/trading/instruments`
- 已完成 `/api/trading/records`
- 已完成 `/api/algo/trading/range-max-amount`

### 3. 数据模型与导入链路已贯通

- 已有 `users`
- 已有 `import_runs`
- 已有 `import_manifests`
- 已有 `import_artifacts`
- 已有 `trading_records`
- 上传文件支持 `.csv` 与 `.xlsx`
- 导入模板已固定为：

```text
instrument_code,instrument_name,trade_date,open,high,low,close,volume,amount
```

- 导入后会记录批次、manifest、artifact 和交易明细
- 普通用户只能看自己的导入批次
- 管理员可以查看全站可见批次，并按用户过滤

### 4. 前端不是空壳，已经完成基础联调界面

- 已完成登录页
- 已完成注册页
- 已完成系统总览页
- 已完成交易分析页
- 已完成登录守卫
- 已完成本地 Token 持久化
- 已完成导入历史、统计、图表、算法结果展示
- 已接入 Element Plus 与 ECharts

### 5. 算法链路已真实接通

- `algo-engine` 不再只是目录骨架
- 已实现 `RangeMaxSegmentTree`
- 已通过 pybind11 暴露 `algo_engine_py`
- 后端已能把数据库中的成交额序列送入 C++ 引擎
- 已返回区间最大成交额以及命中的日期索引

## 部分完成或仍需补强

### 工程与部署

- `deploy/` 目前只有 PostgreSQL 的 `docker-compose.yml`
- 还没有完整的前后端一体化部署编排
- 还没有 Nginx、反向代理、容器化全链路方案

### 文档

- `README.md` 已基本同步到当前系统主线
- `algo-engine/README.md` 仍停留在早期规划描述，尚未同步当前已实现内容
- `docs/` 目前以环境说明与数据源说明为主
- 仍缺少更完整的 API 文档、系统设计文档、实验报告/论文材料沉淀

### 前端构建质量

- 前端生产构建已成功
- 当前仍有较大的 bundle 警告，后续可继续做代码分包和体积优化

## 当前不应再使用的旧判断

以下说法已经不符合仓库现状，不应再出现在进度文档里：

- “frontend 还是空目录”
- “项目仍以股票抓取和电商演示为主线”
- “算法引擎只有占位结构”
- “系统还没有用户注册登录”
- “后端还没有交易上传模型”

## 本轮实际核验结果

本轮在当前仓库中重新核对并验证了以下内容：

- `backend/tests/test_database_pipeline.py` 通过，共 2 个测试
- `backend/tests/test_algo_trading.py` 通过，共 3 个测试
- `ctest --test-dir algo-engine/build --output-on-failure` 通过，共 2 个测试
- `frontend` 执行 `npm run build` 成功

本轮额外观察到：

- 前端构建存在 chunk 体积告警，但不影响当前构建成功
- `algo-engine/build/` 已存在可用构建产物，Python 绑定可被后端测试加载

## 一句话结论

当前项目的真实状态已经是：

`一个具备前端界面、用户鉴权、交易文件上传、导入历史管理、PostgreSQL 持久化，以及 C++ 区间最大成交额分析能力的全栈 MVP。`

它不再是旧版 stock / ecommerce 多分支实验骨架，而是已经收敛到“融合 C++ 算法引擎的交易数据管理与分析系统”主线的实时工程。
