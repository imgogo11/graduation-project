# 环境基线

## 当前结论

截至 `2026-04-06`，当前机器已经具备前期 MVP 推进所需的基础工具能力。Python 部分现在统一采用“**全仓库一个虚拟环境**”的方式管理。

## 已确认可用

| 项目 | 当前状态 |
| --- | --- |
| Git | 已安装 |
| Node.js | 已安装，当前版本 `24.x` |
| npm | 已安装 |
| Python | 已安装，当前版本 `3.13.x` |
| uv | 已安装 |
| Docker Desktop / Compose | 已安装 |
| VS Code | 已安装 |
| CMake | 已安装 |

## Python 管理方式

- 依赖主入口：根目录 `pyproject.toml`
- Python 版本入口：根目录 `.python-version`
- 虚拟环境目录：根目录 `.venv/`
- 默认版本：`Python 3.13`
- 兼容文件：`backend/requirements.txt`、`backend/requirements-optional.txt`

## 默认工作流

创建虚拟环境：

```powershell
uv venv .venv --python 3.13
```

同步默认依赖：

```powershell
uv sync
```

同步扩展数据源依赖：

```powershell
uv sync --extra data-sources
```

检查项目环境：

```powershell
uv run python backend/scripts/check_environment.py
```

导出兼容 requirements：

```powershell
uv run python backend/scripts/export_requirements.py
```

## 版本建议

- `Node.js` 当前是 `24.x`，可以先用于前期开发，但正式前端依赖若出现兼容问题，优先回退到 `20 LTS`。
- `Python` 当前默认沿用 `3.13.x`。如果后续 `pybind11`、旧轮子包或 C++ 绑定阶段出现兼容问题，再回退到 `3.11`，并重新执行 `uv sync`。

## 配置文件命名

- 根目录 `version-description.txt` 用于保留本机环境与版本检查记录，不再占用 `.env` 名称。
- 真正的运行配置模板为根目录 `.env.template`。
- 后续若接入 FastAPI、数据库和 Docker Compose，建议从 `.env.template` 复制出实际本地 `.env`。

## 验收建议

1. 先运行：

   ```powershell
   uv run python backend/scripts/check_environment.py
   ```

2. 再分别完成：
   - Olist 数据集校验
   - 电商模拟数据生成
   - A 股日线抓取
   - 演示爬虫导出
