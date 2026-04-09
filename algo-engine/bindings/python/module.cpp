#include <cstdint>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "algo_engine/segment_tree/range_max_segment_tree.hpp"

namespace py = pybind11;

PYBIND11_MODULE(algo_engine_py, module) {
    module.doc() = "Python bindings for the graduation project algo engine.";

    py::class_<algo_engine::RangeMaxResult>(module, "RangeMaxResult")
        .def_readonly("max_value_scaled", &algo_engine::RangeMaxResult::max_value_scaled)
        .def_readonly("matched_indices", &algo_engine::RangeMaxResult::matched_indices);

    py::class_<algo_engine::RangeMaxSegmentTree>(module, "RangeMaxSegmentTree")
        .def(py::init<std::vector<std::int64_t>>(), py::arg("values"))
        .def("query_inclusive", &algo_engine::RangeMaxSegmentTree::query_inclusive, py::arg("left"), py::arg("right"))
        .def("size", &algo_engine::RangeMaxSegmentTree::size);
}
