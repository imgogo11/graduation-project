#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "algo_engine/cdq/historical_dominance_cdq.hpp"

namespace {

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    using algo_engine::HistoricalDominanceCdqCounter;

    try {
        HistoricalDominanceCdqCounter counter({5, 3, 7, 7, 8}, {4, 6, 2, 4, 4});
        const auto dominated_counts = counter.count_prefix_dominance();

        expect(
            dominated_counts == std::vector<std::int64_t>({0, 0, 0, 2, 3}),
            "dominated counts should match the expected prefix dominance results"
        );
        expect(counter.size() == 5, "counter size should match the point count");

        HistoricalDominanceCdqCounter duplicate_counter({2, 2, 2}, {3, 3, 3});
        const auto duplicate_counts = duplicate_counter.count_prefix_dominance();
        expect(
            duplicate_counts == std::vector<std::int64_t>({0, 1, 2}),
            "duplicate points should dominate later duplicates"
        );

        HistoricalDominanceCdqCounter empty_counter({}, {});
        expect(empty_counter.count_prefix_dominance().empty(), "empty input should return an empty result set");

        bool invalid_input_thrown = false;
        try {
            static_cast<void>(HistoricalDominanceCdqCounter({1, 2}, {1}));
        } catch (const std::invalid_argument&) {
            invalid_input_thrown = true;
        }
        expect(invalid_input_thrown, "mismatched input sizes should throw std::invalid_argument");
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }

    return 0;
}
