#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "algo_module/cdq/historical_dominance_cdq_3d.hpp"

namespace {

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    using algo_module::HistoricalDominance3dCdqCounter;

    try {
        HistoricalDominance3dCdqCounter counter({5, 3, 7, 7, 8}, {4, 6, 2, 4, 4}, {3, 3, 1, 4, 4});
        const auto dominated_counts = counter.count_prefix_dominance();
        expect(
            dominated_counts == std::vector<std::int64_t>({0, 0, 0, 2, 3}),
            "3D dominated counts should match the expected prefix dominance results"
        );
        expect(counter.size() == 5, "3D counter size should match the point count");

        HistoricalDominance3dCdqCounter duplicate_counter({2, 2, 2}, {3, 3, 3}, {4, 4, 4});
        const auto duplicate_counts = duplicate_counter.count_prefix_dominance();
        expect(
            duplicate_counts == std::vector<std::int64_t>({0, 1, 2}),
            "duplicate 3D points should dominate later duplicates"
        );

        HistoricalDominance3dCdqCounter mixed_counter({2, 4, 4, 4}, {2, 1, 3, 3}, {2, 1, 2, 4});
        const auto mixed_counts = mixed_counter.count_prefix_dominance();
        expect(
            mixed_counts == std::vector<std::int64_t>({0, 0, 2, 3}),
            "3D counter should respect all three dominance dimensions"
        );

        HistoricalDominance3dCdqCounter empty_counter({}, {}, {});
        expect(empty_counter.count_prefix_dominance().empty(), "empty 3D input should return an empty result set");

        bool invalid_input_thrown = false;
        try {
            static_cast<void>(HistoricalDominance3dCdqCounter({1, 2}, {1, 2}, {1}));
        } catch (const std::invalid_argument&) {
            invalid_input_thrown = true;
        }
        expect(invalid_input_thrown, "mismatched 3D input sizes should throw std::invalid_argument");
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }

    return 0;
}
