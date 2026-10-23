"""
insseption agent service — TEMPO NL queries.
Public path: /agent/* (reverse-proxied by the API container).
"""

from __future__ import annotations

import os
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


class QueryResponse(BaseModel):
    answer: str = ""
    chart: Optional[dict] = None
    table: Optional[dict] = None
    plan: Optional[dict] = None
    matrix: Optional[str] = None
    columns: Optional[list] = None
    data: Optional[list] = None
    error: Optional[str] = None


@app.post("/api/query", response_model=QueryResponse)
async def query_data(request: QueryRequest):
    agent = get_agent()
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Check OPENROUTER_API_KEY.",
        )
    try:
        result = await agent.query(request.query, generate_chart=request.generate_chart)
        return QueryResponse(**result)
    except Exception as exc:
        import traceback

        print(traceback.format_exc())
        return QueryResponse(answer="", error=str(exc))


@app.get("/health")
async def health():
    agent = get_agent()
    return {
        "status": "healthy",
        "agent_initialized": agent is not None,
        "insseption_api": os.getenv("INSSEPTION_API_URL", "http://insseption:8787/api/v1"),
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
