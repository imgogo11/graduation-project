# 作用:
# - 这是电商查询路由模块，用来暴露订单与商品的最小只读接口。
# 关联文件:
# - 被 backend/app/api/router.py 统一挂载到 `/api/commerce/orders` 和 `/api/commerce/products`。
# - 依赖 backend/app/repositories/commerce.py 执行查询。
# - 返回模型定义在 backend/app/schemas/api.py。
#
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db_session
from app.repositories.commerce import CommerceRepository
from app.schemas.api import OrderRead, ProductRead


router = APIRouter()


@router.get("/orders", response_model=list[OrderRead])
def list_orders(
    source_dataset: str | None = None,
    order_status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_db_session),
) -> list[OrderRead]:
    rows = CommerceRepository.list_orders(
        session,
        source_dataset=source_dataset,
        order_status=order_status,
        limit=limit,
    )
    return [OrderRead.model_validate(item) for item in rows]


@router.get("/products", response_model=list[ProductRead])
def list_products(
    source_dataset: str | None = None,
    category: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_db_session),
) -> list[ProductRead]:
    rows = CommerceRepository.list_products(
        session,
        source_dataset=source_dataset,
        category=category,
        limit=limit,
    )
    return [ProductRead.model_validate(item) for item in rows]
