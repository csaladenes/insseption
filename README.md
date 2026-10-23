# insseption

JSON API + Python client for [INSSE TEMPO-Online](http://statistici.insse.ro:8077/tempo-online/)
(Romania’s National Institute of Statistics).

- **HTTP JSON API** — open `/api/v1/...` in a browser; responses are indented `application/json`
- **Python package** — `from insseption import Client`
- **UI** — chat-first front page at `/` (Ask TEMPO agent); JSON discovery at `/api`

Production: **https://insse.csaladen.es**

[INSSE reuse terms](https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse)

## Python client

Published on **[PyPI](https://pypi.org/project/insseption/)**:

```bash
pip install insseption
```

From source / GitHub (optional):

```bash
pip install "git+https://github.com/csaladenes/insseption.git"
```

```python
from insseption import Client

with Client() as c:                       # https://insse.csaladen.es/api/v1
    print(c.health())
    print(c.context(lang="en")["nodes"][:3])
    meta = c.matrix("POP105A", lang="en")
    data = c.query("POP105A", lang="en")  # default totals / latest year
    print(data["columns"], data["row_count"])
```

Point at a local server:

```python
Client("http://127.0.0.1:8787/api/v1")
```

CLI:

```bash
insseption --base-url http://127.0.0.1:8787/api/v1 health
insseption --base-url http://127.0.0.1:8787/api/v1 query POP105A
```

## JSON API (`/api/v1`)

| Method | Path | Returns |
|--------|------|---------|
| GET | `/api` | Service catalog (JSON) |
| GET | `/api/v1` | Endpoint list |
| GET | `/api/v1/health` | `{ok, upstream_ok, ...}` |
| GET | `/api/v1/meta` | Service metadata |
| GET | `/api/v1/context?lang=en` | Domain tree roots |
| GET | `/api/v1/context/{code}` | Children |
| GET | `/api/v1/matrices/{code}` | Dimensions / options |
| GET | `/api/v1/matrices/{code}/query` | Rows (default selection) |
| POST | `/api/v1/matrices/{code}/query` | Rows (`{lang, selections}`) |
| GET | `/api/v1/news` | Recent updates |
| POST | `/api/v1/translate` | Label translation |

Interactive docs: `/docs` · OpenAPI: `/openapi.json`

Example in browser:

`https://insse.csaladen.es/api/v1/matrices/POP105A/query?lang=en`

POST body:

```json
{
  "lang": "en",
  "selections": { "5": [4931], "1": [1] }
}
```

## Run the API locally

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[server]"
uvicorn insseption.main:app --host 127.0.0.1 --port 8787
```

## Deploy (Docker / Traefik)

Example host layout (adjust to your stack):

- App path: `./insseption/` next to your compose file
- Service: `insseption` (+ optional `insseption-agent`)
- Traefik host rule: `insse.csaladen.es` → `:8787`
- Networks: public edge + internal

```bash
# on the host
# sync ./insseption (rsync --exclude .env) and ensure ./insseption/.env (OPENROUTER_API_KEY)
docker-compose up -d --build --no-deps insseption
curl -sS https://insse.csaladen.es/api/v1/health
```

Guide: https://insse.csaladen.es/docs

## Chat agent (separate container)

NL agent in `./agent` (OpenRouter → TEMPO via the JSON API). The agent
container stays on the internal Docker network; the API reverse-proxies `/agent/*`.
The chat UI **is** the site front page at `/`.

| URL | Purpose |
|-----|---------|
| https://insse.csaladen.es/ | Ask TEMPO (front page) |
| https://insse.csaladen.es/agent/health | Agent health |
| `POST` https://insse.csaladen.es/agent/api/query | `{ "query": "...", "generate_chart": true }` |

```bash
docker-compose up -d --build --no-deps insseption insseption-agent
curl -sS https://insse.csaladen.es/agent/health
```

## Host smoke harness

```bash
# API + docs + chat home + agent against production (or set INSSEPTION_HOST)
python3 scripts/harness.py
# lighter API-only check:
INSSEPTION_BASE=https://insse.csaladen.es/api/v1 python3 scripts/smoke.py
```

## License

**MIT** — © Dénes Csala ([GitHub](https://github.com/csaladenes/insseption)).
Data remains subject to [INSSE](https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse) reuse terms.
