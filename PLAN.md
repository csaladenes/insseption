# insseption plan (OR prewalk, 2026-10-23)

Architecture from Claude Sonnet 5.5 prewalk, adapted for **Netlify Python Functions + Mangum** so the dedicated OpenRouter key lives on the Netlify site (flavour-lab pattern). Fly.io remains a later escape hatch if serverless limits bite.

## Stack
- FastAPI + httpx + Mangum on Netlify Functions (`@netlify/plugin-python`)
- Static frontend in `web/` (no build step)
- Upstream: `http://statistici.insse.ro:8077/tempo-ins` (HTTP-only → our HTTPS tunnel)

## Endpoints (`/api/v1`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + upstream reachability |
| GET | `/meta` | Version, attribution, limits |
| GET | `/context` | Root hierarchy |
| GET | `/context/{code}` | Children |
| GET | `/matrices/{code}?lang=ro\|en` | Metadata |
| POST | `/matrices/{code}/query` | JSON rows via upstream `dataSet` |
| GET | `/news` | Parsed update feed |
| POST | `/translate` | OR-powered label translate (HU) |

Typed tunnel only — no open `/raw/*` proxy.

## Explicitly not v1
No DuckDB warehouse, SDMX, charts/maps, bulk mirror (see gov2-ro/tempo-ins-dump / ins.gov2.ro for that).

## Secrets
- Local: `~/.config/agent-secrets/openrouter-insseption.env` (limit $5, name `insseption`)
- Netlify env: `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`


## Deployed shape (2026-10-23)
- Frontend + JS tunnel: https://csaladenes-insseption.netlify.app
- Python FastAPI: G4 Docker `insseption-api` `:8787`
- OR key `insseption` ($5) in agent-secrets + Netlify env (rotated once after CLI echo)
- Tailscale Serve enable still pending for public Python funnel
