# DataForge — 基于高级数据结构的多源数据智能管理与分析系统

> 毕业设计完整方案 · Opus 4.6 版本

---

## 一、项目概述

### 1.1 项目背景

在金融市场与电商领域，海量时序数据的高效管理与分析是核心需求。传统数据库在面对特定分析场景时（如任意历史时刻的区间第 K 大查询、批量区间统计）往往性能不足。本项目将 ACM/ICPC 竞赛中的高级数据结构与算法工程化，构建一套**高性能数据分析引擎**，为股票数据和购物平台数据提供远超传统方案的查询与分析能力。

### 1.2 核心创新点

| 创新维度 | 具体内容 |
|---------|---------|
| **算法工程化** | 将主席树、线段树、分块、分治等竞赛算法应用于真实业务场景 |
| **混合语言架构** | C++ 计算引擎 + Python 业务层 + 前端可视化三层协作 |
| **双领域数据** | 同一引擎同时服务金融时序数据与电商交易数据 |
| **性能对比** | 提供与传统 SQL/Pandas 的性能基准测试对比 |

### 1.3 系统命名

**DataForge** — 寓意用算法"锻造"数据价值。

---

## 二、技术架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                     │
│   Dashboard │ Stock Charts │ Shopping Analytics │ Query  │
└──────────────────────┬──────────────────────────────────┘
                       │ REST API / WebSocket
┌──────────────────────┴──────────────────────────────────┐
│              Python Backend (FastAPI)                    │
│  Auth │ DataLoader │ TaskScheduler │ API Gateway        │
└──────┬────────────────────────────────┬─────────────────┘
       │ ctypes/pybind11                │ SQLAlchemy
┌──────┴──────────────┐    ┌───────────┴─────────────────┐
│  C++ Algorithm Core │    │   Database Layer             │
│  (Shared Library)   │    │  PostgreSQL │ Redis │ Files  │
│                     │    │                              │
│  • 主席树引擎       │    │  • 股票历史数据              │
│  • 线段树引擎       │    │  • 购物交易数据              │
│  • 分块引擎         │    │  • 用户与权限数据            │
│  • 分治引擎         │    │  • 算法索引缓存              │
│  • Benchmark 模块   │    │                              │
└─────────────────────┘    └─────────────────────────────┘
```

### 2.2 技术栈明细

| 层级 | 技术 | 语言 | 说明 |
|------|------|------|------|
| 前端 | React 18 + TypeScript | TS/JS | SPA 单页应用 |
| 前端图表 | ECharts / D3.js | JS | 数据可视化 |
| 后端框架 | FastAPI | Python | 异步 Web 框架 |
| 算法引擎 | 自研 .so/.dll 库 | C++17 | 核心计算模块 |
| 语言桥接 | pybind11 | C++/Python | C++ ↔ Python 绑定 |
| 主数据库 | PostgreSQL 15 | SQL | 持久化存储 |
| 缓存 | Redis | - | 热点数据缓存 |
| 任务调度 | Celery + Redis | Python | 异步任务队列 |
| 数据采集 | Scrapy / Tushare API | Python | 爬虫与数据源 |
| 容器化 | Docker + docker-compose | - | 开发与部署 |

---

## 三、算法引擎详细设计（C++ 核心）

> **这是本项目的核心亮点，也是工作量最大的模块。**

### 3.1 主席树模块（Persistent Segment Tree）

#### 3.1.1 业务场景

| 场景 | 查询描述 | 复杂度 |
|------|---------|--------|
| **历史区间第 K 大/小** | 查询某只股票在第 L 天到第 R 天内，价格第 K 大的值 | O(log n) |
| **历史快照回溯** | 回到任意历史版本查看当时的数据状态 | O(log n) |
| **区间排名查询** | 查询某个价格在历史区间 [L,R] 中的排名 | O(log n) |
| **区间内值域统计** | 统计区间 [L,R] 内价格在 [a,b] 范围的天数 | O(log n) |

#### 3.1.2 技术实现要点

```
文件: engine/src/persistent_segtree.h / .cpp

核心数据结构:
  struct Node {
      int left_child, right_child;  // 左右子节点编号
      int count;                     // 值域计数
  };

  class PersistentSegTree {
      vector<Node> tree;     // 节点池（动态开点）
      vector<int> roots;     // 每个版本的根节点
      
      int build(int l, int r);
      int update(int prev, int l, int r, int pos);
      int query_kth(int u, int v, int l, int r, int k);
      int query_rank(int u, int v, int l, int r, int val);
      int query_count(int u, int v, int l, int r, int ql, int qr);
  };

关键设计:
  - 动态开点，节点池预分配 n*40 避免频繁 new
  - 离散化处理价格值域
  - 支持序列化/反序列化到磁盘（持久化索引）
```

#### 3.1.3 扩展：带修改的主席树（树状数组套主席树）

```
用于支持数据的动态插入与删除后仍能高效查询:
  - 使用 BIT (树状数组) 维护 O(log n) 棵主席树
  - 单次修改 O(log²n)，查询 O(log²n)
  - 场景：实时更新股票数据后立即支持历史区间查询
```

---

### 3.2 线段树模块（Segment Tree）

#### 3.2.1 业务场景

| 场景 | 查询描述 | 复杂度 |
|------|---------|--------|
| **区间聚合** | 某时间段内的最大/最小/总和/平均价格 | O(log n) |
| **区间修改** | 批量调整价格（复权计算） | O(log n) |
| **连续最大子段和** | 寻找最佳买入卖出时间段（最大利润区间） | O(log n) |
| **区间合并** | 统计价格连续上涨/下跌的最长天数 | O(log n) |
| **购物数据聚合** | 某时间段内各品类销售额/订单数统计 | O(log n) |

#### 3.2.2 技术实现要点

```
文件: engine/src/segment_tree.h / .cpp

模块一：懒标记线段树（区间修改+区间查询）
  class LazySegTree {
      vector<long long> sum, mx, mn, lazy_add, lazy_mul;
      void push_down(int node);
      void range_add(node, l, r, ql, qr, val);
      void range_multiply(node, l, r, ql, qr, val);
      QueryResult range_query(node, l, r, ql, qr);
  };

模块二：最大子段和线段树
  struct Info {
      long long prefix_max, suffix_max, total_max, sum;
  };
  - 用于寻找股票最佳买卖时机
  - pushup 时合并左右子区间信息

模块三：动态开点权值线段树
  - 用于实时维护价格/销售额的分布直方图
  - 支持在线查询中位数、百分位数
```

---

### 3.3 分块模块（Block Decomposition / Sqrt Decomposition）

#### 3.3.1 业务场景

| 场景 | 查询描述 | 复杂度 |
|------|---------|--------|
| **Mo's 算法离线查询** | 批量处理大量区间不同值计数查询 | O((n+q)√n) |
| **带修改的 Mo's** | 支持数据更新的离线区间查询 | O(n^(5/3)) |
| **区间众数** | 查询某时间段内出现最多的价格/商品 | O(√n) |
| **值域分块** | 对价格/销售额进行分段统计 | O(√n) |

#### 3.3.2 技术实现要点

```
文件: engine/src/block_decomp.h / .cpp

模块一：Mo's Algorithm 引擎
  class MoEngine {
      int block_size;
      struct Query { int l, r, id; };
      
      void add(int pos);
      void remove(int pos);
      vector<int> solve(vector<Query>& queries);
  };
  
  应用场景:
    - 查询任意时间段 [L,R] 内不同价格档位的数量
    - 查询任意时间段 [L,R] 内不同商品种类数
    - 批量处理用户的多个历史区间查询请求

模块二：带修改 Mo's (Mo's with Updates)
  struct QueryWithTime { int l, r, time, id; };
  - block_size = n^(2/3)
  - 支持：先修改某些数据点，再查询历史区间

模块三：值域分块
  class ValueBlock {
      vector<int> block_count;
      vector<int> exact_count;
      int query_mode(int l, int r);
      int query_quantile(int l, int r, double p);
  };
```

---

### 3.4 分治模块（Divide and Conquer）

#### 3.4.1 业务场景

| 场景 | 算法 | 复杂度 |
|------|------|--------|
| **逆序对统计** | 归并排序分治 | O(n log n) |
| **CDQ 分治多维偏序** | CDQ 分治 + BIT | O(n log²n) |
| **最近点对** | 平面分治 | O(n log n) |
| **大整数乘法** | Karatsuba / NTT | O(n log n) |

#### 3.4.2 技术实现要点

```
文件: engine/src/divide_conquer.h / .cpp

模块一：逆序对与趋势分析
  long long count_inversions(vector<int>& prices);
  - 衡量股票价格的"混乱程度" → 波动性指标
  - 对比不同时间段的逆序对数量变化

模块二：CDQ 分治 — 三维偏序查询
  struct Order { int time, price, volume; };
  场景：查询满足 time ≤ T, price ≤ P, volume ≥ V 的订单数
  - 第一维排序，第二维 CDQ 分治，第三维 BIT
  - 电商场景：多维筛选高价值订单

模块三：股票形态匹配（最近点对变体）
  - 将股票走势转化为高维特征向量
  - 使用分治法寻找历史上最相似的走势模式

模块四：大规模数据的分治聚合
  - 对超大数据集分治计算统计量
  - 外部排序（External Sort）的分治实现
```

---

### 3.5 C++ 引擎项目结构

```
engine/
├── CMakeLists.txt
├── include/
│   ├── persistent_segtree.h
│   ├── segment_tree.h
│   ├── block_decomp.h
│   ├── divide_conquer.h
│   ├── benchmark.h
│   └── serialization.h
├── src/
│   ├── persistent_segtree.cpp
│   ├── segment_tree.cpp
│   ├── block_decomp.cpp
│   ├── divide_conquer.cpp
│   ├── benchmark.cpp
│   └── serialization.cpp
├── bindings/
│   └── pybind_module.cpp        # pybind11 绑定层
├── tests/
│   ├── test_persistent_segtree.cpp
│   ├── test_segment_tree.cpp
│   ├── test_block_decomp.cpp
│   └── test_divide_conquer.cpp
└── benchmarks/
    └── bench_vs_baseline.cpp
```

**pybind11 绑定示例：**

```cpp
// bindings/pybind_module.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "persistent_segtree.h"
#include "segment_tree.h"

namespace py = pybind11;

PYBIND11_MODULE(dataforge_engine, m) {
    py::class_<PersistentSegTree>(m, "PersistentSegTree")
        .def(py::init<const std::vector<int>&>())
        .def("query_kth", &PersistentSegTree::query_kth)
        .def("query_rank", &PersistentSegTree::query_rank)
        .def("query_count_in_range", &PersistentSegTree::query_count_in_range);
    
    py::class_<LazySegTree>(m, "LazySegTree")
        .def(py::init<const std::vector<long long>&>())
        .def("range_query", &LazySegTree::range_query)
        .def("range_update", &LazySegTree::range_update)
        .def("max_subarray", &LazySegTree::max_subarray);
}
```

---

## 四、Python 后端详细设计

### 4.1 项目结构

```
backend/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # 配置管理
│   ├── dependencies.py         # 依赖注入
│   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── stock.py
│   │   ├── shopping.py
│   │   └── user.py
│   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── stock.py
│   │   ├── shopping.py
│   │   └── query.py
│   ├── api/                    # API 路由
│   │   ├── v1/
│   │   │   ├── stock.py
│   │   │   ├── shopping.py
│   │   │   ├── algorithm.py
│   │   │   ├── benchmark.py
│   │   │   └── auth.py
│   │   └── router.py
│   ├── services/               # 业务逻辑层
│   │   ├── stock_service.py
│   │   ├── shopping_service.py
│   │   ├── engine_service.py   # C++ 引擎调用封装
│   │   └── benchmark_service.py
│   ├── core/
│   │   ├── security.py         # JWT 认证
│   │   ├── engine_bridge.py    # pybind11 桥接层
│   │   └── cache.py            # Redis 缓存
│   └── tasks/                  # Celery 异步任务
│       ├── data_sync.py
│       ├── index_build.py
│       └── report_gen.py
├── scripts/
│   ├── crawl_stock.py          # 股票数据爬虫
│   ├── crawl_shopping.py       # 购物数据生成器
│   ├── init_db.py
│   └── seed_data.py
├── tests/
├── requirements.txt
└── Dockerfile
```

### 4.2 核心 API 设计

| 方法 | 路径 | 功能 | 涉及算法 |
|------|------|------|---------|
| GET | `/api/v1/stock/{code}/kth` | 区间第 K 大价格 | 主席树 |
| GET | `/api/v1/stock/{code}/rank` | 价格历史排名 | 主席树 |
| GET | `/api/v1/stock/{code}/snapshot/{ver}` | 历史快照 | 主席树 |
| GET | `/api/v1/stock/{code}/range-stats` | 区间聚合统计 | 线段树 |
| GET | `/api/v1/stock/{code}/best-trade` | 最大利润区间 | 线段树 |
| GET | `/api/v1/stock/{code}/volatility` | 波动性分析 | 分治 |
| POST | `/api/v1/stock/pattern-match` | K线形态匹配 | 分治 |
| POST | `/api/v1/shopping/batch-distinct` | 批量区间不同值统计 | 分块 |
| GET | `/api/v1/shopping/mode` | 区间众数查询 | 分块 |
| POST | `/api/v1/shopping/multi-filter` | 多维偏序筛选 | CDQ分治 |
| POST | `/api/v1/benchmark/compare` | 算法 vs SQL 性能对比 | Benchmark |

### 4.3 数据采集模块

```python
# 股票数据：使用 Tushare / AKShare API
class StockCrawler:
    """采集A股日K线数据，覆盖约 5000 只股票 × 10 年"""
    def fetch_daily(self, code, start, end) -> pd.DataFrame
    def fetch_realtime(self, code) -> dict
    def store_to_db(self, df, code)

# 购物数据：程序化模拟生成
class ShoppingDataGenerator:
    """基于统计模型生成逼真的购物数据"""
    def generate_orders(self, n) -> pd.DataFrame
    def generate_products(self, n) -> pd.DataFrame
    def generate_users(self, n) -> pd.DataFrame
```

---

## 五、前端详细设计

### 5.1 项目结构

```
frontend/
├── src/
│   ├── components/
│   │   ├── Layout/
│   │   ├── Charts/
│   │   │   ├── CandlestickChart.tsx
│   │   │   ├── VolumeChart.tsx
│   │   │   ├── DistributionChart.tsx
│   │   │   └── HeatmapChart.tsx
│   │   ├── Query/
│   │   │   ├── KthQueryPanel.tsx
│   │   │   ├── RangeQueryPanel.tsx
│   │   │   └── PatternMatchPanel.tsx
│   │   ├── Algorithm/
│   │   │   ├── TreeVisualizer.tsx
│   │   │   └── BenchmarkChart.tsx
│   │   └── DataTable/
│   ├── pages/
│   │   ├── Dashboard.tsx
│   │   ├── StockAnalysis.tsx
│   │   ├── ShoppingAnalysis.tsx
│   │   ├── AlgorithmLab.tsx
│   │   ├── BenchmarkPage.tsx
│   │   └── DataManagement.tsx
│   ├── services/
│   ├── stores/
│   └── utils/
├── package.json
└── Dockerfile
```

### 5.2 核心页面功能

| 页面 | 核心功能 |
|------|---------|
| **Dashboard** | 数据总览、实时指标卡片、快捷查询入口 |
| **StockAnalysis** | K线图 + 区间查询面板 + 第K大查询 + 最佳买卖区间高亮 |
| **ShoppingAnalysis** | 销售趋势图 + 品类分布 + 多维筛选 + 众数统计 |
| **AlgorithmLab** | 算法结构可视化（树形图展示线段树/主席树节点）+ 步骤动画 |
| **BenchmarkPage** | 算法 vs 传统方案性能对比柱状图/折线图 |
| **DataManagement** | 数据 CRUD + 导入/导出 + 数据源配置 |

---

## 六、数据库设计

### 6.1 核心表结构

```sql
-- 股票日K线表
CREATE TABLE stock_daily (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(10) NOT NULL,
    trade_date DATE NOT NULL,
    open_price DECIMAL(10,2),
    close_price DECIMAL(10,2),
    high_price DECIMAL(10,2),
    low_price DECIMAL(10,2),
    volume BIGINT,
    amount DECIMAL(16,2),
    UNIQUE(code, trade_date)
);

-- 购物订单表
CREATE TABLE shopping_order (
    id BIGSERIAL PRIMARY KEY,
    order_no VARCHAR(32) UNIQUE,
    user_id INT REFERENCES users(id),
    product_id INT REFERENCES products(id),
    category_id INT,
    quantity INT,
    unit_price DECIMAL(10,2),
    total_amount DECIMAL(12,2),
    order_time TIMESTAMP NOT NULL,
    status VARCHAR(20)
);

-- 商品表
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200),
    category_id INT,
    brand VARCHAR(100),
    price DECIMAL(10,2),
    stock_quantity INT
);

-- 算法索引元数据表
CREATE TABLE algo_index (
    id SERIAL PRIMARY KEY,
    data_source VARCHAR(50),
    source_key VARCHAR(50),
    algo_type VARCHAR(50),
    index_file_path TEXT,
    data_count INT,
    build_time_ms INT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE,
    password_hash VARCHAR(200),
    role VARCHAR(20) DEFAULT 'user',
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 七、性能基准测试模块

### 7.1 对比方案

| 查询类型 | DataForge (C++) | 传统方案 | 预期加速比 |
|---------|----------------|---------|-----------|
| 区间第 K 大 | 主席树 O(log n) | SQL ORDER BY OFFSET | **100x~1000x** |
| 区间聚合 | 线段树 O(log n) | SQL SUM/MAX O(n) | **10x~100x** |
| 批量区间不同值 | Mo's O((n+q)√n) | 逐个 SQL DISTINCT | **10x~50x** |
| 多维偏序 | CDQ O(n log²n) | 多字段索引嵌套查询 | **5x~20x** |

### 7.2 测试规模

- 小规模：n = 10,000（验证正确性）
- 中规模：n = 1,000,000（展示性能优势）
- 大规模：n = 10,000,000（极限压测）

---

## 八、项目目录总览

```
graduation-project/
├── engine/              # C++ 算法引擎 (~4000 行)
├── backend/             # Python 后端 (~3000 行)
├── frontend/            # React 前端 (~3000 行)
├── docker-compose.yml   # 一键部署
├── docs/                # 项目文档
├── data/                # 示例数据
└── README.md
```

---

## 九、开发计划（共 16 周）

### 阶段一：基础搭建（第 1~3 周）

- [ ] 搭建项目仓库与 CI/CD
- [ ] PostgreSQL + Redis Docker 环境
- [ ] FastAPI 项目骨架（认证、CORS、错误处理）
- [ ] React 项目骨架（路由、布局、主题）
- [ ] 数据库 migration
- [ ] 股票数据爬虫与数据入库

### 阶段二：C++ 引擎核心（第 4~8 周）⭐ 重点

- [ ] 主席树：实现、单元测试、pybind11 绑定
- [ ] 线段树（懒标记 + 最大子段和）：实现、测试、绑定
- [ ] 分块（Mo's + 值域分块）：实现、测试、绑定
- [ ] 分治（逆序对 + CDQ + 最近点对）：实现、测试、绑定
- [ ] 索引序列化/反序列化
- [ ] C++ 单元测试全覆盖 (Google Test)
- [ ] 性能基准测试框架

### 阶段三：后端业务开发（第 9~11 周）

- [ ] 股票数据 CRUD API
- [ ] 购物数据 CRUD API + 数据生成器
- [ ] 算法引擎调用服务层
- [ ] 异步任务：索引构建、数据同步
- [ ] Redis 缓存策略
- [ ] API 文档（Swagger 自动生成）
- [ ] 后端测试

### 阶段四：前端开发（第 12~14 周）

- [ ] Dashboard 仪表盘
- [ ] 股票分析页（K线图 + 查询面板）
- [ ] 购物分析页（图表 + 多维筛选）
- [ ] 算法可视化实验室
- [ ] 性能对比展示页
- [ ] 数据管理页（CRUD）
- [ ] 响应式适配

### 阶段五：集成与论文（第 15~16 周）

- [ ] 全链路集成测试
- [ ] 性能基准测试报告
- [ ] Docker 一键部署验证
- [ ] 毕业论文撰写
- [ ] 答辩 PPT 准备

---

## 十、工作量评估

| 模块 | 代码量预估 | 语言 | 难度 |
|------|-----------|------|------|
| C++ 算法引擎 | ~4,000 行 | C++17 | ⭐⭐⭐⭐⭐ |
| pybind11 绑定 | ~500 行 | C++/Python | ⭐⭐⭐ |
| Python 后端 | ~3,000 行 | Python | ⭐⭐⭐ |
| 数据采集脚本 | ~800 行 | Python | ⭐⭐ |
| React 前端 | ~3,000 行 | TypeScript | ⭐⭐⭐ |
| 测试代码 | ~1,500 行 | C++/Python | ⭐⭐ |
| 部署与文档 | ~500 行 | YAML/MD | ⭐ |
| **总计** | **~13,300 行** | **多语言** | - |

---

## 十一、学术价值与答辩亮点

### 11.1 论文核心章节建议

1. **绪论**：研究背景、问题分析、研究意义
2. **相关技术综述**：持久化数据结构、区间查询算法、混合语言架构
3. **系统设计**：整体架构、算法引擎设计、数据库设计
4. **算法实现与优化**：四大核心算法的实现细节与工程化优化
5. **系统实现**：前后端实现、语言桥接、部署方案
6. **实验与分析**：性能基准测试结果、与传统方案对比图表
7. **总结与展望**

### 11.2 答辩亮点

| 亮点 | 展示方式 |
|------|---------|
| 区间第K大查询比传统SQL快1000倍 | 现场 Demo + 性能对比图 |
| 主席树实现数据零成本历史回溯 | 演示任意历史版本秒级恢复 |
| C++ 引擎通过 pybind11 无缝集成 Python | 展示跨语言调用链路 |
| 算法实验室可视化线段树构建过程 | 现场演示动画 |

---

## 十二、风险与应对

| 风险 | 应对方案 |
|------|---------|
| C++ 编译环境兼容性 | Docker 容器化编译 |
| pybind11 数据传输瓶颈 | numpy buffer protocol 零拷贝传输 |
| 数据采集被反爬 | 模拟数据生成器作为 Plan B |
| 前端大量数据渲染卡顿 | 数据降采样 + ECharts GL |
| 算法正确性验证 | 与暴力算法交叉验证 (stress test) |

---

## 十三、数据流与交互时序

### 13.1 算法查询完整数据流

```
用户在前端发起"区间第K大"查询
         │
         ▼
[React] ──HTTP GET──▶ [FastAPI Router: /api/v1/stock/{code}/kth?l=100&r=500&k=3]
                              │
                              ▼
                     [engine_service.py]
                       ├── 1. 查询 Redis 缓存 → 命中则直接返回
                       ├── 2. 未命中 → 查询 algo_index 表获取索引文件路径
                       ├── 3. 若索引不存在 → 从 DB 加载原始数据 → 构建主席树 → 序列化索引
                       ├── 4. 反序列化索引文件 → 加载到 C++ PersistentSegTree 对象
                       └── 5. 调用 pybind11: engine.query_kth(l, r, k)
                              │
                              ▼
                     [C++ PersistentSegTree::query_kth]
                       ├── 取 roots[l-1] 和 roots[r]
                       ├── 在值域线段树上二分
                       └── 返回离散化逆映射后的真实价格
                              │
                              ▼
                     [engine_service.py]
                       ├── 将结果写入 Redis 缓存 (TTL=300s)
                       └── 封装为 Pydantic Response
                              │
                              ▼
                     [FastAPI] ──JSON Response──▶ [React 前端渲染结果]
```

### 13.2 索引构建异步流程

```
[用户上传数据 / 定时任务触发]
         │
         ▼
[Celery Task: index_build.py]
  ├── 1. 从 PostgreSQL 读取指定股票/品类的全量数据
  ├── 2. 数据预处理（离散化、排序、清洗）
  ├── 3. 调用 C++ 引擎构建各类索引
  │     ├── PersistentSegTree.build(data)
  │     ├── LazySegTree.build(data)
  │     ├── MoEngine.preprocess(data)
  │     └── DivideConquer.preprocess(data)
  ├── 4. 序列化索引到磁盘 (engine/data/{source}_{key}_{algo}.idx)
  ├── 5. 更新 algo_index 表（路径、数据量、构建耗时）
  └── 6. 清除相关 Redis 缓存
```

### 13.3 实时数据推送（WebSocket）

```python
# app/api/v1/websocket.py
@router.websocket("/ws/stock/{code}")
async def stock_realtime(websocket: WebSocket, code: str):
    await websocket.accept()
    while True:
        # 从 Redis Pub/Sub 订阅实时价格更新
        price_data = await redis_subscriber.get_message(f"stock:{code}")
        if price_data:
            # 增量更新线段树
            engine_service.incremental_update(code, price_data)
            # 推送给前端
            await websocket.send_json({
                "type": "price_update",
                "code": code,
                "data": price_data,
                "computed": {
                    "current_rank": engine_service.query_rank(code, price_data["close"]),
                    "day_max_profit": engine_service.query_best_trade(code),
                }
            })
        await asyncio.sleep(1)
```

---

## 十四、API 请求/响应示例

### 14.1 区间第 K 大查询

**请求：**
```http
GET /api/v1/stock/600519/kth?start_day=1&end_day=2000&k=5
Authorization: Bearer <jwt_token>
```

**响应：**
```json
{
    "code": 200,
    "data": {
        "stock_code": "600519",
        "range": [1, 2000],
        "k": 5,
        "kth_price": 1856.50,
        "kth_date": "2021-02-10",
        "query_time_us": 12,
        "algorithm": "persistent_segment_tree",
        "index_info": {
            "data_points": 2430,
            "index_size_kb": 384,
            "build_time_ms": 45
        }
    }
}
```

### 14.2 最佳买卖区间查询

**请求：**
```http
GET /api/v1/stock/000001/best-trade?start_day=1&end_day=1000
```

**响应：**
```json
{
    "code": 200,
    "data": {
        "stock_code": "000001",
        "buy_day": 234,
        "buy_date": "2019-03-15",
        "buy_price": 9.82,
        "sell_day": 567,
        "sell_date": "2020-06-30",
        "sell_price": 18.45,
        "max_profit": 8.63,
        "profit_rate": "87.88%",
        "query_time_us": 8,
        "algorithm": "segment_tree_max_subarray"
    }
}
```

### 14.3 批量区间不同值查询（Mo's 算法）

**请求：**
```http
POST /api/v1/shopping/batch-distinct
Content-Type: application/json

{
    "data_source": "orders",
    "field": "category_id",
    "queries": [
        {"l": 1, "r": 5000},
        {"l": 200, "r": 8000},
        {"l": 3000, "r": 10000}
    ]
}
```

**响应：**
```json
{
    "code": 200,
    "data": {
        "results": [
            {"query_id": 0, "l": 1, "r": 5000, "distinct_count": 42},
            {"query_id": 1, "l": 200, "r": 8000, "distinct_count": 56},
            {"query_id": 2, "l": 3000, "r": 10000, "distinct_count": 48}
        ],
        "total_queries": 3,
        "total_time_us": 1580,
        "algorithm": "mo_algorithm",
        "block_size": 316
    }
}
```

### 14.4 CDQ 分治多维偏序筛选

**请求：**
```http
POST /api/v1/shopping/multi-filter
Content-Type: application/json

{
    "constraints": {
        "time_before": "2024-06-01",
        "price_max": 500.00,
        "quantity_min": 3
    },
    "return_count": true,
    "return_top_k": 10
}
```

**响应：**
```json
{
    "code": 200,
    "data": {
        "matching_count": 12847,
        "top_k_orders": [
            {"order_no": "ORD20240315001", "amount": 499.50, "quantity": 15},
            {"order_no": "ORD20240228042", "amount": 498.00, "quantity": 12}
        ],
        "query_time_us": 3200,
        "algorithm": "cdq_divide_conquer",
        "dimensions": 3
    }
}
```

### 14.5 性能对比接口

**请求：**
```http
POST /api/v1/benchmark/compare
Content-Type: application/json

{
    "query_type": "kth_largest",
    "data_sizes": [10000, 100000, 1000000],
    "query_count": 1000,
    "methods": ["persistent_segtree", "sql_sort", "pandas_nlargest"]
}
```

**响应：**
```json
{
    "code": 200,
    "data": {
        "results": [
            {
                "data_size": 10000,
                "persistent_segtree": {"build_ms": 12, "avg_query_us": 3.2, "total_ms": 15.2},
                "sql_sort": {"avg_query_us": 850, "total_ms": 850},
                "pandas_nlargest": {"avg_query_us": 1200, "total_ms": 1200}
            },
            {
                "data_size": 1000000,
                "persistent_segtree": {"build_ms": 980, "avg_query_us": 4.8, "total_ms": 985.8},
                "sql_sort": {"avg_query_us": 45000, "total_ms": 45000},
                "pandas_nlargest": {"avg_query_us": 98000, "total_ms": 98000}
            }
        ],
        "speedup_summary": {
            "vs_sql": "最高 9375x 加速",
            "vs_pandas": "最高 20416x 加速"
        }
    }
}
```

---

## 十五、安全设计

### 15.1 认证与授权

```python
# app/core/security.py
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"])

class AuthManager:
    SECRET_KEY = config.SECRET_KEY
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE = timedelta(hours=24)

    def create_token(self, user_id: int, role: str) -> str:
        payload = {
            "sub": str(user_id),
            "role": role,
            "exp": datetime.utcnow() + self.ACCESS_TOKEN_EXPIRE
        }
        return jwt.encode(payload, self.SECRET_KEY, algorithm=self.ALGORITHM)

    def verify_token(self, token: str) -> dict:
        return jwt.decode(token, self.SECRET_KEY, algorithms=[self.ALGORITHM])
```

### 15.2 RBAC 角色权限模型

| 角色 | 数据查看 | 数据修改 | 算法查询 | Benchmark | 用户管理 |
|------|---------|---------|---------|-----------|---------|
| visitor | ✅ (限流) | ❌ | ❌ | ❌ | ❌ |
| user | ✅ | ❌ | ✅ | ✅ | ❌ |
| editor | ✅ | ✅ | ✅ | ✅ | ❌ |
| admin | ✅ | ✅ | ✅ | ✅ | ✅ |

### 15.3 API 限流策略

```python
# app/core/rate_limit.py
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

# 不同接口的限流规则
RATE_LIMITS = {
    "auth": "10/minute",         # 登录接口：防暴力破解
    "query_simple": "60/minute", # 简单查询
    "query_algo": "20/minute",   # 算法查询（计算密集）
    "benchmark": "5/minute",     # 性能对比（资源消耗大）
    "data_import": "3/minute",   # 数据导入
}
```

### 15.4 输入校验与安全防护

- **SQL 注入防护**: 全部使用 SQLAlchemy ORM 参数化查询，禁止原始 SQL 拼接
- **XSS 防护**: 前端使用 React 自动转义 + CSP Header
- **CORS 配置**: 仅允许白名单域名访问
- **数据校验**: Pydantic 模型强类型校验所有入参
- **文件上传**: 限制类型（csv/xlsx）、大小（50MB），沙箱路径存储

---

## 十六、扩展数据库设计

### 16.1 补充表结构

```sql
-- 商品分类表
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    parent_id INT REFERENCES categories(id),
    level INT DEFAULT 1,
    sort_order INT DEFAULT 0
);

-- 股票基本信息表
CREATE TABLE stock_info (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(50) NOT NULL,
    industry VARCHAR(50),
    market VARCHAR(10),           -- 'SH' / 'SZ'
    list_date DATE,
    status VARCHAR(10) DEFAULT 'active'
);

-- 查询日志表（用于分析热点查询、优化缓存）
CREATE TABLE query_log (
    id BIGSERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    query_type VARCHAR(50),       -- 'kth' / 'range_stats' / 'mo_distinct' 等
    algorithm VARCHAR(50),
    data_source VARCHAR(50),
    source_key VARCHAR(50),
    params JSONB,                 -- 查询参数
    result_time_us INT,           -- 查询耗时（微秒）
    cache_hit BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 基准测试结果表
CREATE TABLE benchmark_result (
    id SERIAL PRIMARY KEY,
    test_name VARCHAR(100),
    data_size INT,
    query_count INT,
    method VARCHAR(50),
    build_time_ms FLOAT,
    avg_query_us FLOAT,
    p50_query_us FLOAT,
    p99_query_us FLOAT,
    memory_mb FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 数据导入任务表
CREATE TABLE import_task (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    source_type VARCHAR(20),      -- 'csv' / 'api' / 'crawl'
    target_table VARCHAR(50),
    file_path TEXT,
    total_rows INT,
    imported_rows INT DEFAULT 0,
    status VARCHAR(20) DEFAULT 'pending',  -- pending/running/done/failed
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 16.2 索引设计

```sql
-- 高频查询优化索引
CREATE INDEX idx_stock_daily_code_date ON stock_daily(code, trade_date);
CREATE INDEX idx_stock_daily_code_close ON stock_daily(code, close_price);
CREATE INDEX idx_order_time ON shopping_order(order_time);
CREATE INDEX idx_order_user ON shopping_order(user_id);
CREATE INDEX idx_order_category ON shopping_order(category_id);
CREATE INDEX idx_query_log_type_time ON query_log(query_type, created_at);
CREATE INDEX idx_algo_index_source ON algo_index(data_source, source_key, algo_type);
```

### 16.3 ER 关系图

```
┌──────────┐     ┌───────────────┐     ┌──────────┐
│  users   │────<│ shopping_order│>────│ products │
└──────────┘     └───────────────┘     └──────────┘
     │                  │                    │
     │                  │                    │
     ▼                  ▼                    ▼
┌──────────┐     ┌──────────────┐     ┌──────────┐
│query_log │     │  categories  │     │stock_info│
└──────────┘     └──────────────┘     └──────────┘
                                           │
┌──────────────┐  ┌─────────────────┐      │
│ algo_index   │  │benchmark_result │  ┌───┴──────┐
└──────────────┘  └─────────────────┘  │stock_daily│
                                       └──────────┘
┌──────────────┐
│ import_task  │
└──────────────┘
```

---

## 十七、C++ 索引序列化协议

### 17.1 二进制文件格式

```
┌──────────────────────────────────────────────────┐
│ Magic Number: "DFGE" (4 bytes)                   │  文件头
│ Version: uint32 (4 bytes)                        │
│ Algorithm Type: uint8 (1 byte)                   │
│   0x01=PersistentSegTree, 0x02=SegTree,          │
│   0x03=BlockDecomp, 0x04=DivideConquer           │
│ Data Count: uint64 (8 bytes)                     │
│ Node Count: uint64 (8 bytes)                     │
│ Checksum: uint32 (4 bytes, CRC32)                │
├──────────────────────────────────────────────────┤
│ Discretization Map Section                       │  离散化映射
│   Map Size: uint32                               │
│   [original_value: int64, mapped_id: int32] × N  │
├──────────────────────────────────────────────────┤
│ Root Array Section (主席树专用)                   │  版本根节点
│   Root Count: uint32                             │
│   [root_id: int32] × N                           │
├──────────────────────────────────────────────────┤
│ Node Pool Section                                │  节点池
│   [left: int32, right: int32, count: int32] × M  │
└──────────────────────────────────────────────────┘
```

### 17.2 序列化/反序列化接口

```cpp
// include/serialization.h
class IndexSerializer {
public:
    // 序列化到文件
    static bool save(const PersistentSegTree& tree, const std::string& path);
    static bool save(const LazySegTree& tree, const std::string& path);
    static bool save(const MoEngine& engine, const std::string& path);

    // 从文件反序列化
    static PersistentSegTree load_persistent_segtree(const std::string& path);
    static LazySegTree load_lazy_segtree(const std::string& path);
    static MoEngine load_mo_engine(const std::string& path);

private:
    static constexpr char MAGIC[] = "DFGE";
    static constexpr uint32_t VERSION = 1;

    static void write_header(std::ofstream& out, uint8_t algo_type,
                             uint64_t data_count, uint64_t node_count);
    static bool verify_header(std::ifstream& in, uint8_t expected_algo);
    static uint32_t compute_checksum(const void* data, size_t len);
};
```

---

## 十八、前端详细交互设计

### 18.1 Dashboard 仪表盘布局

```
┌─────────────────────────────────────────────────────────────┐
│  [Logo] DataForge           [搜索栏]        [用户头像] ▼    │
├─────┬───────────────────────────────────────────────────────┤
│     │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ 导  │  │ 股票总数 │ │ 订单总数 │ │ 索引数量 │ │ 今日查询 │ │
│ 航  │  │  5,230   │ │ 2.8M     │ │   42     │ │  1,256   │ │
│ 栏  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │
│     │  ┌──────────────────────┐ ┌──────────────────────────┐│
│  📊 │  │                      │ │                          ││
│  📈 │  │   大盘指数走势图     │ │    品类销售额饼图        ││
│  🛒 │  │   (ECharts K线)      │ │    (ECharts Pie)         ││
│  🧪 │  │                      │ │                          ││
│  ⚡ │  └──────────────────────┘ └──────────────────────────┘│
│  📁 │  ┌──────────────────────┐ ┌──────────────────────────┐│
│     │  │  最近查询记录        │ │    算法引擎状态          ││
│     │  │  · 600519 第3大 12µs │ │    主席树: 12个索引 ✅   ││
│     │  │  · Mo's 3查询 1.5ms  │ │    线段树: 8个索引 ✅    ││
│     │  │  · CDQ 筛选 3.2ms    │ │    分块:   5个索引 ✅    ││
│     │  └──────────────────────┘ └──────────────────────────┘│
└─────┴───────────────────────────────────────────────────────┘
```

### 18.2 股票分析页交互流程

```
1. 用户在搜索框输入股票代码 → 自动补全下拉列表
2. 选中后加载该股票的 K线图（默认显示最近 1 年）
3. 用户可通过时间轴滑块选择分析区间 [L, R]
4. 右侧面板显示可用查询：
   ├── [区间第K大] → 输入 K → 点击查询 → 结果高亮在K线图上
   ├── [区间统计] → 显示 max/min/avg/sum 卡片
   ├── [最佳买卖] → 买入/卖出点用箭头标注在K线图上
   ├── [波动性] → 显示逆序对数量 + 趋势图
   └── [形态匹配] → 显示历史相似走势列表 + 叠加对比图
5. 每次查询结果底部显示：算法名称、耗时、数据规模
```

### 18.3 算法实验室可视化

```
┌─────────────────────────────────────────────────────────┐
│  算法实验室                                              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  选择算法: [主席树 ▼]    数据规模: [20 ▼]               │
│  操作: [构建] [插入] [查询第K大] [单步/自动]             │
│                                                         │
│  ┌───────────────────────────────────────┐              │
│  │                                       │              │
│  │     线段树/主席树 节点可视化           │              │
│  │     (D3.js 树形图 + 动画)             │              │
│  │                                       │              │
│  │        [23]                            │              │
│  │       /    \                           │              │
│  │     [12]   [11]   ← 当前访问节点高亮  │              │
│  │    /  \   /  \                         │              │
│  │  [5] [7][6] [5]                        │              │
│  │                                       │              │
│  └───────────────────────────────────────┘              │
│                                                         │
│  执行日志:                                               │
│  > Step 1: 进入根节点 [23], 左子计数=12, k=5 ≤ 12       │
│  > Step 2: 进入左子 [12], 左子计数=5, k=5 ≤ 5           │
│  > Step 3: 进入左子 [5], 到达叶节点, 返回值 = 156.80    │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 十九、Docker 部署架构

### 19.1 docker-compose.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: dataforge
      POSTGRES_USER: dataforge
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./backend/scripts/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dataforge"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"

  engine-builder:
    build:
      context: ./engine
      dockerfile: Dockerfile
    volumes:
      - engine-lib:/app/build/lib

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql://dataforge:${DB_PASSWORD}@postgres:5432/dataforge
      REDIS_URL: redis://redis:6379/0
      ENGINE_LIB_PATH: /app/engine/lib
    volumes:
      - engine-lib:/app/engine/lib
      - index-data:/app/data/indices
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
      engine-builder:
        condition: service_completed_successfully

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: celery -A app.tasks worker -l info -c 4
    environment:
      DATABASE_URL: postgresql://dataforge:${DB_PASSWORD}@postgres:5432/dataforge
      REDIS_URL: redis://redis:6379/0
      ENGINE_LIB_PATH: /app/engine/lib
    volumes:
      - engine-lib:/app/engine/lib
      - index-data:/app/data/indices
    depends_on:
      - backend

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  pgdata:
  engine-lib:
  index-data:
```

### 19.2 C++ 引擎 Dockerfile

```dockerfile
# engine/Dockerfile
FROM gcc:12 AS builder

RUN apt-get update && apt-get install -y cmake python3-dev

# 安装 pybind11
RUN pip3 install pybind11 && \
    pip3 install pybind11[global]

WORKDIR /app
COPY . .

RUN mkdir build && cd build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release \
             -DPYTHON_EXECUTABLE=$(which python3) && \
    make -j$(nproc)

# 输出编译产物到共享 volume
RUN mkdir -p /app/build/lib && \
    cp build/dataforge_engine*.so /app/build/lib/ && \
    cp build/libdataforge_core.so /app/build/lib/
```

### 19.3 一键启动命令

```bash
# 开发环境
docker-compose up -d

# 生产环境（带构建）
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 初始化数据库 + 导入示例数据
docker-compose exec backend python scripts/init_db.py
docker-compose exec backend python scripts/seed_data.py

# 构建全量索引
docker-compose exec backend python -c "from app.tasks.index_build import build_all; build_all.delay()"
```

---

## 二十、测试策略

### 20.1 C++ 引擎测试 (Google Test)

```cpp
// tests/test_persistent_segtree.cpp
#include <gtest/gtest.h>
#include "persistent_segtree.h"
#include <random>
#include <algorithm>

class PSTTest : public ::testing::Test {
protected:
    std::mt19937 rng{42};
};

// 正确性测试：与暴力算法交叉验证
TEST_F(PSTTest, KthQueryCorrectness) {
    int n = 10000;
    std::vector<int> data(n);
    for (int i = 0; i < n; i++) data[i] = rng() % 1000000;

    PersistentSegTree pst(data);

    // 随机 1000 组查询，与排序暴力对比
    for (int q = 0; q < 1000; q++) {
        int l = rng() % n, r = rng() % n;
        if (l > r) std::swap(l, r);
        int k = rng() % (r - l + 1) + 1;

        int pst_result = pst.query_kth(l, r, k);

        // 暴力：取子数组排序后取第k个
        std::vector<int> sub(data.begin() + l, data.begin() + r + 1);
        std::sort(sub.begin(), sub.end());
        int brute_result = sub[k - 1];

        EXPECT_EQ(pst_result, brute_result)
            << "Failed: l=" << l << " r=" << r << " k=" << k;
    }
}

// 边界测试
TEST_F(PSTTest, SingleElement) { /* ... */ }
TEST_F(PSTTest, AllSameValues) { /* ... */ }
TEST_F(PSTTest, MaxDataSize) { /* ... */ }

// 性能测试
TEST_F(PSTTest, PerformanceBenchmark) {
    int n = 1000000;
    std::vector<int> data(n);
    for (int i = 0; i < n; i++) data[i] = rng() % 1000000000;

    auto t0 = std::chrono::high_resolution_clock::now();
    PersistentSegTree pst(data);
    auto t1 = std::chrono::high_resolution_clock::now();

    double build_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    EXPECT_LT(build_ms, 5000) << "Build too slow for n=1M";

    // 10000 次查询
    auto t2 = std::chrono::high_resolution_clock::now();
    for (int q = 0; q < 10000; q++) {
        int l = rng() % n, r = rng() % n;
        if (l > r) std::swap(l, r);
        int k = rng() % (r - l + 1) + 1;
        volatile int res = pst.query_kth(l, r, k);
    }
    auto t3 = std::chrono::high_resolution_clock::now();

    double query_us = std::chrono::duration<double, std::micro>(t3 - t2).count() / 10000;
    EXPECT_LT(query_us, 50) << "Avg query should be < 50µs for n=1M";

    std::cout << "[PERF] Build: " << build_ms << "ms, Avg Query: " << query_us << "µs\n";
}
```

### 20.2 Python 后端测试 (pytest)

```python
# tests/test_stock_api.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def auth_headers(client):
    resp = await client.post("/api/v1/auth/login", json={
        "username": "test_user", "password": "test_pass"
    })
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}

class TestStockAPI:
    async def test_kth_query(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/stock/600519/kth?start_day=1&end_day=100&k=5",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["k"] == 5
        assert data["algorithm"] == "persistent_segment_tree"
        assert data["query_time_us"] < 1000  # 应在1ms以内

    async def test_best_trade(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/stock/000001/best-trade?start_day=1&end_day=500",
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["max_profit"] >= 0
        assert data["buy_day"] < data["sell_day"]

    async def test_unauthorized(self, client):
        resp = await client.get("/api/v1/stock/600519/kth?start_day=1&end_day=100&k=5")
        assert resp.status_code == 401

class TestBenchmarkAPI:
    async def test_benchmark_compare(self, client, auth_headers):
        resp = await client.post("/api/v1/benchmark/compare", json={
            "query_type": "kth_largest",
            "data_sizes": [10000],
            "query_count": 100,
            "methods": ["persistent_segtree", "sql_sort"]
        }, headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()["data"]["results"]
        # C++ 引擎应比 SQL 快
        assert results[0]["persistent_segtree"]["avg_query_us"] < \
               results[0]["sql_sort"]["avg_query_us"]
```

### 20.3 Stress Test（对拍脚本）

```python
# tests/stress_test.py
"""
ACM 风格 Stress Test：随机数据 + 暴力对拍
确保 C++ 引擎在各种随机情况下与暴力结果一致
"""
import random
import dataforge_engine as engine

def brute_kth(data, l, r, k):
    return sorted(data[l:r+1])[k-1]

def brute_max_subarray(data, l, r):
    best = -float('inf')
    for i in range(l, r+1):
        s = 0
        for j in range(i, r+1):
            s += data[j]
            best = max(best, s)
    return best

def stress_test_persistent_segtree(iterations=10000):
    for it in range(iterations):
        n = random.randint(1, 500)
        data = [random.randint(-10**6, 10**6) for _ in range(n)]
        pst = engine.PersistentSegTree(data)

        for _ in range(20):
            l, r = sorted(random.sample(range(n), 2))
            k = random.randint(1, r - l + 1)
            assert pst.query_kth(l, r, k) == brute_kth(data, l, r, k), \
                f"FAIL at iter={it}, l={l}, r={r}, k={k}"

    print(f"✅ PersistentSegTree: {iterations} iterations PASSED")

if __name__ == "__main__":
    stress_test_persistent_segtree()
```

### 20.4 测试覆盖目标

| 模块 | 单元测试 | 集成测试 | 压力测试 | 覆盖率目标 |
|------|---------|---------|---------|-----------|
| C++ 引擎 | ✅ Google Test | ✅ pybind11 调用 | ✅ 对拍 10^4 组 | ≥ 90% |
| Python 后端 | ✅ pytest | ✅ API 端到端 | ✅ locust 负载 | ≥ 85% |
| 前端 | ✅ Jest 组件测试 | ✅ Cypress E2E | - | ≥ 70% |

---

## 二十一、CMake 构建配置

```cmake
# engine/CMakeLists.txt
cmake_minimum_required(VERSION 3.16)
project(DataForgeEngine VERSION 1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

# Release 优化
if(CMAKE_BUILD_TYPE STREQUAL "Release")
    set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
endif()

# 核心静态库
add_library(dataforge_core STATIC
    src/persistent_segtree.cpp
    src/segment_tree.cpp
    src/block_decomp.cpp
    src/divide_conquer.cpp
    src/serialization.cpp
    src/benchmark.cpp
)
target_include_directories(dataforge_core PUBLIC include/)

# 同时编译为共享库（供非 Python 场景使用）
add_library(dataforge_shared SHARED
    src/persistent_segtree.cpp
    src/segment_tree.cpp
    src/block_decomp.cpp
    src/divide_conquer.cpp
    src/serialization.cpp
)
target_include_directories(dataforge_shared PUBLIC include/)
set_target_properties(dataforge_shared PROPERTIES OUTPUT_NAME "dataforge_core")

# pybind11 Python 模块
find_package(pybind11 REQUIRED)
pybind11_add_module(dataforge_engine bindings/pybind_module.cpp)
target_link_libraries(dataforge_engine PRIVATE dataforge_core)

# Google Test 单元测试
enable_testing()
find_package(GTest REQUIRED)

foreach(test_name
    test_persistent_segtree
    test_segment_tree
    test_block_decomp
    test_divide_conquer
)
    add_executable(${test_name} tests/${test_name}.cpp)
    target_link_libraries(${test_name} dataforge_core GTest::gtest_main)
    add_test(NAME ${test_name} COMMAND ${test_name})
endforeach()

# Benchmark 可执行文件
add_executable(bench_vs_baseline benchmarks/bench_vs_baseline.cpp)
target_link_libraries(bench_vs_baseline dataforge_core)
```

---

## 二十二、详细周计划

| 周 | 阶段 | 具体任务 | 产出物 |
|----|------|---------|--------|
| 1 | 基础 | Git 仓库 + Docker 环境 + PostgreSQL/Redis 配置 | docker-compose.yml 可启动 |
| 2 | 基础 | FastAPI 骨架 + JWT 认证 + 数据库 migration | 可登录的空 API |
| 3 | 基础 | 股票爬虫 + 购物数据生成器 + 数据入库 | DB 有 100 万+ 条数据 |
| 4 | 引擎 | 主席树核心实现 + 单元测试 | 通过正确性对拍 |
| 5 | 引擎 | 主席树序列化 + pybind11 绑定 + 性能测试 | Python 可调用主席树 |
| 6 | 引擎 | 线段树（懒标记 + 最大子段和）+ 测试 + 绑定 | 通过对拍 + 绑定可用 |
| 7 | 引擎 | 分块（Mo's + 值域分块）+ 测试 + 绑定 | 通过对拍 + 绑定可用 |
| 8 | 引擎 | 分治（逆序对 + CDQ + 最近点对）+ Benchmark 框架 | 全引擎完成 + 基准数据 |
| 9 | 后端 | 股票 CRUD API + engine_service 集成主席树/线段树 | 股票查询 API 可用 |
| 10 | 后端 | 购物 CRUD API + engine_service 集成分块/分治 | 购物查询 API 可用 |
| 11 | 后端 | Redis 缓存 + Celery 异步索引构建 + Benchmark API | 完整后端 |
| 12 | 前端 | React 骨架 + Dashboard + 路由 + 主题 | 可访问的仪表盘 |
| 13 | 前端 | 股票分析页 + K线图 + 查询面板 + 数据管理页 | 股票功能完整 |
| 14 | 前端 | 购物分析页 + 算法实验室 + Benchmark 展示页 | 全前端完成 |
| 15 | 集成 | 全链路测试 + Bug 修复 + Docker 部署验证 | 可演示的完整系统 |
| 16 | 论文 | 性能测试报告 + 论文撰写 + 答辩 PPT | 毕设交付物 |

---

## 二十三、附加算法扩展（增加工作量与深度）

### 23.1 树状数组套主席树（动态区间第 K 大）

```
场景：股票数据实时更新后，仍支持 O(log²n) 的区间第K大查询

实现要点：
  - 外层 BIT 维护 log(n) 棵主席树
  - 修改: 沿 BIT 向上更新 log(n) 棵树，每棵 O(log n)
  - 查询: 同时在 log(n) 棵树上二分
  - 总复杂度: 修改 O(log²n), 查询 O(log²n)

文件: engine/src/dynamic_kth.h / .cpp (~400行)
```

### 23.2 可持久化并查集 + 回滚

```
场景：购物用户分组管理，支持历史版本回溯

实现要点：
  - 基于主席树实现可持久化数组
  - 在其上构建按秩合并的并查集（不进行路径压缩）
  - 支持查询任意历史版本的连通性
  - 单次操作 O(log²n)

文件: engine/src/persistent_dsu.h / .cpp (~250行)
```

### 23.3 整体二分（Parallel Binary Search）

```
场景：批量回答"第一次出现满足条件X的时刻是哪天"

实现要点：
  - 将 Q 个二分查询并行处理
  - 每轮将所有查询按当前 mid 分成两组
  - 总复杂度 O((N+Q) log N log V)

应用：
  - 批量查询 "股票价格首次超过目标价的日期"
  - 批量查询 "累计销售额首次达到目标的时刻"

文件: engine/src/parallel_binary_search.h / .cpp (~200行)
```

### 23.4 工作量更新

| 模块 | 原估 | 扩展后 | 增量 |
|------|------|--------|------|
| C++ 引擎 | 4,000 行 | 5,200 行 | +1,200 行 |
| pybind11 绑定 | 500 行 | 650 行 | +150 行 |
| **项目总计** | **13,300 行** | **14,650 行** | **+1,350 行** |

---

> **总结**：本项目以"算法工程化"为核心理念，将 ACM/ICPC 竞赛中的高级数据结构（主席树、线段树、分块、分治及其扩展变体）深度融入数据管理系统，通过 C++ 实现计算密集型算法内核、Python 构建灵活的业务层、React 打造交互式前端，形成完整的三层架构。项目涵盖约 14,650 行多语言代码，包含完整的安全设计、部署方案、测试策略和性能基准体系，具备充足的工作量和显著的学术价值。
