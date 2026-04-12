cmake_minimum_required(VERSION 3.20)

project(algo_module LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

add_library(
    algo_module_core
    STATIC
        src/cdq/historical_dominance_cdq.cpp
        src/cdq/historical_dominance_cdq_3d.cpp
        src/segment_tree/range_kth_persistent_segment_tree.cpp
        src/segment_tree/range_max_segment_tree.cpp
)
target_include_directories(
    algo_module_core
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)
target_compile_features(algo_module_core PUBLIC cxx_std_23)

pybind11_add_module(
    algo_module_py
        bindings/python/module.cpp
)
target_link_libraries(algo_module_py PRIVATE algo_module_core)
set_target_properties(
    algo_module_py
    PROPERTIES
        LIBRARY_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/python"
        RUNTIME_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/python"
        ARCHIVE_OUTPUT_DIRECTORY "${PROJECT_BINARY_DIR}/python"
)

if(BUILD_TESTING)
    add_executable(
        range_max_segment_tree_unit
            tests/unit/test_range_max_segment_tree.cpp
    )
    target_link_libraries(range_max_segment_tree_unit PRIVATE algo_module_core)

    add_executable(
        historical_dominance_cdq_unit
            tests/unit/test_historical_dominance_cdq.cpp
    )
    target_link_libraries(historical_dominance_cdq_unit PRIVATE algo_module_core)

    add_executable(
        historical_dominance_cdq_3d_unit
            tests/unit/test_historical_dominance_cdq_3d.cpp
    )
    target_link_libraries(historical_dominance_cdq_3d_unit PRIVATE algo_module_core)

    add_executable(
        range_kth_persistent_segment_tree_unit
            tests/unit/test_range_kth_persistent_segment_tree.cpp
    )
    target_link_libraries(range_kth_persistent_segment_tree_unit PRIVATE algo_module_core)

    add_test(NAME range_max_segment_tree_unit COMMAND range_max_segment_tree_unit)
    add_test(NAME historical_dominance_cdq_unit COMMAND historical_dominance_cdq_unit)
    add_test(NAME historical_dominance_cdq_3d_unit COMMAND historical_dominance_cdq_3d_unit)
    add_test(NAME range_kth_persistent_segment_tree_unit COMMAND range_kth_persistent_segment_tree_unit)
    add_test(
        NAME algo_module_python_smoke
        COMMAND
            ${Python_EXECUTABLE}
            ${PROJECT_SOURCE_DIR}/tests/integration/test_python_binding.py
            ${PROJECT_BINARY_DIR}/python
    )

    add_custom_target(
        algo_module_tests
        DEPENDS
            historical_dominance_cdq_unit
            historical_dominance_cdq_3d_unit
            range_kth_persistent_segment_tree_unit
            range_max_segment_tree_unit
            algo_module_py
    )
endif()
