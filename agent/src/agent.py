"""
Natural-language → insseption TEMPO API → HTML answer (+ charts / county map).
Skill: insseption-agents
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

try:
    from charts import build_chart, expand_county_selections, looks_like_county_query
except ImportError:
    from src.charts import build_chart, expand_county_selections, looks_like_county_query

MODEL = "deepseek/deepseek-v4.1-flash"
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
        chart = None
        table = None

        if matrix and CODE_RE.match(matrix):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    meta_resp = await client.get(
                        f"{self.insse}/matrices/{matrix}", params={"lang": lang}
                    )
                    if meta_resp.status_code < 400:
                        meta = meta_resp.json()

                    want_county = looks_like_county_query(user_query, [])
                    if want_county and meta:
                        selections = expand_county_selections(meta, selections)
                        plan["selections"] = selections
                        # Prefer FOM104F-family for county employment maps
                        if "employee" in user_query.lower() or "salariat" in user_query.lower():
                            if not matrix.startswith("FOM104"):
                                for cand in ("FOM104F", "FOM104D", "FOM104A"):
                                    if any(r.get("code") == cand for r in self.catalog):
                                        matrix = cand
                                        plan["matrix"] = matrix
                                        meta_resp = await client.get(
                                            f"{self.insse}/matrices/{matrix}",
                                            params={"lang": lang},
                                        )
                                        if meta_resp.status_code < 400:
                                            meta = meta_resp.json()
                                            selections = expand_county_selections(
                                                meta, {}
                                            )
                                            plan["selections"] = selections
                                        break

                    data, api_error = await self._run_query(
                        client, matrix, lang, selections
                    )

                    # Retry once with county expansion if sparse result on county ask
                    if (
                        want_county
                        and meta
                        and data
                        and len(data.get("rows") or []) < 10
                    ):
                        selections = expand_county_selections(meta, {})
                        plan["selections"] = selections
                        data2, err2 = await self._run_query(
                            client, matrix, lang, selections
                        )
                        if data2 and len(data2.get("rows") or []) > len(
                            data.get("rows") or []
                        ):
                            data, api_error = data2, err2
            except httpx.HTTPError as exc:
                api_error = str(exc)
        else:
            api_error = plan.get("note") or "No matrix code selected"

        answer = await self._answer(user_query, plan, meta, data, api_error)
        if generate_chart and data and data.get("rows"):
            chart, table = build_chart(user_query, data)

        return {
            "answer": answer,
            "plan": plan,
            "matrix": matrix or None,
            "data": (data or {}).get("rows") if data else None,
            "columns": (data or {}).get("columns") if data else None,
            "chart": chart,
            "table": table,
            "error": api_error,
        }

    async def _run_query(
        self,
        client: httpx.AsyncClient,
        matrix: str,
        lang: str,
        selections: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, str | None]:
        q_resp = await client.post(
            f"{self.insse}/matrices/{matrix}/query",
            params={"lang": lang},
            json={"lang": lang, "selections": selections or {}},
        )
        if q_resp.status_code >= 400:
            return None, f"query HTTP {q_resp.status_code}: {q_resp.text[:200]}"
        return q_resp.json(), None

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
        # Bias employment-by-county toward FOM104F
        ql = query.lower()
        if any(k in ql for k in ("county", "counties", "jude", "employee", "salariat")):
            for code in ("FOM104F", "FOM104D"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        return "\n".join(f"{r['code']}\t{r.get('name','')}" for r in picks)

    async def _plan(self, user_query: str) -> dict[str, Any]:
        catalog = self._catalog_snippet(user_query)
        system = (
            "You plan read-only queries against the Romania INSSE TEMPO API via insseption. "
            "Return ONLY a JSON object with keys: "
            "matrix (TEMPO code like POP105A or FOM104F or null), "
            "lang ('ro' or 'en'), "
            "selections (object mapping dimension id strings to arrays of nomItemId ints; "
            "use {} for defaults — the server expands county maps), "
            "note (short rationale). "
            "For average employees / salariati by county / județ / map, prefer FOM104F. "
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
