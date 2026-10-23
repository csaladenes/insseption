"""
insseption agent service — TEMPO NL queries.
Public path: /agent/* (reverse-proxied by the API container).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from agent import TempoAgent
except ImportError:
    from src.agent import TempoAgent

load_dotenv()

app = FastAPI(title="insseption agent", version="0.1.1")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent: TempoAgent | None = None


def get_agent() -> TempoAgent | None:
    global _agent
    if _agent is None:
        try:
            _agent = TempoAgent()
        except Exception as exc:
            print(f"Warning: agent init failed: {exc}")
            _agent = None
    return _agent


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=2000)
    generate_chart: bool = True
    chart_type: Optional[str] = None
    lang: Optional[str] = Field(
        default=None,
        description="UI language hint: ro|en|hu (answers follow the question; TEMPO data uses ro/en).",
    )
    session_id: Optional[str] = Field(
        default=None, description="Chat session id for follow-up context (30 min TTL)."
    )
    history: Optional[list[dict]] = Field(
        default=None, description="Optional client-side prior turns [{role, content}]."
    )


class QueryResponse(BaseModel):
    answer: str = ""
    chart: Optional[dict] = None
    table: Optional[dict] = None
    plan: Optional[dict] = None
    db_query: Optional[dict] = None
    matrix: Optional[str] = None
    columns: Optional[list] = None
    data: Optional[list] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    context_reset: bool = False
    context_notice: Optional[str] = None


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("insseption.agent")
# Cloudflare drops proxied requests at ~100s; finish before that.
DEADLINE_S = float(os.getenv("AGENT_DEADLINE_S", "85"))
TIMEOUT_MSG = {
    "ro": "Interogarea a durat prea mult. Încearcă o întrebare mai precisă (un an, o regiune).",
    "en": "The query took too long. Try a more specific question (one year, one region).",
    "hu": "A lekérdezés túl sokáig tartott. Próbálj pontosabb kérdést (egy év, egy régió).",
}


@app.post("/api/query", response_model=QueryResponse)
async def query_data(request: QueryRequest):
    agent = get_agent()
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check OPENROUTER_API_KEY.",
        )
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            agent.query(
                request.query,
                generate_chart=request.generate_chart,
                lang=request.lang,
                session_id=request.session_id,
                history=request.history,
            ),
            timeout=DEADLINE_S,
        )
        log.info(
            "query ok %.1fs lang=%s matrix=%s err=%s q=%r",
            time.monotonic() - t0,
            request.lang,
            result.get("matrix"),
            (result.get("error") or "")[:120],
            request.query[:80],
        )
        return QueryResponse(**result)
    except asyncio.TimeoutError:
        log.error(
            "query TIMEOUT %.1fs lang=%s q=%r",
            time.monotonic() - t0,
            request.lang,
            request.query[:80],
        )
        return QueryResponse(
            answer="",
            error=TIMEOUT_MSG.get(request.lang or "ro", TIMEOUT_MSG["en"]),
            session_id=request.session_id,
        )
    except Exception as exc:
        log.exception(
            "query FAILED %.1fs q=%r", time.monotonic() - t0, request.query[:80]
        )
        return QueryResponse(answer="", error=str(exc), session_id=request.session_id)


@app.get("/health")
async def health():
    agent = get_agent()
    try:
        from models_tier import MODEL_EXECUTE, MODEL_PREFLIGHT
    except ImportError:
        from src.models_tier import MODEL_EXECUTE, MODEL_PREFLIGHT

    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "insseption_api": os.getenv("INSSEPTION_API_URL", "http://insseption:8787/api/v1"),
        "models": {
            "preflight": os.getenv("LLM_MODEL_PREFLIGHT", MODEL_PREFLIGHT),
            "execute": os.getenv(
                "LLM_MODEL_EXECUTE", os.getenv("LLM_MODEL", MODEL_EXECUTE)
            ),
        },
    }


@app.get("/")
async def root():
    return {
        "service": "insseption agent",
        "version": "0.1.1",
        "endpoints": {"query": "POST /api/query", "health": "GET /health"},
        "example": {
            "query": "What is Romania's usually resident population?",
            "generate_chart": True,
        },
    }
