"""
Natural-language → insseption TEMPO API → HTML answer (+ optional Chart.js).
Mirrors the GEM portal-agent shape, but talks HTTP to the JSON tunnel
instead of SQLite.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

MODEL = "openai/gpt-4.1-nano"
CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")


class TempoAgent:
    def __init__(self) -> None:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self.api_key = key
        self.base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model = os.getenv("LLM_MODEL", MODEL)
        self.insse = os.getenv(
            "INSSEPTION_API_URL", "http://insseption:8787/api/v1"
        ).rstrip("/")
        self.referrer = os.getenv("OPENROUTER_REFERRER", "https://insse.csaladen.es")
        self.title = os.getenv("OPENROUTER_TITLE", "insseption agent")
        self.catalog = self._load_catalog(
            os.getenv("CATALOG_PATH", "/app/config/catalog.json")
        )

    @staticmethod
    def _load_catalog(path: str) -> list[dict[str, str]]:
        p = Path(path)
        if not p.is_file():
            return []
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    async def query(self, user_query: str, generate_chart: bool = True) -> dict[str, Any]:
        plan = await self._plan(user_query)
        matrix = (plan.get("matrix") or "").strip().upper()
        lang = plan.get("lang") if plan.get("lang") in ("ro", "en") else "en"
        selections = plan.get("selections") if isinstance(plan.get("selections"), dict) else {}

        data: dict[str, Any] | None = None
        meta: dict[str, Any] | None = None
        api_error: str | None = None

        if matrix and CODE_RE.match(matrix):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    meta_resp = await client.get(
                        f"{self.insse}/matrices/{matrix}", params={"lang": lang}
                    )
                    if meta_resp.status_code < 400:
                        meta = meta_resp.json()
                    q_resp = await client.post(
                        f"{self.insse}/matrices/{matrix}/query",
                        params={"lang": lang},
                        json={"lang": lang, "selections": selections or {}},
                    )
                    if q_resp.status_code >= 400:
                        api_error = f"query HTTP {q_resp.status_code}: {q_resp.text[:200]}"
                    else:
                        data = q_resp.json()
            except httpx.HTTPError as exc:
                api_error = str(exc)
        else:
            api_error = plan.get("note") or "No matrix code selected"

        answer = await self._answer(user_query, plan, meta, data, api_error)
        chart = None
        if generate_chart and data and data.get("rows"):
            chart = self._chart_js(user_query, data)

        return {
            "answer": answer,
            "plan": plan,
            "matrix": matrix or None,
            "data": (data or {}).get("rows") if data else None,
            "columns": (data or {}).get("columns") if data else None,
            "chart": chart,
            "error": api_error,
        }

    async def _chat(self, system: str, user: str, temperature: float = 0) -> str:
        body = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.referrer,
            "X-Title": self.title,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions", headers=headers, json=body
            )
        if resp.status_code >= 400:
            raise RuntimeError(f"OpenRouter HTTP {resp.status_code}: {resp.text[:200]}")
        content = (
            ((resp.json().get("choices") or [{}])[0].get("message") or {}).get("content")
            or ""
        ).strip()
        return self._strip_fences(content)

    @staticmethod
    def _strip_fences(content: str) -> str:
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            for prefix in ("json", "html"):
                if content.lower().startswith(prefix):
                    content = content[len(prefix) :].lstrip()
        return content

    def _catalog_snippet(self, query: str, limit: int = 40) -> str:
        q = query.lower()
        tokens = [t for t in re.split(r"\W+", q) if len(t) >= 3]
        scored: list[tuple[int, dict[str, str]]] = []
        for row in self.catalog:
            name = (row.get("name") or "").lower()
            code = (row.get("code") or "").lower()
            score = 0
            if code and code in q:
                score += 10
            for t in tokens:
                if t in name or t in code:
                    score += 1
            if score:
                scored.append((score, row))
        scored.sort(key=lambda x: (-x[0], x[1].get("code") or ""))
        picks = [r for _, r in scored[:limit]]
        if not picks:
            picks = self.catalog[:25]
        return "\n".join(f"{r['code']}\t{r.get('name','')}" for r in picks)

    async def _plan(self, user_query: str) -> dict[str, Any]:
        catalog = self._catalog_snippet(user_query)
        system = (
            "You plan read-only queries against the Romania INSSE TEMPO API via insseption. "
            "Return ONLY a JSON object with keys: "
            "matrix (TEMPO code like POP105A or null), "
            "lang ('ro' or 'en'), "
            "selections (object mapping dimension id strings to arrays of nomItemId ints; "
            "use {} for defaults = totals / latest year), "
            "note (short rationale). "
            "Prefer well-known codes from the catalogue. Never invent codes."
        )
        user = f"Question: {user_query}\n\nCatalogue candidates:\n{catalog}"
        raw = await self._chat(system, user)
        try:
            if not raw.startswith("{"):
                start, end = raw.find("{"), raw.rfind("}")
                if start >= 0 and end > start:
                    raw = raw[start : end + 1]
            plan = json.loads(raw)
            if not isinstance(plan, dict):
                raise ValueError("not an object")
            return plan
        except Exception:
            return {
                "matrix": None,
                "lang": "en",
                "selections": {},
                "note": f"Could not parse plan: {raw[:160]}",
            }

    async def _answer(
        self,
        user_query: str,
        plan: dict[str, Any],
        meta: dict[str, Any] | None,
        data: dict[str, Any] | None,
        api_error: str | None,
    ) -> str:
        sample_rows = (data or {}).get("rows", [])[:30] if data else []
        columns = (data or {}).get("columns") if data else None
        payload = {
            "question": user_query,
            "plan": plan,
            "matrix_name": (meta or {}).get("name"),
            "columns": columns,
            "row_count": (data or {}).get("row_count"),
            "sample_rows": sample_rows,
            "api_error": api_error,
            "attribution": "Sursa: INS TEMPO-Online (via insseption).",
        }
        system = (
            "You are the insseption assistant for Romania INSSE TEMPO statistics. "
            "Answer in the same language as the question. "
            "Return ONLY clean HTML fragments (p, h3, ul, li, strong, table, code) — "
            "no html/body/script tags. "
            "If data is present, summarise it and cite the matrix code. "
            "If empty or errored, say so and suggest a matrix code to try. "
            "Do not invent numbers."
        )
        raw = await self._chat(system, json.dumps(payload, ensure_ascii=False))
        if not raw.startswith("<"):
            raw = f"<p>{raw}</p>"
        return raw

    @staticmethod
    def _chart_js(query: str, data: dict[str, Any]) -> dict[str, Any] | None:
        columns = data.get("columns") or []
        rows = data.get("rows") or []
        if len(columns) < 2 or not rows:
            return None
        # pick last numeric-ish column as values, first as labels
        label_i = 0
        value_i = len(columns) - 1
        labels: list[str] = []
        values: list[float] = []
        for row in rows[:40]:
            if not isinstance(row, (list, tuple)) or len(row) <= value_i:
                continue
            label = re.sub(r"<[^>]+>", "", str(row[label_i])).strip()
            # Skip TEMPO header / unit rows echoed as data
            if not label or label.lower() in {c.lower() for c in columns}:
                continue
            if label.lower().startswith(("mu:", "um:", "year ", "anul ")):
                continue
            raw = re.sub(r"<[^>]+>", "", str(row[value_i]))
            raw = re.sub(r"[^\d.\-]", "", raw.replace(",", ""))
            try:
                val = float(raw)
            except (TypeError, ValueError):
                continue
            # Years masquerading as values (e.g. 2026) — keep only if no larger series
            values.append(val)
            labels.append(label[:48])
        if not values:
            return None
        # Drop year-like points when a real magnitude exists alongside them
        if any(v >= 10_000 for v in values):
            kept = [(l, v) for l, v in zip(labels, values) if v < 1900 or v > 2100]
            if kept:
                labels, values = [k[0] for k in kept], [k[1] for k in kept]
        chart_type = "bar" if len(values) <= 6 else "line"
        return {
            "type": "chartjs",
            "config": {
                "type": chart_type,
                "data": {
                    "labels": labels,
                    "datasets": [
                        {
                            "label": columns[value_i] if value_i < len(columns) else "value",
                            "data": values,
                            "borderColor": "#0b3d91",
                            "backgroundColor": "rgba(11,61,145,0.35)",
                            "tension": 0.25,
                        }
                    ],
                },
                "options": {
                    "responsive": True,
                    "plugins": {
                        "title": {"display": True, "text": query[:80]},
                        "legend": {"display": False},
                    },
                },
            },
        }
