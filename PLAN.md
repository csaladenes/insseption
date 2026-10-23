# insseption — status

Shipped:

- JSON API + Python client (`pip install insseption`) for INSSE TEMPO-Online
- Production: https://insse.csaladen.es — chat UI at `/`, API at `/api/v1`, docs at `/docs`
- Separate `insseption-agent` container (OpenRouter → TEMPO), proxied under `/agent/*`
- Host smoke: `python3 scripts/harness.py`

Default LLM: `deepseek/deepseek-v4.1-flash` (override with `LLM_MODEL` / `OPENROUTER_MODEL`).
