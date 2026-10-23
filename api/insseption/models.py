from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    lang: str = Field(default="ro", pattern="^(ro|en)$")
    selections: dict[str, list[int]] = Field(
        default_factory=dict,
        description="Map of dimCode (as string) → list of nomItemId values",
    )


class TranslateRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=50)
    target: str = Field(..., pattern="^(hu|ro|en)$")


class HealthResponse(BaseModel):
    ok: bool
    version: str
    upstream_ok: bool
    attribution: str


class MetaResponse(BaseModel):
    version: str
    attribution: str
    terms_url: str
    max_cells: int
    translate_enabled: bool
    openrouter_model: str | None
    languages: list[str]
    existing_solutions: list[dict[str, str]]


def _strip_html(name: str | None) -> str | None:
    if not name:
        return name
    # TEMPO sometimes embeds <a href=...>Press releases</a> in names
    if "<" not in name:
        return name
    out = []
    in_tag = False
    for ch in name:
        if ch == "<":
            in_tag = True
            continue
        if ch == ">":
            in_tag = False
            continue
        if not in_tag:
            out.append(ch)
    return "".join(out).strip()


def normalize_context_nodes(raw: Any, parent_code: str | None = None) -> list[dict[str, Any]]:
    """Normalize both root list and child `{children:[…]}` TEMPO shapes."""
    out: list[dict[str, Any]] = []
    if isinstance(raw, list):
        # Root endpoint returns a flat forest; if parent_code is None keep level-0 only
        for item in raw:
            if not isinstance(item, dict):
                continue
            ctx = item.get("context") or {}
            level = item.get("level")
            if parent_code is None and level not in (0, None):
                # still include level 0; skip deeper on root browse
                if level != 0:
                    continue
            out.append(
                {
                    "code": ctx.get("code"),
                    "name": _strip_html(ctx.get("name")),
                    "level": level,
                    "parent_code": item.get("parentCode"),
                    "children_url": ctx.get("childrenUrl"),
                    "url": ctx.get("url"),
                    "comment": ctx.get("comment"),
                }
            )
        return out

    if isinstance(raw, dict):
        children = raw.get("children") or []
        for ctx in children:
            if not isinstance(ctx, dict):
                continue
            out.append(
                {
                    "code": ctx.get("code"),
                    "name": _strip_html(ctx.get("name")),
                    "level": None,
                    "parent_code": parent_code or (raw.get("context") or {}).get("code"),
                    "children_url": ctx.get("childrenUrl"),
                    "url": ctx.get("url"),
                    "comment": ctx.get("comment"),
                }
            )
    return out


def normalize_matrix_meta(raw: dict[str, Any], code: str) -> dict[str, Any]:
    dims = []
    for d in raw.get("dimensionsMap") or []:
        dims.append(
            {
                "dim_code": d.get("dimCode"),
                "label": d.get("label"),
                "options": [
                    {
                        "label": o.get("label"),
                        "nom_item_id": o.get("nomItemId"),
                        "offset": o.get("offset"),
                        "parent_id": o.get("parentId"),
                    }
                    for o in (d.get("options") or [])
                ],
            }
        )
    return {
        "code": code.upper(),
        "name": raw.get("matrixName"),
        "ancestors": raw.get("ancestors") or [],
        "periodicity": raw.get("periodicitati") or [],
        "definition": raw.get("definitie"),
        "methodology": raw.get("metodologie"),
        "last_update": raw.get("ultimaActualizare"),
        "observations": raw.get("observatii"),
        "dimensions": dims,
        "details": raw.get("details") or {},
        "sources": raw.get("surseDeDate") or [],
    }


def build_upstream_query(
    meta: dict[str, Any],
    selections: dict[str, list[int]],
    lang: str,
    code: str,
    max_cells: int,
) -> dict[str, Any]:
    dims = meta.get("dimensionsMap") or []
    arr: list[list[dict[str, Any]]] = []
    product = 1
    for dim in dims:
        dim_code = str(dim.get("dimCode"))
        opts = dim.get("options") or []
        by_id = {o.get("nomItemId"): o for o in opts}
        wanted = selections.get(dim_code) or selections.get(str(dim.get("dimCode")))
        if not wanted:
            # default: Total-like first option, or last year for Ani
            label = (dim.get("label") or "").lower()
            if opts and (
                "ani" in label or "year" in label or "perioad" in label
            ):
                chosen = [opts[-1]]
            else:
                total = next(
                    (
                        o
                        for o in opts
                        if (o.get("label") or "").strip().lower()
                        in ("total", "total ")
                    ),
                    None,
                )
                chosen = [total or opts[0]] if opts else []
        else:
            chosen = []
            for nid in wanted:
                opt = by_id.get(nid)
                if opt is None:
                    from .errors import ApiError

                    raise ApiError(
                        "bad_selection",
                        f"Unknown nomItemId {nid} for dimension {dim_code}",
                        status=422,
                    )
                chosen.append(opt)
        if not chosen:
            from .errors import ApiError

            raise ApiError(
                "empty_dimension",
                f"No options selected for dimension {dim_code}",
                status=422,
            )
        product *= len(chosen)
        if product > max_cells:
            from .errors import ApiError

            raise ApiError(
                "too_many_cells",
                f"Selection product {product} exceeds max_cells={max_cells}; narrow a dimension.",
                status=422,
            )
        arr.append(chosen)

    return {
        "language": lang,
        "matrixName": code.upper(),
        "arr": arr,
        "matrixDetails": meta.get("details") or {},
    }


def dataset_to_rows(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, list) or not raw:
        return {"columns": [], "rows": [], "raw": raw}
    # TEMPO dataSet returns nested header rows then data; flatten simply
    header = raw[0] if isinstance(raw[0], list) else []
    # find first row that looks like data (last cell numeric-ish) after headers
    columns = [str(c) for c in header]
    rows: list[list[Any]] = []
    for row in raw[1:]:
        if not isinstance(row, list):
            continue
        # skip repeated header-like rows
        if row == header:
            continue
        rows.append(row)
    return {"columns": columns, "rows": rows}
