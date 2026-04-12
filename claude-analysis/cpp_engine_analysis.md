# C++ 算法引擎实际使用情况分析

## 一、C++ 引擎中实现了哪些算法

| # | 算法类 | 文件 | 核心能力 | 复杂度 |
|---|--------|------|----------|--------|
| 1 | `RangeMaxSegmentTree` | [range_max_segment_tree.cpp](file:///d:/graduation-project/algo-module/src/segment_tree/range_max_segment_tree.cpp) | 区间最大值查询 + 回收所有命中位置 | 建树 O(n)，查询 O(log n) |
| 2 | `RangeKthPersistentSegmentTree` | [range_kth_persistent_segment_tree.cpp](file:///d:/graduation-project/algo-module/src/segment_tree/range_kth_persistent_segment_tree.cpp) | 可持久化线段树（主席树），支持精确区间第 K 大 | 建树 O(n log n)，查询 O(log n) |
| 3 | `HistoricalDominanceCdqCounter` | [historical_dominance_cdq.cpp](file:///d:/graduation-project/algo-module/src/cdq/historical_dominance_cdq.cpp) | CDQ 分治 + 树状数组，统计二维前缀支配计数 | O(n log² n) |
| 4 | `HistoricalDominance3dCdqCounter` | [historical_dominance_cdq_3d.cpp](file:///d:/graduation-project/algo-module/src/cdq/historical_dominance_cdq_3d.cpp) | 三维 CDQ 分治，统计三维前缀支配计数 | O(n log³ n) |

所有算法通过 [module.cpp](file:///d:/graduation-project/algo-module/bindings/python/module.cpp)（pybind11）暴露为 Python 可调用的 `algo_module_py` 模块。

---

## 二、真正调用 C++ 的业务链路追踪

Python 侧的桥接层在 [adapters/trading.py](file:///d:/graduation-project/backend/app/algo_bridge/adapters/trading.py)，共 **5 个函数**调用了 C++ 模块：

### 链路 1：区间最大成交额

```
前端 → GET /api/algo/trading/range-max-amount
  → algo_trading.py:query_range_max_amount()
    → adapters/trading.py:query_range_max()    ← 调用 C++ RangeMaxSegmentTree
```

- **C++ 实际作用**：对单支股票在指定日期区间内查找成交额最大值及其命中日期  
- **业务场景**：用户选定批次、标的、日期区间 → 返回最大成交额及对应交易日

### 链路 2：区间第 K 大成交量（精确解）

```
前端 → GET /api/algo/trading/range-kth-volume?method=persistent_segment_tree
  → algo_trading.py:query_range_kth_volume()
    → adapters/trading.py:query_range_kth()    ← 调用 C++ RangeKthPersistentSegmentTree
```

- **C++ 实际作用**：主席树精确查找区间第 K 大成交量及命中日期
- **业务场景**：用户指定批次、标的、日期区间、K 值 → 返回精确排名结果

### 链路 3：区间第 K 大成交量（近似解）

```
前端 → GET /api/algo/trading/range-kth-volume?method=t_digest
  → algo_trading.py:query_range_kth_volume()
    → adapters/trading.py:query_range_kth_tdigest()    ← 纯 Python tdigest，未用 C++
```

> [!IMPORTANT]
> t-digest 近似方案是**纯 Python 实现**（[tdigest.py](file:///d:/graduation-project/backend/app/algo_bridge/tdigest.py) + [vendor/tdigest.py](file:///d:/graduation-project/backend/app/vendor/tdigest.py)），并没有使用 C++ 引擎。

### 链路 4：联合异常排序（二维 CDQ）

```
前端 → GET /api/algo/trading/joint-anomaly-ranking
  → algo_trading.py:query_joint_anomaly_ranking()
    → adapters/trading.py:query_historical_dominance()    ← 调用 C++ HistoricalDominanceCdqCounter
```

- **C++ 实际作用**：给定每日 `return_z20` 和 `volume_ratio20` 两个指标，用 CDQ 分治统计每个事件在历史窗口中被多少事件"支配"，据此计算联合异常百分位
- **业务场景**：跨标的联合异常事件排名榜

### 链路 5：风险雷达（三维 CDQ + 线段树 + 主席树）

```
前端 → GET /api/algo/risk-radar/*
  → risk_radar.py → algo_indexes.py:_build_cache()
    → adapters/trading.py:query_historical_dominance_3d()    ← 调用 C++ HistoricalDominance3dCdqCounter
    → algo_indexes.py:_build_instrument_indexes()
      → module.RangeMaxSegmentTree(amounts_scaled)           ← 成交额区间最大值
      → module.RangeKthPersistentSegmentTree(volumes_scaled) ← 成交量精确第K大
      → module.RangeKthPersistentSegmentTree(amplitudes_scaled) ← 振幅精确第K大
```

- **C++ 实际作用**：风险雷达是 C++ 使用的**最重承载者**——每个标的同时构建了 `RangeMaxSegmentTree`（成交额）+ 两棵 `RangeKthPersistentSegmentTree`（成交量/振幅），再加上一次三维 CDQ 分治来计算联合异常严重等级
- **业务场景**：批次导入后异步构建索引 → 前端展示风险雷达总览、事件列表、标的画像、日历热图、事件上下文

---

## 三、总结：C++ 引擎的实际覆盖面

| 业务板块 | C++ 算法 | 是否真实使用 C++ |
|----------|----------|------------------|
| 区间最大成交额 | `RangeMaxSegmentTree` | ✅ 是 |
| 区间第 K 大（精确） | `RangeKthPersistentSegmentTree` | ✅ 是 |
| 区间第 K 大（近似） | t-digest | ❌ **纯 Python** |
| 联合异常排序 | `HistoricalDominanceCdqCounter` | ✅ 是 |
| 风险雷达索引构建 | 三维CDQ + 线段树 + 主席树 | ✅ 是（最重度使用） |
| 风险雷达事件上下文窗口查询 | `RangeKthPersistentSegmentTree` | ✅ 是 |
| 风险雷达局部成交额峰值 | `RangeMaxSegmentTree` | ✅ 是 |
| 数据上传 / 导入管理 | — | ❌ 无关 |
| 用户鉴权 / 权限 | — | ❌ 无关 |
| 10 个分析接口（摘要/指标/风险/异常等） | Pandas 计算 | ❌ **纯 Python/Pandas** |

---

## 四、设计合理性评估

### ✅ 做得好的部分

1. **分层清晰**：`C++ 算法层 → pybind11 绑定 → Python bridge (adapters) → Service → Route`，职责分离明确
2. **算法选择切题**：
   - 主席树做区间第 K 大是**经典竞赛数据结构**的工程化应用，选型正确
   - CDQ 分治计算"历史前缀支配计数"来推导联合异常百分位，方案**新颖且言之有理**
   - 区间最大值线段树虽然简单，但作为基础能力整合在体系内很自然
3. **精确/近似双方案对比**：同一个查询提供 C++ 精确解和 Python 近似解，具有实验对比价值
4. **风险雷达是真正的重度应用**：每个标的构建多棵树、三维 CDQ、窗口查询、局部峰值，不是"纸上谈兵"

### ⚠️ 值得注意的问题

1. **t-digest 没有用 C++ 实现**：在题目强调"融合 C++ 算法引擎"的前提下，近似方案完全是 Python 实现，作为对比实验可以接受；但如果论文要强调 C++ 性能优势，建议补充 C++ 版 t-digest 或在论文中明确说明
2. **10 个 trading_analysis 分析接口完全不经过 C++**：这些接口（摘要、质量、指标、风险、异常、横截面、相关性、范围对比）全部用 Pandas 实现。这本身没问题（Pandas 处理这些完全合理），但意味着系统的"分析"大部分不依赖 C++
3. **线段树每次请求都重建**：在 `algo_trading.py:query_range_max_amount()` 和 `query_range_kth_volume()` 中，**每次 API 调用都从数据库取数据、重新建树然后查询一次**。风险雷达的 `algo_indexes.py` 做了缓存和快照持久化，设计更好；但基础查询接口没有复用构建好的树
4. **CDQ 的"前缀支配计数"输入顺序是自然时间序**：这意味着一个事件只被时间上更早的事件支配。这对于"历史百分位"是正确的语义，设计合理

### 💡 整体结论

> C++ 引擎的使用是**真实的、有深度的**，不是装饰性的。4 个 C++ 算法类覆盖了 3 个业务板块（区间查询、联合异常、风险雷达），尤其风险雷达是重度使用场景。设计分层合理，算法选型与业务需求匹配。主要不足是基础 algo 接口缺少树的缓存机制，以及 t-digest 未用 C++ 实现。
