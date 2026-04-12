#pragma once

#include <cstdint>
#include <vector>

namespace algo_module {

class HistoricalDominanceCdqCounter {
  public:
    struct Point {
        int order{0};
        std::int64_t primary_value_scaled{0};
        int secondary_rank{0};
    };

    HistoricalDominanceCdqCounter(
        std::vector<std::int64_t> primary_values_scaled,
        std::vector<std::int64_t> secondary_values_scaled
    );

    std::vector<std::int64_t> count_prefix_dominance() const;
    int size() const;

  private:
    int n_{0};
    int secondary_rank_count_{0};
    std::vector<Point> points_;
};

}  // namespace algo_module
