# Python Environment

## Recommended baseline

- Python `3.13`
- `uv` for dependency and virtual-environment management

## Initialization

```powershell
uv venv .venv --python 3.13
uv sync
```

## Compatibility requirements

The project keeps:

- `backend/requirements.txt`
- `backend/requirements-optional.txt`

Regenerate them from `pyproject.toml` with:

```powershell
.\.venv\Scripts\python.exe backend/scripts/export_requirements.py
```

## Key dependencies

- FastAPI
- SQLAlchemy
- Alembic
- Pandas
- openpyxl
- python-multipart
- pybind11

The project no longer depends on legacy crawler or e-commerce dataset packages.
