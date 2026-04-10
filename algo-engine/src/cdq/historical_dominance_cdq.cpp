#include "algo_engine/cdq/historical_dominance_cdq.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>

namespace algo_engine {
namespace {

class FenwickTree {
  public:
    explicit FenwickTree(int size) : tree_(static_cast<std::size_t>(size) + 1, 0) {}

    void add(int index, std::int64_t delta) {
        while (index < static_cast<int>(tree_.size())) {
            tree_[static_cast<std::size_t>(index)] += delta;
            index += index & -index;
        }
    }

    [[nodiscard]] std::int64_t prefix_sum(int index) const {
        std::int64_t result = 0;
        while (index > 0) {
            result += tree_[static_cast<std::size_t>(index)];
            index -= index & -index;
        }
        return result;
    }

  private:
    std::vector<std::int64_t> tree_;
};

void cdq_count(
    std::vector<HistoricalDominanceCdqCounter::Point>& points,
    std::vector<HistoricalDominanceCdqCounter::Point>& buffer,
    int left,
    int right,
    FenwickTree& fenwick_tree,
    std::vector<std::int64_t>& dominated_counts
) {
    if (left >= right) {
        return;
    }

    const int mid = left + (right - left) / 2;
    cdq_count(points, buffer, left, mid, fenwick_tree, dominated_counts);
    cdq_count(points, buffer, mid + 1, right, fenwick_tree, dominated_counts);

    int left_index = left;
    int right_index = mid + 1;
    int merge_index = left;
    std::vector<int> added_secondary_ranks;
    added_secondary_ranks.reserve(static_cast<std::size_t>(mid - left + 1));

    while (right_index <= right) {
        while (left_index <= mid && points[left_index].primary_value_scaled <= points[right_index].primary_value_scaled) {
            fenwick_tree.add(points[left_index].secondary_rank, 1);
            added_secondary_ranks.push_back(points[left_index].secondary_rank);
            buffer[static_cast<std::size_t>(merge_index++)] = points[left_index++];
        }

        dominated_counts[static_cast<std::size_t>(points[right_index].order)] +=
            fenwick_tree.prefix_sum(points[right_index].secondary_rank);
        buffer[static_cast<std::size_t>(merge_index++)] = points[right_index++];
    }

    while (left_index <= mid) {
        buffer[static_cast<std::size_t>(merge_index++)] = points[left_index++];
    }

    for (const int secondary_rank : added_secondary_ranks) {
        fenwick_tree.add(secondary_rank, -1);
    }

    std::copy(
        buffer.begin() + left,
        buffer.begin() + right + 1,
        points.begin() + left
    );
}

}  // namespace

HistoricalDominanceCdqCounter::HistoricalDominanceCdqCounter(
    std::vector<std::int64_t> primary_values_scaled,
    std::vector<std::int64_t> secondary_values_scaled
) : n_(static_cast<int>(primary_values_scaled.size())) {
    if (primary_values_scaled.size() != secondary_values_scaled.size()) {
        throw std::invalid_argument("primary and secondary value vectors must have the same size");
    }

    if (n_ == 0) {
        return;
    }

    std::vector<std::int64_t> unique_secondary_values = secondary_values_scaled;
    std::sort(unique_secondary_values.begin(), unique_secondary_values.end());
    unique_secondary_values.erase(
        std::unique(unique_secondary_values.begin(), unique_secondary_values.end()),
        unique_secondary_values.end()
    );
    secondary_rank_count_ = static_cast<int>(unique_secondary_values.size());

    points_.reserve(static_cast<std::size_t>(n_));
    for (int index = 0; index < n_; ++index) {
        const auto iterator = std::lower_bound(
            unique_secondary_values.begin(),
            unique_secondary_values.end(),
            secondary_values_scaled[static_cast<std::size_t>(index)]
        );
        const int secondary_rank = static_cast<int>(iterator - unique_secondary_values.begin()) + 1;
        points_.push_back(Point{
            .order = index,
            .primary_value_scaled = primary_values_scaled[static_cast<std::size_t>(index)],
            .secondary_rank = secondary_rank,
        });
    }
}

std::vector<std::int64_t> HistoricalDominanceCdqCounter::count_prefix_dominance() const {
    if (n_ == 0) {
        return {};
    }

    std::vector<Point> working_points = points_;
    std::vector<Point> buffer(static_cast<std::size_t>(n_));
    std::vector<std::int64_t> dominated_counts(static_cast<std::size_t>(n_), 0);
    FenwickTree fenwick_tree(secondary_rank_count_);

    cdq_count(working_points, buffer, 0, n_ - 1, fenwick_tree, dominated_counts);
    return dominated_counts;
}

int HistoricalDominanceCdqCounter::size() const {
    return n_;
}

}  // namespace algo_engine
