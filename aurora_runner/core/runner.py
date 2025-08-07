from __future__ import annotations

import csv
import os
import re
from typing import Dict, List
from urllib.parse import urlparse

from .config_loader import Config, Step
from .http_client import HttpClient
from ..utils.logger import setup_logger


logger = setup_logger("aurora.runner")


class SafeDict(dict):
    def __missing__(self, key):  # type: ignore
        return "{" + key + "}"


def _render(text: str, variables: Dict[str, str]) -> str:
    try:
        return text.format_map(SafeDict(variables))
    except Exception:
        return text


def _domain_allowed(url: str, allowlist: List[str]) -> bool:
    domain = urlparse(url).netloc.split(":")[0]
    return any(domain == allowed or domain.endswith("." + allowed) for allowed in allowlist)


def _extract_json_dot_path(obj, path: str):
    cur = obj
    for part in path.split('.'):
        if isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except Exception:
                return None
        elif isinstance(cur, dict):
            if part in cur:
                cur = cur[part]
            else:
                return None
        else:
            return None
    return cur


def run_config(config: Config, *, concurrency: int = 1, proxies=None) -> None:
    # Basic single-flow runner; concurrency here is reserved for future dataset execution
    proxy = None
    if proxies:
        proxy = proxies.get_next_proxy()
    client = HttpClient(proxy=proxy)

    variables: Dict[str, str] = {}

    for step in config.steps:
        url = _render(step.request.url, variables)
        if not _domain_allowed(url, config.allowlist):
            raise PermissionError(f"Domain não permitido pela allowlist: {url}")

        headers = {k: _render(v, variables) for k, v in step.request.headers.items()}
        body = _render(step.request.body, variables) if step.request.body else None

        logger.info(f"Step: {step.name} {step.request.method} {url}")
        resp = client.request(
            method=step.request.method,
            url=url,
            headers=headers,
            cookies=step.request.cookies,
            data=body,
            timeout=step.request.timeout,
            allow_redirects=step.request.allow_redirects,
        )

        text = resp.text
        # assertions
        for ar in step.asserts:
            if ar.type == "regex" and ar.source == "text":
                if not re.search(ar.pattern, text, re.S):
                    raise AssertionError(f"Assert falhou: regex '{ar.pattern}' não encontrada em resposta")

        # extractions
        for ex in step.extract:
            if ex.type == "json":
                try:
                    data = resp.json()
                except Exception:
                    data = None
                if data is not None and ex.path and ex.assign_to:
                    value = _extract_json_dot_path(data, ex.path)
                    if value is not None:
                        variables[ex.assign_to] = str(value)
                        logger.info(f"Var '{ex.assign_to}' = {variables[ex.assign_to]}")
            elif ex.type == "regex" and ex.pattern and ex.assign_to:
                m = re.search(ex.pattern, text, re.S)
                if m:
                    variables[ex.assign_to] = m.group(1) if m.groups() else m.group(0)
                    logger.info(f"Var '{ex.assign_to}' = {variables[ex.assign_to]}")

        # saves
        for sv in step.save:
            if sv.type == "csv":
                os.makedirs(os.path.dirname(sv.file), exist_ok=True)
                file_exists = os.path.exists(sv.file)
                with open(sv.file, "a", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=sv.fields)
                    if not file_exists:
                        writer.writeheader()
                    row = {k: variables.get(k, "") for k in sv.fields}
                    writer.writerow(row)
                    logger.info(f"Salvo em {sv.file}: {row}")

    client.close()