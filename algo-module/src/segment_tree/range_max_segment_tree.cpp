#include "algo_module/segment_tree/range_max_segment_tree.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace algo_module {

RangeMaxSegmentTree::RangeMaxSegmentTree(std::vector<std::int64_t> values) : n_(static_cast<int>(values.size())) {
    while (tree_size_ < std::max(1, n_)) {
        tree_size_ <<= 1;
    }

    tree_.assign(tree_size_ * 2, kNegativeInfinity);
    for (int index = 0; index < n_; ++index) {
        tree_[tree_size_ + index] = values[index];
    }
    for (int node = tree_size_ - 1; node > 0; --node) {
        tree_[node] = std::max(tree_[node * 2], tree_[node * 2 + 1]);
    }
}

RangeMaxResult RangeMaxSegmentTree::query_inclusive(int left, int right) const {
    if (n_ == 0) {
        throw std::out_of_range("segment tree is empty");
    }
    if (left < 0 || right < 0 || left >= n_ || right >= n_) {
        throw std::out_of_range("query indices are out of range");
    }
    if (left > right) {
        throw std::invalid_argument("left index must be less than or equal to right index");
    }

    const std::int64_t max_value_scaled = query_max_half_open(left, right + 1);
    std::vector<int> matched_indices;
    collect_matches(1, 0, tree_size_ - 1, left, right, max_value_scaled, matched_indices);
    return RangeMaxResult{max_value_scaled, std::move(matched_indices)};
}

int RangeMaxSegmentTree::size() const {
    return n_;
}

std::int64_t RangeMaxSegmentTree::query_max_half_open(int left, int right) const {
    std::int64_t result = kNegativeInfinity;
    left += tree_size_;
    right += tree_size_;

    while (left < right) {
        if ((left & 1) == 1) {
            result = std::max(result, tree_[left]);
            ++left;
        }
        if ((right & 1) == 1) {
            --right;
            result = std::max(result, tree_[right]);
        }
        left >>= 1;
        right >>= 1;
    }
    return result;
}

void RangeMaxSegmentTree::collect_matches(
    int node,
    int node_left,
    int node_right,
    int query_left,
    int query_right,
    std::int64_t target,
    std::vector<int>& matched_indices
) const {
    if (query_right < node_left || node_right < query_left) {
        return;
    }
    if (tree_[node] < target) {
        return;
    }
    if (node_left == node_right) {
        if (node_left < n_ && tree_[node] == target) {
            matched_indices.push_back(node_left);
        }
        return;
    }

    const int mid = node_left + (node_right - node_left) / 2;
    collect_matches(node * 2, node_left, mid, query_left, query_right, target, matched_indices);
    collect_matches(node * 2 + 1, mid + 1, node_right, query_left, query_right, target, matched_indices);
}

}  // namespace algo_module
