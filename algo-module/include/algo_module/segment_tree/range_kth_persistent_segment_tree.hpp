#pragma once

#include <cstdint>
#include <vector>

namespace algo_module {

struct RangeKthResult {
    std::int64_t kth_value_scaled;
    std::vector<int> matched_indices;
};

class RangeKthPersistentSegmentTree {
  public:
    explicit RangeKthPersistentSegmentTree(std::vector<std::int64_t> values);

    RangeKthResult query_inclusive(int left, int right, int k) const;
    int size() const;

  private:
    struct Node {
        int left_child{0};
        int right_child{0};
        int count{0};
    };

    int n_{0};
    std::vector<std::int64_t> unique_values_;
    std::vector<std::vector<int>> positions_by_compressed_index_;
    std::vector<int> roots_;
    std::vector<Node> nodes_;

    int update(int previous_node, int node_left, int node_right, int position);
    int query_kth_largest(int left_root, int right_root, int node_left, int node_right, int k) const;
    void validate_query(int left, int right, int k) const;
    std::vector<int> collect_matches(int compressed_index, int left, int right) const;
};

}  // namespace algo_module
