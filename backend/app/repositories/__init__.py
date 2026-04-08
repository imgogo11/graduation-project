# 作用:
# - 这是仓储层包初始化文件，用来归档数据库访问相关模块。
# 关联文件:
# - 被 backend/app/services/imports.py 和 backend/app/api/routes/*.py 间接依赖。
# - 当前主要承载 imports.py、stocks.py、commerce.py。
#
"""Repository helpers for database access."""
