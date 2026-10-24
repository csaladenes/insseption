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


def _has_letters(cell: Any) -> bool:
    return bool(re.search(r"[^\W\d_]", re.sub(r"<[^>]+>", "", str(cell))))


def wide_series(rows: list[Any]) -> tuple[list[str], list[tuple[str, list[float | None]]], str] | None:
    """Wide TEMPO responses (years as columns): (year labels, [(row label, values per year)], label name)."""
    header = None
    year_idx: list[int] = []
    for row in rows:
        if not isinstance(row, (list, tuple)):
            continue
        idx = [
            i
            for i, c in enumerate(row)
            if re.search(r"\b(?:year|anul)\s+(19\d{2}|20\d{2})\b", str(c), re.I)
            or re.fullmatch(r"(19\d{2}|20\d{2})", str(c).strip())
        ]
        if len(idx) >= 2:
            header, year_idx = row, idx
            break
    if header is None:
        return None
    years = [re.search(r"(19\d{2}|20\d{2})", str(header[i])).group(1) for i in year_idx]
    label_i = year_idx[0] - 1
    series: list[tuple[str, list[float | None]]] = []
    for row in rows:
        if row is header or not isinstance(row, (list, tuple)) or len(row) != len(header):
            continue
        cells = [row[i] for i in year_idx]
        if all(_has_letters(c) for c in cells):
            continue
        vals = [None if _has_letters(c) else parse_number(c) for c in cells]
        if sum(v is not None for v in vals) == 0:
            continue
        label = re.sub(r"<[^>]+>", "", str(row[label_i])).strip() if label_i >= 0 else ""
        series.append((label, vals))
    if not series:
        return None
    label_name = str(header[label_i]).strip() if label_i >= 0 else "label"
    return years, series, label_name


def extract_series(data: dict[str, Any]) -> tuple[list[str], list[float], list[list[Any]]]:
    """Return labels, values, and clean table rows [label, value].

    Supports tall rows and wide TEMPO responses where years are columns.
    """
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    if not rows:
        return [], [], []

    # --- Wide format: header row contains Year YYYY across columns ---
    wide = wide_series(rows)
    if wide:
        years, series, _ = wide
        if len(series) == 1:
            label_vals = [(y, v) for y, v in zip(years, series[0][1]) if v is not None]
            if label_vals:
                return (
                    [y for y, _ in label_vals],
                    [v for _, v in label_vals],
                    [[y, v] for y, v in label_vals],
                )
        else:
            latest = [(lab, next((v for v in reversed(vals) if v is not None), None)) for lab, vals in series]
            latest = [(lab, v) for lab, v in latest if v is not None]
            if latest:
                return [l for l, _ in latest], [v for _, v in latest], [[l, v] for l, v in latest]

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
        if _has_letters(row[value_i]):
            continue
        val = parse_number(row[value_i])
        if val is None:
            continue
        labels.append(label)
        values.append(val)
        table.append([label, val])

    return labels, values, table


def looks_like_county_query(query: str, labels: list[str]) -> bool:
    q = strip_diacritics(query).lower()
    if any(k in q for k in ("county", "counties", "judet", "judete", "județ", "megye", "map", "harta", "choropleth")):
        return True
    # many short place-like labels
    if len(labels) >= 20:
        sample = " ".join(labels[:10]).lower()
        if any(n in sample for n in ("cluj", "timis", "bihor", "iasi", "constanta")):
            return True
    return False


_EXPLICIT_KIND = (
    ("bar", ("bar chart", "bar graph", "grafic cu bare", "diagrama cu bare", "oszlopdiagram")),
    ("line", ("line chart", "line graph", "grafic liniar", "vonaldiagram")),
    ("map", ("map", "harta", "terkep", "choropleth")),
)


def strong_kind(query: str, labels: list[str]) -> str | None:
    """Chart kind implied by an explicit request or by the data's shape; None when undecided."""
    q = strip_diacritics(query).lower()
    for kind, words in _EXPLICIT_KIND:
        if any(re.search(r"(?<![a-z])" + re.escape(w), q) for w in words):
            return kind
    yearish = bool(labels) and all(
        str(x).isdigit() and 1900 <= int(str(x)) <= 2100
        for x in labels[: min(5, len(labels))]
    )
    if yearish:
        return "line"
    if looks_like_county_query(query, labels):
        return "map"
    if parse_year_range(query):
        return "line" if len(labels) < 2 else ("map" if len(labels) >= 5 else "bar")
    return None


def choose_kind(query: str, labels: list[str], values: list[float]) -> str:
    strong = strong_kind(query, labels)
    if strong:
        return strong
    q = strip_diacritics(query).lower()
    if re.search(r"(?<![a-z])(?:trend|over time|time series|evolut|years|(?:ani|anii|anilor)(?![a-z]))", q):
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
        # mapbox8-style green → yellow → red (low → high), 5 quintiles
        "colors": ["#239f69", "#8fbf4a", "#f5d232", "#c52b69", "#850237"],
        "color_low": "#239f69",
        "color_high": "#850237",
    }


def build_chart(
    query: str,
    data: dict[str, Any],
    *,
    hint: str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Return (chart, table) following insseption-agents skill.

    Single-number answers keep a table but skip the chart. ``hint`` (the planner's
    chart_hint) only breaks ties when neither the request nor the data shape decides.
    """
    labels, values, table_rows = extract_series(data)
    if not values:
        return None, None
    columns = data.get("columns") or []
    value_label = str(columns[-1]) if columns else "value"
    kind = strong_kind(query, labels) or (hint if hint in ("line", "bar", "map") else None) or choose_kind(query, labels, values)
    table = {"columns": ["label", "value"], "rows": table_rows}
    wide = wide_series(data.get("rows") or [])
    if wide and len(wide[1]) > 1:
        years, series, label_name = wide
        table = {"columns": [label_name, *years], "rows": [[lab, *vals] for lab, vals in series]}
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
    years = sorted({int(y) for y in _YEAR_LIST_RE.findall(text)})
    if len(years) >= 2:
        return years[0], years[-1]
    return None


_NUM_WORDS = {
    "two": 2, "three": 3, "five": 5, "ten": 10, "doi": 2, "trei": 3, "cinci": 5, "zece": 10,
    "ket": 2, "harom": 3, "ot": 5, "tiz": 10,
}
_RELATIVE_RE = re.compile(
    r"(?:last|past|recent|ultimii|ultimele|elmult|utolso)\s+(\d{1,2}|[a-z]+)\s+(?:years?|ani|ev)",
    re.I,
)


def relative_year_range(text: str, meta: dict[str, Any]) -> tuple[int, int] | None:
    """'last 10 years' / 'ultimii 5 ani' / 'elmúlt 5 év' → span ending at the matrix's latest year."""
    m = _RELATIVE_RE.search(strip_diacritics(text or "").lower())
    if not m:
        return None
    raw = m.group(1)
    n = int(raw) if raw.isdigit() else _NUM_WORDS.get(raw)
    if not n:
        return None
    latest = None
    for d in meta.get("dimensions") or []:
        lab = (d.get("label") or "").lower()
        if any(k in lab for k in ("year", "ani", "perioad")) and "age" not in lab:
            ys = [int(y) for o in d.get("options") or [] for y in _YEAR_LIST_RE.findall(str(o.get("label") or ""))]
            if ys:
                latest = max(ys)
    if latest is None:
        return None
    return latest - n + 1, latest


def apply_year_range_selections(
    meta: dict[str, Any],
    selections: dict[str, Any] | None,
    text: str,
    yr: tuple[int, int] | None = None,
) -> dict[str, list[int]]:
    """Select year span + sensible TOTAL defaults on other dimensions."""
    out: dict[str, list[int]] = {}
    if selections:
        for k, v in selections.items():
            if isinstance(v, list):
                out[str(k)] = [int(x) for x in v]
    yr = yr or parse_year_range(text)
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


def apply_single_year(
    meta: dict[str, Any], selections: dict[str, Any] | None, year: int
) -> dict[str, list[int]]:
    """Pin the year dimension to one requested year (when the matrix has it); drop non-dim keys."""
    out = {
        str(k): [int(x) for x in v]
        for k, v in (selections or {}).items()
        if str(k).isdigit() and isinstance(v, list)
    }
    for d in meta.get("dimensions") or []:
        lab = (d.get("label") or "").lower()
        if not (any(k in lab for k in ("year", "ani", "perioad")) and "age" not in lab):
            continue
        for o in d.get("options") or []:
            ys = _YEAR_LIST_RE.findall(str(o.get("label") or ""))
            if ys and int(ys[0]) == year and o.get("nom_item_id") is not None:
                out[str(d.get("dim_code"))] = [int(o["nom_item_id"])]
                break
    return out


def mentioned_years(text: str) -> tuple[int, int] | None:
    """Year range from free text, including a single year as (y, y)."""
    yr = parse_year_range(text)
    if yr:
        return yr
    years = [int(y) for y in _YEAR_LIST_RE.findall(text or "")]
    return (years[0], years[0]) if years else None


def prefer_matrix_for_years(
    text: str, current: str | None, years: tuple[int, int] | None = None
) -> str | None:
    """Suggest a population matrix that better covers an older year window."""
    if not current or current not in ("POP105A", "POP107A", "POP111A"):
        return current
    yr = years or parse_year_range(text)
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
    if "REGION" in Lu or "REGIUNE" in Lu:
        return False
    return True


def expand_county_selections(meta: dict[str, Any], selections: dict[str, Any] | None) -> dict[str, list[int]]:
    """Force TOTAL×counties when meta has a territory dimension; latest year unless one is chosen."""
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
        elif any(
            k in lab
            for k in ("year", "ani", "perioad", "luni", "month", "trimestr", "quarter", "év", "hónap", "negyedév")
        ):
            if not out.get(code):
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


_COUNTY_ALIASES = {
    "bucharest": ("bucharest", "bucuresti", "bukarest"),
    "cluj": ("cluj", "kolozs"),
    "timis": ("timis", "temes"),
    "bihor": ("bihor", "bihar"),
    "mures": ("mures", "maros"),
    "harghita": ("harghita", "hargita"),
    "covasna": ("covasna", "kovaszna"),
    "satu mare": ("satu mare", "szatmar"),
    "brasov": ("brasov", "brasso"),
    "sibiu": ("sibiu", "szeben"),
    "maramures": ("maramures", "maramaros"),
    "salaj": ("salaj", "szilagy"),
    "bistrita-nasaud": ("bistrita", "beszterce"),
    "hunedoara": ("hunedoara", "hunyad"),
    "iasi": ("iasi", "jaszvasar"),
    "constanta": ("constanta", "konstanca"),
}


def _county_keys(label: str) -> tuple[str, ...]:
    key = norm_county(label)
    key = re.sub(r"^municipiul\s+|\s+municipality$", "", key).strip()
    key = norm_county(key)
    return _COUNTY_ALIASES.get(key, (key,))


def select_named_counties(
    meta: dict[str, Any], selections: dict[str, Any] | None, query: str
) -> dict[str, list[int]] | None:
    """Select only the counties named in the query (e.g. 'Cluj and Timiș'); None if none named."""
    q = strip_diacritics(query or "").lower()
    for d in meta.get("dimensions") or []:
        lab = (d.get("label") or "").lower()
        if not any(k in lab for k in ("county", "counties", "jude", "territor")):
            continue
        ids: list[int] = []
        for o in d.get("options") or []:
            olab = o.get("label") or ""
            if o.get("nom_item_id") is None or not _is_county_option(olab):
                continue
            for key in _county_keys(olab):
                tail = "" if len(key) >= 4 else r"(?![a-z])"
                if re.search(r"(?<![a-z])" + re.escape(key) + tail, q):
                    ids.append(int(o["nom_item_id"]))
                    break
        if not ids:
            return None
        out = {str(k): [int(x) for x in v] for k, v in (selections or {}).items() if isinstance(v, list)}
        out[str(d.get("dim_code"))] = ids
        return out
    return None
