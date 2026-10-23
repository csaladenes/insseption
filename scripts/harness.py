#!/usr/bin/env python3
"""Host-side API + agent smoke harness for production or a local stack.

  INSSEPTION_HOST=https://insse.csaladen.es python3 scripts/harness.py
  INSSEPTION_HOST=http://127.0.0.1:8787 python3 scripts/harness.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

HOST = os.environ.get("INSSEPTION_HOST", "https://insse.csaladen.es").rstrip("/")
AGENT_QUERY = os.environ.get(
    "INSSEPTION_AGENT_QUERY",
    "Romania total usually resident population latest year POP105A",
)
TIMEOUT = float(os.environ.get("INSSEPTION_HARNESS_TIMEOUT", "90"))


class Fail(Exception):
    pass


def call(
    method: str,
    path: str,
    *,
    body=None,
    accept: str = "application/json",
    expect_json: bool = True,
):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HOST}{path}",
        data=data,
        method=method,
        headers={
            "Accept": accept,
            "Content-Type": "application/json",
            "User-Agent": "insseption-harness/0.1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read()
            ctype = r.headers.get("Content-Type", "")
            if expect_json:
                return r.status, json.loads(raw.decode() or "null"), ctype
            return r.status, raw, ctype
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode() or "null")
        except Exception:
            payload = raw[:300]
        raise Fail(f"{method} {path} -> HTTP {exc.code}: {payload}") from exc
    except Exception as exc:
        raise Fail(f"{method} {path} -> {exc}") from exc


def check(name: str, cond, detail="") -> None:
    if not cond:
        raise Fail(f"{name} failed{': ' + detail if detail else ''}")
    print(f"  ok  {name}" + (f" ({detail})" if detail else ""))


def test_api() -> None:
    print("== API ==")
    st, health, _ = call("GET", "/api/v1/health")
    check("health status", st == 200 and health.get("ok") is True, str(health))
    check("upstream", health.get("upstream_ok") is True)

    st, root, _ = call("GET", "/api")
    check("api discovery", st == 200 and root.get("name") == "insseption", root.get("version"))

    st, meta, _ = call("GET", "/api/v1/meta")
    check("meta", st == 200 and meta.get("version"), meta.get("version"))

    st, ctx, _ = call("GET", "/api/v1/context?lang=en")
    nodes = ctx.get("nodes") or []
    check("context", st == 200 and len(nodes) > 0, f"{len(nodes)} nodes")

    st, matrix, _ = call("GET", "/api/v1/matrices/POP105A?lang=en")
    check(
        "matrix POP105A",
        st == 200 and (matrix.get("code") or "").upper() == "POP105A",
        (matrix.get("name") or "")[:60],
    )

    st, query, _ = call(
        "POST",
        "/api/v1/matrices/POP105A/query",
        body={"lang": "en", "selections": {}},
    )
    rows = query.get("row_count")
    cols = query.get("columns") or []
    check("query POP105A", st == 200 and rows is not None and len(cols) > 0, f"rows={rows}")

    # Expect a large national total somewhere in the payload (~19M).
    blob = json.dumps(query)
    check("population magnitude", "190" in blob or "19." in blob or "19," in blob, "saw 19…")


def test_docs_and_static() -> None:
    print("== Docs / static ==")
    st, html, ctype = call("GET", "/docs/en", accept="text/html", expect_json=False)
    text = html.decode("utf-8", errors="replace")
    check("docs/en", st == 200 and "text/html" in ctype, f"{len(text)} bytes")
    check("docs cite MIT", "MIT" in text)
    check("docs cite GitHub", "github.com/csaladenes/insseption" in text)
    check("docs cite ROEM", "econ.ubbcluj.ro/roem" in text or "ROEM" in text)
    check("docs cite INSSE", "INSSE" in text)

    st, js, ctype = call("GET", "/chat.js", accept="*/*", expect_json=False)
    check("chat.js", st == 200 and b"chat" in js.lower(), f"{len(js)} bytes")

    st, idx, ctype = call("GET", "/", accept="text/html", expect_json=False)
    text = idx.decode("utf-8", errors="replace").lower()
    check("chat home", st == 200 and "text/html" in ctype and "insse-chat-mount" in text)


def test_agent() -> None:
    print("== Agent ==")
    st, health, _ = call("GET", "/agent/health")
    check(
        "agent health",
        st == 200 and health.get("status") == "healthy",
        f"initialized={health.get('agent_initialized')}",
    )
    check("agent ready", health.get("agent_initialized") is True)

    st, ans, _ = call(
        "POST",
        "/agent/api/query",
        body={"query": AGENT_QUERY, "generate_chart": False},
    )
    check("agent query http", st == 200, f"matrix={ans.get('matrix')}")
    check("agent no hard error", not ans.get("error"), str(ans.get("error") or "")[:120])
    answer = ans.get("answer") or ""
    check("agent answer", len(answer) > 20, f"{len(answer)} chars")
    matrix = (ans.get("matrix") or "").upper()
    check("agent matrix", matrix in ("", "POP105A") or matrix.startswith("POP"), matrix or "none")


def main() -> int:
    print("HOST", HOST)
    try:
        test_api()
        test_docs_and_static()
        test_agent()
    except Fail as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
