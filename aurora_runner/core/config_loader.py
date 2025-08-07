from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractRule:
    type: str  # 'json' or 'regex'
    path: Optional[str] = None  # for json dot-path
    assign_to: Optional[str] = None
    source: Optional[str] = None  # 'text' for regex
    pattern: Optional[str] = None  # for regex


@dataclass
class SaveRule:
    type: str  # 'csv'
    file: str
    fields: List[str]


@dataclass
class AssertRule:
    type: str  # 'regex'
    source: str  # 'text'
    pattern: str


@dataclass
class RequestDef:
    method: str
    url: str
    headers: Dict[str, str] = field(default_factory=dict)
    cookies: Dict[str, str] = field(default_factory=dict)
    body: Optional[str] = None
    timeout: float = 20.0
    allow_redirects: bool = True


@dataclass
class Step:
    name: str
    request: RequestDef
    extract: List[ExtractRule] = field(default_factory=list)
    asserts: List[AssertRule] = field(default_factory=list)
    save: List[SaveRule] = field(default_factory=list)


@dataclass
class Config:
    name: str
    allowlist: List[str]
    steps: List[Step]


def _ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("Config YAML deve ser um objeto de nível raiz")

    name = data.get("name")
    allowlist = data.get("allowlist") or []
    raw_steps = data.get("steps") or []

    if not name:
        raise ValueError("Campo 'name' é obrigatório")
    if not isinstance(allowlist, list) or not allowlist:
        raise ValueError("Campo 'allowlist' deve ser uma lista não-vazia de domínios")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("Campo 'steps' deve ser uma lista não-vazia")

    steps: List[Step] = []
    for raw in raw_steps:
        req_raw = raw.get("request") or {}
        request = RequestDef(
            method=str(req_raw.get("method") or "GET").upper(),
            url=str(req_raw.get("url") or ""),
            headers=dict(req_raw.get("headers") or {}),
            cookies=dict(req_raw.get("cookies") or {}),
            body=req_raw.get("body"),
            timeout=float(req_raw.get("timeout") or 20.0),
            allow_redirects=bool(req_raw.get("allow_redirects", True)),
        )
        if not request.url:
            raise ValueError("Cada step.request.url é obrigatório")

        extract_rules: List[ExtractRule] = []
        for ex in _ensure_list(raw.get("extract")):
            extract_rules.append(
                ExtractRule(
                    type=str(ex.get("type") or "").lower(),
                    path=ex.get("path"),
                    assign_to=ex.get("assign_to"),
                    source=ex.get("source"),
                    pattern=ex.get("pattern"),
                )
            )

        assert_rules: List[AssertRule] = []
        for ar in _ensure_list(raw.get("asserts")):
            assert_rules.append(
                AssertRule(
                    type=str(ar.get("type") or "").lower(),
                    source=str(ar.get("source") or "text"),
                    pattern=str(ar.get("pattern") or ""),
                )
            )

        save_rules: List[SaveRule] = []
        for sv in _ensure_list(raw.get("save")):
            save_rules.append(
                SaveRule(
                    type=str(sv.get("type") or "").lower(),
                    file=str(sv.get("file") or "results/output.csv"),
                    fields=[str(x) for x in (sv.get("fields") or [])],
                )
            )

        steps.append(
            Step(
                name=str(raw.get("name") or request.url),
                request=request,
                extract=extract_rules,
                asserts=assert_rules,
                save=save_rules,
            )
        )

    return Config(name=name, allowlist=allowlist, steps=steps)