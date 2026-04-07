# 作用:
# - 这是 backend/app 包的初始化文件，用来声明后端应用主包命名空间。
# 关联文件:
# - 由 backend/scripts 下的多个脚本通过 `from app...` 的方式间接依赖。
# - 当前主要承载 backend/app/data_sources/ 这一子包。
#
"""Backend application package."""
