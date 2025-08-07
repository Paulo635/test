from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Optional


class ProxyManager:
    def __init__(self, proxies: Optional[Iterable[str]] = None) -> None:
        self._raw: List[str] = list(proxies or [])
        self._cycle = itertools.cycle(self._raw) if self._raw else None

    @staticmethod
    def parse_requests_proxy(url: str) -> Dict[str, str]:
        # supports http/https. For SOCKS, user must install PySocks and use socks5:// schema
        return {"http": url, "https": url}

    def get_next_proxy(self) -> Optional[Dict[str, str]]:
        if not self._cycle:
            return None
        next_url = next(self._cycle)
        return self.parse_requests_proxy(next_url)

    @classmethod
    def from_file(cls, path: str) -> "ProxyManager":
        items: List[str] = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                items.append(line)
        return cls(items)