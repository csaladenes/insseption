"""Chart builders for the insseption agent (bar / line / Romania county map).

Follows skill: insseption-agents.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any


def strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_county(s: str) -> str:
    s = strip_diacritics(re.sub(r"<[^>]+>", "", str(s))).strip().lower()
    s = s.replace("–", "-").replace("—", "-")
    s = re.sub(r"\s+", " ", s)
    aliases = {
        "bucuresti": "bucharest",
        "municipiul bucuresti": "bucharest",
        "bucharest": "bucharest",
        "bistrita-nasaud": "bistrita-nasaud",
        "caras-severin": "caras-severin",
        "satu mare": "satu mare",
    }
    return aliases.get(s, s)


def parse_number(raw: Any) -> float | None:
    if raw is None:
        return None
    s = re.sub(r"<[^>]+>", "", str(raw))
    s = s.replace("\xa0", "").replace(" ", "")
    # European thousands: 171.451,2 or 171451
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def extract_series(data: dict[str, Any]) -> tuple[list[str], list[float], list[list[Any]]]:
    """Return labels, values, and clean table rows [label, value].

    Supports tall rows and wide TEMPO responses where years are columns.
    """
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    if not rows:
        return [], [], []

    # --- Wide format: header row contains Year YYYY across columns ---
    header = None
    data_row = None
    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        year_cells = [
            i
            for i, c in enumerate(row)
            if re.search(r"\b(?:year|anul)\s+(19\d{2}|20\d{2})\b", str(c), re.I)
            or re.fullmatch(r"(19\d{2}|20\d{2})", str(c).strip())
        ]
        if len(year_cells) >= 2:
            header = row
            break
    if header is not None:
        # last non-header numeric-ish row with same width
        for row in reversed(rows):
            if not isinstance(row, (list, tuple)) or len(row) != len(header):
                continue
            nums = [parse_number(c) for c in row]
            if sum(v is not None and v > 1000 for v in nums) >= 2:
                data_row = row
                break
        if data_row is not None:
            labels: list[str] = []
            values: list[float] = []
            table: list[list[Any]] = []
            for i, cell in enumerate(header):
                m = re.search(r"(19\d{2}|20\d{2})", str(cell))
                if not m:
                    continue
                val = parse_number(data_row[i])
                if val is None:
                    continue
                labels.append(m.group(1))
                values.append(val)
                table.append([m.group(1), val])
            if values:
                return labels, values, table

    if len(columns) < 2:
        return [], [], []

    # Prefer territory-like column for labels when present
    label_i = 0
    for i, c in enumerate(columns):
        cl = str(c).lower()
        if any(k in cl for k in ("county", "jude", "macroregion", "territor", "regiun", "year", "ani")):
            label_i = i
            break
    value_i = len(columns) - 1

    labels = []
    values = []
    table = []
    colset = {str(c).lower() for c in columns}

    for row in rows:
        if not isinstance(row, (list, tuple)) or len(row) <= max(label_i, value_i):
            continue
        label = re.sub(r"<[^>]+>", "", str(row[label_i])).strip()
        if not label or label.lower() in colset:
            continue
        if label.lower().startswith(("mu:", "um:", "nace")):
            continue
        if label.lower() in {"number of persons"}:
            continue
        val = parse_number(row[value_i])
        if val is None:
            continue
        labels.append(label)
        values.append(val)
        table.append([label, val])

    if any(v >= 10_000 for v in values):
        kept = [(l, v) for l, v in zip(labels, values) if v < 1900 or v > 2100]
        if kept:
            labels = [k[0] for k in kept]
            values = [k[1] for k in kept]
            table = [[l, v] for l, v in kept]

    return labels, values, table


def looks_like_county_query(query: str, labels: list[str]) -> bool:
    q = strip_diacritics(query).lower()
    if any(k in q for k in ("county", "counties", "judet", "judete", "județ", "map", "harta", "choropleth")):
        return True
    # many short place-like labels
    if len(labels) >= 20:
        sample = " ".join(labels[:10]).lower()
        if any(n in sample for n in ("cluj", "timis", "bihor", "iasi", "constanta")):
            return True
    return False


def choose_kind(query: str, labels: list[str], values: list[float]) -> str:
    yearish = bool(labels) and all(
        str(x).isdigit() and 1900 <= int(str(x)) <= 2100
        for x in labels[: min(5, len(labels))]
    )
    if parse_year_range(query) or yearish:
        return "line"
    if looks_like_county_query(query, labels):
        return "map"
    q = strip_diacritics(query).lower()
    if any(
        k in q
        for k in (
            "trend",
            "over time",
            "time series",
            "evolutie",
            "evolution",
            "ani",
            "years",
        )
    ):
        return "line"
    if len(values) <= 12:
        return "bar"
    return "line"


def chartjs_config(
    kind: str,
    query: str,
    labels: list[str],
    values: list[float],
    value_label: str = "value",
) -> dict[str, Any]:
    ctype = "bar" if kind == "bar" else "line"
    return {
        "type": "chartjs",
        "kind": ctype,
        "config": {
            "type": ctype,
            "data": {
                "labels": labels,
                "datasets": [
                    {
                        "label": value_label,
                        "data": values,
                        "borderColor": "#7096C2",
                        "backgroundColor": "rgba(112,150,194,0.35)",
                        "tension": 0.25,
                    }
                ],
            },
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "title": {"display": True, "text": query[:90], "color": "#F6F6F6"},
                    "legend": {"display": False},
                },
                "scales": {
                    "x": {
                        "ticks": {"color": "rgba(246,246,246,0.58)", "maxRotation": 60},
                        "grid": {"color": "rgba(255,255,255,0.06)"},
                    },
                    "y": {
                        "ticks": {"color": "rgba(246,246,246,0.58)"},
                        "grid": {"color": "rgba(255,255,255,0.06)"},
                    },
                },
            },
        },
    }


def choropleth_payload(query: str, labels: list[str], values: list[float]) -> dict[str, Any]:
    mapping: dict[str, float] = {}
    for lab, val in zip(labels, values):
        mapping[norm_county(lab)] = val
    return {
        "type": "choropleth",
        "kind": "map",
        "title": query[:90],
        "geo": "/geo/romania-counties.json",
        "object": "ROU_adm1",
        "name_property": "NAME_1",
        "values": mapping,
        "color_low": "#0b1019",
        "color_high": "#7096C2",
    }


def build_chart(
    query: str,
    data: dict[str, Any],
    *,
    force_kind: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (chart, table) following insseption-agents skill.

    Single-number answers keep a table but skip the chart.
    """
    labels, values, table_rows = extract_series(data)
    if not values:
        return None, None
    columns = data.get("columns") or []
    value_label = str(columns[-1]) if columns else "value"
    kind = force_kind or choose_kind(query, labels, values)
    table = {"columns": ["label", "value"], "rows": table_rows}
    # One figure → no chart (still return the table for download/context)
    if len(values) < 2:
        return None, table
    if kind == "map":
        if len(values) < 5:
            return None, table
        return choropleth_payload(query, labels, values), table
    return chartjs_config(kind, query, labels, values, value_label), table


_YEAR_RE = re.compile(
    r"(?P<a>19\d{2}|20\d{2})\s*(?:[-–—]|to|until|pana|până|bis)\s*(?P<b>19\d{2}|20\d{2})",
    re.I,
)
_YEAR_LIST_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")


def parse_year_range(text: str) -> tuple[int, int] | None:
    """Extract an inclusive year range from free text, if present."""
    if not text:
        return None
    m = _YEAR_RE.search(text)
    if m:
        a, b = int(m.group("a")), int(m.group("b"))
        return (a, b) if a <= b else (b, a)
    years = [int(y) for y in _YEAR_LIST_RE.findall(text)]
    if len(years) >= 2:
        return min(years), max(years)
    return None


def apply_year_range_selections(
    meta: dict[str, Any],
    selections: dict[str, Any] | None,
    text: str,
) -> dict[str, list[int]]:
    """Select year span + sensible TOTAL defaults on other dimensions."""
    out: dict[str, list[int]] = {}
    if selections:
        for k, v in selections.items():
            if isinstance(v, list):
                out[str(k)] = [int(x) for x in v]
    yr = parse_year_range(text)
    dims = meta.get("dimensions") or []
    if not yr:
        return out
    lo, hi = yr

    def _total_id(opts: list[dict[str, Any]]) -> int | None:
        for o in opts:
            lab = (o.get("label") or "").strip().lower()
            if lab in {"total", "total ", "totale"} or lab.upper() == "TOTAL":
                if o.get("nom_item_id") is not None:
                    return int(o["nom_item_id"])
        for o in opts:
            if "total" in (o.get("label") or "").strip().lower() and o.get("nom_item_id") is not None:
                return int(o["nom_item_id"])
        if opts and opts[0].get("nom_item_id") is not None:
            return int(opts[0]["nom_item_id"])
        return None

    for d in dims:
        code = str(d.get("dim_code") or d.get("id") or "")
        if not code:
            continue
        lab = (d.get("label") or "").lower()
        opts = d.get("options") or []
        if not opts:
            continue
        if any(k in lab for k in ("year", "ani", "perioad")) and "age" not in lab:
            ids: list[int] = []
            for o in opts:
                ys = _YEAR_LIST_RE.findall(str(o.get("label") or ""))
                if not ys:
                    continue
                y = int(ys[0])
                if lo <= y <= hi and o.get("nom_item_id") is not None:
                    ids.append(int(o["nom_item_id"]))
            if ids:
                out[code] = ids
            else:
                # no overlap — keep closest available years inside matrix span
                all_y = []
                for o in opts:
                    ys = _YEAR_LIST_RE.findall(str(o.get("label") or ""))
                    if ys and o.get("nom_item_id") is not None:
                        all_y.append((int(ys[0]), int(o["nom_item_id"])))
                if all_y:
                    # prefer years nearest to requested window
                    mid = (lo + hi) / 2
                    all_y.sort(key=lambda x: abs(x[0] - mid))
                    pick = sorted(all_y[: min(12, len(all_y))], key=lambda x: x[0])
                    out[code] = [i for _, i in pick]
        elif code not in out:
            tid = _total_id(opts)
            if tid is not None:
                out[code] = [tid]
    return out


def prefer_matrix_for_years(text: str, current: str | None) -> str | None:
    """Suggest a matrix that better covers an older year window."""
    yr = parse_year_range(text)
    if not yr:
        return None
    lo, hi = yr
    # POP105A starts 2003; legally resident POP107A from 1992; POP111A to 1991
    if hi < 1992:
        return "POP111A"
    if lo < 2003:
        return "POP107A"
    return current


# --- TEMPO selection helpers -------------------------------------------------

_REGION_LABELS = {
    "TOTAL",
    "MACROREGION 1",
    "MACROREGION 2",
    "MACROREGION 3",
    "MACROREGION 4",
    "NORTH - WEST",
    "CENTER",
    "NORTH - EAST",
    "SOUTH - EAST",
    "SOUTH - MUNTENIA",
    "BUCHAREST - ILFOV",
    "SOUTH - WEST OLTENIA",
    "WEST",
}


def _is_county_option(label: str) -> bool:
    L = (label or "").strip()
    Lu = L.upper()
    if not L or Lu in _REGION_LABELS:
        return False
    if "MACROREGION" in Lu or Lu.startswith("MACRO"):
        return False
    if "REGION" in Lu:
        return False
    return True


def expand_county_selections(meta: dict[str, Any], selections: dict[str, Any] | None) -> dict[str, list[int]]:
    """Force TOTAL×counties×latest year when meta has a territory dimension."""
    out: dict[str, list[int]] = {}
    if selections:
        for k, v in selections.items():
            if isinstance(v, list):
                out[str(k)] = [int(x) for x in v]

    dims = meta.get("dimensions") or []
    for d in dims:
        code = str(d.get("dim_code"))
        lab = (d.get("label") or "").lower()
        opts = d.get("options") or []
        if not opts:
            continue
        if any(k in lab for k in ("macroregion", "county", "counties", "jude", "territor")):
            out[code] = [
                int(o["nom_item_id"])
                for o in opts
                if o.get("nom_item_id") is not None and _is_county_option(o.get("label") or "")
            ]
        elif any(k in lab for k in ("year", "ani", "perioad")):
            out[code] = [int(opts[-1]["nom_item_id"])]
        elif any(k in lab for k in ("nace", "activit", "caen")):
            total = next(
                (o for o in opts if (o.get("label") or "").strip().upper() == "TOTAL"),
                opts[0],
            )
            out[code] = [int(total["nom_item_id"])]
        elif "sex" in lab or "sexe" in lab:
            total = next(
                (o for o in opts if "total" in (o.get("label") or "").strip().lower()),
                opts[0],
            )
            out[code] = [int(total["nom_item_id"])]
        elif code not in out:
            out[code] = [int(opts[0]["nom_item_id"])]
    return out
