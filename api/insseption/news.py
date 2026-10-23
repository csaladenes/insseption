from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup

MATRIX_CODE_RE = re.compile(r"^[A-Z0-9]{4,10}$")


def parse_news_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []
    rows = table.find_all("tr")
    if len(rows) < 2:
        return []
    headers = [c.get_text(strip=True) for c in rows[0].find_all(["td", "th"])]
    out: list[dict[str, Any]] = []
    for tr in rows[1:]:
        cells = [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        if not cells:
            continue
        item = {headers[i] if i < len(headers) else f"col_{i}": cells[i] for i in range(len(cells))}
        # common columns: Activitatea / Data / Domeniu / ... / Cod matrice
        code = None
        for v in cells:
            if MATRIX_CODE_RE.match(v):
                code = v
                break
        if code is None:
            continue
        out.append(
            {
                "code": code,
                "activity": item.get("Activitatea") or item.get("Activity"),
                "date": item.get("Data") or item.get("Date"),
                "domain": item.get("Domeniu") or item.get("Domain"),
                "raw": item,
            }
        )
    return out
