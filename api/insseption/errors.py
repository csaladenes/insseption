from __future__ import annotations

from typing import Any

from fastapi import Request

from .jsonutil import ApiJSONResponse


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status: int = 400,
        upstream_status: int | None = None,
    ):
        self.code = code
        self.message = message
        self.status = status
        self.upstream_status = upstream_status
        super().__init__(message)

    def body(self) -> dict[str, Any]:
        err: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.upstream_status is not None:
            err["upstream_status"] = self.upstream_status
        return {"error": err}


async def api_error_handler(_request: Request, exc: ApiError) -> ApiJSONResponse:
    return ApiJSONResponse(status_code=exc.status, content=exc.body())
