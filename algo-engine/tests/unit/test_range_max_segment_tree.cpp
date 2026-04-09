#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "algo_engine/segment_tree/range_max_segment_tree.hpp"

namespace {

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    using algo_engine::RangeMaxSegmentTree;

    try {
        RangeMaxSegmentTree tree({100, 250, 250, 80});

        const auto full_range = tree.query_inclusive(0, 3);
        expect(full_range.max_value_scaled == 250, "full range max should be 250");
        expect(full_range.matched_indices == std::vector<int>({1, 2}), "full range indices should be [1, 2]");

        const auto single_point = tree.query_inclusive(3, 3);
        expect(single_point.max_value_scaled == 80, "single point max should be 80");
        expect(single_point.matched_indices == std::vector<int>({3}), "single point indices should be [3]");

        bool invalid_range_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(2, 1));
        } catch (const std::invalid_argument&) {
            invalid_range_thrown = true;
        }
        expect(invalid_range_thrown, "left > right should throw std::invalid_argument");

        bool out_of_range_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(-1, 1));
        } catch (const std::out_of_range&) {
            out_of_range_thrown = true;
        }
        expect(out_of_range_thrown, "out-of-range query should throw std::out_of_range");
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }

    return 0;
}
