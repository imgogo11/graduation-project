# 作用:
# - 这是 app.data_sources 子包的初始化文件，用来统一导出数据源层通用的数据契约类型。
# 关联文件:
# - 直接从 backend/app/data_sources/contracts.py 重新导出 DatasetArtifact、
#   ImportManifest、SourceType 和 write_manifest。
# - 供其他模块使用 `from app.data_sources import ...` 的包级导入方式。
#
"""Data-source utilities for the MVP ingestion flow."""

from .contracts import DatasetArtifact, ImportManifest, SourceType, write_manifest

__all__ = [
    "DatasetArtifact",
    "ImportManifest",
    "SourceType",
    "write_manifest",
]
