# 毕业论文目录结构

## 论文题目

**《基于 C++ 算法模块的股票交易数据管理与分析系统设计与实现》**

Design and Implementation of a Stock Trading Data Management and Analysis System Based on C++ Algorithm Module

---

## 前置部分

- 封面
- 原创性声明 / 学术诚信声明
- 中文摘要
- Abstract（英文摘要）
- 目录
- 插图清单
- 表格清单
- 主要符号与缩略语说明

---

## 正文

### 第 1 章 绪论

#### 1.1 研究背景与意义

- 股票历史交易数据规模持续增长，传统表格方式难以高效管理与分析
- Python 生态虽擅长业务开发与数据处理，但在区间查询、顺序统计、多维联合异常计算等场景下性能受限
- C++ 算法模块能在关键路径提供数量级的性能提升，将其集成到 Web 全栈系统中具有工程实践价值
- 本系统将"数据管理 + 交易分析 + C++ 算法引擎 + 风险雷达"统一到一个可运行、可验证的全栈平台

#### 1.2 国内外研究现状

- 1.2.1 金融交易数据管理系统研究现状
- 1.2.2 股票分析与可视化平台研究现状
- 1.2.3 高性能区间查询与顺序统计算法研究现状（线段树、主席树、t-digest）
- 1.2.4 多维异常检测与联合异常排序研究现状（CDQ 分治、支配计数）

> 写作建议：以"已有工作做了什么、尚存哪些不足"为脉络，自然引出本系统定位。

#### 1.3 研究目标与主要内容

- 构建支持注册登录、权限隔离和交易文件导入的数据管理系统
- 实现八大分析面板：摘要、质量、指标、风险、异常、横截面、相关性、范围对比
- 设计 C++ 算法引擎并通过 pybind11 集成：区间最大成交额、区间第 K 大成交量（精确 + 近似双方案）、联合异常排序
- 构建三维风险雷达：索引构建、快照缓存、异常事件总览/榜单/标的画像/日期聚合/事件钻取
- 通过自动化测试与对比实验验证系统正确性与算法效果

#### 1.4 技术路线与研究方法

- 技术路线图（建议配图）
- 前端：Vue 3 + TypeScript + Element Plus + ECharts
- 后端：FastAPI + SQLAlchemy 2 + Alembic + Pandas
- 数据库：PostgreSQL
- 算法引擎：C++23 + pybind11 + CMake + CTest
- 近似查询补充：Python t-digest
- 环境管理：uv + Docker Compose

#### 1.5 论文结构安排

- 简述第 2–7 章的主要内容与逻辑衔接

---

### 第 2 章 相关技术与理论基础

#### 2.1 前端技术栈

- 2.1.1 Vue 3 组合式 API 与组件化开发
- 2.1.2 TypeScript 类型安全与工程规范
- 2.1.3 Vue Router 路由守卫与导航控制
- 2.1.4 Element Plus UI 组件库
- 2.1.5 ECharts 数据可视化引擎

#### 2.2 后端技术栈

- 2.2.1 FastAPI 异步框架与路由组织
- 2.2.2 SQLAlchemy 2 ORM 与 Mapped 声明式建模
- 2.2.3 Pydantic 2 数据校验与序列化
- 2.2.4 Alembic 数据库版本迁移
- 2.2.5 Pandas 时间序列处理与指标计算

#### 2.3 数据库技术

- 2.3.1 PostgreSQL 关系型数据库
- 2.3.2 条件唯一索引与软删除设计

#### 2.4 身份认证与权限控制

- 2.4.1 JWT Bearer Token 认证机制
- 2.4.2 PBKDF2-SHA256 密码哈希
- 2.4.3 用户/管理员双角色权限模型

#### 2.5 算法理论基础

- 2.5.1 线段树与区间最大值查询（RangeMaxSegmentTree）
- 2.5.2 可持久化线段树与区间第 K 大查询（RangeKthPersistentSegmentTree）
- 2.5.3 t-digest 近似分位与近似顺序统计
- 2.5.4 CDQ 分治与二维/三维历史支配计数（HistoricalDominanceCDQ / 3D）

#### 2.6 跨语言集成技术

- 2.6.1 pybind11 C++/Python 绑定机制
- 2.6.2 CMake 构建系统与 CTest 测试框架

---

### 第 3 章 系统需求分析

#### 3.1 用户角色与业务场景

- 3.1.1 普通用户：注册、登录、上传交易文件、查看分析结果
- 3.1.2 管理员：全站批次可见、跨用户数据管理与验证

#### 3.2 功能需求分析

- 3.2.1 用户鉴权需求（注册、登录、当前用户信息）
- 3.2.2 数据导入管理需求（CSV/XLSX 上传、数据集命名、导入历史、统计、软删除）
- 3.2.3 交易记录查询需求（标的列表、记录列表、分页）
- 3.2.4 分析中心需求（八大分析面板）
  - 交易摘要分析
  - 数据质量分析
  - 技术指标分析（MA/EMA/MACD/RSI/Bollinger/ATR）
  - 风险指标分析（区间收益率、波动率、最大回撤、上涨日占比）
  - 异常检测分析（放量异常、收益率异常、振幅异常、突破前高/前低）
  - 横截面排序分析
  - 收益率相关性矩阵分析
  - 范围对比分析（同批次/跨批次、同标的/多标的、不同日期范围）
- 3.2.5 C++ 算法增强需求
  - 区间最大成交额查询
  - 区间第 K 大成交量查询（精确解 + 近似解）
  - 联合异常排序
- 3.2.6 风险雷达需求
  - 索引状态管理与重建
  - 异常事件总览与分级
  - 事件榜单与标的风险画像
  - 日期聚合与日历视图
  - 事件上下文钻取（窗口分位、分布变化、局部成交额峰值）

#### 3.3 非功能需求分析

- 3.3.1 正确性：导入校验、字段合法性、权限隔离、算法精度
- 3.3.2 性能：C++ 算法查询效率、索引缓存与快照复用
- 3.3.3 可维护性：前后端分层、路由与服务分离
- 3.3.4 可扩展性：算法模块可通过 pybind11 持续扩展
- 3.3.5 可用性：交互友好、错误提示明确、可视化结果直观
- 3.3.6 安全性：密码哈希、Token 鉴权、数据按用户隔离

#### 3.4 业务流程与用例分析

- 用户注册登录流程图
- 文件上传与导入处理流程图
- 分析中心查询流程图
- 风险雷达索引构建与查询流程图
- 核心用例图

---

### 第 4 章 系统总体设计

#### 4.1 系统总体架构

- 四层架构设计（建议配图）：
  - 表现层：Vue 前端页面与 ECharts 可视化组件
  - 服务层：FastAPI 路由、业务服务、权限依赖、算法适配
  - 数据层：PostgreSQL、ORM 实体模型、Alembic 迁移
  - 算法层：C++ 算法引擎（algo-module）、Python Bridge（algo_bridge）、风险雷达索引缓存

#### 4.2 前端模块设计

- 4.2.1 页面模块划分
  - LoginPage / RegisterPage（登录/注册）
  - OverviewPage（系统总览）
  - TradingPage（交易数据管理）
  - AnalysisPage（分析中心）
  - RiskRadarPage（风险雷达）
- 4.2.2 通用组件设计（AppShell、StatCard、PanelCard、EChartPanel、EmptyState）
- 4.2.3 前端 API 封装层设计（auth / imports / trading / analysis / riskRadar / health）
- 4.2.4 状态管理设计（auth store / runtime store）
- 4.2.5 路由守卫与登录态持久化设计

#### 4.3 后端模块设计

- 4.3.1 路由层设计（api/routes）
  - 鉴权路由：auth.py
  - 健康检查路由：health.py
  - 导入管理路由：imports.py
  - 交易查询路由：trading.py
  - 分析路由：trading_analysis.py
  - 算法路由：algo/trading.py、algo/indexes.py、algo/risk_radar.py
- 4.3.2 服务层设计（services）
  - AuthService
  - ImportsService
  - TradingAnalysisService
  - TradingAlgoService
  - AlgoIndexManager
  - RiskRadarService
- 4.3.3 数据访问层设计（repositories）
  - UsersRepository
  - ImportsRepository
  - TradingRepository
- 4.3.4 数据模型层设计（schemas / models）
- 4.3.5 核心基础层设计（core：config / database / security）

#### 4.4 数据库设计

- 4.4.1 E-R 图（建议配图）
- 4.4.2 users 表设计
- 4.4.3 import_runs 表设计
- 4.4.4 import_manifests 表设计
- 4.4.5 import_artifacts 表设计
- 4.4.6 trading_records 表设计
- 4.4.7 索引与约束策略
  - 条件唯一索引（同用户 + 未删除 + 活跃状态下 dataset_name 唯一）
  - 复合唯一约束（import_run_id + instrument_code + trade_date）
  - 软删除时间戳字段

#### 4.5 核心接口设计

- 4.5.1 鉴权接口组（register / login / me）
- 4.5.2 导入管理接口组（runs / stats / trading / 软删除）
- 4.5.3 交易查询接口组（instruments / records）
- 4.5.4 分析中心接口组（summary / quality / indicators / risk / anomalies / cross-section / correlation / compare-scopes）
- 4.5.5 算法接口组（range-max-amount / range-kth-volume / joint-anomaly-ranking）
- 4.5.6 风险雷达接口组（索引状态 / 重建 / 总览 / 事件列表 / 标的列表 / 日期聚合 / 事件上下文）

> 每组说明：输入参数、输出结构、访问控制规则、错误响应场景。

#### 4.6 C++ 算法模块与 Python Bridge 集成设计

- 4.6.1 algo-module 目录组织与构建方式（建议配图）
  - include/ → 头文件（segment_tree / cdq / common）
  - src/ → 实现文件
  - bindings/python/ → pybind11 绑定模块 module.cpp
  - tests/ → 单元测试与集成测试
- 4.6.2 pybind11 绑定与 algo_module_py 模块导出
- 4.6.3 algo_bridge 适配层设计
  - loaders/trading.py → 数据序列构建（成交额/成交量/联合异常事件）
  - adapters/trading.py → C++ / t-digest 调用封装
  - tdigest.py → 分块索引近似查询

#### 4.7 风险雷达索引与缓存设计

- 4.7.1 索引生命周期状态机（pending → building → ready / failed）
- 4.7.2 InstrumentAlgoIndex 对象结构（含 RangeMax/RangeKth 线段树、t-digest 分块索引）
- 4.7.3 RiskRadarIndexCache 对象结构（概览、事件、标的画像、日历、标的索引）
- 4.7.4 快照写入与加载复用机制
- 4.7.5 三维 CDQ 支配计数在事件分级中的应用
- 4.7.6 事件上下文解释生成（窗口分位、分布变化、局部成交额峰值）

---

### 第 5 章 系统详细实现

#### 5.1 用户认证与权限隔离实现

- 5.1.1 注册与登录接口实现
- 5.1.2 JWT 签发与校验流程
- 5.1.3 PBKDF2-SHA256 密码哈希实现
- 5.1.4 普通用户/管理员访问控制依赖注入
- 5.1.5 前端路由守卫与 Token 持久化

#### 5.2 文件上传与数据导入实现

- 5.2.1 上传文件保存路径组织（data/uploads/trading/{user_id}/{run_id}/）
- 5.2.2 中英文别名表头标准化映射（trading_head.json）
- 5.2.3 必填列、可选列与重复记录校验
- 5.2.4 导入批次、manifest、artifact 与交易记录写入流程
- 5.2.5 导入失败标记、软删除与数据集名称复用机制
- 5.2.6 命令行导入脚本实现（import_data.py）

#### 5.3 交易记录查询与统计总览实现

- 5.3.1 批次列表查询与统计信息生成
- 5.3.2 标的列表与交易记录查询
- 5.3.3 总览页面：健康状态、按月导入趋势、最近导入记录

#### 5.4 交易分析中心实现

- 5.4.1 交易摘要分析（统计最高价、最低价、均价、总成交量等）
- 5.4.2 数据质量分析（覆盖率、缺失日期、OHLC 合法性、零值检测、扁平日）
- 5.4.3 技术指标分析（MA5/10/20、EMA12/26、MACD/Signal/Histogram、RSI14、Bollinger Bands、ATR14）
- 5.4.4 风险指标分析（区间收益率、波动率、最大回撤及持续天数、上涨日占比、最大单日涨跌幅）
- 5.4.5 异常检测分析（放量异常 2× 基线、收益率异常 3σ、振幅异常 2× 基线、突破前高/前低）
- 5.4.6 横截面排序分析（按 total_return / volatility / total_volume / total_amount / average_amplitude 多指标排序）
- 5.4.7 收益率相关性矩阵分析
- 5.4.8 范围对比分析（标的重叠、记录重叠、逐字段不一致检测与样例展示）

#### 5.5 C++ 算法查询实现

##### 5.5.1 区间最大成交额实现

- 数据加载与整数缩放（scale_amount / unscale_amount）
- RangeMaxSegmentTree 构建与区间查询
- 重复最大值日期的匹配返回

##### 5.5.2 区间第 K 大成交量实现

- **精确方案：可持久化线段树**
  - 值域离散化与前缀版本构建
  - 区间第 K 大查询流程
  - 命中日期匹配与返回
- **近似方案：t-digest**
  - 分块索引设计（RangeKthTDigestBlockIndex）
  - k → quantile 近似映射规则
  - is_approx 标记与 approximation_note 说明
- 双方案统一接口与 method 参数切换

##### 5.5.3 联合异常排序实现

- 联合异常事件序列构建（return_z20 × volume_ratio20）
- 二维 CDQ 历史支配计数算法应用
- joint_percentile 计算与 severity 分级（medium ≥ 0.90 / high ≥ 0.95 / critical ≥ 0.99）
- 排序策略与 Top-N 截断

#### 5.6 三维风险雷达实现

##### 5.6.1 索引构建实现

- 每标的数据加载与序列化
- RangeMaxSegmentTree（成交额）构建
- RangeKthPersistentSegmentTree（成交量/振幅）构建
- RangeKthTDigestBlockIndex（成交量/振幅）构建
- 三维 CDQ 支配计数（return_z20 × volume_ratio20 × amplitude_ratio20）

##### 5.6.2 缓存与快照实现

- JSON 快照写入与读取
- 内存缓存命中与 reuse_count 计数
- AlgoIndexManager 状态管理与异步构建

##### 5.6.3 总览与事件查询实现

- 总览计数（total_events / impacted_instrument_count / medium/high/critical）
- 事件列表多维过滤（日期范围/标的/严重度/Top-N）
- 标的风险画像排序
- 日历聚合视图

##### 5.6.4 事件上下文钻取实现

- 多窗口分位查询（20/60/120 日窗口，p50/p90/p95/top1/top3）
- 前后分布变化对比（volume / amplitude，before vs after 的 median/p90/p95）
- 局部成交额峰值检测（±20 日半径）
- cause_label 归因标签（price-led / volume-led / amplitude-led / three-factor resonance）

#### 5.7 前端页面实现

- 5.7.1 登录页与注册页实现
- 5.7.2 系统总览页实现（统计卡片、健康状态、月度趋势、最近导入）
- 5.7.3 交易数据管理页实现（文件上传、批次管理、区间算法卡片、算法切换）
- 5.7.4 分析中心页实现（六大区域联动：摘要/指标/风险/异常/横截面相关性/质量对比）
- 5.7.5 风险雷达页实现（异常散点图、事件榜单、标的画像、日历热力图、事件钻取面板）

---

### 第 6 章 系统测试与实验分析

#### 6.1 测试环境与实验数据

- 6.1.1 运行环境（Windows 10、Python 3.13、Node.js 20、PostgreSQL 15、MSVC C++23）
- 6.1.2 测试框架（Python unittest、CTest、npm build 验证）
- 6.1.3 测试数据集说明

#### 6.2 功能测试

- 6.2.1 后端数据库主链路测试（test_database_pipeline.py）
  - 注册登录 → 上传文件 → 导入批次 → 查询记录 → 软删除 → 名称复用
- 6.2.2 交易分析链路测试（test_trading_analysis.py）
  - 摘要、质量、指标、风险、异常、横截面、相关性、范围对比
- 6.2.3 算法链路测试（test_algo_trading.py）
  - 区间最大成交额功能正确性
  - 区间第 K 大成交量双方案功能正确性
  - 联合异常排序功能正确性
  - 重复值处理、边界 k 值、空区间、越界参数
- 6.2.4 t-digest 近似查询测试（test_tdigest_range_kth.py）
- 6.2.5 风险雷达测试（test_risk_radar.py）
- 6.2.6 C++ 单元测试
  - test_range_max_segment_tree.cpp
  - test_range_kth_persistent_segment_tree.cpp
  - test_historical_dominance_cdq.cpp
  - test_historical_dominance_cdq_3d.cpp
- 6.2.7 Python 绑定集成测试（test_python_binding.py / algo_module_python_smoke）
- 6.2.8 前端构建验证（npm run build）

#### 6.3 算法正确性验证

- 6.3.1 区间最大成交额重复最大值命中验证
- 6.3.2 区间第 K 大：精确解与暴力排序对拍
- 6.3.3 区间第 K 大：近似解与精确解误差对比
- 6.3.4 联合异常排序 joint_percentile 计算正确性
- 6.3.5 三维 CDQ 支配计数与暴力对拍

#### 6.4 性能与效果实验

- 6.4.1 精确方案（persistent_segment_tree）vs 暴力基线性能对比
- 6.4.2 精确方案 vs 近似方案（t-digest）结果对比与误差统计
- 6.4.3 风险雷达索引构建耗时与快照复用效率
- 6.4.4 联合异常排序效果展示（榜单 + 钻取解释）

> 建议输出：构建时间对比表、查询时间对比表、误差统计表、可视化截图。

#### 6.5 结果分析

- 系统是否完成需求分析中定义的业务闭环
- C++ 算法模块是否真正提升了分析能力
- 精确/近似两套方案各自的适用场景
- 风险雷达索引缓存方案的有效性
- 三维联合异常分级在实际数据中的区分度

---

### 第 7 章 总结与展望

#### 7.1 工作总结

- 实现了完整的"注册→上传→管理→分析→算法→风险雷达"全栈业务闭环
- 实现了前后端联动与 ECharts 可视化展示
- 实现了 C++ 算法引擎（3 种数据结构 + 3 种算法）通过 pybind11 集成
- 实现了三维风险雷达索引构建、快照缓存与事件钻取解释

#### 7.2 创新点与贡献

- 将 C++23 算法模块（线段树、主席树、CDQ 分治）通过 pybind11 集成到 Python Web 全栈系统
- 区间第 K 大查询同时提供精确（可持久化线段树）与近似（t-digest）两套方案，并支持前端实时切换
- 基于三维 CDQ 历史支配计数构建联合异常排序与风险雷达，提供事件分级、归因标签与上下文钻取

#### 7.3 不足与局限

- 部署方案偏开发环境，尚未完成容器化全链路编排
- 实验数据规模有限，大规模场景下的性能评估有待补充
- 前端 bundle 体积较大，可继续进行代码分包优化
- 算法种类仍可继续丰富

#### 7.4 后续改进方向

- 完善生产环境部署与 Nginx 反向代理配置
- 增加更多算法能力（如区间中位数、加权排序）与系统化性能评测
- 扩展更丰富的数据源接入与多维度分析
- 增强前端大规模数据可视化性能
- 引入实时更新与推送机制

---

## 后置部分

### 参考文献

### 致谢

### 附录

- 附录 A 核心 API 接口清单（含请求参数与响应结构）
- 附录 B 数据库表结构字段说明
- 附录 C 关键测试用例摘要
- 附录 D 主要页面截图
- 附录 E 运行命令与部署说明
- 附录 F C++ 算法核心代码片段

---

## 建议图表清单

### 建议图

| 编号 | 图名 | 建议出现章节 |
|------|------|-------------|
| 图 1-1 | 技术路线图 | 1.4 |
| 图 4-1 | 系统总体架构图（四层） | 4.1 |
| 图 4-2 | 前后端与算法模块交互图 | 4.1 |
| 图 4-3 | 前端页面模块划分图 | 4.2 |
| 图 4-4 | 后端模块分层图 | 4.3 |
| 图 4-5 | 数据库 E-R 图 | 4.4 |
| 图 4-6 | algo-module 目录结构与构建流程图 | 4.6 |
| 图 4-7 | 区间第 K 大双方案设计图 | 4.6 |
| 图 4-8 | 风险雷达索引生命周期状态机图 | 4.7 |
| 图 3-1 | 用户注册登录流程图 | 3.4 |
| 图 3-2 | 文件上传与导入处理流程图 | 3.4 |
| 图 3-3 | 分析中心查询流程图 | 3.4 |
| 图 3-4 | 风险雷达索引构建与查询流程图 | 3.4 |
| 图 3-5 | 系统用例图 | 3.4 |
| 图 5-1 | pybind11 调用链路图 | 5.5 |
| 图 5-2 | 三维 CDQ 事件分级流程图 | 5.6 |
| 图 5-3 | 事件上下文钻取数据生成图 | 5.6 |
| 图 6-1 | 精确/近似方案查询时间对比图 | 6.4 |
| 图 6-2 | 近似方案误差分布图 | 6.4 |
| 图 6-3 | 风险雷达索引构建时间趋势图 | 6.4 |

### 建议表

| 编号 | 表名 | 建议出现章节 |
|------|------|-------------|
| 表 2-1 | 关键技术栈汇总表 | 2.1–2.6 |
| 表 3-1 | 功能需求汇总表 | 3.2 |
| 表 4-1 | 核心数据表设计汇总表 | 4.4 |
| 表 4-2 | 核心 API 接口清单表 | 4.5 |
| 表 4-3 | 算法复杂度对比表 | 4.6 |
| 表 6-1 | 测试环境配置表 | 6.1 |
| 表 6-2 | 功能测试用例与结果表 | 6.2 |
| 表 6-3 | 算法正确性测试结果表 | 6.3 |
| 表 6-4 | 精确/近似方案实验对比表 | 6.4 |
| 表 6-5 | 索引构建耗时统计表 | 6.4 |

---

## 章节与代码映射

| 论文章节 | 主要代码位置 | 写作重点 |
|----------|-------------|---------|
| 5.1 认证与权限 | `backend/app/api/routes/auth.py`、`backend/app/services/auth.py`、`backend/app/core/security.py`、`frontend/src/stores/auth.ts`、`frontend/src/router/` | JWT 流程、密码哈希、角色隔离 |
| 5.2 上传与导入 | `backend/app/services/imports.py`、`backend/app/repositories/imports.py`、`backend/app/services/trading_head.json` | 表头映射、批次管理、软删除 |
| 5.3 查询与总览 | `backend/app/api/routes/imports.py`、`backend/app/api/routes/trading.py`、`frontend/src/pages/OverviewPage.vue` | 统计卡片、月度趋势 |
| 5.4 分析中心 | `backend/app/services/trading_analysis.py`（830 行）、`frontend/src/pages/AnalysisPage.vue`（52467 字节） | 八大分析面板的实现逻辑 |
| 5.5 算法查询 | `backend/app/services/algo_trading.py`、`backend/app/algo_bridge/`、`algo-module/src/` | 三种算法实现与调用链路 |
| 5.6 风险雷达 | `backend/app/services/algo_indexes.py`（517 行）、`backend/app/services/risk_radar.py`、`frontend/src/pages/RiskRadarPage.vue` | 索引构建、缓存复用、事件钻取 |
| 5.7 前端页面 | `frontend/src/pages/`、`frontend/src/components/`、`frontend/src/api/` | 页面组织与交互实现 |
| 6.2–6.3 测试 | `backend/tests/`、`algo-module/tests/` | 覆盖场景与测试结果 |

---

## 写作注意事项

1. 全文统一使用"本系统""本文所设计系统"等称呼
2. t-digest 表述为"近似分位/近似第 K 大查询方案"，不表述为"任意区间严格 O(1) 的精确解"
3. 第 4 章侧重"设计"层面（架构图、接口规格、数据模型），第 5 章展开"实现"细节（代码流程、关键代码片段）
4. 第 6 章不仅要说"接口通了"，还要给出测试场景、实验数据和分析结论
5. 风险雷达和联合异常排序是系统特色，建议在第 5.6 章充分展开
6. 已退场的旧分支（电商、爬虫、synthetic 数据）仅在必要处简要说明不纳入研究范围
7. 若需压缩篇幅，优先压缩绪论和研究现状铺陈，不压缩第 5 章和第 6 章核心内容
