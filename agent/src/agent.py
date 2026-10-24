"""
Natural-language → TEMPO DB query → clean/analyze → table/chart.
Skill: insseption-agents
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import httpx

try:
    from charts import (
        apply_year_range_selections,
        build_chart,
        expand_county_selections,
        looks_like_county_query,
        mentioned_years,
        parse_year_range,
        prefer_matrix_for_years,
        relative_year_range,
        apply_single_year,
        select_named_counties,
    )
    from models_tier import MODEL_EXECUTE, MODEL_PREFLIGHT
    from session import history_text, load_session, save_turn
except ImportError:
    from src.charts import (
        apply_year_range_selections,
        build_chart,
        expand_county_selections,
        looks_like_county_query,
        mentioned_years,
        parse_year_range,
        prefer_matrix_for_years,
        relative_year_range,
        apply_single_year,
        select_named_counties,
    )
    from src.models_tier import MODEL_EXECUTE, MODEL_PREFLIGHT
    from src.session import history_text, load_session, save_turn

CODE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{2,19}$")
SYNONYMS: dict[str, tuple[str, ...]] = {
    "șomaj": ("unemploy",), "somaj": ("unemploy",), "munkanélk": ("unemploy",),
    "rata": ("rate",), "ráta": ("rate",), "arány": ("rate",),
    "județ": ("counties",), "judet": ("counties",), "megy": ("counties",),
    "popula": ("population",), "népess": ("population",), "locuitor": ("population",),
    "salari": ("earnings", "employees"), "câștig": ("earnings",), "castig": ("earnings",),
    "fizet": ("earnings",), "bér": ("earnings",), "angajaț": ("employees",),
    "turist": ("tourist", "arrivals"), "turism": ("tourist",), "cazar": ("accommodation",),
    "inflați": ("consumer price",), "inflati": ("consumer price",), "infláci": ("consumer price",),
    "prețur": ("price",), "preturi": ("price",), "ár": ("price",),
    "nașter": ("live-born", "live-birth"), "naster": ("live-born", "live-birth"),
    "născu": ("live-born",), "születés": ("live-born", "live-birth"),
    "átlagbér": ("average", "earnings"), "salariul": ("average", "earnings"), "decese": ("deaths",), "deces": ("deaths",),
    "halálozás": ("deaths",), "căsător": ("marriages",), "casator": ("marriages",),
    "divorț": ("divorces",), "emigr": ("emigrants",), "imigr": ("immigrants",),
    "locuin": ("dwellings",), "lakás": ("dwellings", "finished dwellings"),
    "építés": ("construction", "dwellings"), "épület": ("building", "dwellings"),
    "lakóépület": ("residential", "dwellings"), "építkezés": ("construction", "dwellings"),
    "construcț": ("construction", "dwellings"), "construc": ("construction", "dwellings"),
    "clădir": ("building", "dwellings"), "edifici": ("building", "dwellings"),
    "elev": ("pupils",),
    "student": ("students",), "școl": ("school",), "spital": ("hospital",),
    "medic": ("physicians",), "export": ("exports",), "import": ("imports",),
    "pib": ("gross domestic product",), "gdp": ("gross domestic product",),
    "agricult": ("agricultural",), "recolt": ("production",), "energie": ("energy",),
    "pensi": ("pension",), "nyugdíj": ("pension",), "infracți": ("crime",),
    "vârst": ("age",), "korcsop": ("age",),
}
LLM_TIMEOUT_S = float(os.getenv("AGENT_LLM_TIMEOUT_S", "35"))
log = logging.getLogger("insseption.agent")

MASTER_PIPELINE = """
You are the insseption TEMPO agent for Romania INSSE statistics.
Internal pipeline (never describe these steps to the end user):

Step 0 — PREFLIGHT: Start from a default plan, then revise it if needed
  using conversation history (follow-ups like "1990-2000" mean continue the
  prior topic — e.g. chart population over that period). Prefer catalogue codes.

Step 1 — TRANSLATE: Turn the (possibly resolved) question into a TEMPO database query
  {matrix, lang, selections, note}.

Step 2 — RETURN QUERY: Keep the structured DB query for the runtime.

Step 3 — ANALYZE: After real data returns, clean/reformat, then interpret
  only those values. Never invent numbers.

Step 4 — PRESENT: Table + chart via predefined skills. Skip charts for a single number.
  User-facing HTML: concise answer only — no step lists, no "preflight" talk.
""".strip()


def _user_turns(hist: str) -> str:
    """History lines the user wrote; assistant answers quote other years (e.g. the latest)."""
    return "\n".join(line for line in (hist or "").splitlines() if line.startswith("user:"))


def _kw_hit(keyword: str, text: str) -> bool:
    """Keyword match anchored at a word start; suffixes allowed for inflected forms."""
    return re.search(r"(?<!\w)" + re.escape(keyword.lower()), text) is not None


class TempoAgent:
    def __init__(self) -> None:
        key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self.api_key = key
        self.base_url = os.getenv(
            "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
        ).rstrip("/")
        self.model_preflight = os.getenv("LLM_MODEL_PREFLIGHT", MODEL_PREFLIGHT)
        self.model_execute = os.getenv("LLM_MODEL_EXECUTE", MODEL_EXECUTE)
        # legacy single override applies to execute tier
        if os.getenv("LLM_MODEL"):
            self.model_execute = os.getenv("LLM_MODEL", self.model_execute)
        self.insse = os.getenv(
            "INSSEPTION_API_URL", "http://insseption:8787/api/v1"
        ).rstrip("/")
        self.referrer = os.getenv("OPENROUTER_REFERRER", "https://insse.csaladen.es")
        self.title = os.getenv("OPENROUTER_TITLE", "insseption agent")
        self.catalog = self._load_catalog(
            os.getenv("CATALOG_PATH", "/app/config/catalog.json")
        )
        self.knowledge = self._load_knowledge(
            os.getenv("KNOWLEDGE_PATH", "/app/config/knowledge.json")
        )

    @staticmethod
    def _load_knowledge(path: str) -> dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

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

    async def query(
        self,
        user_query: str,
        generate_chart: bool = True,
        lang: str | None = None,
        session_id: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        sid, stored, expired = load_session(session_id)
        # Prefer server session; fall back to client-provided history for first hop
        messages = stored or list(history or [])
        hist = history_text(messages)

        ui_lang = (lang or "").strip().lower()
        if ui_lang not in ("ro", "en", "hu"):
            ui_lang = None

        context_notice = None
        if expired:
            context_notice = self._context_notice(ui_lang)

        # Resolve follow-ups with mid-tier preflight model first when history exists
        effective_query = user_query
        if hist and not expired:
            effective_query = await self._resolve_followup(
                user_query, hist, ui_lang=ui_lang
            )

        plan = await self._plan(effective_query, ui_lang=ui_lang, history=hist)
        plan = await self._preflight(
            effective_query, plan, ui_lang=ui_lang, history=hist
        )
        matrix = (plan.get("matrix") or "").strip().upper()
        asked_years = mentioned_years(effective_query)
        # Knowledge bank: topic→matrix override, only when the matrix covers the asked years
        kb_topics = (self.knowledge or {}).get("topic_hints") or {}
        kb_matrices = (self.knowledge or {}).get("matrices") or {}
        ql_lower = effective_query.lower()
        kb_hits = sorted(
            (
                (max(len(k) for k in hit_kws), topic, hint)
                for topic, hint in kb_topics.items()
                if hint.get("matrix")
                and (hit_kws := [k for k in hint.get("keywords") or [] if _kw_hit(k, ql_lower)])
            ),
            key=lambda x: -x[0],
        )
        for _, topic, hint in kb_hits:
            kb_code = hint["matrix"]
            span = (kb_matrices.get(kb_code) or {}).get("year_range")
            if asked_years and span and (asked_years[0] < span[0] or asked_years[1] > span[1]):
                continue
            if kb_code != matrix:
                matrix = kb_code
                plan["matrix"] = matrix
                plan["note"] = f"kb:{topic}"
            break
        # Older population windows need a matrix that actually covers those years
        alt = prefer_matrix_for_years(
            "\n".join([_user_turns(hist), user_query, effective_query]), matrix, years=asked_years
        )
        if alt and alt != matrix:
            matrix = alt
            plan["matrix"] = matrix
            plan["chart_hint"] = plan.get("chart_hint") or "line"
            plan.setdefault("preflight", {})
            if isinstance(plan["preflight"], dict):
                plan["preflight"] = {
                    **plan["preflight"],
                    "revised": True,
                    "reason": (plan["preflight"].get("reason") or "")
                    + f" Switched to {matrix} to cover the requested years.",
                }
        data_lang = plan.get("lang") if plan.get("lang") in ("ro", "en") else "en"
        selections = (
            plan.get("selections") if isinstance(plan.get("selections"), dict) else {}
        )
        db_query = {
            "matrix": matrix or None,
            "lang": data_lang,
            "selections": selections,
            "note": plan.get("note"),
            "endpoint": f"POST /api/v1/matrices/{matrix}/query" if matrix else None,
            "preflight": plan.get("preflight"),
            "ui_lang": ui_lang,
            "resolved_query": effective_query if effective_query != user_query else None,
            "models": {
                "preflight": self.model_preflight,
                "execute": self.model_execute,
            },
        }

        data: dict[str, Any] | None = None
        meta: dict[str, Any] | None = None
        api_error: str | None = None
        chart = None
        table = None
        cleaned: dict[str, Any] | None = None

        combined_text = f"{_user_turns(hist)}\n{user_query}\n{effective_query}"

        if matrix and CODE_RE.match(matrix):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    meta_resp = await client.get(
                        f"{self.insse}/matrices/{matrix}", params={"lang": data_lang}
                    )
                    if meta_resp.status_code < 400:
                        meta = meta_resp.json()

                    want_county = looks_like_county_query(effective_query, []) or (
                        looks_like_county_query(user_query, []) and not parse_year_range(user_query)
                    )
                    current_text = f"{user_query}\n{effective_query}"
                    year_range = parse_year_range(current_text)
                    if not year_range and not mentioned_years(current_text):
                        year_range = parse_year_range(combined_text)
                    named = None

                    if meta:
                        if not year_range:
                            year_range = relative_year_range(current_text, meta)
                        # Year spans from follow-ups like "1990-2000"
                        if year_range:
                            selections = apply_year_range_selections(
                                meta, selections, combined_text, yr=year_range
                            )
                            plan["selections"] = selections
                            db_query["selections"] = selections
                            # Prefer line charts for evolution
                            plan["chart_hint"] = "line"
                        else:
                            one = mentioned_years(current_text)
                            if one and one[0] == one[1]:
                                selections = apply_single_year(meta, selections, one[0])
                                plan["selections"] = selections
                                db_query["selections"] = selections

                        named = select_named_counties(meta, selections, effective_query)
                        if named:
                            selections = named
                            plan["selections"] = selections
                            db_query["selections"] = selections
                        elif want_county:
                            selections = expand_county_selections(meta, selections)
                            plan["selections"] = selections
                            db_query["selections"] = selections
                            ql = effective_query.lower()
                            if "employee" in ql or "salariat" in ql:
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
                                                params={"lang": data_lang},
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
                        client, matrix, data_lang, selections
                    )

                    if (
                        want_county
                        and not named
                        and meta
                        and data
                        and len(data.get("rows") or []) < 10
                    ):
                        selections = expand_county_selections(meta, selections)
                        plan["selections"] = selections
                        db_query["selections"] = selections
                        data2, err2 = await self._run_query(
                            client, matrix, data_lang, selections
                        )
                        if data2 and len(data2.get("rows") or []) > len(
                            data.get("rows") or []
                        ):
                            data, api_error = data2, err2
            except httpx.HTTPError as exc:
                api_error = str(exc)
        else:
            api_error = plan.get("note") or "No matrix code selected (step 1 failed)"

        if data and data.get("rows"):
            cleaned = self._clean_data(data)

        chart_hint = plan.get("chart_hint") if isinstance(plan.get("chart_hint"), str) else None
        if generate_chart and cleaned and cleaned.get("rows"):
            chart, table = build_chart(
                effective_query,
                {
                    "columns": cleaned.get("columns") or data.get("columns"),
                    "rows": cleaned.get("raw_rows") or data.get("rows"),
                    "row_count": cleaned.get("row_count"),
                },
                hint=chart_hint,
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
            effective_query,
            db_query,
            meta,
            cleaned or data,
            table,
            api_error,
            history=hist,
        )
        if context_notice:
            answer = f"<p class=\"insse-chat-meta\">{context_notice}</p>" + answer

        # Persist turn (plain text-ish for history)
        plain = re.sub(r"<[^>]+>", " ", answer)
        plain = re.sub(r"\s+", " ", plain).strip()
        save_turn(sid, user_query, plain, matrix=matrix or None)

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
            "session_id": sid,
            "context_reset": expired,
            "context_notice": context_notice,
        }

    @staticmethod
    def _context_notice(ui_lang: str | None) -> str:
        if ui_lang == "ro":
            return (
                "Contextul conversației a fost resetat după mai mult de 30 de minute "
                "de inactivitate. Continuă cu o întrebare nouă, completă."
            )
        if ui_lang == "hu":
            return (
                "A beszélgetés kontextusa törlődött 30 perc inaktivitás után. "
                "Folytasd egy új, teljes kérdéssel."
            )
        return (
            "Conversation context was cleared after more than 30 minutes of inactivity. "
            "Please continue with a full new question."
        )

    @staticmethod
    def _clean_data(data: dict[str, Any]) -> dict[str, Any]:
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
            if cells and all(
                c.lower() in {str(x).lower() for x in columns} for c in cells if c
            ):
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

    async def _chat(
        self,
        system: str,
        user: str,
        *,
        model: str,
        temperature: float = 0,
    ) -> str:
        body = {
            "model": model,
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
        resp = None
        async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
            for attempt in range(2):
                try:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions", headers=headers, json=body
                    )
                except httpx.TimeoutException:
                    if attempt:
                        raise RuntimeError(f"OpenRouter timeout ({model})")
                    log.warning("openrouter timeout model=%s, retrying", model)
                    continue
                if resp.status_code in (429, 500, 502, 503, 504) and not attempt:
                    log.warning(
                        "openrouter HTTP %s model=%s, retrying", resp.status_code, model
                    )
                    await asyncio.sleep(1.5)
                    continue
                break
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
        # Catalogue names are English-only.
        for t in list(tokens):
            for stem, words in SYNONYMS.items():
                if t.startswith(stem) or (len(stem) >= 5 and stem in t):
                    tokens.extend(words)
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
        if any(k in ql for k in ("employee", "salariat", "angajat", "alkalmazott")):
            for code in ("FOM104F", "FOM104D"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        if any(k in ql for k in ("population", "populatie", "populație", "népesség", "resident")):
            for code in ("POP105A", "POP107A", "POP101A"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        if any(k in ql for k in ("dwelling", "housing", "lakás", "locuin", "construction", "épít", "construcț", "building", "épület")):
            for code in ("LOC104A", "LOC101A", "LOC101B", "LOC105A", "LOC102A", "LOC103A"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        # Explicit topic boosts for common domains
        if any(k in ql for k in ("inflation", "inflație", "infláció", "consumer price", "prețuri", "preturi", "price index")):
            for code in ("IPC101A",):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        if any(k in ql for k in ("unemployment", "șomaj", "somaj", "munkanélk", "unemployment rate")):
            for code in ("SOM103A",):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        if any(k in ql for k in ("earnings", "salarii", "câștig", "castig", "fizet", "bér", "wage", "kereset")):
            for code in ("FOM106E", "FOM106A"):
                if not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        # Knowledge bank topic hints
        kb_topics = (self.knowledge or {}).get("topic_hints") or {}
        for topic, hint in kb_topics.items():
            kws = hint.get("keywords") or []
            if any(k in ql for k in kws):
                code = hint.get("matrix")
                if code and not any(p.get("code") == code for p in picks):
                    hit = next((r for r in self.catalog if r.get("code") == code), None)
                    if hit:
                        picks.insert(0, hit)
        return "\n".join(f"{r['code']}\t{r.get('name','')}" for r in picks)

    async def _resolve_followup(
        self,
        user_query: str,
        history: str,
        *,
        ui_lang: str | None,
    ) -> str:
        """Mid-tier: turn short follow-ups into a full standalone question."""
        system = (
            f"{MASTER_PIPELINE}\n\n"
            "You resolve follow-up messages into ONE standalone statistics question.\n"
            "Use the conversation history. Examples:\n"
            '- History about current population + user \"1990-2000\" '
            "→ \"Show Romania's usually resident population from 1990 to 2000\".\n"
            "- If the new message is already complete, return it unchanged.\n"
            "Return ONLY the rewritten question text — no JSON, no quotes, no preamble."
        )
        user = json.dumps(
            {"history": history, "latest_user_message": user_query, "ui_lang": ui_lang},
            ensure_ascii=False,
        )
        try:
            resolved = await self._chat(
                system, user, model=self.model_preflight, temperature=0
            )
            resolved = resolved.strip().strip('"').strip()
            return resolved or user_query
        except Exception:
            return user_query

    async def _plan(
        self,
        user_query: str,
        ui_lang: str | None = None,
        history: str = "",
    ) -> dict[str, Any]:
        catalog = self._catalog_snippet(user_query)
        prefer = "en" if ui_lang == "en" else "ro" if ui_lang in ("ro", "hu") else None
        if prefer:
            lang_line = (
                "  lang — 'ro' or 'en' for TEMPO labels "
                f"(prefer '{prefer}' if unclear),\n"
            )
        else:
            lang_line = "  lang — 'ro' or 'en' (match the question),\n"
        system = (
            f"{MASTER_PIPELINE}\n\n"
            "You are drafting the default plan (Step 1). Preflight will revise it next.\n"
            "Translate the human question into a TEMPO DB query.\n"
            "Return ONLY a JSON object with keys:\n"
            "  matrix — TEMPO dataset code (e.g. POP105A, FOM104F) or null if unknown,\n"
            f"{lang_line}"
            "  selections — object mapping dimension id strings to arrays of nomItemId ints; "
            "use {} when defaults are fine,\n"
            "  note — one short sentence: which dataset you picked and why,\n"
            "  chart_hint — optional 'line'|'bar'|'map'|null.\n"
            "Rules:\n"
            "- Prefer catalogue codes. Never invent codes.\n"
            "- ALWAYS match the topic first (inflation, unemployment, dwellings, population, etc.) — use the topic from the question to pick the right matrix family. Use matrix_year_ranges only to choose between matrices covering the SAME topic.\n"
            "- If the question mentions specific years, pick a matrix whose year_range covers them.\n"
            "- For population over time / year ranges, prefer POP105A and chart_hint=line.\n"
            "- For average employees by county, prefer FOM104F and chart_hint=map.\n"
            "- Do not invent data values."
        )
        # Add knowledge bank context: year ranges and known dims for top candidates
        kb_mats = (self.knowledge or {}).get("matrices") or {}
        kb_info = {}
        for line in catalog.splitlines():
            code = line.split("\t")[0].strip()
            if code in kb_mats:
                kb_info[code] = {
                    "year_range": kb_mats[code].get("year_range"),
                    "name": kb_mats[code].get("name", "")[:80],
                }
        user = json.dumps(
            {
                "question": user_query,
                "history": history,
                "catalogue_candidates": catalog,
                "matrix_year_ranges": kb_info,
            },
            ensure_ascii=False,
        )
        raw = await self._chat(system, user, model=self.model_execute)
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
                "lang": prefer or "en",
                "selections": {},
                "note": f"Could not parse plan: {raw[:160]}",
            }

    async def _preflight(
        self,
        user_query: str,
        plan: dict[str, Any],
        ui_lang: str | None = None,
        history: str = "",
    ) -> dict[str, Any]:
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
                                    "id": d.get("id") or d.get("dim_code"),
                                    "name": d.get("name") or d.get("label"),
                                    "options": len(
                                        d.get("options") or d.get("items") or []
                                    ),
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
            "You are executing Step 0 — PREFLIGHT (mid-tier analysis).\n"
            "Revise the default plan using the question AND conversation history.\n"
            "Return ONLY JSON: matrix, lang, selections, note, chart_hint, "
            "preflight {revised: bool, reason}.\n"
            "Revise when follow-ups change years/geography, or the matrix family is wrong.\n"
            "For year ranges (e.g. 1990-2000) set chart_hint=line and keep population matrices.\n"
            "CRITICAL: If default_plan.matrix appears in catalogue_candidates, TRUST IT and keep it. Never reject a code just because you do not recognise it. Only change if you have a clearly better one from the catalogue. Never invent matrix codes. Keep selections {} unless you know exact nomItemIds."
        )
        user = json.dumps(
            {
                "question": user_query,
                "history": history,
                "default_plan": plan,
                "matrix_meta": meta_summary,
                "catalogue_candidates": catalog,
                "ui_lang": ui_lang,
            },
            ensure_ascii=False,
        )
        raw = await self._chat(system, user, model=self.model_preflight)
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
            "chart_hint": revised.get("chart_hint", plan.get("chart_hint")),
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
        history: str = "",
    ) -> str:
        sample_rows = (data or {}).get("rows", [])[:50] if data else []
        table_rows = (table or {}).get("rows", [])[:60] if table else []
        payload = {
            "question": user_query,
            "history": history,
            "db_query": db_query,
            "matrix_name": (meta or {}).get("name"),
            "columns": (data or {}).get("columns"),
            "row_count": (data or {}).get("row_count"),
            "sample_rows": sample_rows,
            "presentation_columns": (table or {}).get("columns"),
            "presentation_table": table_rows,
            "api_error": api_error,
            "attribution": "Sursa: INS TEMPO-Online (via insseption).",
            "ui_lang": (db_query or {}).get("ui_lang"),
        }
        system = (
            f"{MASTER_PIPELINE}\n\n"
            "Write the user-facing answer only.\n"
            "Return ONLY clean HTML fragments (p, h3, ul, li, strong, table, code).\n"
            "Rules:\n"
            "- Answer in the same language as the question "
            "(if unclear, use ui_lang: ro/en/hu).\n"
            "- Summarise cleaned numbers in plain language.\n"
            "- Prefer everyday wording; you may mention the official table code once.\n"
            "- Do not say 'matrix'. Never mention steps/preflight/pipeline.\n"
            "- NEVER say 'you would need to query', 'to find this', 'to get this data', "
            "'the dataset with code', or describe how to obtain data. "
            "Just answer directly with the numbers you have.\n"
            "- Do not invent numbers; use only sample_rows / presentation_table.\n"
            "- End with 2–4 related follow-up questions the user might ask next.\n"
            "- Put each follow-up as: "
            "<button type=\"button\" class=\"insse-chat-suggest\">…</button> "
            "inside a short list under a heading like "
            "'Ce propun' / 'You could also ask' / 'Ajánlom' (match answer language).\n"
            "- Suggestion button text must be a complete, ready-to-send question."
        )
        raw = await self._chat(
            system, json.dumps(payload, ensure_ascii=False), model=self.model_execute
        )
        if not raw.startswith("<"):
            raw = f"<p>{raw}</p>"
        return raw
