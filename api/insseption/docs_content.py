"""Guide content: recipes, reference, errors, changelog (English source)."""

from __future__ import annotations

VERSION = "0.1.0, 23 October 2026"

LANGS = [
    ("curl", "curl"),
    ("python", "Python"),
    ("r", "R"),
    ("js", "JavaScript"),
    ("excel", "Excel / Sheets"),
]

RECIPES = [
    {
        "id": "browse",
        "title": "Browse the TEMPO tree",
        "lead": "Find datasets and codes: list the root domains (social, economic, …), then open a"
                "branch. <code>lang=en</code> or <code>lang=ro</code> selects the upstream language.",
        "url": "/api/v1/context?lang=en",
        "code": {
            "curl": 'curl -sS "{BASE}/api/v1/context?lang=en" | jq .\n'
                    'curl -sS "{BASE}/api/v1/context/1?lang=en" | jq .',
            "python": '''from insseption import Client

with Client("{BASE}/api/v1") as c:
    roots = c.context(lang="en")["nodes"]
    print([n["name"] for n in roots])
    kids = c.context("1", lang="en")["nodes"]
    print([n["code"] for n in kids[:5]])''',
            "r": '''library(httr2)

roots <- request("{BASE}/api/v1/context") |>
  req_url_query(lang = "en") |>
  req_perform() |>
  resp_body_json()
vapply(roots$nodes, \\(n) n$name, character(1))''',
            "js": '''const roots = await (await fetch("{BASE}/api/v1/context?lang=en")).json();
console.log(roots.nodes.map(n => n.name));
const kids = await (await fetch("{BASE}/api/v1/context/1?lang=en")).json();
console.log(kids.nodes.slice(0, 5));''',
            "excel": '''// Power Query > Blank Query > Advanced Editor
let
    Source = Json.Document(Web.Contents("{BASE}/api/v1/context", [Query=[lang="en"]])),
    Nodes = Table.FromRecords(Source[nodes])
in
    Nodes''',
        },
    },
    {
        "id": "meta",
        "title": "Inspect a matrix and its dimensions",
        "lead": "Before you query, inspect the matrix: dimension labels and the <code>nom_item_id</code>"
                "options you will pass in <code>selections</code> (e.g. <code>POP105A</code>).",
        "url": "/api/v1/matrices/POP105A?lang=en",
        "code": {
            "curl": 'curl -sS "{BASE}/api/v1/matrices/POP105A?lang=en" | jq \'.dimensions[] | {dim_code,label}\'',
            "python": '''from insseption import Client

with Client("{BASE}/api/v1") as c:
    m = c.matrix("POP105A", lang="en")
    print(m["name"])
    for d in m["dimensions"]:
        print(d["dim_code"], d["label"], "options=", len(d["options"]))''',
            "r": '''library(httr2)

m <- request("{BASE}/api/v1/matrices/POP105A") |>
  req_url_query(lang = "en") |>
  req_perform() |>
  resp_body_json()
cat(m$name, "\\n")
lapply(m$dimensions, \\(d) c(d$dim_code, d$label, length(d$options)))''',
            "js": '''const m = await (await fetch("{BASE}/api/v1/matrices/POP105A?lang=en")).json();
console.log(m.name);
console.table(m.dimensions.map(d => ({ code: d.dim_code, label: d.label, n: d.options.length })));''',
            "excel": '''let
    Source = Json.Document(Web.Contents("{BASE}/api/v1/matrices/POP105A", [Query=[lang="en"]])),
    Dims = Table.FromRecords(Source[dimensions])
in
    Dims''',
        },
    },
    {
        "id": "query-get",
        "title": "Quick query (browser-friendly GET)",
        "lead": "For a dashboard tile or a quick check: with no body the API picks sensible defaults"
                "(totals / latest year). Open the URL in a browser — the answer is indented JSON.",
        "url": "/api/v1/matrices/POP105A/query?lang=en",
        "code": {
            "curl": 'curl -sS "{BASE}/api/v1/matrices/POP105A/query?lang=en" | jq \'{columns,row_count}\'',
            "python": '''from insseption import Client

with Client("{BASE}/api/v1") as c:
    data = c.query("POP105A", lang="en")  # empty selections → defaults
    print(data["columns"])
    print(data["row_count"], "rows")
    print(data["rows"][:3])''',
            "r": '''library(httr2)

data <- request("{BASE}/api/v1/matrices/POP105A/query") |>
  req_url_query(lang = "en") |>
  req_perform() |>
  resp_body_json()
str(data$columns)
length(data$rows)''',
            "js": '''const data = await (await fetch("{BASE}/api/v1/matrices/POP105A/query?lang=en")).json();
console.log(data.columns, data.row_count);
console.table(data.rows.slice(0, 5));''',
            "excel": '''let
    Source = Json.Document(Web.Contents("{BASE}/api/v1/matrices/POP105A/query", [Query=[lang="en"]])),
    Rows = Table.FromRows(Source[rows], Source[columns])
in
    Rows''',
        },
    },
    {
        "id": "query-post",
        "title": "Query with explicit dimension selections",
        "lead": "Pick series with dimension filters: <code>selections</code> maps each dimension code to"
                "a list of <code>nom_item_id</code> values from the matrix metadata. Use POST when the"
                "slice is larger than a query string comfortably holds.",
        "url": "/api/v1/matrices/POP105A/query",
        "code": {
            "curl": '''curl -sS -X POST "{BASE}/api/v1/matrices/POP105A/query" \\
  -H "content-type: application/json" \\
  -d '{"lang":"en","selections":{"1":[1],"2":[105],"3":[108],"4":[112],"5":[4931],"6":[9685]}}' \\
  | jq '{row_count, rows}' ''',
            "python": '''from insseption import Client

# ids come from c.matrix(...)["dimensions"][*]["options"][*]["nom_item_id"]
sel = {
    "1": [1],       # age: Total
    "2": [105],     # sex: Total
    "3": [108],     # area: Total
    "4": [112],     # geo: TOTAL
    "5": [4931],    # year: 2026
    "6": [9685],    # unit
}
with Client("{BASE}/api/v1") as c:
    data = c.query("POP105A", selections=sel, lang="en")
    print(data["rows"])''',
            "r": '''library(httr2)

body <- list(
  lang = "en",
  selections = list(`1` = list(1), `2` = list(105), `3` = list(108),
                    `4` = list(112), `5` = list(4931), `6` = list(9685))
)
data <- request("{BASE}/api/v1/matrices/POP105A/query") |>
  req_body_json(body) |>
  req_perform() |>
  resp_body_json()
data$rows''',
            "js": '''const body = {
  lang: "en",
  selections: { "1": [1], "2": [105], "3": [108], "4": [112], "5": [4931], "6": [9685] },
};
const data = await (await fetch("{BASE}/api/v1/matrices/POP105A/query", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify(body),
})).json();
console.log(data.rows);''',
            "excel": '''// Prefer GET defaults, or load CSV (next recipe) into Power Query.
// POST bodies are awkward in Excel — use Python/R/curl for selections.''',
        },
    },
    {
        "id": "csv",
        "title": "Download CSV for analysis",
        "lead": "A whole table, ready for pandas or Excel: add <code>?format=csv</code> "
                "(POST with the same <code>selections</code> body). UTF-8 CSV with a header row "
                "and a dot as the decimal separator.",
        "url": "/api/v1/matrices/POP105A/query?format=csv",
        "code": {
            "curl": '''curl -sS -X POST "{BASE}/api/v1/matrices/POP105A/query?format=csv" \\
  -H "content-type: application/json" \\
  -d '{"lang":"en","selections":{}}' -o pop105a.csv''',
            "python": '''import io
import pandas as pd
import requests

r = requests.post(
    "{BASE}/api/v1/matrices/POP105A/query",
    params={"format": "csv"},
    json={"lang": "en", "selections": {}},
    timeout=60,
)
r.raise_for_status()
df = pd.read_csv(io.StringIO(r.text))
print(df.head())''',
            "r": '''library(httr2)
library(readr)

resp <- request("{BASE}/api/v1/matrices/POP105A/query") |>
  req_url_query(format = "csv") |>
  req_body_json(list(lang = "en", selections = setNames(list(), character(0)))) |>
  req_perform()
df <- read_csv(resp_body_string(resp), show_col_types = FALSE)
head(df)''',
            "js": '''const r = await fetch("{BASE}/api/v1/matrices/POP105A/query?format=csv", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ lang: "en", selections: {} }),
});
const csv = await r.text();
console.log(csv.split("\\n").slice(0, 5).join("\\n"));''',
            "excel": '''// Save CSV from curl/Python, then Data > From Text/CSV.
// Or use the GET JSON recipe and convert in Power Query.''',
        },
    },
    {
        "id": "news",
        "title": "See what INSSE updated recently",
        "lead": "Parsed from TEMPO’s news table: matrix codes, dates and domains — useful for refresh jobs.",
        "url": "/api/v1/news",
        "code": {
            "curl": 'curl -sS "{BASE}/api/v1/news" | jq \'.items[:5]\'',
            "python": '''from insseption import Client

with Client("{BASE}/api/v1") as c:
    news = c.news()
    for item in news["items"][:5]:
        print(item["date"], item["code"], item.get("domain"))''',
            "r": '''library(httr2)
news <- request("{BASE}/api/v1/news") |> req_perform() |> resp_body_json()
head(do.call(rbind, lapply(news$items[1:5], as.data.frame)), 5)''',
            "js": '''const news = await (await fetch("{BASE}/api/v1/news")).json();
console.table(news.items.slice(0, 8).map(i => ({ date: i.date, code: i.code, domain: i.domain })));''',
            "excel": '''let
    Source = Json.Document(Web.Contents("{BASE}/api/v1/news")),
    Items = Table.FromRecords(Source[items])
in
    Items''',
        },
    },
    {
        "id": "package",
        "title": "Use the Python package",
        "lead": "The same calls without hand-written URLs: <code>pip install insseption</code> (or"
                "install from this repo). The <code>Client</code> mirrors every HTTP route and returns"
                "parsed JSON.",
        "url": "/api/v1/meta",
        "code": {
            "curl": '# the package wraps these HTTP calls\ncurl -sS "{BASE}/api/v1/meta" | jq .',
            "python": '''# pip install .   (from the repo)  or: pip install insseption
from insseption import Client

c = Client("{BASE}/api/v1")
print(c.health())
print(c.query("POP105A", lang="en")["row_count"])
c.close()''',
            "r": '''# R users: httr2 against the same URLs (see other recipes).
# There is also CRAN TEMPO for bulk CSV dumps of the whole warehouse.''',
            "js": '''// fetch against {BASE}/api/v1 — or use the page UI at {BASE}/''',
            "excel": '''// Not applicable — use CSV downloads from the query endpoint.''',
        },
    },
]

REFERENCE = [
    {
        "path": "/api/v1/health",
        "method": "GET",
        "access": "open",
        "summary": "Liveness and upstream reachability",
        "returns": "JSON: ok, version, upstream_ok, attribution",
        "params": [],
        "example": "/api/v1/health",
    },
    {
        "path": "/api/v1/meta",
        "method": "GET",
        "access": "open",
        "summary": "Service metadata",
        "returns": "JSON: version, languages, translate_enabled, existing_solutions",
        "params": [],
        "example": "/api/v1/meta",
    },
    {
        "path": "/api/v1/context",
        "method": "GET",
        "access": "open",
        "summary": "Root TEMPO domains",
        "returns": "JSON: nodes[{code,name,level,url}]",
        "params": [("lang", "query", "ro|en — upstream label language")],
        "example": "/api/v1/context?lang=en",
    },
    {
        "path": "/api/v1/context/{code}",
        "method": "GET",
        "access": "open",
        "summary": "Children of a context node",
        "returns": "JSON: nodes (folders or matrix leaves)",
        "params": [("code", "path", "TEMPO context code, e.g. 1 or 1010"),
                   ("lang", "query", "ro|en")],
        "example": "/api/v1/context/1010?lang=en",
    },
    {
        "path": "/api/v1/matrices/{code}",
        "method": "GET",
        "access": "open",
        "summary": "Matrix metadata and dimension options",
        "returns": "JSON: name, dimensions, definition, details",
        "params": [("code", "path", "Matrix code, e.g. POP105A"),
                   ("lang", "query", "ro|en")],
        "example": "/api/v1/matrices/POP105A?lang=en",
    },
    {
        "path": "/api/v1/matrices/{code}/query",
        "method": "GET",
        "access": "open",
        "summary": "Query with default selections",
        "returns": "JSON: columns, rows, row_count (or CSV if format=csv)",
        "params": [("lang", "query", "ro|en"),
                   ("format", "query", "json|csv")],
        "example": "/api/v1/matrices/POP105A/query?lang=en",
    },
    {
        "path": "/api/v1/matrices/{code}/query",
        "method": "POST",
        "access": "open",
        "summary": "Query with JSON body",
        "returns": "JSON rows or CSV",
        "params": [("body.lang", "body", "ro|en"),
                   ("body.selections", "body", "map dim_code → [nom_item_id,…]"),
                   ("format", "query", "json|csv")],
        "example": "/api/v1/matrices/POP105A/query",
    },
    {
        "path": "/api/v1/news",
        "method": "GET",
        "access": "open",
        "summary": "Recent TEMPO matrix updates",
        "returns": "JSON: items[{code,date,domain,…}], count",
        "params": [],
        "example": "/api/v1/news",
    },
    {
        "path": "/api/v1/translate",
        "method": "POST",
        "access": "open",
        "summary": "Translate label strings (OpenRouter)",
        "returns": "JSON: {target, texts[]}",
        "params": [("body.texts", "body", "1–50 strings"),
                   ("body.target", "body", "hu|ro|en")],
        "example": "/api/v1/translate",
    },
]

ERRORS = [
    (404, "Not found", "Unknown matrix code or path."),
    (422, "Unprocessable", "Bad code, empty dimension, unknown nom_item_id, or selection product too large."),
    (502, "Bad gateway", "TEMPO-Online upstream error or non-JSON response."),
    (503, "Unavailable", "Upstream circuit open, or translate disabled (no OpenRouter key)."),
]

CHANGELOG = [
    ("2026-10-23", "v0.1.0 — JSON API tunnel for TEMPO-Online, Python client, ROEM Traefik deploy, trilingual guide."),
]
