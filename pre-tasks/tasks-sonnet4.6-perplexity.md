# 毕业设计方案：QuantiCore 智能数据管理系统

> 一个融合 ACM/ICPC 算法竞赛思维、面向股票与购物平台数据的全栈数据管理系统

---

## 一、项目概述

### 1.1 项目名称
**QuantiCore** —— 基于高级数据结构的智能数据管理与分析平台

### 1.2 系统定位
| 维度       | 描述                                                    |
| ---------- | ------------------------------------------------------- |
| 目标用户   | 数据分析师、量化研究者、电商运营人员                    |
| 核心价值   | 利用竞赛级数据结构提升海量时序/交易数据的查询与分析效率 |
| 技术亮点   | C++ 高性能算法引擎 + Python 数据处理层 + 现代前端交互   |
| 工作量保证 | 前端 + 后端 + 算法引擎 + 数据库 + 部署文档，约 3-4 个月 |

---

## 二、需求分析

### 2.1 功能性需求

#### 股票数据模块
- 导入/管理历史 K 线数据（日线/分钟线）
- **区间统计查询**：任意时间段内的最大值、最小值、均值、方差
- **历史版本查询**：查询某只股票在某一历史时刻的价格快照（可持久化数据结构）
- **Top-K 涨幅排行**：实时/历史区间内涨幅最大的 K 只股票
- 趋势图表可视化（前端）

#### 购物平台数据模块
- 商品信息、订单、用户行为数据管理
- **区间销量聚合**：任意价格区间/时间区间内的订单总量、总金额
- **分类 Top-K 查询**：各品类销量前 K 名商品
- **滑动窗口统计**：近 N 天的实时销售趋势
- 用户行为序列分析

### 2.2 非功能性需求
- 单次区间查询响应时间：< 50ms（数据量 10^6 量级）
- 支持并发查询
- 前端响应式设计，支持图表交互

---

## 三、系统架构
┌─────────────────────────────────────────────────────────────┐
│ 前端 (Vue 3 + TypeScript) │
│ 股票仪表盘 | 购物数据看板 | 查询界面 | 图表 │
└────────────────────────┬────────────────────────────────────┘
│ RESTful API / WebSocket
┌────────────────────────▼────────────────────────────────────┐
│ 后端服务层 (Python · FastAPI) │
│ 业务逻辑 | 数据校验 | 任务调度 | 缓存 (Redis) │
└────────────────────────┬────────────────────────────────────┘
│ gRPC / 共享内存 / subprocess
┌────────────────────────▼────────────────────────────────────┐
│ 算法引擎层 (C++ · 核心模块) │
│ 主席树引擎 | 线段树引擎 | 分块引擎 | 分治查询引擎 │
└────────────────────────┬────────────────────────────────────┘
│
┌────────────────────────▼────────────────────────────────────┐
│ 数据存储层 │
│ PostgreSQL (结构化) | Redis (缓存) | CSV/HDF5 (历史) │
└─────────────────────────────────────────────────────────────┘

---

## 四、技术栈选型

| 层次         | 技术                              | 理由                                   |
| ------------ | --------------------------------- | -------------------------------------- |
| **前端**     | Vue 3 + TypeScript + ECharts      | 现代响应式，ECharts 对金融图表支持极好 |
| **后端服务** | Python 3.11 + FastAPI             | 异步高性能，与 C++ 通信方便            |
| **算法引擎** | C++17（pybind11 暴露接口）        | 发挥竞赛水平，极致性能                 |
| **ORM**      | SQLAlchemy + Alembic              | 数据库迁移管理                         |
| **数据库**   | PostgreSQL                        | 支持时序索引，稳定可靠                 |
| **缓存**     | Redis                             | 热点查询缓存，降低引擎压力             |
| **数据处理** | Pandas / NumPy / Akshare（爬数据）| Python 数据清洗与接入                  |
| **通信**     | pybind11 / gRPC（可选）           | C++ 引擎与 Python 层无缝对接           |
| **部署**     | Docker + Docker Compose           | 一键部署，易于演示                     |

---

## 五、C++ 算法引擎设计（核心亮点）

> 这是整个项目体现 ACM/ICPC 竞赛能力的核心模块。

### 5.1 主席树引擎（Persistent Segment Tree）

**使用场景**：股票数据历史版本查询  
**解决问题**：  
- 查询"第 t 天时，某只股票价格在 [lo, hi] 区间内的统计值（分位数/频次）"  
- 支持不可变历史版本，O(log N) 时间/空间增量更新  

```cpp
// persistent_seg_tree.hpp
struct Node {
    int left, right, cnt;
    long long sum;
};

class PersistentSegTree {
    vector<Node> tree;
    vector<int> roots;  // roots[i] = 第 i 个版本的根节点
public:
    int build(int l, int r);
    int update(int prev, int l, int r, int pos, long long val);
    long long query(int vl, int vr, int l, int r, int ql, int qr);  // 区间第 k 大 / 区间和
    void add_version(int prev_root, int pos, long long val);
    // 暴露给 Python 的接口（pybind11）
    long long range_kth(int version_l, int version_r, int k);
    long long range_sum(int version, int ql, int qr);
};
```

**对应查询功能**：  
- `GET /stock/{symbol}/history?version=150&price_lo=10&price_hi=50` → 第 150 天时，价格在 10-50 之间的交易次数

---

### 5.2 线段树引擎（Segment Tree with Lazy Propagation）

**使用场景**：股票/订单区间聚合查询  
**解决问题**：  
- 区间最大值/最小值/求和/均值  
- 区间批量更新（如批量价格调整）  

```cpp
// seg_tree.hpp
template <typename T>
struct SegTree {
    int n;
    vector<T> tree, lazy;
    
    void build(const vector<T>& a);
    void push_down(int node);
    void range_update(int node, int l, int r, int ql, int qr, T val);
    T range_query_max(int node, int l, int r, int ql, int qr);
    T range_query_sum(int node, int l, int r, int ql, int qr);
    
    // 支持多种聚合：MAX / MIN / SUM / COUNT
    T query(int ql, int qr, AggType agg);
};
```

**对应查询功能**：  
- `GET /stock/{symbol}/range?start=2020-01-01&end=2023-12-31&agg=max_price`  
- `GET /orders/range?price_lo=100&price_hi=500&agg=total_amount`

---

### 5.3 分块引擎（Sqrt Decomposition）

**使用场景**：订单数据的在线更新 + 快速区间统计  
**解决问题**：  
- 数据频繁插入更新（线段树重建代价高），分块可 O(√N) 支持动态插入  
- 块内维护有序数组，支持区间 Top-K  

```cpp
// block_decompose.hpp
class BlockArray {
    int block_size;
    vector<vector<long long>> blocks;      // 每块的有序数据
    vector<long long> block_sum;
    vector<long long> block_max;
public:
    void insert(int pos, long long val);
    void update(int pos, long long new_val);
    long long range_sum(int l, int r);
    long long range_kth(int l, int r, int k);   // 区间第 k 大（购物 Top-K）
    int range_count_greater(int l, int r, long long threshold);
};
```

**对应查询功能**：  
- 购物平台：实时插入订单后立即查询近 N 条订单中金额前 K 大  
- 允许 O(√N) 级别插入，比线段树更适合高频写入场景

---

### 5.4 分治查询引擎（Divide & Conquer）

**使用场景**：离线批量查询优化  
**解决问题**：  
- 当前端提交一批"区间查询请求"（如导出报表）时，用离线分治避免重复计算  
- CDQ 分治：解决三维偏序（时间 × 价格区间 × 品类）  

```cpp
// cdq_divide.hpp
struct Query {
    int time_l, time_r;
    long long price_l, price_r;
    int category;
    long long& result;
};

class CDQEngine {
public:
    // CDQ 分治：批量处理 m 个区间查询，时间复杂度 O((N+M) log^2 N)
    void solve(vector<Query>& queries, vector<DataPoint>& data);
private:
    void divide(int ql, int qr, vector<Query>& queries, vector<DataPoint>& data);
    void merge_count(vector<DataPoint>& left, vector<DataPoint>& right, vector<Query>& q);
};
```

**对应功能**：  
- `POST /batch-query`：一次提交 1000 条区间查询，CDQ 分治批量返回结果  
- 导出「时间 × 品类 × 销量」三维分析报表

---

### 5.5 pybind11 接口暴露

```cpp
// bindings.cpp
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include "persistent_seg_tree.hpp"
#include "seg_tree.hpp"
#include "block_decompose.hpp"
#include "cdq_divide.hpp"

PYBIND11_MODULE(quanticore_engine, m) {
    m.doc() = "QuantiCore C++ Algorithm Engine";
    
    py::class_<PersistentSegTree>(m, "PersistentSegTree")
        .def(py::init<int>())
        .def("add_version", &PersistentSegTree::add_version)
        .def("range_kth",   &PersistentSegTree::range_kth)
        .def("range_sum",   &PersistentSegTree::range_sum);
    
    py::class_<SegTree<long long>>(m, "SegTree")
        .def(py::init<const std::vector<long long>&>())
        .def("range_query", &SegTree<long long>::query)
        .def("range_update",&SegTree<long long>::range_update);
    
    py::class_<BlockArray>(m, "BlockArray")
        .def(py::init<int>())
        .def("insert",      &BlockArray::insert)
        .def("range_kth",   &BlockArray::range_kth)
        .def("range_sum",   &BlockArray::range_sum);
    
    py::class_<CDQEngine>(m, "CDQEngine")
        .def(py::init<>())
        .def("batch_solve", &CDQEngine::solve);
}
```

---

## 六、Python 后端设计（FastAPI）

### 6.1 项目目录结构
backend/
├── main.py # FastAPI 应用入口
├── config.py # 配置管理
├── engine/
│ ├── _init_.py
│ ├── quanticore_engine.so # 编译后的 C++ 模块
│ └── engine_manager.py # 引擎初始化/生命周期管理
├── api/
│ ├── stock.py # 股票数据路由
│ ├── orders.py # 订单数据路由
│ └── batch.py # 批量查询路由
├── services/
│ ├── stock_service.py # 股票业务逻辑
│ ├── order_service.py # 订单业务逻辑
│ └── cache_service.py # Redis 缓存服务
├── models/
│ ├── stock.py # ORM 模型
│ └── order.py
├── schemas/
│ ├── stock.py # Pydantic 数据校验
│ └── order.py
├── data/
│ ├── fetcher.py # Akshare 爬取股票数据
│ └── cleaner.py # Pandas 数据清洗
├── tests/
│ └── test_engine.py # 算法引擎单元测试
└── requirements.txt

### 6.2 核心 API 设计

#### 股票模块
GET /api/stock/list # 股票列表
POST /api/stock/import # 导入 CSV 数据
GET /api/stock/{symbol}/kline # K 线数据
GET /api/stock/{symbol}/range-query # 区间聚合（调用线段树引擎）
?start=&end=&agg=max|min|sum|avg
GET /api/stock/{symbol}/history-snapshot # 历史快照（调用主席树引擎）
?version=&price_lo=&price_hi=
GET /api/stock/topk # 涨幅 Top-K（线段树+堆）
?start=&end=&k=10


#### 购物模块
GET /api/orders/list # 订单列表（分页）
POST /api/orders/create # 新建订单（触发分块引擎插入）
GET /api/orders/range-query # 区间查询（分块引擎）
?date_start=&date_end=&price_lo=&price_hi=&agg=sum|count|kth
GET /api/orders/topk-products # Top-K 商品销量（分块引擎）
?category=&k=10&date_start=&date_end=
POST /api/orders/batch-analyze # CDQ 分治批量查询


### 6.3 引擎调用示例（Python 侧）

```python
# engine_manager.py
import quanticore_engine as qce
import numpy as np

class StockEngineManager:
    def __init__(self):
        self.seg_trees: dict[str, qce.SegTree] = {}
        self.pst_trees: dict[str, qce.PersistentSegTree] = {}
    
    def build_for_symbol(self, symbol: str, prices: list[float]):
        """为某支股票构建线段树和主席树"""
        scaled = [int(p * 100) for p in prices]  # 转整数
        self.seg_trees[symbol] = qce.SegTree(scaled)
        n = len(scaled)
        pst = qce.PersistentSegTree(n)
        for i, v in enumerate(scaled):
            pst.add_version(i, v)
        self.pst_trees[symbol] = pst
    
    def range_max_price(self, symbol: str, l: int, r: int) -> float:
        return self.seg_trees[symbol].range_query(l, r, "MAX") / 100.0
    
    def history_count_in_range(self, symbol: str, version: int, 
                                price_lo: float, price_hi: float) -> int:
        lo = int(price_lo * 100)
        hi = int(price_hi * 100)
        return self.pst_trees[symbol].range_sum(version, lo, hi)
```

### 6.4 数据爬取与清洗（Python）

```python
# data/fetcher.py
import akshare as ak
import pandas as pd

def fetch_stock_daily(symbol: str, start: str, end: str) -> pd.DataFrame:
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                            start_date=start, end_date=end, adjust="qfq")
    df = df.rename(columns={
        "日期": "date", "开盘": "open", "收盘": "close",
        "最高": "high", "最低": "low", "成交量": "volume"
    })
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna().sort_values("date").reset_index(drop=True)
    return df

def generate_mock_orders(n: int = 100000) -> pd.DataFrame:
    """生成购物平台模拟数据，保证演示数据量"""
    import numpy as np
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "order_id":   range(n),
        "user_id":    rng.integers(1, 10001, n),
        "product_id": rng.integers(1, 1001, n),
        "category":   rng.choice(["电子", "服装", "食品", "家居", "图书"], n),
        "price":      rng.uniform(10, 5000, n).round(2),
        "quantity":   rng.integers(1, 10, n),
        "amount":     None,  # 计算列
        "created_at": pd.date_range("2022-01-01", periods=n, freq="5min")
    }).assign(amount=lambda df: df["price"] * df["quantity"])
```

---

## 七、前端设计（Vue 3 + ECharts）

### 7.1 目录结构
frontend/
├── src/
│ ├── views/
│ │ ├── StockDashboard.vue # 股票看板
│ │ ├── StockDetail.vue # 股票详情 + 区间查询
│ │ ├── OrderDashboard.vue # 购物数据看板
│ │ ├── BatchQuery.vue # 批量分析
│ │ └── AlgorithmViz.vue # 数据结构可视化（亮点页）
│ ├── components/
│ │ ├── KLineChart.vue # K 线图（ECharts）
│ │ ├── RangeQueryPanel.vue # 区间查询控件
│ │ ├── TopKTable.vue # Top-K 排行表
│ │ ├── PerformanceMonitor.vue # 查询耗时对比图
│ │ └── TreeVisualizer.vue # 线段树节点可视化
│ ├── api/
│ │ └── index.ts # Axios 封装
│ └── stores/
│ └── queryStore.ts # Pinia 状态管理
└── vite.config.ts


### 7.2 核心页面功能

#### 股票看板
- ECharts K 线图（含均线、布林带叠加）
- 区间查询面板：拖动日期范围 → 调用线段树引擎返回 max/min/avg
- 历史快照查询：输入版本号 + 价格区间 → 主席树返回分布信息
- Top-K 涨幅榜（实时刷新）

#### 数据结构可视化页（亮点！）
- 动态展示线段树节点的查询路径（高亮经过的节点）
- 对比展示：暴力 O(N) vs 线段树 O(log N) 查询耗时折线图
- 分块结构示意图（块内排序可视化）

#### 购物数据看板
- 时间区间销售漏斗图
- 各品类销量热力图
- 价格区间分布直方图（分块引擎驱动）
- 实时订单流（WebSocket 推送 + 前端滚动列表）

---

## 八、数据库设计

### 8.1 核心表

```sql
-- 股票基础信息
CREATE TABLE stocks (
    symbol      VARCHAR(10) PRIMARY KEY,
    name        VARCHAR(50) NOT NULL,
    market      VARCHAR(10),          -- 'SH'/'SZ'
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 股票日线数据
CREATE TABLE stock_daily (
    id          BIGSERIAL PRIMARY KEY,
    symbol      VARCHAR(10) REFERENCES stocks(symbol),
    date        DATE NOT NULL,
    open        NUMERIC(12,4),
    high        NUMERIC(12,4),
    low         NUMERIC(12,4),
    close       NUMERIC(12,4),
    volume      BIGINT,
    UNIQUE(symbol, date)
);
CREATE INDEX idx_stock_daily_symbol_date ON stock_daily(symbol, date);

-- 购物订单
CREATE TABLE orders (
    id          BIGSERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    category    VARCHAR(30),
    price       NUMERIC(12,2),
    quantity    INTEGER,
    amount      NUMERIC(14,2),
    created_at  TIMESTAMP NOT NULL
);
CREATE INDEX idx_orders_created ON orders(created_at);
CREATE INDEX idx_orders_category ON orders(category);

-- 查询日志（用于性能分析展示）
CREATE TABLE query_logs (
    id           BIGSERIAL PRIMARY KEY,
    query_type   VARCHAR(50),          -- 'seg_tree'/'pst'/'block'/'cdq'
    params       JSONB,
    elapsed_ms   FLOAT,
    result_count INTEGER,
    created_at   TIMESTAMP DEFAULT NOW()
);
```

---

## 九、项目工作量分解

| 模块                         | 工作内容                                   | 预估工时 |
| ---------------------------- | ------------------------------------------ | -------- |
| **C++ 引擎 - 线段树**        | 区间查询/更新、懒传播、pybind11 绑定       | 5天      |
| **C++ 引擎 - 主席树**        | 可持久化建树、版本管理、历史查询           | 5天      |
| **C++ 引擎 - 分块**          | 动态插入、块内有序、Top-K                  | 3天      |
| **C++ 引擎 - CDQ 分治**      | 离线批量查询、三维偏序                     | 4天      |
| **Python 数据层**            | 数据爬取、清洗、ORM、引擎管理类            | 4天      |
| **Python 后端 API**          | FastAPI 路由、Redis 缓存、WebSocket        | 5天      |
| **前端 - 股票看板**          | K 线图、区间查询面板、Top-K 榜             | 5天      |
| **前端 - 购物看板**          | 漏斗图、热力图、直方图                     | 4天      |
| **前端 - 数据结构可视化**    | 线段树动画、性能对比图                     | 3天      |
| **数据库设计 + 迁移**        | 建表、索引、Alembic 脚本                   | 2天      |
| **测试 & 性能基准**          | 单元测试、压测报告（10^6 数据量）          | 3天      |
| **Docker 部署 + 文档**       | docker-compose、README、接口文档（Swagger）| 2天      |
| **毕业论文**                 | 系统设计、算法分析、性能实验               | 10天     |
| **合计**                     |                                            | **~55天**|

---

## 十、关键技术难点与创新点

### 10.1 主席树版本管理映射
股票每日收盘数据天然对应"第 i 天"版本，将离散价格值通过坐标压缩映射到主席树下标，支持任意历史日期的价格区间分布查询，时间复杂度 O(log N)。

### 10.2 分块支持在线订单插入
与线段树相比，分块允许 O(√N) 级别的动态插入，更适合购物订单的实时写入场景，同时依然保持 O(√N) 的区间 Top-K 查询。

### 10.3 CDQ 分治批量报表
将前端提交的批量区间查询转为离线任务，利用 CDQ 分治将 M 次查询的总时间复杂度从 O(M·N) 降至 O((N+M)log²N)，显著提升报表导出速度。

### 10.4 性能对比实验（论文亮点）
在 10^6 数据量下，对比以下方案的查询耗时：
- 暴力 O(N) 遍历（Python 基准）
- 线段树 O(log N)（C++ 引擎）
- 分块 O(√N)（C++ 引擎）
- 数据库 SQL 聚合索引

结果以折线图形式在前端"算法对比"页面呈现，直观说明数据结构的工程价值。

---

## 十一、开发环境与部署

### 11.1 本地开发

```bash
# 1. 编译 C++ 引擎
cd cpp_engine
mkdir build && cd build
cmake .. -DPYTHON_EXECUTABLE=$(which python3)
make -j4
cp quanticore_engine*.so ../../backend/engine/

# 2. 启动后端
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# 3. 启动前端
cd frontend
npm install
npm run dev
```

### 11.2 Docker Compose 部署

```yaml
# docker-compose.yml
version: "3.9"
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: quanticore
      POSTGRES_PASSWORD: quanticore123
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine

  backend:
    build: ./backend
    depends_on: [postgres, redis]
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:quanticore123@postgres/quanticore
      REDIS_URL: redis://redis:6379

  frontend:
    build: ./frontend
    ports: ["3000:80"]
    depends_on: [backend]

volumes:
  pgdata:
```

---

## 十二、毕业论文章节建议

| 章节   | 内容                                                       |
| ------ | ---------------------------------------------------------- |
| 第一章 | 绪论：研究背景、意义、国内外现状、论文结构                 |
| 第二章 | 需求分析：功能需求、非功能需求、用例图                     |
| 第三章 | 系统设计：总体架构、数据库设计、接口设计                   |
| 第四章 | 核心算法设计与实现：主席树/线段树/分块/CDQ 分治原理+代码   |
| 第五章 | 系统实现：前后端实现、C++/Python 集成                      |
| 第六章 | 测试与性能分析：功能测试、性能对比实验（含图表）           |
| 第七章 | 总结与展望                                                 |


这份方案完整覆盖了你的所有需求，以下是几个核心设计决策的说明：

工作量保证：C++ 引擎（4个数据结构）+ Python 后端（FastAPI + 数据清洗）+ Vue 前端（3个主要看板）+ 数据库设计 + Docker 部署 + 论文，按正常开发节奏约需 2-3 个月，工作量充实 。

ACM 能力融入：四个数据结构各有明确的业务对应场景——主席树解决历史版本查询、线段树处理区间聚合、分块支持动态在线插入、CDQ 分治优化批量离线查询，不是为了用而用，每个都有实际价值 。

C++/Python 协作：通过 pybind11 将 C++ 编译为 .so 动态库，Python 直接 import 调用，性能与开发效率兼顾。这也是工业界（如 NumPy、PyTorch）的标准做法 。

论文亮点：第六章的性能对比实验——暴力 vs 线段树 vs 分块 vs 数据库索引的 benchmark——能直观证明算法的工程价值，是论文最有说服力的部分。