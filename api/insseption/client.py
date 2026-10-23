"""Synchronous Python client for the insseption JSON API."""

from __future__ import annotations

from typing import Any, Mapping, Sequence
from urllib.parse import quote

import httpx

DEFAULT_BASE_URL = "https://insse.csaladen.es/api/v1"


class InsseptionError(RuntimeError):
    """Raised when the API returns a non-2xx or an error payload."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class Client:
    """Thin httpx wrapper around `/api/v1`.

    Example::

        from insseption import Client

        c = Client()  # or Client("http://127.0.0.1:8787/api/v1")
        print(c.health())
        meta = c.matrix("POP105A", lang="en")
        data = c.query("POP105A", lang="en")  # defaults = totals / latest year
        print(data["row_count"], data["columns"])
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = 60.0,
        headers: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=timeout,
            headers={
                "Accept": "application/json",
                "User-Agent": "insseption-python/0.1.0",
                **(dict(headers) if headers else {}),
            },
            transport=transport,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        resp = self._client.request(method, path, params=params, json=json_body)
        ctype = resp.headers.get("content-type", "")
        data: Any
        if "json" in ctype or resp.text[:1] in "{[":
            try:
                data = resp.json()
            except ValueError as exc:
                raise InsseptionError(
                    "Response was not valid JSON",
                    status_code=resp.status_code,
                    payload=resp.text[:500],
                ) from exc
        else:
            data = resp.text

        if resp.status_code >= 400:
            if isinstance(data, dict) and isinstance(data.get("error"), dict):
                msg = data["error"].get("message") or str(data["error"])
            else:
                msg = f"HTTP {resp.status_code}"
            raise InsseptionError(msg, status_code=resp.status_code, payload=data)
        return data

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health")

    def meta(self) -> dict[str, Any]:
        return self._request("GET", "/meta")

    def context(self, code: str | None = None, *, lang: str = "ro") -> dict[str, Any]:
        if code is None:
            return self._request("GET", "/context", params={"lang": lang})
        return self._request(
            "GET", f"/context/{quote(str(code), safe='')}", params={"lang": lang}
        )

    def matrix(self, code: str, *, lang: str = "ro") -> dict[str, Any]:
        return self._request(
            "GET",
            f"/matrices/{quote(str(code), safe='')}",
            params={"lang": lang},
        )

    def query(
        self,
        code: str,
        selections: Mapping[str, Sequence[int]] | None = None,
        *,
        lang: str = "ro",
        format: str = "json",
    ) -> Any:
        """Query a matrix.

        ``selections`` maps dimension code (str) → list of ``nom_item_id`` ints.
        Empty / omitted selections use API defaults (totals / latest year).
        """
        body = {
            "lang": lang,
            "selections": {
                str(k): [int(x) for x in v]
                for k, v in (selections or {}).items()
            },
        }
        return self._request(
            "POST",
            f"/matrices/{quote(str(code), safe='')}/query",
            params={"format": format},
            json_body=body,
        )

    def news(self) -> dict[str, Any]:
        return self._request("GET", "/news")

    def translate(self, texts: Sequence[str], target: str = "hu") -> list[str]:
        data = self._request(
            "POST",
            "/translate",
            json_body={"texts": list(texts), "target": target},
        )
        return list(data.get("texts") or [])


# Back-compat alias
InsseClient = Client
