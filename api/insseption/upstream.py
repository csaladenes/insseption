from __future__ import annotations

import asyncio
import hashlib
import json
import time
from typing import Any

import httpx
from cachetools import TTLCache

from . import config
from .errors import ApiError

_client: httpx.AsyncClient | None = None
_sem = asyncio.Semaphore(4)
_fail_streak = 0
_breaker_until = 0.0

_cache_context: TTLCache = TTLCache(maxsize=256, ttl=24 * 3600)
_cache_meta: TTLCache = TTLCache(maxsize=512, ttl=24 * 3600)
_cache_news: TTLCache = TTLCache(maxsize=4, ttl=3600)
_cache_query: TTLCache = TTLCache(maxsize=256, ttl=6 * 3600)
_inflight: dict[str, asyncio.Future] = {}


def _check_breaker() -> None:
    global _fail_streak
    if time.time() < _breaker_until:
        raise ApiError(
            "upstream_unavailable",
            "TEMPO-Online temporarily unavailable (circuit open).",
            status=503,
        )


def _record_success() -> None:
    global _fail_streak
    _fail_streak = 0


def _record_failure() -> None:
    global _fail_streak, _breaker_until
    _fail_streak += 1
    if _fail_streak >= 5:
        _breaker_until = time.time() + 30
        _fail_streak = 0


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=config.UPSTREAM_BASE,
            headers={
                "User-Agent": config.USER_AGENT,
                "Accept": "application/json, text/html, */*",
                "Referer": "http://statistici.insse.ro:8077/tempo-online/",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=httpx.Timeout(connect=3.0, read=20.0, write=10.0, pool=5.0),
            follow_redirects=True,
        )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    json_body: Any | None = None,
    expect_json: bool = True,
) -> Any:
    _check_breaker()
    client = await get_client()
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            async with _sem:
                resp = await client.request(
                    method, path, params=params, json=json_body
                )
            if resp.status_code >= 400:
                _record_failure()
                raise ApiError(
                    "upstream_http",
                    f"Upstream returned HTTP {resp.status_code}",
                    status=502,
                    upstream_status=resp.status_code,
                )
            _record_success()
            if expect_json:
                try:
                    return resp.json()
                except json.JSONDecodeError as exc:
                    raise ApiError(
                        "upstream_json",
                        "Upstream returned non-JSON body",
                        status=502,
                    ) from exc
            return resp.text
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_exc = exc
            _record_failure()
            if method.upper() != "GET" or attempt == 1:
                raise ApiError(
                    "upstream_network",
                    f"Upstream network error: {exc}",
                    status=502,
                ) from exc
            await asyncio.sleep(0.3)
    raise ApiError("upstream_network", str(last_exc), status=502)


def _cache_get(cache: TTLCache, key: str) -> Any | None:
    try:
        return cache[key]
    except KeyError:
        return None


async def _singleflight(key: str, coro_factory):
    existing = _inflight.get(key)
    if existing is not None:
        return await asyncio.shield(existing)
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    _inflight[key] = fut
    try:
        result = await coro_factory()
        fut.set_result(result)
        return result
    except Exception as exc:
        fut.set_exception(exc)
        raise
    finally:
        _inflight.pop(key, None)


async def fetch_context(code: str | None = None, lang: str = "ro") -> Any:
    path = "/context/" if not code else f"/context/{code}"
    key = f"ctx:{lang}:{code or ''}"
    cached = _cache_get(_cache_context, key)
    if cached is not None:
        return cached

    async def load():
        data = await _request("GET", path, params={"lang": lang})
        _cache_context[key] = data
        return data

    return await _singleflight(key, load)


async def fetch_matrix_meta(code: str, lang: str = "ro") -> Any:
    code = code.upper()
    key = f"meta:{lang}:{code}"
    cached = _cache_get(_cache_meta, key)
    if cached is not None:
        return cached

    async def load():
        data = await _request(
            "GET", f"/matrix/{code}", params={"lang": lang}
        )
        _cache_meta[key] = data
        return data

    return await _singleflight(key, load)


async def fetch_dataset(code: str, body: dict[str, Any]) -> Any:
    code = code.upper()
    canon = json.dumps(body, sort_keys=True, ensure_ascii=False)
    key = "q:" + hashlib.sha256(canon.encode()).hexdigest()
    cached = _cache_get(_cache_query, key)
    if cached is not None:
        return cached

    async def load():
        data = await _request(
            "POST", f"/matrix/dataSet/{code}", json_body=body
        )
        _cache_query[key] = data
        return data

    return await _singleflight(key, load)


async def fetch_news_html() -> str:
    key = "news"
    cached = _cache_get(_cache_news, key)
    if cached is not None:
        return cached

    async def load():
        text = await _request("GET", "/news/", expect_json=False)
        _cache_news[key] = text
        return text

    return await _singleflight(key, load)


async def ping_upstream() -> bool:
    try:
        await _request("GET", "/context/", params={"lang": "ro"})
        return True
    except ApiError:
        return False
