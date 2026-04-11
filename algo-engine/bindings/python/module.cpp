#include <cstdint>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "algo_engine/cdq/historical_dominance_cdq.hpp"
#include "algo_engine/cdq/historical_dominance_cdq_3d.hpp"
#include "algo_engine/segment_tree/range_kth_persistent_segment_tree.hpp"
#include "algo_engine/segment_tree/range_max_segment_tree.hpp"

namespace py = pybind11;

PYBIND11_MODULE(algo_engine_py, module) {
    module.doc() = "Python bindings for the graduation project algo engine.";

    py::class_<algo_engine::RangeMaxResult>(module, "RangeMaxResult")
        .def_readonly("max_value_scaled", &algo_engine::RangeMaxResult::max_value_scaled)
        .def_readonly("matched_indices", &algo_engine::RangeMaxResult::matched_indices);

    py::class_<algo_engine::RangeKthResult>(module, "RangeKthResult")
        .def_readonly("kth_value_scaled", &algo_engine::RangeKthResult::kth_value_scaled)
        .def_readonly("matched_indices", &algo_engine::RangeKthResult::matched_indices);

    py::class_<algo_engine::RangeMaxSegmentTree>(module, "RangeMaxSegmentTree")
        .def(py::init<std::vector<std::int64_t>>(), py::arg("values"))
        .def("query_inclusive", &algo_engine::RangeMaxSegmentTree::query_inclusive, py::arg("left"), py::arg("right"))
        .def("size", &algo_engine::RangeMaxSegmentTree::size);

    py::class_<algo_engine::RangeKthPersistentSegmentTree>(module, "RangeKthPersistentSegmentTree")
        .def(py::init<std::vector<std::int64_t>>(), py::arg("values"))
        .def(
            "query_inclusive",
            &algo_engine::RangeKthPersistentSegmentTree::query_inclusive,
            py::arg("left"),
            py::arg("right"),
            py::arg("k")
        )
        .def("size", &algo_engine::RangeKthPersistentSegmentTree::size);

    py::class_<algo_engine::HistoricalDominanceCdqCounter>(module, "HistoricalDominanceCdqCounter")
        .def(
            py::init<std::vector<std::int64_t>, std::vector<std::int64_t>>(),
            py::arg("primary_values_scaled"),
            py::arg("secondary_values_scaled")
        )
        .def("count_prefix_dominance", &algo_engine::HistoricalDominanceCdqCounter::count_prefix_dominance)
        .def("size", &algo_engine::HistoricalDominanceCdqCounter::size);

    py::class_<algo_engine::HistoricalDominance3dCdqCounter>(module, "HistoricalDominance3dCdqCounter")
        .def(
            py::init<std::vector<std::int64_t>, std::vector<std::int64_t>, std::vector<std::int64_t>>(),
            py::arg("primary_values_scaled"),
            py::arg("secondary_values_scaled"),
            py::arg("tertiary_values_scaled")
        )
        .def("count_prefix_dominance", &algo_engine::HistoricalDominance3dCdqCounter::count_prefix_dominance)
        .def("size", &algo_engine::HistoricalDominance3dCdqCounter::size);
}
