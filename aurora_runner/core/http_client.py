from __future__ import annotations

import time
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests


class HttpClient:
    def __init__(
        self,
        default_headers: Optional[Dict[str, str]] = None,
        proxy: Optional[Dict[str, str]] = None,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update(default_headers or {})
        self.proxy = proxy
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds

    def _request(
        self,
        method: str,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        cookies: Optional[Dict[str, str]] = None,
        data: Optional[str] = None,
        timeout: float = 20.0,
        allow_redirects: bool = True,
    ) -> requests.Response:
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    cookies=cookies,
                    data=data,
                    timeout=timeout,
                    allow_redirects=allow_redirects,
                    proxies=self.proxy,
                )
                return resp
            except requests.RequestException as exc:  # pragma: no cover
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_backoff_seconds * (2 ** attempt))
                else:
                    raise exc
        assert False, f"unreachable: {last_exc}"

    def get_domain(self, url: str) -> str:
        return urlparse(url).netloc.split(":")[0]

    def request(self, **kwargs) -> requests.Response:
        return self._request(**kwargs)

    def close(self) -> None:
        self.session.close()