# 作用:
# - 这是电商仓储模块，用来封装订单和商品的最小只读查询逻辑。
# 关联文件:
# - 被 backend/app/api/routes/commerce.py 直接依赖。
# - 相关 ORM 实体定义在 backend/app/models/entities.py。
#
from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import Order, Product


class CommerceRepository:
    @staticmethod
    def list_orders(
        session: Session,
        *,
        source_dataset: str | None = None,
        order_status: str | None = None,
        limit: int = 100,
    ) -> list[Order]:
        stmt = select(Order).order_by(desc(Order.order_purchase_timestamp), desc(Order.order_id)).limit(limit)
        if source_dataset:
            stmt = stmt.where(Order.source_dataset == source_dataset)
        if order_status:
            stmt = stmt.where(Order.order_status == order_status)
        return list(session.scalars(stmt))

    @staticmethod
    def list_products(
        session: Session,
        *,
        source_dataset: str | None = None,
        category: str | None = None,
        limit: int = 100,
    ) -> list[Product]:
        stmt = select(Product).order_by(Product.product_id).limit(limit)
        if source_dataset:
            stmt = stmt.where(Product.source_dataset == source_dataset)
        if category:
            stmt = stmt.where(Product.product_category_name == category)
        return list(session.scalars(stmt))
