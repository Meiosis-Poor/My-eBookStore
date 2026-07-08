from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def fail(message: str, status_code: int = 400, code: int = 1) -> HTTPException:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message, "data": None})


def http_exception_handler(_: Any, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and {"code", "message", "data"} <= set(exc.detail.keys()):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"code": 1, "message": str(exc.detail), "data": None})
