# 作用:
# - 这是 backend/app/core 包的初始化文件，用来归档配置、数据库连接等基础设施模块。
# 关联文件:
# - 由 backend/app/main.py、backend/scripts/import_data.py 和各 API / 服务模块间接依赖。
# - 当前主要承载 config.py 和 database.py 两个基础模块。
#
"""Core backend infrastructure helpers."""
