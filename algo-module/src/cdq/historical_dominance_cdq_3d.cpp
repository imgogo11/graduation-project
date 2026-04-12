#include "algo_module/cdq/historical_dominance_cdq_3d.hpp"

#include <algorithm>
#include <stdexcept>
#include <utility>
#include <vector>

namespace algo_module {
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

struct CrossPoint {
    int answer_index{0};
    std::int64_t primary_value_scaled{0};
    std::int64_t secondary_value_scaled{0};
    int tertiary_rank{0};
    bool is_update{false};
};

bool compare_by_primary(
    const CrossPoint& left,
    const CrossPoint& right
) {
    if (left.primary_value_scaled != right.primary_value_scaled) {
        return left.primary_value_scaled < right.primary_value_scaled;
    }
    if (left.is_update != right.is_update) {
        return left.is_update && !right.is_update;
    }
    if (left.secondary_value_scaled != right.secondary_value_scaled) {
        return left.secondary_value_scaled < right.secondary_value_scaled;
    }
    return left.tertiary_rank < right.tertiary_rank;
}

void count_cross_3d(
    std::vector<CrossPoint>& points,
    std::vector<CrossPoint>& buffer,
    int left,
    int right,
    FenwickTree& fenwick_tree,
    std::vector<std::int64_t>& dominated_counts
) {
    if (left >= right) {
        return;
    }

    const int mid = left + (right - left) / 2;
    count_cross_3d(points, buffer, left, mid, fenwick_tree, dominated_counts);
    count_cross_3d(points, buffer, mid + 1, right, fenwick_tree, dominated_counts);

    int left_index = left;
    int right_index = mid + 1;
    int merge_index = left;
    std::vector<int> added_tertiary_ranks;
    added_tertiary_ranks.reserve(static_cast<std::size_t>(mid - left + 1));

    while (left_index <= mid && right_index <= right) {
        if (points[left_index].secondary_value_scaled <= points[right_index].secondary_value_scaled) {
            if (points[left_index].is_update) {
                fenwick_tree.add(points[left_index].tertiary_rank, 1);
                added_tertiary_ranks.push_back(points[left_index].tertiary_rank);
            }
            buffer[static_cast<std::size_t>(merge_index++)] = points[left_index++];
        } else {
            if (!points[right_index].is_update) {
                dominated_counts[static_cast<std::size_t>(points[right_index].answer_index)] +=
                    fenwick_tree.prefix_sum(points[right_index].tertiary_rank);
            }
            buffer[static_cast<std::size_t>(merge_index++)] = points[right_index++];
        }
    }

    while (right_index <= right) {
        if (!points[right_index].is_update) {
            dominated_counts[static_cast<std::size_t>(points[right_index].answer_index)] +=
                fenwick_tree.prefix_sum(points[right_index].tertiary_rank);
        }
        buffer[static_cast<std::size_t>(merge_index++)] = points[right_index++];
    }

    while (left_index <= mid) {
        buffer[static_cast<std::size_t>(merge_index++)] = points[left_index++];
    }

    for (const int tertiary_rank : added_tertiary_ranks) {
        fenwick_tree.add(tertiary_rank, -1);
    }

    std::copy(
        buffer.begin() + left,
        buffer.begin() + right + 1,
        points.begin() + left
    );
}

void count_prefix_recursive(
    const std::vector<HistoricalDominance3dCdqCounter::Point>& points,
    int left,
    int right,
    int tertiary_rank_count,
    std::vector<std::int64_t>& dominated_counts
) {
    if (left >= right) {
        return;
    }

    const int mid = left + (right - left) / 2;
    count_prefix_recursive(points, left, mid, tertiary_rank_count, dominated_counts);
    count_prefix_recursive(points, mid + 1, right, tertiary_rank_count, dominated_counts);

    std::vector<CrossPoint> cross_points;
    cross_points.reserve(static_cast<std::size_t>(right - left + 1));

    for (int index = left; index <= mid; ++index) {
        const auto& point = points[static_cast<std::size_t>(index)];
        cross_points.push_back(CrossPoint{
            .answer_index = point.order,
            .primary_value_scaled = point.primary_value_scaled,
            .secondary_value_scaled = point.secondary_value_scaled,
            .tertiary_rank = point.tertiary_rank,
            .is_update = true,
        });
    }
    for (int index = mid + 1; index <= right; ++index) {
        const auto& point = points[static_cast<std::size_t>(index)];
        cross_points.push_back(CrossPoint{
            .answer_index = point.order,
            .primary_value_scaled = point.primary_value_scaled,
            .secondary_value_scaled = point.secondary_value_scaled,
            .tertiary_rank = point.tertiary_rank,
            .is_update = false,
        });
    }

    std::sort(cross_points.begin(), cross_points.end(), compare_by_primary);
    std::vector<CrossPoint> buffer(cross_points.size());
    FenwickTree fenwick_tree(tertiary_rank_count);
    count_cross_3d(
        cross_points,
        buffer,
        0,
        static_cast<int>(cross_points.size()) - 1,
        fenwick_tree,
        dominated_counts
    );
}

}  // namespace

HistoricalDominance3dCdqCounter::HistoricalDominance3dCdqCounter(
    std::vector<std::int64_t> primary_values_scaled,
    std::vector<std::int64_t> secondary_values_scaled,
    std::vector<std::int64_t> tertiary_values_scaled
) : n_(static_cast<int>(primary_values_scaled.size())) {
    if (
        primary_values_scaled.size() != secondary_values_scaled.size()
        || primary_values_scaled.size() != tertiary_values_scaled.size()
    ) {
        throw std::invalid_argument("primary, secondary, and tertiary value vectors must have the same size");
    }

    if (n_ == 0) {
        return;
    }

    std::vector<std::int64_t> unique_tertiary_values = tertiary_values_scaled;
    std::sort(unique_tertiary_values.begin(), unique_tertiary_values.end());
    unique_tertiary_values.erase(
        std::unique(unique_tertiary_values.begin(), unique_tertiary_values.end()),
        unique_tertiary_values.end()
    );
    tertiary_rank_count_ = static_cast<int>(unique_tertiary_values.size());

    points_.reserve(static_cast<std::size_t>(n_));
    for (int index = 0; index < n_; ++index) {
        const auto tertiary_iterator = std::lower_bound(
            unique_tertiary_values.begin(),
            unique_tertiary_values.end(),
            tertiary_values_scaled[static_cast<std::size_t>(index)]
        );
        const int tertiary_rank = static_cast<int>(tertiary_iterator - unique_tertiary_values.begin()) + 1;
        points_.push_back(Point{
            .order = index,
            .primary_value_scaled = primary_values_scaled[static_cast<std::size_t>(index)],
            .secondary_value_scaled = secondary_values_scaled[static_cast<std::size_t>(index)],
            .tertiary_rank = tertiary_rank,
        });
    }
}

std::vector<std::int64_t> HistoricalDominance3dCdqCounter::count_prefix_dominance() const {
    if (n_ == 0) {
        return {};
    }

    std::vector<std::int64_t> dominated_counts(static_cast<std::size_t>(n_), 0);
    count_prefix_recursive(points_, 0, n_ - 1, tertiary_rank_count_, dominated_counts);
    return dominated_counts;
}

int HistoricalDominance3dCdqCounter::size() const {
    return n_;
}

}  // namespace algo_module
