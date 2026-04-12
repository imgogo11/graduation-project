# 项目进度

更新时间：2026-04-10

## 当前项目定位

当前仓库的主线已经不是早期的“股票抓取 + 电商演示 + benchmark 预留”组合方案，而是一个已经落地到可联调、可验证状态的：

`基于 C++ 算法模块的股票交易数据管理与分析系统设计与实现（Stock Trading Data Management and Analysis System Based on C++ Algorithm Module）`

当前真实业务链路为：

`用户注册/登录 -> 上传 CSV/XLSX 交易文件 -> 生成导入批次 / manifest / artifact / trading_records -> 按权限查询批次与标的 -> 执行摘要 / 质量 / 指标 / 风险 / 异常 / 横截面 / 相关性 / 范围对比分析 -> 调用 C++ / Python 混合算法接口完成区间最大成交额、区间第 K 大成交量与联合异常排序`

已经退出主链、只剩历史痕迹或文档痕迹的旧方向包括：

- 股票爬虫导入主链
- 电商演示数据导入主链
- synthetic 电商数据主链
- benchmark 业务接口主链（当前仅保留离线 benchmark 脚本痕迹，不属于产品主链）

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

### 算法模块

- C++23
- pybind11
- CMake
- CTest
- Python bridge + `t_digest` 近似查询补充链路

## 当前实时项目骨架

```text
graduation-project/
├─ frontend/                         Vue 前端工程，已完成交易页与分析页联调
│  ├─ src/
│  │  ├─ api/                        前端 API 封装（auth / imports / health / trading / analysis）
│  │  ├─ components/                 AppShell、统计卡片、空状态、图表面板等组件
│  │  ├─ pages/                      Login / Register / Overview / Trading / Analysis 页面
│  │  ├─ router/                     前端路由与登录守卫
│  │  ├─ stores/                     auth / runtime 状态管理
│  │  ├─ utils/                      格式化与错误信息处理
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
│  │  │     ├─ trading_analysis.py   摘要 / 质量 / 指标 / 风险 / 异常 / 横截面 / 相关性 / 范围对比
│  │  │     └─ algo/trading.py       区间最大成交额 / 第 K 大成交量 / 联合异常排序
│  │  ├─ core/
│  │  │  ├─ config.py                环境变量与运行配置
│  │  │  ├─ database.py              Engine / Session / 建表 / 连接检查
│  │  │  └─ security.py              密码哈希与 Token 编解码
│  │  ├─ algo_bridge/
│  │  │  ├─ adapters/trading.py      Python -> C++ / t-digest 算法调用
│  │  │  └─ loaders/trading.py       成交额 / 成交量 / 联合异常事件序列构建
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
│  │  │  ├─ trading_analysis.py
│  │  │  └─ algo_trading.py
│  │  ├─ vendor/
│  │  │  └─ tdigest.py               近似第 K 大查询支持
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
│  │  ├─ export_requirements.py
- ?????? `benchmarks/` ???????????????Kth ??????? Locust ?????/??????????? `results/` ? `images/`
│  └─ tests/
│     ├─ test_database_pipeline.py
│     ├─ test_algo_trading.py
│     ├─ test_trading_analysis.py
│     └─ test_tdigest_range_kth.py
├─ algo-module/                      C++ 算法模块与 Python 绑定
│  ├─ include/algo_module/
│  │  ├─ cdq/
│  │  │  └─ historical_dominance_cdq.hpp
│  │  └─ segment_tree/
│  │     ├─ range_kth_persistent_segment_tree.hpp
│  │     └─ range_max_segment_tree.hpp
│  ├─ src/
│  │  ├─ cdq/
│  │  │  └─ historical_dominance_cdq.cpp
│  │  └─ segment_tree/
│  │     ├─ range_kth_persistent_segment_tree.cpp
│  │     └─ range_max_segment_tree.cpp
│  ├─ bindings/python/
│  │  └─ module.cpp
│  ├─ tests/
│  │  ├─ unit/test_range_max_segment_tree.cpp
│  │  ├─ unit/test_historical_dominance_cdq.cpp
│  │  ├─ unit/test_range_kth_persistent_segment_tree.cpp
│  │  └─ integration/test_python_binding.py
│  ├─ CMakeLists.txt
│  └─ build/                         本地已存在构建产物与 CTest 测试目标
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
- 系统已收敛为股票单一场景，上传、存储、查询与分析链路不再区分商品类型
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
- 已完成 `/api/trading/analysis/summary`
- 已完成 `/api/trading/analysis/quality`
- 已完成 `/api/trading/analysis/indicators`
- 已完成 `/api/trading/analysis/risk`
- 已完成 `/api/trading/analysis/anomalies`
- 已完成 `/api/trading/analysis/cross-section`
- 已完成 `/api/trading/analysis/correlation`
- 已完成 `/api/trading/analysis/compare-scopes`，并保留 `/api/trading/analysis/compare-runs` 兼容别名
- 已完成 `/api/algo/trading/range-max-amount`
- 已完成 `/api/algo/trading/range-kth-volume`
- 已完成 `/api/algo/trading/joint-anomaly-ranking`

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
- 数据已经能够支撑单标的分析、多标的横截面分析、相关性分析与范围对比分析

### 4. 前端不是空壳，已经完成基础联调界面

- 已完成登录页
- 已完成注册页
- 已完成系统总览页
- 已完成交易上传与批次管理页
- 已完成独立分析中心页
- 已完成登录守卫
- 已完成本地 Token 持久化
- 已完成导入历史、统计、图表、算法结果展示
- 已完成摘要、质量、指标、风险、异常、横截面、相关性、范围对比与联合异常榜单展示
- 已接入 Element Plus 与 ECharts

### 5. 算法链路已真实接通

- `algo-module` 不再只是目录骨架
- 已实现 `RangeMaxSegmentTree`
- 已实现 `RangeKthPersistentSegmentTree`
- 已实现 `HistoricalDominanceCDQ`
- 已通过 pybind11 暴露 `algo_module_py`
- 后端已能把数据库中的成交额序列送入 C++ 引擎做区间最大值查询
- 后端已能把数据库中的成交量序列送入精确第 K 大查询，或走 `t_digest` 近似查询链路
- 后端已能把联合异常事件序列送入 CDQ 历史支配计数算法，并返回排序结果
- 前端已经可以切换精确 / 近似算法方式，并展示命中日期或近似说明

## 部分完成或仍需补强

### 工程与部署

- `deploy/` 目前只有 PostgreSQL 的 `docker-compose.yml`
- 还没有完整的前后端一体化部署编排
- 还没有 Nginx、反向代理、容器化全链路方案

### 文档

- `README.md` 已基本同步到当前系统主线
- `algo-module/README.md` 仍停留在早期规划描述，尚未同步当前已实现内容
- `docs/` 目前以环境说明与数据源说明为主
- ?????? `benchmarks/` ???????????????Kth ??????? Locust ?????/??????????? `results/` ? `images/`
- 仍缺少更完整的 API 文档、系统设计文档、实验报告/论文材料沉淀

### 前端构建质量

- 前端生产构建已成功
- 当前仍有较大的 bundle 告警，后续可继续做代码分包和体积优化

## 当前不应再使用的旧判断

以下说法已经不符合仓库现状，不应再出现在进度文档里：

- “frontend 还是空目录”
- “项目仍以股票抓取和电商演示为主线”
- “系统只有 Trading 页面，没有独立 Analysis 页面”
- “后端只有基础导入接口，没有分析接口”
- “算法模块只有占位结构”
- “系统还没有用户注册登录”
- “后端还没有交易上传模型”
- “系统只有区间最大成交额，没有第 K 大和联合异常能力”

## 本轮实际核验结果

本轮在当前仓库中重新核对并验证了以下内容：

- `backend/tests/test_database_pipeline.py` 通过，共 2 个测试
- `backend/tests/test_algo_trading.py` 通过，共 14 个测试
- `backend/tests/test_trading_analysis.py` 通过，共 3 个测试
- `backend/tests/test_tdigest_range_kth.py` 通过，共 2 个测试
- `ctest --test-dir algo-module/build --output-on-failure` 通过，共 4 个测试
- `frontend` 执行 `npm run build` 成功

本轮额外观察到：

- 前端构建存在 chunk 体积告警，但不影响当前构建成功
- `algo_module_python_smoke` 已通过，说明 pybind11 绑定产物可被 Python 正常加载
- `algo-module/build/` 已存在可用构建产物，C++ 单元测试与 Python smoke test 均可运行

## 一句话结论

当前项目的真实状态已经是：

`一个具备前端界面、用户鉴权、交易文件上传、导入历史管理、PostgreSQL 持久化、交易分析中心，以及 C++ / Python 混合算法能力（区间最大成交额、区间第 K 大成交量、联合异常排序）的全栈 MVP。`

它不再是旧版 stock / ecommerce 多分支实验骨架，而是已经收敛到“基于 C++ 算法模块的股票交易数据管理与分析系统”主线、并完成多项分析能力落地的实时工程。
