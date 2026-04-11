#pragma once

#include <cstdint>
#include <vector>

namespace algo_engine {

class HistoricalDominance3dCdqCounter {
  public:
    struct Point {
        int order{0};
        std::int64_t primary_value_scaled{0};
        std::int64_t secondary_value_scaled{0};
        int tertiary_rank{0};
    };

    HistoricalDominance3dCdqCounter(
        std::vector<std::int64_t> primary_values_scaled,
        std::vector<std::int64_t> secondary_values_scaled,
        std::vector<std::int64_t> tertiary_values_scaled
    );

    std::vector<std::int64_t> count_prefix_dominance() const;
    int size() const;

  private:
    int n_{0};
    int tertiary_rank_count_{0};
    std::vector<Point> points_;
};

}  // namespace algo_engine
