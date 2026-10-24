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

The two services deploy differently:

| Change in | How it reaches the container | After rsync |
|-----------|------------------------------|-------------|
| `api/insseption/**` | baked into the `insseption` image | `docker-compose build insseption && docker-compose up -d insseption` |
| `web/**` | bind-mounted read-only | nothing (static files) |
| `agent/src/**`, `agent/config/**` | bind-mounted | `docker-compose restart insseption-agent` |
| `agent/eval`, `scripts/eval_agent.py` | not mounted | copy into the agent container (`docker exec -i … sh -c 'cat > /app/…'`) |

An rsynced API fix without a rebuild runs the old code with no error.

Offline tests (canned TEMPO payloads, no network):

```bash
uv run --no-project --with pytest python -m pytest agent/tests -q
uv run --no-project --with pytest --with cachetools --with httpx python -m pytest api/tests -q
```

Agent eval (35 graded cases, LLM judge) runs inside the agent container:

```bash
docker exec insseption-agent python scripts/eval_agent.py \
  --base http://localhost:8000 --concurrency 3 --out /tmp/eval.json
```

Guide: https://insse.csaladen.es/docs


## Ask TEMPO UI notes

- Header attribution: **“Date de la / Data from …”** the National Institute of Statistics (never brand as official INS without that prefix).
- Home example pills: random sample from `web/examples.json` (large RO/EN/HU pools); click submits the question.
- County maps: Mapbox GL choropleth with **5 quintiles**, green → yellow → red (`#239f69` → `#f5d232` → `#850237`), caption + legend **above** the map.
- Agent follow-ups (“Ce propun” / “You could also ask” / “Ajánlom”) render as **clickable buttons** that submit the chat.
- Session context ~30 minutes; dual OpenRouter tiers (preflight / execute). Docs are trilingual at `/docs/{en|ro|hu}` and `/docs/{lang}/reference`.

## Chat agent (separate container)

NL agent in `./agent` (OpenRouter → TEMPO via the JSON API). The agent
container stays on the internal Docker network; the API reverse-proxies `/agent/*`.
The chat UI **is** the site front page at `/`.

| URL | Purpose |
|-----|---------|
| https://insse.csaladen.es/ | Ask TEMPO agent (landing) |
| https://insse.csaladen.es/docs | Guide |
| https://insse.csaladen.es/chat | Redirect → `/` |
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
