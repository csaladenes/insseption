# insseption

JSON API + Python client for [INSSE TEMPO-Online](http://statistici.insse.ro:8077/tempo-online/)
(Romania’s National Institute of Statistics).

- **HTTP JSON API** — open `/api/v1/...` in a browser; responses are indented `application/json`
- **Python package** — `from insseption import Client`
- **UI** — chat-first front page at `/` (Ask TEMPO agent); JSON discovery at `/api`

Production target: **https://insse.csaladen.es** (ROEM AWS / Traefik)

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
| GET | `/` | Service catalog (JSON) |
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

## Deploy (ROEM AWS Traefik stack)

Integrated into the existing `covid19-romania` compose (same pattern as `fastapi`):

- Host path: `/home/ec2-user/covid19-romania/insseption/`
- Service: `insseption` in `docker-compose.yml`
- Traefik: `Host:insse.csaladen.es` → `:8787`
- Networks: `web` + `internal`

```bash
# on ROEM
cd /home/ec2-user/covid19-romania
# edit/sync ./insseption (rsync --exclude .env) and ensure ./insseption/.env (OPENROUTER_API_KEY). Guide: https://insse.csaladen.es/docs
docker-compose up -d --build --no-deps insseption
curl -sS https://insse.csaladen.es/api/v1/health
```

## Floating chat agent (separate container)

GEM-style NL agent in `./agent` (OpenRouter → TEMPO via the JSON API). The agent
container stays on the internal Docker network; the API reverse-proxies `/agent/*`:

| URL | Purpose |
|-----|---------|
| https://insse.csaladen.es/index.html | UI + bottom-right chat FAB |
| https://insse.csaladen.es/agent/health | Agent health |
| `POST` https://insse.csaladen.es/agent/api/query | `{ "query": "...", "generate_chart": true }` |

```bash
# on ROEM (after syncing ./insseption/agent and compose service)
docker-compose up -d --build --no-deps insseption insseption-agent
curl -sS https://insse.csaladen.es/agent/health
```


## Host smoke harness

```bash
# API + docs cite + chat.js + agent against production (or set INSSEPTION_HOST)
python3 scripts/harness.py
# lighter API-only check:
INSSEPTION_BASE=https://insse.csaladen.es/api/v1 python3 scripts/smoke.py
```

## License

**MIT** — © Dénes Csala ([GitHub](https://github.com/csaladenes/insseption)).
Hosted on [ROEM](https://econ.ubbcluj.ro/roem) (AWS / Traefik).
Data remains subject to [INSSE](https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse) reuse terms.
