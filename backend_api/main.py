"""Compatibility shim for uvicorn import path.

Some existing startup commands reference `backend_api.main:app`.
The real application lives in `backend_api/app/main.py`. Create a
thin re-export so both module paths work.
"""
from backend_api.app.main import app  # noqa: E402,F401

__all__ = ["app"]
