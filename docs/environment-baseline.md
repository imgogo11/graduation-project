# 环境基线

## 当前结论

截至 `2026-04-06`，当前机器已经具备前期 MVP 推进所需的基础工具能力，但还没有装齐项目所需的 Python 依赖。

## 已确认可用

| 项目 | 当前状态 |
| --- | --- |
| Git | 已安装 |
| Node.js | 已安装，当前版本 `24.x` |
| npm | 已安装 |
| Python | 已安装，当前版本 `3.13.x` |
| Docker Desktop / Compose | 已安装 |
| VS Code | 已安装 |
| CMake | 已安装 |

## 需要补齐的 Python 包

核心 MVP 依赖：

- `fastapi`
- `akshare`
- `pybind11`
- `beautifulsoup4`

可选依赖：

- `tushare`
- `scrapy`

安装命令：

```powershell
pip install -r backend/requirements.txt
```

如需扩展：

```powershell
pip install -r backend/requirements-optional.txt
```

## 版本建议

- `Node.js` 当前是 `24.x`，可以先用于前期开发，但正式前端依赖若出现兼容问题，优先回退到 `20 LTS`。
- `Python` 当前是 `3.13.x`，可以先启动脚本开发；如果后续 `pybind11`、旧轮子包或某些数据源库出现兼容问题，优先补一个 `Python 3.11` 虚拟环境。

## 配置文件命名

- 根目录 `version-description.txt` 用于保留本机环境与版本检查记录，不再占用 `.env` 名称。
- 真正的运行配置模板已经改为根目录 `.env.template`。
- 后续若接入 FastAPI、数据库和 Docker Compose，建议从 `.env.template` 复制出实际本地 `.env`。

## 验收建议

1. 先运行：

   ```powershell
   python backend/scripts/check_environment.py
   ```

2. 再分别完成：
   - Olist 数据集校验
   - 电商模拟数据生成
   - A 股日线抓取
   - 演示爬虫导出
