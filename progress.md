# 项目进度

更新时间：2026-04-28

## 1. 当前定位

当前仓库主线已经稳定为：

**股票交易数据管理与分析系统的设计与实现**

真实业务链路为：

```text
用户注册/登录
-> 上传 CSV/XLSX 股票交易文件
-> 预览列头映射并确认导入
-> 生成导入批次、manifest、artifact、trading_records
-> 使用统一筛选器选择批次、股票、日期范围和样本数
-> 查看金融分析、快照与相关性、风险雷达、算法查询结果
-> 管理员查看资产、用户、调用记录和运行监控
```

已经退出主业务主线的方向：

- 股票爬虫作为在线导入主链路
- 电商或 synthetic 演示系统
- 旧版 `/analysis-center` 单页大杂烩
- 旧版范围对比模块
- 旧版“治理/快照”页面命名

## 2. 当前技术框架

### 前端

- Vue 3
- TypeScript
- Vite 5
- Vue Router 4
- Naive UI
- ECharts

### 后端

- FastAPI
- SQLAlchemy 2
- Pydantic 2
- Alembic
- Pandas
- Uvicorn

### 数据与运行环境

- PostgreSQL
- Python 3.13
- uv / `.venv`
- Node.js 20+ / npm
- Docker Compose

### 算法模块

- C++23
- CMake
- CTest
- pybind11
- Python bridge
- t-digest 近似查询补充链路

## 3. 当前项目骨架

```text
graduation-project/
├─ web/
│  ├─ src/
│  │  ├─ api/                     前端 API 封装
│  │  ├─ assets/branding/         品牌图片
│  │  ├─ components/              AppShell、筛选器、图表、卡片、空状态
│  │  ├─ constants/               品牌常量
│  │  ├─ pages/                   用户端与管理员端页面
│  │  ├─ router/                  路由与权限守卫
│  │  ├─ stores/                  auth / datasetContext / layout / runtime
│  │  ├─ utils/                   格式化、中文显示、审计映射
│  │  ├─ App.vue
│  │  └─ main.ts
│  ├─ package.json
│  └─ vite.config.ts
├─ backend/
│  ├─ app/
│  │  ├─ api/routes/              health / auth / imports / trading / analysis / admin / algo
│  │  ├─ algo_bridge/             Python 到 C++ 算法适配
│  │  ├─ core/                    配置、数据库、安全
│  │  ├─ models/                  ORM 实体
│  │  ├─ repositories/            数据访问
│  │  ├─ schemas/                 Pydantic 契约
│  │  ├─ services/                导入、分析、索引、风险雷达服务
│  │  ├─ vendor/                  t-digest 支持
│  │  └─ main.py
│  ├─ alembic/
│  ├─ scripts/
│  └─ tests/
├─ algo-module/
│  ├─ include/algo_module/
│  ├─ src/
│  ├─ bindings/python/
│  ├─ tests/
│  └─ CMakeLists.txt
├─ benchmarks/
│  ├─ query_efficiency/
│  ├─ kth_comparison/
│  ├─ platform_quality/
│  └─ run_all.py
├─ data/
│  ├─ processed/auto-generate/    手动测试数据
│  ├─ processed/fetch/            离线获取的完整需求数据
│  └─ uploads/                    用户上传与运行期产物
├─ deploy/
├─ docs/
├─ scripts/
├─ README.md
├─ require.md
├─ tasks.md
└─ progress.md
```

## 4. 已完成内容

### 4.1 业务主线

- 已统一到“用户上传股票交易文件”的产品路径。
- 已完成用户、导入批次、文件产物、交易记录、审计日志、算法索引等核心对象。
- 普通用户仅可访问本人数据。
- 管理员可查看全站数据资产、用户、运行监控和审计日志。

### 4.2 前端页面

用户端：

- `/workbench` 工作台
- `/datasets` 数据集管理
- `/analysis/market` 金融分析
- `/analysis/governance` 快照与相关性
- `/algo-radar/risk` 风险雷达
- `/algo-radar/algorithms` 算法查询与事件上下文

管理员端：

- `/admin/assets` 数据资产总览
- `/admin/users` 用户管理
- `/admin/activity` 用户调用记录
- `/admin/runs` 运行监控

近期前端整理已经完成：

- 统一筛选器标题和字段重构。
- 移除共享范围设置卡片、范围对比模块和多个重复摘要卡片。
- “治理/快照”重命名为“快照与相关性”。
- 金融分析页保留基础摘要、价格走势与技术信号、风险指标、异常检测、横截面对比。
- 快照与相关性页保留数据质量、估值与基本面快照、相关性矩阵。
- 风险雷达页和算法查询页的大表格改为单列排放。
- 风险事件原因、异常类型等英文描述已中文化。
- 顶部系统状态改为全局同步算法索引信息，不再依赖进入风险雷达页面。
- 左侧菜单栏宽度已调整，品牌名称可单行显示。

### 4.3 后端接口

已完成：

- `/api/health`
- `/api/auth/register`
- `/api/auth/login`
- `/api/auth/me`
- `/api/admin/users`
- `/api/admin/overview`
- `/api/admin/assets/overview`
- `/api/admin/audit-logs`
- `/api/admin/audit-logs/stats`
- `/api/admin/runs/monitor`
- `/api/imports/runs`
- `/api/imports/stats`
- `/api/imports/trading/preview`
- `/api/imports/trading/commit`
- `/api/imports/trading`
- `/api/imports/runs/{run_id}`
- `/api/trading/stocks`
- `/api/trading/records`
- `/api/trading/analysis/summary`
- `/api/trading/analysis/quality`
- `/api/trading/analysis/indicators`
- `/api/trading/analysis/risk`
- `/api/trading/analysis/snapshot`
- `/api/trading/analysis/anomalies`
- `/api/trading/analysis/cross-section`
- `/api/trading/analysis/correlation`
- `/api/algo/trading/range-max-amount`
- `/api/algo/trading/range-kth-volume`
- `/api/algo/trading/joint-anomaly-ranking`
- `/api/algo/indexes/status`
- `/api/algo/indexes/rebuild`
- `/api/algo/risk-radar/overview`
- `/api/algo/risk-radar/events`
- `/api/algo/risk-radar/stocks`
- `/api/algo/risk-radar/calendar`
- `/api/algo/risk-radar/event-context`

### 4.4 数据导入与数据集

- 支持 `.csv` 和 `.xlsx`。
- 支持列头解析、映射确认和提交导入。
- 支持重复源列映射检测。
- 支持导入历史、交易样本和当前数据集摘要。
- 当前规范字段为：

```text
stock_code, stock_name, trade_date, open, high, low, close, volume, amount, turnover
```

- 已生成手动测试文件：

```text
data/processed/auto-generate/manual_test_boundary_stocks_10x600_20220103_20240517.csv
```

该文件覆盖多股票、长时间序列、成交额峰值、重复极值、异常成交、边界日期等手动测试场景。

### 4.5 算法链路

已实现：

- `RangeMaxSegmentTree`：区间最大成交额
- `RangeKthPersistentSegmentTree`：精确区间第 K 大成交量
- `HistoricalDominanceCDQ`：联合异常排序与历史支配计数
- 3D CDQ 支持风险雷达联合分位
- Python bridge + pybind11 调用
- t-digest 近似第 K 大查询
- 风险雷达索引、事件、日历、股票画像和事件上下文

### 4.6 测试与验证

当前可运行验证项：

- 后端 pytest
- 前端 `npm run typecheck`
- 前端 `npm run build`
- C++ `ctest`
- benchmark 三套件

最近多次前端修改后均已通过：

```text
npm run typecheck
```

## 5. 当前仍需补强

### 工程部署

- 仍缺完整前后端一体化 Docker Compose。
- 仍缺 Nginx 或等价反向代理。
- 仍缺生产环境部署文档和脚本固化。

### 文档材料

- `algo-module/README.md` 仍需同步当前真实算法实现。
- 仍需补全 API 详细文档。
- 仍需补全算法设计说明、指标口径说明、实验报告和答辩材料。

### 数据能力

- `trading_records` 当前是真实主表。
- `benchmark_close`、估值字段和基本面字段已经是 `trading_records` 的可选增强列，上传文件提供并完成映射后可以入库。
- 这些增强列不是最小导入必需字段；普通 OHLCV 文件仍可导入，相关指标按缺字段规则降级。
- 如后续论文需要，可继续把当前宽表可选列拆分为“行情主表 + 基准序列 + 估值快照 + 财务报告”的多表设计。

## 6. 当前不应再使用的旧判断

以下说法已经过期：

- “前端还是空目录”
- “前端使用 Element Plus”
- “系统仍以股票爬虫作为主导入链路”
- “分析中心是单页大杂烩”
- “治理/快照是当前页面名”
- “范围对比仍是主要模块”
- “算法模块只有占位结构”
- “只有区间最大成交额，没有第 K 大和联合异常”
- “风险雷达为空是因为算法索引未构建”

## 7. 一句话结论

当前项目已经是一个具备 Web 页面、用户鉴权、交易文件导入、PostgreSQL 持久化、金融分析、快照与相关性、异常检测、风险雷达、C++/Python 混合算法和管理员后台的全栈 MVP。
