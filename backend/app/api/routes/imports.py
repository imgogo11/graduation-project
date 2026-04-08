# 作用:
# - 这是数据导入路由模块，用来暴露股票、Olist、合成电商三条入库入口以及导入记录查询接口。
# 关联文件:
# - 被 backend/app/api/router.py 统一挂载到 `/api/imports/*`。
# - 直接依赖 backend/app/services/imports.py 负责实际导入逻辑。
# - 使用 backend/app/schemas/api.py 中的 ImportRequest 和 ImportRunRead 作为请求/响应模型。
#
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db_session
from app.repositories.imports import ImportRunRepository
from app.schemas.api import ImportRequest, ImportRunRead
from app.services.imports import ImportExecutionError, ImportService


router = APIRouter()
service = ImportService()


def _resolve_manifest(path_value: str | None, default_path: Path) -> Path:
    if path_value:
        return Path(path_value).expanduser().resolve()
    return default_path.resolve()


@router.get("/runs", response_model=list[ImportRunRead])
def list_import_runs(limit: int = 20, session: Session = Depends(get_db_session)) -> list[ImportRunRead]:
    runs = ImportRunRepository.list_runs(session, limit=limit)
    return [ImportRunRead.model_validate(item) for item in runs]


@router.post("/stocks/akshare", response_model=ImportRunRead)
def import_stock_manifest(payload: ImportRequest, session: Session = Depends(get_db_session)) -> ImportRunRead:
    settings = get_settings()
    try:
        run = service.import_stock_manifest(session, _resolve_manifest(payload.manifest_path, settings.default_stock_manifest))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"Import run {exc.run_id} failed: {exc}") from exc
    return ImportRunRead.model_validate(run)


@router.post("/ecommerce/olist", response_model=ImportRunRead)
def import_olist_manifest(payload: ImportRequest, session: Session = Depends(get_db_session)) -> ImportRunRead:
    settings = get_settings()
    try:
        run = service.import_olist_manifest(session, _resolve_manifest(payload.manifest_path, settings.default_olist_manifest))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"Import run {exc.run_id} failed: {exc}") from exc
    return ImportRunRead.model_validate(run)


@router.post("/ecommerce/synthetic", response_model=ImportRunRead)
def import_synthetic_manifest(payload: ImportRequest, session: Session = Depends(get_db_session)) -> ImportRunRead:
    settings = get_settings()
    try:
        run = service.import_synthetic_manifest(
            session,
            _resolve_manifest(payload.manifest_path, settings.default_synthetic_manifest),
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportExecutionError as exc:
        raise HTTPException(status_code=500, detail=f"Import run {exc.run_id} failed: {exc}") from exc
    return ImportRunRead.model_validate(run)
