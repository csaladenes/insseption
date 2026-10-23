"""
Natural-language → TEMPO DB query → clean/analyze → table/chart.
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

# Master contract for every LLM call in this agent.
MASTER_PIPELINE = """
You are the insseption TEMPO agent for Romania INSSE statistics.
Internal pipeline (never describe these steps to the end user):

Step 0 — PREFLIGHT: Start from a default plan, then revise it if needed
  (wrong matrix family, user-named code ignored, county map needs different
  dataset/selections, lang mismatch). Prefer catalogue codes; never invent codes.

Step 1 — TRANSLATE: Turn the human question into a TEMPO database query
  {matrix, lang, selections, note}.

Step 2 — RETURN QUERY: Keep the structured DB query for the runtime
  (do not narrate step numbers or "pipeline" in user-facing HTML).

Step 3 — ANALYZE: After real data returns, clean/reformat, then interpret
  only those values. Never invent numbers.

Step 4 — PRESENT: Table + chart via predefined skills (bar / line / county map).
  User-facing HTML: concise answer only — no step lists, no "preflight" talk.
""".strip()


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
        # Default plan draft, then Step 0 PREFLIGHT revise if needed
        plan = await self._plan(user_query)
        plan = await self._preflight(user_query, plan)
        matrix = (plan.get("matrix") or "").strip().upper()
        lang = plan.get("lang") if plan.get("lang") in ("ro", "en") else "en"
        selections = (
            plan.get("selections") if isinstance(plan.get("selections"), dict) else {}
        )
        db_query = {
            "matrix": matrix or None,
            "lang": lang,
            "selections": selections,
            "note": plan.get("note"),
            "endpoint": f"POST /api/v1/matrices/{matrix}/query" if matrix else None,
            "preflight": plan.get("preflight"),
        }

        data: dict[str, Any] | None = None
        meta: dict[str, Any] | None = None
        api_error: str | None = None
        chart = None
        table = None
        cleaned: dict[str, Any] | None = None

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
                        db_query["selections"] = selections
                        if "employee" in user_query.lower() or "salariat" in user_query.lower():
                            if not matrix.startswith("FOM104"):
                                for cand in ("FOM104F", "FOM104D", "FOM104A"):
                                    if any(r.get("code") == cand for r in self.catalog):
                                        matrix = cand
                                        plan["matrix"] = matrix
                                        db_query["matrix"] = matrix
                                        db_query["endpoint"] = (
                                            f"POST /api/v1/matrices/{matrix}/query"
                                        )
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
                                            db_query["selections"] = selections
                                        break

                    data, api_error = await self._run_query(
                        client, matrix, lang, selections
                    )

                    if (
                        want_county
                        and meta
                        and data
                        and len(data.get("rows") or []) < 10
                    ):
                        selections = expand_county_selections(meta, {})
                        plan["selections"] = selections
                        db_query["selections"] = selections
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
            api_error = plan.get("note") or "No matrix code selected (step 1 failed)"

        # Step 3: clean / reformat before analysis
        if data and data.get("rows"):
            cleaned = self._clean_data(data)

        # Step 4: presentation skill (table + chart)
        if generate_chart and cleaned and cleaned.get("rows"):
            chart, table = build_chart(
                user_query,
                {
                    "columns": cleaned.get("columns") or data.get("columns"),
                    "rows": cleaned.get("raw_rows") or data.get("rows"),
                    "row_count": cleaned.get("row_count"),
                },
            )
            if table is None and cleaned.get("table_rows"):
                table = {
                    "columns": cleaned.get("table_columns") or ["label", "value"],
                    "rows": cleaned["table_rows"],
                }
        elif cleaned and cleaned.get("table_rows"):
            table = {
                "columns": cleaned.get("table_columns") or ["label", "value"],
                "rows": cleaned["table_rows"],
            }

        answer = await self._answer(
            user_query, db_query, meta, cleaned or data, table, api_error
        )

        return {
            "answer": answer,
            "plan": plan,
            "db_query": db_query,
            "matrix": matrix or None,
            "data": (data or {}).get("rows") if data else None,
            "columns": (data or {}).get("columns") if data else None,
            "chart": chart,
            "table": table,
            "error": api_error,
        }

    @staticmethod
    def _clean_data(data: dict[str, Any]) -> dict[str, Any]:
        """Step 3 helper: normalize labels/numbers; drop empty/header junk."""
        try:
            from charts import extract_series
        except ImportError:
            from src.charts import extract_series

        labels, values, table_rows = extract_series(data)
        columns = data.get("columns") or []
        raw_rows = data.get("rows") or []
        clean_rows: list[list[Any]] = []
        for row in raw_rows:
            if not isinstance(row, (list, tuple)):
                continue
            cells = [re.sub(r"<[^>]+>", "", str(c)).strip() for c in row]
            if not any(cells):
                continue
            # drop pure header echoes
            if cells and all(c.lower() in {str(x).lower() for x in columns} for c in cells if c):
                continue
            clean_rows.append(cells)
        return {
            "columns": columns,
            "rows": clean_rows,
            "raw_rows": raw_rows,
            "row_count": len(clean_rows),
            "labels": labels,
            "values": values,
            "table_columns": ["label", "value"],
            "table_rows": table_rows,
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
        ql = query.lower()
        if any(k in ql for k in ("county", "counties", "jude", "employee", "salariat")):
            for code in ("FOM104F", "FOM104D"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        return "\n".join(f"{r['code']}\t{r.get('name','')}" for r in picks)

    async def _plan(self, user_query: str) -> dict[str, Any]:
        """Step 1: default TEMPO DB query plan (before preflight revise)."""
        catalog = self._catalog_snippet(user_query)
        system = (
            f"{MASTER_PIPELINE}\n\n"
            "You are drafting the default plan (Step 1). Preflight will revise it next.\n"
            "Translate the human question into a TEMPO DB query.\n"
            "Return ONLY a JSON object with keys:\n"
            "  matrix — TEMPO dataset code (e.g. POP105A, FOM104F) or null if unknown,\n"
            "  lang — 'ro' or 'en' (match the question),\n"
            "  selections — object mapping dimension id strings to arrays of nomItemId ints; "
            "use {} when defaults are fine (server expands county maps),\n"
            "  note — one short sentence: which dataset you picked and why.\n"
            "Rules:\n"
            "- Prefer well-known codes from the catalogue. Never invent codes.\n"
            "- If the user already names a code (e.g. POP105A), use it.\n"
            "- For average employees / salariați by county / județ / map, prefer FOM104F.\n"
            "- Do not fetch or invent data values here — only return the query."
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

    async def _preflight(self, user_query: str, plan: dict[str, Any]) -> dict[str, Any]:
        """Step 0: revise the default plan when the first pick looks wrong."""
        catalog = self._catalog_snippet(user_query, limit=30)
        matrix = (plan.get("matrix") or "").strip().upper()
        lang = plan.get("lang") if plan.get("lang") in ("ro", "en") else "en"
        meta_summary: dict[str, Any] | None = None
        if matrix and CODE_RE.match(matrix):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(
                        f"{self.insse}/matrices/{matrix}", params={"lang": lang}
                    )
                    if resp.status_code < 400:
                        meta = resp.json()
                        dims = []
                        for d in (meta.get("dimensions") or [])[:12]:
                            if not isinstance(d, dict):
                                continue
                            dims.append(
                                {
                                    "id": d.get("id") or d.get("dimensionId"),
                                    "name": d.get("name") or d.get("label"),
                                    "options": len(d.get("options") or d.get("items") or []),
                                }
                            )
                        meta_summary = {
                            "code": matrix,
                            "name": meta.get("name"),
                            "dimensions": dims,
                        }
            except httpx.HTTPError:
                meta_summary = {"code": matrix, "error": "meta fetch failed"}

        system = (
            f"{MASTER_PIPELINE}\n\n"
            "You are executing Step 0 — PREFLIGHT only.\n"
            "You receive a default plan. Revise it if necessary; otherwise keep it.\n"
            "Return ONLY JSON with keys:\n"
            "  matrix, lang, selections, note,\n"
            "  preflight — object {revised: bool, reason: short string}.\n"
            "Revise when:\n"
            "- User named a different matrix code than the default.\n"
            "- Question is county/județ/map but matrix is not county-capable "
            "(prefer FOM104F for average employees by county).\n"
            "- Matrix is null/unknown but catalogue has a clear better match.\n"
            "- Language should follow the question.\n"
            "Never invent matrix codes. Keep selections as {} unless you know "
            "exact nomItemId ints from context. Do not mention steps to users."
        )
        user = json.dumps(
            {
                "question": user_query,
                "default_plan": plan,
                "matrix_meta": meta_summary,
                "catalogue_candidates": catalog,
            },
            ensure_ascii=False,
        )
        raw = await self._chat(system, user)
        try:
            if not raw.startswith("{"):
                start, end = raw.find("{"), raw.rfind("}")
                if start >= 0 and end > start:
                    raw = raw[start : end + 1]
            revised = json.loads(raw)
            if not isinstance(revised, dict):
                raise ValueError("not an object")
        except Exception:
            out = dict(plan)
            out["preflight"] = {
                "revised": False,
                "reason": f"preflight parse failed; keeping default ({raw[:120]})",
            }
            return out

        out = {
            "matrix": revised.get("matrix", plan.get("matrix")),
            "lang": revised.get("lang", plan.get("lang")),
            "selections": revised.get("selections", plan.get("selections")) or {},
            "note": revised.get("note", plan.get("note")),
            "preflight": revised.get("preflight")
            if isinstance(revised.get("preflight"), dict)
            else {
                "revised": (revised.get("matrix") or "") != (plan.get("matrix") or ""),
                "reason": "preflight completed",
            },
        }
        if out["lang"] not in ("ro", "en"):
            out["lang"] = lang
        if not isinstance(out["selections"], dict):
            out["selections"] = {}
        return out

    async def _answer(
        self,
        user_query: str,
        db_query: dict[str, Any],
        meta: dict[str, Any] | None,
        data: dict[str, Any] | None,
        table: dict[str, Any] | None,
        api_error: str | None,
    ) -> str:
        """Steps 3–4 narrative: analyze cleaned data; presentation skill owns chart/table."""
        sample_rows = (data or {}).get("rows", [])[:30] if data else []
        table_rows = (table or {}).get("rows", [])[:40] if table else []
        payload = {
            "question": user_query,
            "db_query": db_query,
            "matrix_name": (meta or {}).get("name"),
            "columns": (data or {}).get("columns"),
            "row_count": (data or {}).get("row_count"),
            "sample_rows": sample_rows,
            "presentation_table": table_rows,
            "api_error": api_error,
            "attribution": "Sursa: INS TEMPO-Online (via insseption).",
        }
        system = (
            f"{MASTER_PIPELINE}\n\n"
            "Write the user-facing answer only (after analyze/present).\n"
            "Charts/tables are built by the presentation skill — do not explain the pipeline.\n"
            "Return ONLY clean HTML fragments (p, h3, ul, li, strong, table, code) — "
            "no html/body/script tags.\n"
            "Rules:\n"
            "- Answer in the same language as the question.\n"
            "- Summarise the cleaned numbers in plain language (population, jobs, counties…).\n"
            "- Prefer everyday wording over jargon. You may mention the official table "
            "code once in parentheses if useful, but do not say 'matrix'.\n"
            "- If errored/empty: say so and suggest what to ask next — do not invent values.\n"
            "- Never mention steps, preflight, pipeline, or internal planning.\n"
            "- Do not invent numbers; use only sample_rows / presentation_table."
        )
        raw = await self._chat(system, json.dumps(payload, ensure_ascii=False))
        if not raw.startswith("<"):
            raw = f"<p>{raw}</p>"
        return raw
