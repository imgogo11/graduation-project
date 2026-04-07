# 作用:
# - 这是合成电商数据模块的单元测试文件，用来验证生成出的多张表之间引用关系是否一致，
#   以及写盘后关键 CSV 和 manifest 是否成功创建。
# 关联文件:
# - 直接导入 backend/app/data_sources/ecommerce_synthetic.py 中的 generate_bundle 和 write_bundle。
# - 主要验证 backend/scripts/generate_ecommerce_synthetic.py 背后的核心业务逻辑是否正常。
#
from __future__ import annotations

from pathlib import Path
import sys
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = BACKEND_DIR.parent / "data" / "processed" / "test_artifacts" / "synthetic"
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.data_sources.ecommerce_synthetic import generate_bundle, write_bundle


class SyntheticEcommerceTests(unittest.TestCase):
    def test_generate_bundle_keeps_references_consistent(self) -> None:
        frames = generate_bundle(
            order_count=50,
            user_count=20,
            product_count=12,
            start_date="2024-01-01",
            end_date="2024-06-01",
            seed=7,
        )

        order_ids = set(frames["orders"]["order_id"])
        customer_ids = set(frames["customers"]["customer_id"])
        product_ids = set(frames["products"]["product_id"])

        self.assertTrue(order_ids)
        self.assertTrue(customer_ids)
        self.assertTrue(product_ids)
        self.assertTrue(set(frames["order_items"]["order_id"]).issubset(order_ids))
        self.assertTrue(set(frames["orders"]["customer_id"]).issubset(customer_ids))
        self.assertTrue(set(frames["order_items"]["product_id"]).issubset(product_ids))
        self.assertTrue((frames["orders"]["source_type"] == "synthetic").all())

    def test_write_bundle_creates_manifest(self) -> None:
        frames = generate_bundle(
            order_count=10,
            user_count=5,
            product_count=5,
            start_date="2024-01-01",
            end_date="2024-03-01",
            seed=11,
        )

        manifest_path = write_bundle(
            frames=frames,
            output_dir=OUTPUT_ROOT,
            seed=11,
            start_date="2024-01-01",
            end_date="2024-03-01",
        )
        self.assertTrue(manifest_path.exists())
        self.assertTrue((OUTPUT_ROOT / "orders.csv").exists())
        self.assertTrue((OUTPUT_ROOT / "product_price_history.csv").exists())


if __name__ == "__main__":
    unittest.main()
