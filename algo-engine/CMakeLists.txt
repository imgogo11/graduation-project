cmake_minimum_required(VERSION 3.20)

project(algo_engine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include(CTest)

find_package(Python COMPONENTS Interpreter Development REQUIRED)
find_package(pybind11 CONFIG REQUIRED)

add_library(
    algo_engine_core
    STATIC
        src/segment_tree/range_max_segment_tree.cpp
)
target_include_directories(
    algo_engine_core
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)
target_compile_features(algo_engine_core PUBLIC cxx_std_23)

pybind11_add_module(
    algo_engine_py
        bindings/python/module.cpp
)
target_link_libraries(algo_engine_py PRIVATE algo_engine_core)
set_target_properties(
    algo_engine_py
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
    target_link_libraries(range_max_segment_tree_unit PRIVATE algo_engine_core)

    add_test(NAME range_max_segment_tree_unit COMMAND range_max_segment_tree_unit)
    add_test(
        NAME algo_engine_python_smoke
        COMMAND
            ${Python_EXECUTABLE}
            ${PROJECT_SOURCE_DIR}/tests/integration/test_python_binding.py
            ${PROJECT_BINARY_DIR}/python
    )

    add_custom_target(
        algo_engine_tests
        DEPENDS
            range_max_segment_tree_unit
            algo_engine_py
    )
endif()
