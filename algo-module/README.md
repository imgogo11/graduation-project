# Algo Module

This directory hosts the C++ algorithm module and pybind11 binding layer for the graduation project.

## Layout

- `include/algo_module/`: public headers grouped by algorithm family
- `src/`: C++ implementation files
- `bindings/python/`: pybind11 module export entry
- `tests/unit/`: C++ unit tests executed through CTest
- `tests/integration/`: Python binding smoke tests for `algo_module_py`

## Build

```powershell
cmake -S algo-module -B algo-module/build -DPython_EXECUTABLE="<python>" -Dpybind11_DIR="<pybind11-cmake-dir>"
cmake --build algo-module/build
ctest --test-dir algo-module/build --output-on-failure
```

## Targets

- `algo_module_core`: C++ static library with segment tree and CDQ implementations
- `algo_module_py`: Python extension module loaded by `backend/app/algo_bridge/`
- `algo_module_tests`: convenience target that builds all tests and the Python extension
