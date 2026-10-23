from __future__ import annotations

import json
from typing import Any

from fastapi.responses import JSONResponse
from starlette.requests import Request


class ApiJSONResponse(JSONResponse):
    """Browser-friendly JSON: indented, UTF-8, explicit content-type."""

    media_type = "application/json; charset=utf-8"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ).encode("utf-8")


def wants_pretty(request: Request) -> bool:
    q = request.query_params.get("pretty")
    if q is not None:
        return q.lower() not in ("0", "false", "no")
    accept = request.headers.get("accept", "")
    return "text/html" in accept
