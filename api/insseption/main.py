from __future__ import annotations

import csv
import io
import re
from contextlib import asynccontextmanager

import os
from pathlib import Path as FsPath

from fastapi import APIRouter, FastAPI, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .errors import ApiError, api_error_handler
from .jsonutil import ApiJSONResponse
from .llm import translate_enabled, translate_texts
from .models import (
    MetaResponse,
    QueryRequest,
    TranslateRequest,
    build_upstream_query,
    dataset_to_rows,
    normalize_context_nodes,
    normalize_matrix_meta,
)
from .news import parse_news_html
from . import docs
from .upstream import (
    close_client,
    fetch_context,
    fetch_dataset,
    fetch_matrix_meta,
    fetch_news_html,
    ping_upstream,
)

CODE_RE = re.compile(config.MATRIX_CODE_RE)

EXISTING_SOLUTIONS = [
    {
        "name": "mark-veres/tempo.py",
        "url": "https://github.com/mark-veres/tempo.py",
        "note": "Thin Python client (WIP)",
    },
    {
        "name": "RProjectRomania/TEMPO",
        "url": "https://github.com/RProjectRomania/TEMPO",
        "note": "CRAN R package for bulk CSV",
    },
    {
        "name": "gov2-ro/tempo-ins-dump",
        "url": "https://github.com/gov2-ro/tempo-ins-dump",
        "note": "Full warehouse + UI at ins.gov2.ro",
    },
    {
        "name": "alecsandrei/QTempo",
        "url": "https://github.com/alecsandrei/QTempo",
        "note": "QGIS plugin",
    },
]

ENDPOINTS = [
    {"method": "GET", "path": "/api/v1/health", "description": "Liveness + upstream reachability"},
    {"method": "GET", "path": "/api/v1/meta", "description": "Service metadata"},
    {"method": "GET", "path": "/api/v1/context", "description": "Root TEMPO domains (?lang=ro|en)"},
    {"method": "GET", "path": "/api/v1/context/{code}", "description": "Child nodes"},
    {"method": "GET", "path": "/api/v1/matrices/{code}", "description": "Matrix metadata + dimensions"},
    {
        "method": "GET",
        "path": "/api/v1/matrices/{code}/query",
        "description": "Query with default selections (browser-friendly)",
    },
    {
        "method": "POST",
        "path": "/api/v1/matrices/{code}/query",
        "description": "Query with JSON body {lang, selections}",
    },
    {"method": "GET", "path": "/api/v1/news", "description": "Recent matrix updates"},
    {"method": "POST", "path": "/api/v1/translate", "description": "Translate labels via OpenRouter"},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_client()


router = APIRouter()


@router.get("/health", response_class=ApiJSONResponse)
async def health():
    upstream_ok = await ping_upstream()
    return {
        "ok": True,
        "version": config.VERSION,
        "upstream_ok": upstream_ok,
        "attribution": config.ATTRIBUTION,
    }


@router.get("/meta", response_class=ApiJSONResponse)
async def meta():
    return MetaResponse(
        version=config.VERSION,
        attribution=config.ATTRIBUTION,
        terms_url=config.TERMS_URL,
        max_cells=config.MAX_CELLS,
        translate_enabled=translate_enabled(),
        openrouter_model=config.OPENROUTER_MODEL if translate_enabled() else None,
        languages=["ro", "en", "hu"],
        existing_solutions=EXISTING_SOLUTIONS,
    )


@router.get("/context", response_class=ApiJSONResponse)
async def context_root(lang: str = Query("ro", pattern="^(ro|en)$")):
    raw = await fetch_context(None, lang=lang)
    return {
        "lang": lang,
        "nodes": normalize_context_nodes(raw, parent_code=None),
        "attribution": config.ATTRIBUTION,
    }


@router.get("/context/{code}", response_class=ApiJSONResponse)
async def context_child(code: str, lang: str = Query("ro", pattern="^(ro|en)$")):
    raw = await fetch_context(code, lang=lang)
    return {
        "lang": lang,
        "parent": code,
        "nodes": normalize_context_nodes(raw, parent_code=code),
        "attribution": config.ATTRIBUTION,
    }


@router.get("/matrices/{code}", response_class=ApiJSONResponse)
async def matrix_meta(code: str, lang: str = Query("ro", pattern="^(ro|en)$")):
    if not CODE_RE.match(code):
        raise ApiError("bad_code", "Invalid matrix code", status=422)
    raw = await fetch_matrix_meta(code, lang=lang)
    if not isinstance(raw, dict) or not raw.get("dimensionsMap"):
        raise ApiError("not_found", f"Matrix {code} not found", status=404)
    return {
        **normalize_matrix_meta(raw, code),
        "lang": lang,
        "attribution": config.ATTRIBUTION,
    }


async def _run_query(code: str, body: QueryRequest, format: str):
    if not CODE_RE.match(code):
        raise ApiError("bad_code", "Invalid matrix code", status=422)
    meta_raw = await fetch_matrix_meta(code, lang=body.lang)
    if not isinstance(meta_raw, dict):
        raise ApiError("not_found", f"Matrix {code} not found", status=404)
    upstream_body = build_upstream_query(
        meta_raw,
        {str(k): v for k, v in body.selections.items()},
        body.lang,
        code,
        config.MAX_CELLS,
    )
    raw = await fetch_dataset(code, upstream_body)
    parsed = dataset_to_rows(raw)
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        if parsed["columns"]:
            w.writerow(parsed["columns"])
        for row in parsed["rows"]:
            w.writerow(row)
        return PlainTextResponse(
            buf.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{code.upper()}.csv"',
                "X-Source": "INS TEMPO-Online",
            },
        )
    return {
        "code": code.upper(),
        "lang": body.lang,
        "columns": parsed["columns"],
        "rows": parsed["rows"],
        "row_count": len(parsed["rows"]),
        "attribution": config.ATTRIBUTION,
    }


@router.get("/matrices/{code}/query", response_class=ApiJSONResponse)
async def matrix_query_get(
    code: str,
    lang: str = Query("en", pattern="^(ro|en)$"),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """Browser-friendly GET: default selections (totals / latest year)."""
    return await _run_query(code, QueryRequest(lang=lang, selections={}), format)


@router.post("/matrices/{code}/query", response_class=ApiJSONResponse)
async def matrix_query_post(
    code: str,
    body: QueryRequest,
    format: str = Query("json", pattern="^(json|csv)$"),
):
    return await _run_query(code, body, format)


@router.get("/news", response_class=ApiJSONResponse)
async def news():
    html = await fetch_news_html()
    items = parse_news_html(html)
    return {
        "items": items[:200],
        "count": len(items),
        "attribution": config.ATTRIBUTION,
    }


@router.post("/translate", response_class=ApiJSONResponse)
async def translate(body: TranslateRequest):
    out = await translate_texts(body.texts, body.target)
    return {"target": body.target, "texts": out}


def create_app() -> FastAPI:
    app = FastAPI(
        title="insseption API",
        version=config.VERSION,
        description=(
            "JSON API tunnel for Romania INSSE TEMPO-Online. "
            "Guide with examples: `/docs`. Interactive reference: `/docs/reference`."
        ),
        lifespan=lifespan,
        default_response_class=ApiJSONResponse,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1")
    app.include_router(router, prefix="/v1")
    app.include_router(docs.router)
    docs.attach_openapi(app)

    @app.get("/", response_class=ApiJSONResponse)
    async def root():
        return {
            "name": "insseption",
            "version": config.VERSION,
            "type": "json-api",
            "content_type": "application/json",
            "base": "/api/v1",
            "docs": "/docs",
            "openapi": "/openapi.json",
            "python_client": "pip install insseption",
            "pypi": "https://pypi.org/project/insseption/",
            "endpoints": ENDPOINTS,
            "attribution": config.ATTRIBUTION,
            "terms_url": config.TERMS_URL,
        }

    @app.get("/api", response_class=ApiJSONResponse)
    @app.get("/api/v1", response_class=ApiJSONResponse)
    async def api_index():
        return {
            "base": "/api/v1",
            "endpoints": ENDPOINTS,
            "attribution": config.ATTRIBUTION,
        }

    @app.middleware("http")
    async def add_source_headers(request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Source"] = "INS TEMPO-Online"
        response.headers.setdefault("Cache-Control", "public, max-age=60")
        if "application/json" in (response.headers.get("content-type") or ""):
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response


    agent_url = os.environ.get(
        "INSSEPTION_AGENT_URL", "http://insseption-agent:8000"
    ).rstrip("/")

    @app.api_route("/agent", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    @app.api_route("/agent/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
    async def agent_proxy(request: Request, path: str = ""):
        """Reverse-proxy to the separate insseption-agent container."""
        import httpx

        target = f"{agent_url}/{path}" if path else f"{agent_url}/"
        if request.url.query:
            target = f"{target}?{request.url.query}"
        headers = {
            k: v
            for k, v in request.headers.items()
            if k.lower() not in {"host", "content-length", "transfer-encoding"}
        }
        body = await request.body()
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                upstream = await client.request(
                    request.method, target, headers=headers, content=body
                )
        except httpx.HTTPError as exc:
            return ApiJSONResponse(
                {"detail": f"agent unreachable: {exc}"}, status_code=502
            )
        excluded = {"content-encoding", "transfer-encoding", "content-length", "connection"}
        out_headers = {
            k: v for k, v in upstream.headers.items() if k.lower() not in excluded
        }
        return Response(
            content=upstream.content,
            status_code=upstream.status_code,
            headers=out_headers,
            media_type=upstream.headers.get("content-type"),
        )

    static_dir = os.environ.get("INSSEPTION_STATIC_DIR", "").strip()
    if static_dir:
        root = FsPath(static_dir)
        if root.is_dir():
            # API routes already registered; UI at /
            app.mount("/", StaticFiles(directory=str(root), html=True), name="ui")

    return app


app = create_app()
