#!/usr/bin/env python3
"""Crawl TEMPO context tree and write web/catalog.json (code + name)."""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.request
from collections import deque
from pathlib import Path

BASE = "http://statistici.insse.ro:8077/tempo-ins"
OUT = Path(__file__).resolve().parents[1] / "web" / "catalog.json"
UA = "insseption/0.1 (+https://github.com/csaladenes/insseption)"
HTML_RE = re.compile(r"<[^>]+>")
MATRIX_RE = re.compile(r"^[A-Z][A-Z0-9]{3,9}$")


def get(path: str, lang: str = "ro"):
    req = urllib.request.Request(
        f"{BASE}{path}?lang={lang}",
        headers={"User-Agent": UA, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def clean(name: str) -> str:
    return HTML_RE.sub("", name or "").strip()


def walk(lang: str = "en") -> list[dict]:
    matrices: dict[str, str] = {}
    queue: deque[str] = deque()
    # seed from root children (level-0 domains)
    root = get("/context/", lang=lang)
    for item in root:
        ctx = item.get("context") or {}
        if item.get("level") == 0 and ctx.get("code"):
            queue.append(ctx["code"])
    seen_nodes = set(queue)

    while queue:
        code = queue.popleft()
        try:
            payload = get(f"/context/{code}", lang=lang)
        except Exception as exc:
            print(f"skip {code}: {exc}", file=sys.stderr)
            continue
        time.sleep(0.12)
        for ctx in payload.get("children") or []:
            c = ctx.get("code") or ""
            name = clean(ctx.get("name") or "")
            url = (ctx.get("url") or "").lower()
            if url == "matrix" or MATRIX_RE.match(c):
                matrices[c.upper()] = name
            elif c and c not in seen_nodes:
                seen_nodes.add(c)
                queue.append(c)
    return [{"code": k, "name": v} for k, v in sorted(matrices.items())]


def main() -> int:
    lang = sys.argv[1] if len(sys.argv) > 1 else "en"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    print(f"crawling catalog lang={lang}…")
    rows = walk(lang)
    if limit:
        rows = rows[:limit]
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(rows)} matrices → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
