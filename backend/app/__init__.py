# 作用:
# - 这是 backend/app 包的初始化文件，用来声明后端应用主包命名空间。
# - 当前除了保留数据源子包，还承载 FastAPI 路由、数据库基础设施、模型、仓储和服务层。
# 关联文件:
# - 由 backend/scripts 下的多个脚本通过 `from app...` 的方式间接依赖。
# - 由 backend/app/main.py 作为后端应用主入口依赖。
# - 由 backend/app/core/、backend/app/api/、backend/app/models/、backend/app/services/ 等子包共同组成。
#
"""Backend application package."""
