#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

#include "algo_engine/segment_tree/range_kth_persistent_segment_tree.hpp"

namespace {

void expect(bool condition, const std::string& message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

}  // namespace

int main() {
    using algo_engine::RangeKthPersistentSegmentTree;

    try {
        RangeKthPersistentSegmentTree tree({100, 250, 250, 80, 300});

        const auto first_largest = tree.query_inclusive(0, 4, 1);
        expect(first_largest.kth_value_scaled == 300, "k=1 should return the largest value");
        expect(first_largest.matched_indices == std::vector<int>({4}), "k=1 matches should be [4]");

        const auto second_largest = tree.query_inclusive(0, 4, 2);
        expect(second_largest.kth_value_scaled == 250, "k=2 should return 250");
        expect(second_largest.matched_indices == std::vector<int>({1, 2}), "k=2 matches should be [1, 2]");

        const auto third_largest = tree.query_inclusive(0, 4, 3);
        expect(third_largest.kth_value_scaled == 250, "k=3 should still return 250 because duplicates count");
        expect(third_largest.matched_indices == std::vector<int>({1, 2}), "k=3 matches should be [1, 2]");

        const auto smallest = tree.query_inclusive(0, 4, 5);
        expect(smallest.kth_value_scaled == 80, "k=n should return the smallest value");
        expect(smallest.matched_indices == std::vector<int>({3}), "k=n matches should be [3]");

        const auto single_point = tree.query_inclusive(3, 3, 1);
        expect(single_point.kth_value_scaled == 80, "single-point query should return the point value");
        expect(single_point.matched_indices == std::vector<int>({3}), "single-point matches should be [3]");

        bool invalid_k_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(0, 4, 0));
        } catch (const std::invalid_argument&) {
            invalid_k_thrown = true;
        }
        expect(invalid_k_thrown, "k <= 0 should throw std::invalid_argument");

        invalid_k_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(0, 4, 6));
        } catch (const std::invalid_argument&) {
            invalid_k_thrown = true;
        }
        expect(invalid_k_thrown, "k larger than interval size should throw std::invalid_argument");

        bool invalid_range_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(4, 3, 1));
        } catch (const std::invalid_argument&) {
            invalid_range_thrown = true;
        }
        expect(invalid_range_thrown, "left > right should throw std::invalid_argument");

        bool out_of_range_thrown = false;
        try {
            static_cast<void>(tree.query_inclusive(-1, 1, 1));
        } catch (const std::out_of_range&) {
            out_of_range_thrown = true;
        }
        expect(out_of_range_thrown, "out-of-range query should throw std::out_of_range");

        RangeKthPersistentSegmentTree empty_tree({});
        out_of_range_thrown = false;
        try {
            static_cast<void>(empty_tree.query_inclusive(0, 0, 1));
        } catch (const std::out_of_range&) {
            out_of_range_thrown = true;
        }
        expect(out_of_range_thrown, "querying an empty tree should throw std::out_of_range");
    } catch (const std::exception& exc) {
        std::cerr << exc.what() << '\n';
        return 1;
    }

    return 0;
}
