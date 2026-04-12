#include <cstdint>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "algo_module/cdq/historical_dominance_cdq.hpp"
#include "algo_module/cdq/historical_dominance_cdq_3d.hpp"
#include "algo_module/segment_tree/range_kth_persistent_segment_tree.hpp"
#include "algo_module/segment_tree/range_max_segment_tree.hpp"

namespace py = pybind11;

PYBIND11_MODULE(algo_module_py, module) {
    module.doc() = "Python bindings for the graduation project algo engine.";

    py::class_<algo_module::RangeMaxResult>(module, "RangeMaxResult")
        .def_readonly("max_value_scaled", &algo_module::RangeMaxResult::max_value_scaled)
        .def_readonly("matched_indices", &algo_module::RangeMaxResult::matched_indices);

    py::class_<algo_module::RangeKthResult>(module, "RangeKthResult")
        .def_readonly("kth_value_scaled", &algo_module::RangeKthResult::kth_value_scaled)
        .def_readonly("matched_indices", &algo_module::RangeKthResult::matched_indices);

    py::class_<algo_module::RangeMaxSegmentTree>(module, "RangeMaxSegmentTree")
        .def(py::init<std::vector<std::int64_t>>(), py::arg("values"))
        .def("query_inclusive", &algo_module::RangeMaxSegmentTree::query_inclusive, py::arg("left"), py::arg("right"))
        .def("size", &algo_module::RangeMaxSegmentTree::size);

    py::class_<algo_module::RangeKthPersistentSegmentTree>(module, "RangeKthPersistentSegmentTree")
        .def(py::init<std::vector<std::int64_t>>(), py::arg("values"))
        .def(
            "query_inclusive",
            &algo_module::RangeKthPersistentSegmentTree::query_inclusive,
            py::arg("left"),
            py::arg("right"),
            py::arg("k")
        )
        .def("size", &algo_module::RangeKthPersistentSegmentTree::size);

    py::class_<algo_module::HistoricalDominanceCdqCounter>(module, "HistoricalDominanceCdqCounter")
        .def(
            py::init<std::vector<std::int64_t>, std::vector<std::int64_t>>(),
            py::arg("primary_values_scaled"),
            py::arg("secondary_values_scaled")
        )
        .def("count_prefix_dominance", &algo_module::HistoricalDominanceCdqCounter::count_prefix_dominance)
        .def("size", &algo_module::HistoricalDominanceCdqCounter::size);

    py::class_<algo_module::HistoricalDominance3dCdqCounter>(module, "HistoricalDominance3dCdqCounter")
        .def(
            py::init<std::vector<std::int64_t>, std::vector<std::int64_t>, std::vector<std::int64_t>>(),
            py::arg("primary_values_scaled"),
            py::arg("secondary_values_scaled"),
            py::arg("tertiary_values_scaled")
        )
        .def("count_prefix_dominance", &algo_module::HistoricalDominance3dCdqCounter::count_prefix_dominance)
        .def("size", &algo_module::HistoricalDominance3dCdqCounter::size);
}
