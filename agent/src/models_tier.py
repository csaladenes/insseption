"""OpenRouter model tiers for the insseption agent.

Use the real model ids as named variables; env can override which tier is wired where.
"""

from __future__ import annotations

import os

# Actual OpenRouter model ids
MINIMAX_M3_1_FLASH = "minimax/minimax-m3.1-flash"
DEEPSEEK_V4_1_FLASH = "deepseek/deepseek-v4.1-flash"

# Tier roles
# - PREFLIGHT / mid: rewrite follow-ups, revise default TEMPO plan
# - EXECUTE / small: draft plan JSON + final HTML answer
MODEL_PREFLIGHT = os.getenv("LLM_MODEL_PREFLIGHT", MINIMAX_M3_1_FLASH)
MODEL_EXECUTE = os.getenv("LLM_MODEL_EXECUTE", DEEPSEEK_V4_1_FLASH)

# Back-compat aliases
MODEL_MID = MODEL_PREFLIGHT
MODEL_SMALL = MODEL_EXECUTE
