#!/usr/bin/env python3
"""Smoke-test local or deployed API."""

from __future__ import annotations

import json
import os
import sys
import urllib.request

BASE = os.environ.get("INSSEPTION_BASE", "http://127.0.0.1:8000/api/v1").rstrip("/")


def call(method: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, json.loads(r.read())


def main() -> int:
    print("BASE", BASE)
    st, health = call("GET", "/health")
    assert st == 200 and health.get("ok"), health
    print("health", health)
    st, meta = call("GET", "/meta")
    print("meta.translate_enabled", meta.get("translate_enabled"))
    st, ctx = call("GET", "/context?lang=en")
    print("context nodes", len(ctx.get("nodes") or []))
    st, m = call("GET", "/matrices/POP105A?lang=en")
    print("matrix", m.get("code"), m.get("name", "")[:60])
    # totals + latest year defaults via empty selections
    st, q = call(
        "POST",
        "/matrices/POP105A/query",
        {"lang": "en", "selections": {}},
    )
    print("query rows", q.get("row_count"), "cols", len(q.get("columns") or []))
    st, news = call("GET", "/news")
    print("news", news.get("count"))
    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
