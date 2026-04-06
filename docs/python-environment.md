# Python 环境管理

## 目标

本项目采用“**全仓库一个 Python 虚拟环境**”的方式管理，体验上接近 PyCharm 为单个项目创建独立虚拟环境，但依赖入口统一改为 `uv + pyproject.toml`。

## 约定

- Python 版本：`3.13`
- 虚拟环境目录：根目录 `.venv/`
- 依赖主入口：根目录 `pyproject.toml`
- 兼容文件：`backend/requirements.txt`、`backend/requirements-optional.txt`

## 推荐命令

创建环境：

```powershell
uv venv .venv --python 3.13
```

安装默认依赖：

```powershell
uv sync
```

安装扩展数据源依赖：

```powershell
uv sync --extra data-sources
```

运行脚本：

```powershell
uv run python backend/scripts/check_environment.py
uv run python backend/scripts/generate_ecommerce_synthetic.py --order-count 100000
```

运行测试：

```powershell
uv run python -m unittest discover backend/tests -v
```

导出兼容层 requirements：

```powershell
uv run python backend/scripts/export_requirements.py
```

## PyCharm 使用建议

1. 打开整个仓库根目录 `D:\graduation-project`
2. 解释器选择根目录 `.venv\Scripts\python.exe`
3. 后续依赖安装以 `uv sync` 为准，不在 PyCharm 里手动逐个安装包

## 回退预案

默认先沿用 `Python 3.13`。如果未来在 `pybind11`、C++ 扩展编译或某些第三方依赖上出现兼容问题，再把 `.python-version` 改为 `3.11`，重建 `.venv` 后重新执行 `uv sync`。
