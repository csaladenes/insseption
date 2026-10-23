from __future__ import annotations

import os

VERSION = "0.1.1"
UPSTREAM_BASE = os.environ.get(
    "INSSEPTION_UPSTREAM", "http://statistici.insse.ro:8077/tempo-ins"
).rstrip("/")
MAX_CELLS = int(os.environ.get("INSSEPTION_MAX_CELLS", "20000"))
USER_AGENT = f"insseption/{VERSION} (+https://github.com/csaladenes/insseption)"
ATTRIBUTION = (
    "Sursa: Institutul Național de Statistică – TEMPO-Online. "
    "Unofficial mirror; no endorsement implied."
)
TERMS_URL = "https://insse.ro/cms/ro/content/reutilizarea-statisticilor-sse"
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.environ.get(
    "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
).rstrip("/")
OPENROUTER_MODEL = os.environ.get(
    "OPENROUTER_MODEL", "deepseek/deepseek-v4.1-flash"
)
MATRIX_CODE_RE = r"^[A-Za-z0-9_]{3,20}$"
