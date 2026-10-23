# insseption — status

Shipped:

- JSON API + Python client (`pip install insseption`) for INSSE TEMPO-Online
- Production: https://insse.csaladen.es
  - `/` — Ask TEMPO agent landing (ORI-style stage, RoEM theme)
  - `/chat` — redirects to `/`
  - `/docs` — trilingual guide · `/docs/reference` — Swagger
  - `/api/v1` — JSON API · `/agent/*` — NL agent (preflight → query → analyze → present)
- Skill: `insseption-agents` (internal pipeline + charts / county maps / CSV·PNG; steps hidden from users)
- Separate `insseption-agent` container (OpenRouter → TEMPO), proxied under `/agent/*`
- Host smoke: `python3 scripts/harness.py` (if present)

Default LLM: `deepseek/deepseek-v4.1-flash` (override with `LLM_MODEL` / `OPENROUTER_MODEL`).

Version: **0.1.1**
