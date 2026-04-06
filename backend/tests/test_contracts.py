from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = BACKEND_DIR.parent / "data" / "processed" / "test_artifacts" / "contracts"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.data_sources.contracts import DatasetArtifact, ImportManifest, SourceType, now_utc_iso, write_manifest


class ContractTests(unittest.TestCase):
    def test_write_manifest_serializes_source_type(self) -> None:
        manifest = ImportManifest(
            dataset_name="demo",
            source_type=SourceType.CSV,
            source_name="unit-test",
            source_uri="https://example.com",
            created_at=now_utc_iso(),
            record_count=3,
            columns=["a", "b"],
            artifacts=[
                DatasetArtifact(name="demo.csv", path="demo.csv", rows=3, columns=["a", "b"])
            ],
            metadata={"source_type": SourceType.CSV.value},
        )

        path = write_manifest(manifest, OUTPUT_ROOT / "manifest.json")
        text = path.read_text(encoding="utf-8")

        self.assertIn('"source_type": "csv"', text)
        self.assertIn('"dataset_name": "demo"', text)


if __name__ == "__main__":
    unittest.main()
