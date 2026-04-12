#pragma once

#include <cstdint>
#include <limits>
#include <vector>

namespace algo_module {

struct RangeMaxResult {
    std::int64_t max_value_scaled;
    std::vector<int> matched_indices;
};

class RangeMaxSegmentTree {
  public:
    explicit RangeMaxSegmentTree(std::vector<std::int64_t> values);

    RangeMaxResult query_inclusive(int left, int right) const;
    int size() const;

  private:
    static constexpr std::int64_t kNegativeInfinity = std::numeric_limits<std::int64_t>::lowest();

    int n_{0};
    int tree_size_{1};
    std::vector<std::int64_t> tree_;

    std::int64_t query_max_half_open(int left, int right) const;
    void collect_matches(
        int node,
        int node_left,
        int node_right,
        int query_left,
        int query_right,
        std::int64_t target,
        std::vector<int>& matched_indices
    ) const;
};

}  // namespace algo_module
