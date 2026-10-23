#!/usr/bin/env python3
"""Graded eval + stress run for the insseption agent (stdlib only).

  python scripts/eval_agent.py --base http://localhost:8000 --label baseline
  python scripts/eval_agent.py --base http://localhost:8001 --label gemini --concurrency 4
  python scripts/eval_agent.py --base https://insse.csaladen.es/agent --burst 8

Rule checks per case: no error, latency, matrix prefix, chart kind, answer
language, numeric range, refusals, forbidden strings. With OPENROUTER_API_KEY
set, an LLM judge scores faithfulness to the returned table (0-2).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "eval" / "agent_eval.json"
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "google/gemini-3.8-flash")
LATENCY_MAX_S = 85.0

LANG_MARKERS = {
    "ro": [" și ", " este ", " în ", " din ", " pentru ", " sunt ", " fost ", " anul ", " care "],
    "hu": [" és ", " az ", " egy ", " volt ", " szerint ", " évben ", " között ", " megyé"],
    "en": [" the ", " and ", " of ", " in ", " was ", " is ", " were ", " for "],
}
REFUSE_MARKERS = [
    "nu pot", "nu am", "nu ofer", "nu se găsesc", "nu dispun", "doar date", "statistic",
    "can't", "cannot", "only", "not able", "no data", "outside",
    "nem tudok", "csak", "nincs",
]


def post(base: str, payload: dict, timeout: float = 100.0) -> tuple[int, dict | None, float]:
    req = urllib.request.Request(
        base.rstrip("/") + "/api/query",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", "replace")
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, None, time.monotonic() - t0
    except Exception:
        return 0, None, time.monotonic() - t0
    dt = time.monotonic() - t0
    try:
        return status, json.loads(body), dt
    except json.JSONDecodeError:
        return status, None, dt


def plain(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html or "")).strip()


def prose_head(html: str, limit: int = 800) -> str:
    """Leading answer prose, without tables or suggestion buttons (place names skew language)."""
    html = re.sub(r"<table\b.*?</table>", " ", html or "", flags=re.S | re.I)
    return answer_body(html)[:limit]


def answer_body(html: str) -> str:
    """Answer text without follow-up suggestion buttons."""
    return plain(re.sub(r"<button\b[^>]*>.*?</button>", " ", html or "", flags=re.S | re.I))


def data_values(rows) -> list[float]:
    out: list[float] = []
    stack = list(rows or [])
    while stack:
        v = stack.pop()
        if isinstance(v, dict):
            stack.extend(v.values())
        elif isinstance(v, (list, tuple)):
            stack.extend(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            out.append(float(v))
        elif isinstance(v, str):
            try:
                out.append(float(re.sub(r"<[^>]+>|[,\s]", "", v)))
            except ValueError:
                pass
    return out


def numbers_in(text: str) -> list[float]:
    out: list[float] = []
    scale_re = r"(milioane|milion|million|millió|mii|thousand|ezer)?"
    for m in re.finditer(r"(\d{1,3}(?:[ .,\u00a0\u202f]\d{3})+|\d+(?:[.,]\d+)?)\s*" + scale_re, text, re.I):
        raw, scale = m.group(1), (m.group(2) or "").lower()
        if re.fullmatch(r"\d{1,3}(?:[ .,\u00a0\u202f]\d{3})+", raw):
            val = float(re.sub(r"[ .,\u00a0\u202f]", "", raw))
        else:
            val = float(raw.replace(",", "."))
        if scale.startswith(("milio", "millio", "millió")):
            val *= 1e6
        elif scale in ("mii", "thousand", "ezer"):
            val *= 1e3
        out.append(val)
    return out


def detect_lang(text: str) -> str | None:
    t = f" {text.lower()} "
    scores = {k: sum(t.count(m) for m in v) for k, v in LANG_MARKERS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def chart_kind(chart: dict | None) -> str:
    if not chart:
        return "none"
    return (chart.get("kind") or chart.get("type") or "chart").lower()


def judge(case: dict, question: str, resp: dict) -> dict:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        return {"score": None, "reason": "no key"}
    rows = (resp.get("data") or [])[:120]
    prompt = (
        "You grade a statistics assistant for Romania's INS TEMPO database.\n"
        f"Question: {question}\nMatrix used: {resp.get('matrix')}\n"
        f"Columns: {json.dumps(resp.get('columns'), ensure_ascii=False)}\n"
        f"Rows (first 40): {json.dumps(rows, ensure_ascii=False)[:6000]}\n"
        f"Answer: {plain(resp.get('answer', ''))[:3000]}\n\n"
        "Score 0-2. 2 = answers the question, every figure is supported by the rows, "
        "correct units and period. 1 = mostly right but vague, off-period or weak dataset choice. "
        "0 = wrong numbers, invented facts, wrong topic, or not an answer. "
        "For out-of-scope/nonsense questions, 2 = polite decline that offers what the database can do. "
        'Reply JSON only: {"score": n, "reason": "<=25 words"}'
    )
    body = json.dumps({
        "model": JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            content = json.loads(r.read())["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", content, re.S)
        return json.loads(m.group(0)) if m else {"score": None, "reason": content[:80]}
    except Exception as exc:
        return {"score": None, "reason": f"judge error {exc}"[:80]}


def run_case(base: str, case: dict, use_judge: bool) -> dict:
    sid = None
    total = 0.0
    status, resp = 0, None
    for q in case["turns"]:
        status, resp, dt = post(base, {"query": q, "lang": case["lang"], "session_id": sid})
        total += dt
        if resp:
            sid = resp.get("session_id") or sid
    last_dt = dt
    checks: dict[str, bool] = {}
    resp = resp or {}
    text = plain(resp.get("answer", ""))
    refuse = case.get("refuse", False)

    checks["http_ok"] = status == 200 and bool(resp)
    checks["answered"] = bool(text) and not (resp.get("error") and not text)
    checks["latency"] = last_dt < LATENCY_MAX_S
    matrix = (resp.get("matrix") or "").upper()
    if case.get("matrix"):
        checks["matrix"] = any(matrix.startswith(p) for p in case["matrix"])
    if refuse:
        checks["no_data_on_refusal"] = not resp.get("chart")
    kind = chart_kind(resp.get("chart"))
    want = case.get("chart", "any")
    if want == "none":
        checks["chart"] = kind == "none"
    elif want == "chart":
        checks["chart"] = kind != "none"
    elif want != "any":
        checks["chart"] = kind == want
    if text:
        lang = detect_lang(prose_head(resp.get("answer", "")))
        if lang:
            checks["lang"] = lang == case["lang"]
    if case.get("numbers"):
        lo, hi = case["numbers"]
        rows = [resp.get("data"), (resp.get("table") or {}).get("rows")]
        checks["data_numbers"] = any(lo <= n <= hi for n in data_values(rows))
        checks["numbers"] = any(lo <= n <= hi for n in numbers_in(answer_body(resp.get("answer", ""))))
    for bad in case.get("forbid", []):
        checks[f"forbid:{bad}"] = bad.lower() not in text.lower()

    j = judge(case, case["turns"][-1], resp) if use_judge and checks["http_ok"] else {"score": None}
    passed = all(checks.values()) and (j.get("score") is None or j["score"] >= 1)
    return {
        "id": case["id"], "lang": case["lang"], "passed": passed,
        "latency_s": round(last_dt, 1), "total_s": round(total, 1),
        "matrix": matrix or None, "chart": kind, "error": resp.get("error"),
        "failed": [k for k, v in checks.items() if not v],
        "judge": j, "answer": text[:600],
    }


def burst(base: str, n: int) -> None:
    qs = ["Câți locuitori are România?", "Rata șomajului pe județe", "Inflation in Romania last 5 years"]
    print(f"\nburst: {n} concurrent requests -> {base}")
    with ThreadPoolExecutor(n) as ex:
        res = list(ex.map(lambda i: post(base, {"query": qs[i % len(qs)], "lang": "ro"}), range(n)))
    ok = [r for r in res if r[0] == 200 and r[1] and not r[1].get("error")]
    lat = sorted(r[2] for r in res)
    print(f"  ok {len(ok)}/{n}  latency min {lat[0]:.1f}s  median {statistics.median(lat):.1f}s  max {lat[-1]:.1f}s")
    for st, body, dt in res:
        if not (st == 200 and body and not body.get("error")):
            print(f"  FAIL status={st} {dt:.1f}s err={(body or {}).get('error')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=os.getenv("AGENT_BASE", "http://localhost:8000"))
    ap.add_argument("--cases", default=str(DEFAULT_CASES))
    ap.add_argument("--label", default="run")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--burst", type=int, default=0, help="run only a concurrency burst of N requests")
    ap.add_argument("--out", help="write JSON report here")
    args = ap.parse_args()

    if args.burst:
        burst(args.base, args.burst)
        return 0

    cases = json.loads(Path(args.cases).read_text())["cases"]
    if args.only:
        keep = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in keep]
    t0 = time.monotonic()
    with ThreadPoolExecutor(args.concurrency) as ex:
        results = list(ex.map(lambda c: run_case(args.base, c, not args.no_judge), cases))
    wall = time.monotonic() - t0

    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        js = r["judge"].get("score")
        print(f"{mark} {r['id']:<22} {r['latency_s']:>5.1f}s {str(r['matrix']):<9} {r['chart']:<5} judge={js} "
              + (f"failed={r['failed']} " if r["failed"] else "")
              + (f"| {r['judge'].get('reason')}" if js is not None and js < 2 else ""))
    lat = sorted(r["latency_s"] for r in results)
    scores = [r["judge"]["score"] for r in results if isinstance(r["judge"].get("score"), (int, float))]
    summary = {
        "label": args.label, "base": args.base, "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "latency_median_s": statistics.median(lat),
        "latency_p90_s": lat[int(0.9 * (len(lat) - 1))],
        "judge_mean": round(statistics.mean(scores), 2) if scores else None,
        "wall_s": round(wall, 1),
    }
    print("\n" + json.dumps(summary))
    if args.out:
        Path(args.out).write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=1))
    return 0 if summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
