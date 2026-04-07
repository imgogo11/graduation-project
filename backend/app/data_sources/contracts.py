# 作用:
# - 这是数据源层的公共契约模块，统一定义来源类型、数据产物描述、
#   manifest 结构以及 manifest 写盘函数。
# 关联文件:
# - 被 backend/app/data_sources/olist.py、stock.py、ecommerce_synthetic.py、
#   demo_crawler.py 共同依赖。
# - 被 backend/app/data_sources/__init__.py 重新导出。
# - 被 backend/tests/test_contracts.py 直接导入并测试。
#
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
import json
from pathlib import Path
from typing import Any


class SourceType(StrEnum):
    CSV = "csv"
    API = "api"
    SYNTHETIC = "synthetic"
    CRAWL = "crawl"


@dataclass(slots=True)
class DatasetArtifact:
    name: str
    path: str
    rows: int
    columns: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "path": self.path,
            "rows": self.rows,
            "columns": self.columns,
        }


@dataclass(slots=True)
class ImportManifest:
    dataset_name: str
    source_type: SourceType
    source_name: str
    source_uri: str | None
    created_at: str
    record_count: int
    columns: list[str]
    artifacts: list[DatasetArtifact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "source_uri": self.source_uri,
            "created_at": self.created_at,
            "record_count": self.record_count,
            "columns": self.columns,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "metadata": self.metadata,
        }


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_manifest(manifest: ImportManifest, path: Path) -> Path:
    ensure_directory(path.parent)
    path.write_text(
        json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path
