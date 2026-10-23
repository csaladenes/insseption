"""/docs — trilingual guide (EN/RO/HU) + Swagger reference.

    GET /docs              EN, or redirect to /docs/ro|/docs/hu from Accept-Language
    GET /docs/en|ro|hu     Guide: quick start, model, recipes, catalogue, reference, errors, cite
    GET /docs/reference    Swagger UI on /openapi.json
    GET /openapi.json      OpenAPI schema with servers + tags
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import __version__, config, docs_content as C, docs_i18n as I

router = APIRouter(include_in_schema=False)

ASSETS = Path(__file__).resolve().parent / "docs_assets"
STYLE = (ASSETS / "style.css").read_text(encoding="utf-8")
DOCS_JS = (ASSETS / "docs.js").read_text(encoding="utf-8")
SORT_JS = (ASSETS / "sort.js").read_text(encoding="utf-8") if (ASSETS / "sort.js").is_file() else ""

HLJS = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0"
SWAGGER = "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14"
HL_CLASS = {
    "curl": "language-bash",
    "python": "language-python",
    "r": "language-r",
    "js": "language-javascript",
    "excel": "nohighlight",
}
GLOBE = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.6 2.8 3.9 6 3.9 9.5s-1.3 6.7-3.9 9.5'
    'M12 2.5C9.4 5.3 8.1 8.5 8.1 12s1.3 6.7 3.9 9.5"/></svg>'
)
CHEVRON = (
    '<svg class="chev" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true">'
    '<path d="M2 4.5l4 4 4-4"/></svg>'
)

PUBLIC_BASE = "https://insse.csaladen.es"
GITHUB = "https://github.com/csaladenes/insseption"
ROEM = "https://econ.ubbcluj.ro/roem"
INSSE_TERMS = "https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse"


def e(v) -> str:
    return html.escape("" if v is None else str(v))


def table(headers: list[str], rows: list[str], empty: str, cls: str = "") -> str:
    if not rows:
        return f'<p class="muted">{empty}</p>'
    th = "".join(f"<th>{e(h)}</th>" for h in headers)
    return (
        f'<div class="card tablecard"><div class="scroll"><table class="{cls}">'
        f"<thead><tr>{th}</tr></thead><tbody>{''.join(rows)}</tbody></table></div></div>"
    )


def page_path(lang: str) -> str:
    return "/docs/en" if lang == "en" else f"/docs/{lang}"


def lang_switch(lang: str) -> str:
    t = I.UI[lang]
    items = "".join(
        f'<li><a href="{page_path(code)}" hreflang="{code}" lang="{code}"'
        f'{" aria-current=true" if code == lang else ""}>{I.NAMES[code]}</a></li>'
        for code in I.ORDER
    )
    return (
        f'<details class="lang-switch"><summary aria-label="{e(t["lang_label"])}: {I.NAMES[lang]}">{GLOBE}'
        f'<span>{lang.upper()}</span>{CHEVRON}</summary><ul>{items}</ul></details>'
    )


def shell(
    title: str,
    body: str,
    *,
    lang: str = "en",
    guide: str = "/docs",
    extra_head: str = "",
    scripts: str = "",
) -> HTMLResponse:
    t = I.UI[lang]
    switch = f'<div class="langs">{lang_switch(lang)}</div>'
    return HTMLResponse(
        f"""<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{e(t['description'])}">
<title>{e(title)} · {e(t['site'])}</title>
<style>{STYLE}</style>{extra_head}</head><body>
<header><div class="brand">insseption <b>API</b><span>{e(t['site'])}</span></div>
<nav><a href="{guide}">{e(t['nav_guide'])}</a>
<a href="/docs/reference">{e(t['nav_ref'])}</a>
<a href="/chat">{e(t['nav_chat'])}</a>
<a href="{GITHUB}" target="_blank" rel="noopener">{e(t['nav_github'])}</a></nav>{switch}</header>
<main>{body}</main>{scripts}</body></html>"""
    )


def fill(text: str, **values) -> str:
    for k, v in values.items():
        text = text.replace(f"[[{k}]]", str(v))
    return text


def localise(src: str, lang: str) -> str:
    if lang == "en":
        return src
    for en, tr in sorted(I.COMMENTS.items(), key=lambda kv: -len(kv[0])):
        if lang in tr:
            src = src.replace(en, tr[lang])
    return src


def code_block(prog: str, src: str, base: str, lang: str = "en") -> str:
    t = I.UI[lang]
    text = localise(src, lang).replace("{BASE}", base).replace("{KEY}", "YOUR_KEY")
    return (
        f'<div class="code" data-lang="{prog}"><button class="copy" type="button">{e(t["copy"])}</button>'
        f'<pre><code class="{HL_CLASS[prog]}">{e(text)}</code></pre></div>'
    )


def plain_block(text: str, cls: str = "language-bash") -> str:
    return f'<div class="code"><pre><code class="{cls}">{e(text)}</code></pre></div>'


def variants(code: dict, base: str, lang: str = "en") -> str:
    blocks = "".join(code_block(prog, code[prog], base, lang) for prog, _ in C.LANGS if prog in code)
    only = ""
    if len(code) < len(C.LANGS):
        names = ", ".join(n for prog, n in C.LANGS if prog in code)
        only = (
            f'<p class="only small muted" hidden>{e(fill(I.UI[lang]["only_shown"], NAMES=names))}</p>'
        )
    return f'<div class="variants">{only}{blocks}</div>'


def badge(lang: str) -> str:
    return f'<span class="badge open">{I.UI[lang]["badge_open"]}</span>'


def request_line(method: str, url: str, base: str, lang: str = "en") -> str:
    full = base + url if url.startswith("/") else url
    return (
        f'<div class="req"><span class="verb">{e(method)}</span><span class="path">{e(url)}</span>'
        f'{badge(lang)}'
        f'<a class="try" href="{e(full)}" target="_blank" rel="noopener">{I.UI[lang]["open_answer"]}</a></div>'
    )


def link(url: str, label: str) -> str:
    return f'<a href="{e(url)}" target="_blank" rel="noopener">{e(label)}</a>'


def recipe_text(r: dict, lang: str) -> tuple[str, str]:
    if lang == "en":
        return r["title"], r["lead"]
    return I.RECIPES[r["id"]][lang]


def reference_text(r: dict, lang: str):
    if lang == "en":
        return r["summary"], r["returns"], r["params"]
    key = f"{r['path']}|{r['method']}"
    return I.REFERENCE[key][lang]


def catalogue_rows() -> list[dict]:
    path = Path(__file__).resolve().parents[2] / "web" / "catalog.json"
    # also try /app/web in container
    for candidate in (path, Path("/app/web/catalog.json")):
        if candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except Exception:
                pass
    return [{"code": "POP105A", "name": "Usually resident population…"}]


def sample_answer() -> str:
    sample = {
        "code": "POP105A",
        "lang": "en",
        "columns": ["Age group and ages", "Sex", "Years", "UM: Number of persons"],
        "rows": [
            ["Total", "Total", "Year 2024", 19064409],
            ["Total", "Male", "Year 2024", 9254312],
            ["Total", "Female", "Year 2024", 9810097],
        ],
        "row_count": 3,
        "attribution": config.ATTRIBUTION,
    }
    return json.dumps(sample, ensure_ascii=False, indent=2)


def base_url(request: Request) -> str:
    xf_proto = request.headers.get("x-forwarded-proto")
    xf_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if xf_host:
        scheme = xf_proto or request.url.scheme or "https"
        return f"{scheme}://{xf_host}".rstrip("/")
    return PUBLIC_BASE


def render(base: str, matrices: list[dict], sample: str, lang: str = "en") -> str:
    t = I.UI[lang]
    toc = [
        ("start", t["toc_start"]),
        ("access", t["toc_access"]),
        ("model", t["toc_model"]),
        ("recipes", t["toc_recipes"]),
    ] + [(r["id"], recipe_text(r, lang)[0]) for r in C.RECIPES] + [
        ("catalogue", t["toc_catalogue"]),
        ("reference", t["toc_reference"]),
        ("errors", t["toc_errors"]),
        ("cite", t["toc_cite"]),
        ("history", t["toc_history"]),
    ]
    recipe_ids = {r["id"] for r in C.RECIPES}
    toc_html = "".join(
        f'<a href="#{i}"{" class=sub" if i in recipe_ids else ""}>{e(x)}</a>' for i, x in toc
    )
    tabs = "".join(
        f'<button type="button" data-lang="{prog}" aria-selected="false">{name}</button>'
        for prog, name in C.LANGS
    )

    recipes = ""
    for r in C.RECIPES:
        title, lead = recipe_text(r, lang)
        method = "POST" if r["id"] in ("query-post", "csv") else "GET"
        recipes += (
            f'\n<div class="card recipe" id="{r["id"]}"><h3>{e(title)}</h3>'
            f'<p>{fill(lead, BASE=e(base))}</p>'
            f'\n{request_line(method, r["url"], base, lang)}'
            f'{variants(r["code"], base, lang)}</div>'
        )

    cat_rows = []
    for m in matrices[:400]:
        code = m.get("code") or ""
        name = m.get("name") or ""
        meta = f"{base}/api/v1/matrices/{code}?lang=en"
        cat_rows.append(
            f"<tr><td><code>{e(code)}</code></td><td>{e(name)}</td>"
            f"<td class='small'>{link(meta, t['cat_about'])} · "
            f"{link(base + '/api/v1/matrices/' + code + '/query?lang=en', 'query')}</td></tr>"
        )
    cat_html = table(t["cat_head"], cat_rows, t["cat_empty"], cls="sortable catalogue")

    ref_rows = []
    for r in C.REFERENCE:
        summary, returns, params = reference_text(r, lang)
        plist = "".join(
            f"<li><code>{n}</code> <span class='muted'>({k})</span> {w}</li>" for n, k, w in params
        )
        ex = r["example"]
        ref_rows.append(
            f"<tr><td><code>{e(r['method'])} {e(r['path'])}</code></td><td>{badge(lang)}</td>"
            f"<td><b>{e(summary)}</b><div class='small muted'>{returns}</div>"
            f"{f'<ul class=small>{plist}</ul>' if plist else ''}"
            f"<div class='small'>{t['eg']} {link(base + ex, ex)}</div></td></tr>"
        )
    ref_html = table(t["ref_head"], ref_rows, "", cls="ref")

    err_html = table(
        t["err_head"],
        [
            f"<tr><td class='num'>{c}</td><td>{title}</td>"
            f"<td>{w if lang == 'en' else I.ERRORS[c][lang]}</td></tr>"
            for c, title, w in C.ERRORS
        ],
        "",
    )
    changes = "".join(
        f"<tr><td class='small' style='white-space:nowrap'>{d}</td>"
        f"<td>{x if lang == 'en' else I.CHANGELOG[d][lang]}</td></tr>"
        for d, x in C.CHANGELOG
    )
    year, today = time.gmtime().tm_year, time.strftime("%Y-%m-%d", time.gmtime())
    cite = t["cite_text"].format(
        YEAR=year, DATE=today, URL=f"{base}/api/v1/matrices/POP105A"
    )

    return f"""
<div class="layout"><aside class="toc">{toc_html}</aside><article>
<div class="hero"><h1>{e(t['h1'])}</h1>
<p class="lead">{t['lead']}</p>
<div class="base"><span class="muted small">{e(t['base_label'])}</span><code>{e(base)}</code>
<a class="btn small" href="/docs/reference">{e(t['btn_ref'])}</a>
<a class="btn small" href="/chat">{e(t['nav_chat'])}</a></div>
<div class="facts">
<div class="card static"><b>{e(t['fact_open_b'])}</b><span>{e(t['fact_open'])}</span></div>
<div class="card static"><b>{e(t['fact_langs_b'])}</b><span>{e(t['fact_langs'])}</span></div>
<div class="card static"><b>{e(t['fact_formats_b'])}</b><span>{e(t['fact_formats'])}</span></div>
<div class="card static"><b>{e(t['fact_client_b'])}</b><span>{e(t['fact_client'])}</span></div></div></div>

<div class="toolbar"><span class="muted small">{e(t['examples_in'])}</span>
<div class="tabs" role="tablist">{tabs}</div></div>

<section id="start"><h2>{e(t['toc_start'])}</h2>
{fill(t['start'], START_CODE=variants(C.RECIPES[2]['code'], base, lang), SAMPLE=plain_block(sample, 'language-json'))}</section>

<section id="access"><h2>{e(t['toc_access'])}</h2>{t['access']}{plain_block(t['access_code'])}
<div class="callout">{t['access_callout']}</div>
{t['access_2']}</section>

<section id="model"><h2>{e(t['toc_model'])}</h2>{t['model']}</section>

<section id="recipes"><h2>{e(t['toc_recipes'])}</h2>{t['recipes']}{recipes}</section>

<section id="catalogue"><h2>{e(t['toc_catalogue'])}</h2>{t['catalogue']}
<input class="filter" id="dsfilter" type="search" placeholder="{e(t['filter_placeholder'])}" aria-label="{e(t['filter_label'])}">
{cat_html}</section>

<section id="reference"><h2>{e(t['toc_reference'])}</h2>{t['reference']}{ref_html}</section>

<section id="errors"><h2>{e(t['toc_errors'])}</h2>{t['errors']}{err_html}
<h3>{e(t['h_formats'])}</h3>{t['formats']}<h3>{e(t['h_caching'])}</h3>{t['caching']}
<h3>{e(t['h_web'])}</h3>{t['web']}</section>

<section id="cite"><h2>{e(t['toc_cite'])}</h2>{t['cite']}{plain_block(cite, 'nohighlight')}
<p class="muted small">{e(t['cite_note'])}</p>
{fill(t['cite_software'], GITHUB=GITHUB, ROEM=ROEM, INSSE=INSSE_TERMS)}</section>

<section id="history"><h2>{e(t['toc_history'])}</h2>
<div class="card tablecard"><div class="scroll"><table><tbody>{changes}</tbody></table></div></div>
<p class="note">{fill(t['history_note'], VERSION=e(C.VERSION))}</p></section>
</article></div>"""


def accepted(request: Request) -> str:
    best, best_q = "en", 0.0
    for i, part in enumerate(request.headers.get("accept-language", "").split(",")):
        bits = part.strip().split(";")
        code = bits[0].strip().lower()[:2]
        q = 1.0
        for b in bits[1:]:
            if b.strip().startswith("q="):
                try:
                    q = float(b.strip()[2:])
                except ValueError:
                    q = 0.0
        if code in I.LANGS and q - i * 1e-6 > best_q:
            best, best_q = code, q - i * 1e-6
    return best


def guide(request: Request, lang: str) -> HTMLResponse:
    base = base_url(request)
    t = I.UI[lang]
    body = render(base, catalogue_rows(), sample_answer(), lang)
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    root = request.scope.get("root_path", "")
    alt = "".join(
        f'<link rel="alternate" hreflang="{c}" href="https://{e(host)}{root}{page_path(c)}">'
        for c in I.LANGS
    )
    alt += f'<link rel="alternate" hreflang="x-default" href="https://{e(host)}{root}/docs">'
    head = f'{alt}<link rel="stylesheet" href="{HLJS}/styles/github-dark.min.css">'
    strings = {k: t[k] for k in ("copy", "copied", "key_invalid", "title_with_key", "title_no_key")}
    scripts = (
        f'<script src="{HLJS}/highlight.min.js"></script>'
        f'<script src="{HLJS}/languages/r.min.js"></script>'
        f'<script>window.INSSE_T = {json.dumps(strings, ensure_ascii=False)};</script>'
        f'<script>{SORT_JS}</script><script>{DOCS_JS}</script>'
    )
    return shell(t["html_title"], body, lang=lang, guide=page_path(lang), extra_head=head, scripts=scripts)


@router.get("/docs", response_class=HTMLResponse)
def docs_root(request: Request):
    lang = accepted(request)
    if lang != "en":
        return RedirectResponse(page_path(lang), status_code=302, headers={"Vary": "Accept-Language"})
    resp = guide(request, "en")
    resp.headers["Vary"] = "Accept-Language"
    return resp


@router.get("/docs/", include_in_schema=False)
def docs_slash():
    return RedirectResponse("/docs", status_code=308)


@router.get("/docs/en", response_class=HTMLResponse)
def docs_en(request: Request):
    return guide(request, "en")


@router.get("/docs/ro", response_class=HTMLResponse)
def docs_ro(request: Request):
    return guide(request, "ro")


@router.get("/docs/hu", response_class=HTMLResponse)
def docs_hu(request: Request):
    return guide(request, "hu")


@router.get("/docs/reference", response_class=HTMLResponse)
def reference(request: Request):
    schema_url = request.scope.get("root_path", "") + "/openapi.json"
    lang = accepted(request)
    t = I.UI[lang]
    body = (
        f'<p class="muted small" style="max-width:900px">Every endpoint with its parameters. '
        f'Explanations and examples are in the <a href="{page_path(lang)}">guide</a> '
        f'(English, Română, Magyar).</p><div id="swagger-ui"></div>'
    )
    head = (
        f'<link rel="stylesheet" href="{SWAGGER}/swagger-ui.css"><style>'
        f"#swagger-ui {{ background:#F6F6F6; border-radius:20px; padding:4px 8px 20px; color:#06090D }}"
        f"#swagger-ui .topbar {{ display:none }} #swagger-ui .info {{ margin:24px 0 }}</style>"
    )
    scripts = (
        f'<script src="{SWAGGER}/swagger-ui-bundle.js"></script><script>'
        f"SwaggerUIBundle({{ url: {json.dumps(schema_url)}, dom_id: '#swagger-ui', deepLinking: true, "
        f"docExpansion: 'list', defaultModelsExpandDepth: -1, tryItOutEnabled: true, "
        f"displayRequestDuration: true }});</script>"
    )
    return shell(t["nav_ref"], body, lang=lang, guide=page_path(lang), extra_head=head, scripts=scripts)


def attach_openapi(app) -> None:
    """Replace FastAPI's default schema with tagged servers + description."""

    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title="insseption API",
            version=__version__,
            routes=app.routes,
            description=(
                "JSON API tunnel for Romania INSSE TEMPO-Online. "
                "Guide with examples: `/docs`. Interactive reference: `/docs/reference`."
            ),
        )
        schema["servers"] = [{"url": PUBLIC_BASE}]
        schema["tags"] = [
            {"name": "open", "description": "Public JSON endpoints (no API key)."},
            {"name": "translate", "description": "Optional OpenRouter-backed label translation."},
        ]
        app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = custom_openapi  # type: ignore[method-assign]


@router.get("/openapi.json", include_in_schema=False)
def openapi_json(request: Request):
    app = request.app
    return JSONResponse(app.openapi())
