#include "algo_engine/segment_tree/range_kth_persistent_segment_tree.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace algo_engine {

RangeKthPersistentSegmentTree::RangeKthPersistentSegmentTree(std::vector<std::int64_t> values)
    : n_(static_cast<int>(values.size())) {
    nodes_.push_back(Node{});
    roots_.reserve(n_ + 1);
    roots_.push_back(0);

    if (n_ == 0) {
        return;
    }

    unique_values_ = values;
    std::sort(unique_values_.begin(), unique_values_.end());
    unique_values_.erase(std::unique(unique_values_.begin(), unique_values_.end()), unique_values_.end());

    positions_by_compressed_index_.assign(unique_values_.size(), {});

    for (int index = 0; index < n_; ++index) {
        const int compressed_index = static_cast<int>(
            std::lower_bound(unique_values_.begin(), unique_values_.end(), values[index]) - unique_values_.begin()
        );
        positions_by_compressed_index_[compressed_index].push_back(index);
        roots_.push_back(update(roots_.back(), 0, static_cast<int>(unique_values_.size()) - 1, compressed_index));
    }
}

RangeKthResult RangeKthPersistentSegmentTree::query_inclusive(int left, int right, int k) const {
    validate_query(left, right, k);

    const int compressed_index =
        query_kth_largest(roots_[left], roots_[right + 1], 0, static_cast<int>(unique_values_.size()) - 1, k);
    return RangeKthResult{
        unique_values_[compressed_index],
        collect_matches(compressed_index, left, right),
    };
}

int RangeKthPersistentSegmentTree::size() const {
    return n_;
}

int RangeKthPersistentSegmentTree::update(int previous_node, int node_left, int node_right, int position) {
    nodes_.push_back(nodes_[previous_node]);
    const int current_node = static_cast<int>(nodes_.size()) - 1;
    nodes_[current_node].count += 1;

    if (node_left == node_right) {
        return current_node;
    }

    const int mid = node_left + (node_right - node_left) / 2;
    if (position <= mid) {
        nodes_[current_node].left_child = update(nodes_[previous_node].left_child, node_left, mid, position);
    } else {
        nodes_[current_node].right_child = update(nodes_[previous_node].right_child, mid + 1, node_right, position);
    }
    return current_node;
}

int RangeKthPersistentSegmentTree::query_kth_largest(
    int left_root,
    int right_root,
    int node_left,
    int node_right,
    int k
) const {
    if (node_left == node_right) {
        return node_left;
    }

    const int right_left_child = nodes_[right_root].right_child;
    const int left_left_child = nodes_[left_root].right_child;
    const int right_count = nodes_[right_left_child].count - nodes_[left_left_child].count;
    const int mid = node_left + (node_right - node_left) / 2;
    if (right_count >= k) {
        return query_kth_largest(nodes_[left_root].right_child, nodes_[right_root].right_child, mid + 1, node_right, k);
    }
    return query_kth_largest(
        nodes_[left_root].left_child,
        nodes_[right_root].left_child,
        node_left,
        mid,
        k - right_count
    );
}

void RangeKthPersistentSegmentTree::validate_query(int left, int right, int k) const {
    if (n_ == 0) {
        throw std::out_of_range("persistent segment tree is empty");
    }
    if (left < 0 || right < 0 || left >= n_ || right >= n_) {
        throw std::out_of_range("query indices are out of range");
    }
    if (left > right) {
        throw std::invalid_argument("left index must be less than or equal to right index");
    }

    const int interval_length = right - left + 1;
    if (k <= 0 || k > interval_length) {
        throw std::invalid_argument("k must be between 1 and the interval length");
    }
}

std::vector<int> RangeKthPersistentSegmentTree::collect_matches(int compressed_index, int left, int right) const {
    const auto& positions = positions_by_compressed_index_[compressed_index];
    const auto first = std::lower_bound(positions.begin(), positions.end(), left);
    const auto last = std::upper_bound(positions.begin(), positions.end(), right);
    return std::vector<int>(first, last);
}

}  // namespace algo_engine
