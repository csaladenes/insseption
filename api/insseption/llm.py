from __future__ import annotations

import hashlib
import json
from typing import Any

import httpx
from cachetools import TTLCache

from . import config
from .errors import ApiError

_translate_cache: TTLCache = TTLCache(maxsize=2048, ttl=7 * 24 * 3600)


def translate_enabled() -> bool:
    return bool(config.OPENROUTER_API_KEY)


async def translate_texts(texts: list[str], target: str) -> list[str]:
    if not translate_enabled():
        raise ApiError(
            "translate_disabled",
            "OPENROUTER_API_KEY not configured",
            status=503,
        )
    if len(texts) > 50:
        raise ApiError("too_many_texts", "Max 50 texts per call", status=422)
    total_chars = sum(len(t) for t in texts)
    if total_chars > 4000:
        raise ApiError("texts_too_long", "Max 4000 characters per call", status=422)

    results: list[str | None] = [None] * len(texts)
    missing: list[tuple[int, str]] = []
    for i, text in enumerate(texts):
        key = hashlib.sha256(f"{target}\0{text}".encode()).hexdigest()
        try:
            results[i] = _translate_cache[key]
        except KeyError:
            missing.append((i, text))

    if not missing:
        return [r or "" for r in results]

    payload_texts = [t for _, t in missing]
    system = (
        "Translate Romanian or English statistical labels into the target language. "
        "Keep numbers, units, codes, and abbreviations unchanged. "
        "Return ONLY a JSON array of strings, same length and order as the input."
    )
    user = json.dumps({"target": target, "texts": payload_texts}, ensure_ascii=False)
    body = {
        "model": config.OPENROUTER_MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://insseption.netlify.app",
        "X-Title": "insseption",
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{config.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=body,
            )
    except httpx.HTTPError as exc:
        raise ApiError("llm_network", str(exc), status=502) from exc

    if resp.status_code >= 400:
        detail = resp.text[:200]
        try:
            detail = (resp.json().get("error") or {}).get("message") or detail
        except Exception:
            pass
        raise ApiError(
            "llm_http",
            f"OpenRouter HTTP {resp.status_code}: {detail}",
            status=502,
            upstream_status=resp.status_code,
        )

    data: dict[str, Any] = resp.json()
    content = (
        ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    ).strip()
    if content.startswith("```"):
        lines = content.splitlines()
        # drop first fence line and trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        content = "\n".join(lines).strip()
        if content.startswith("json"):
            content = content[4:].lstrip()
    # tolerate leading prose: take first [...] array
    if not content.startswith("["):
        start = content.find("[")
        end = content.rfind("]")
        if start >= 0 and end > start:
            content = content[start : end + 1]
    try:
        translated = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ApiError(
            "llm_parse",
            f"Model did not return JSON array: {content[:120]!r}",
            status=502,
        ) from exc
    if not isinstance(translated, list) or len(translated) != len(payload_texts):
        raise ApiError(
            "llm_shape",
            "Model returned wrong number of translations",
            status=502,
        )

    for (i, original), out in zip(missing, translated):
        text_out = str(out)
        key = hashlib.sha256(f"{target}\0{original}".encode()).hexdigest()
        _translate_cache[key] = text_out
        results[i] = text_out

    return [r or "" for r in results]
