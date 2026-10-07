"""Завантаження конфігів і моків."""
from __future__ import annotations

import csv
import json
import os
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "config"
MOCKS = ROOT / "mocks"
DATA = ROOT / "data"
PROMPTS = ROOT / "prompts"
CACHE = ROOT / "cache"
DEMO = ROOT / "demo"


def _yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache
def policy() -> dict:
    return _yaml(CONFIG / "policy.yaml")


@lru_cache
def catalog() -> dict:
    return _yaml(CONFIG / "app_catalog.yaml")["apps"]


@lru_cache
def kb() -> dict:
    """KB = kb.yaml, або (якщо задано KB_RUNTIME_PATH і файл існує) статті, синхронізовані з Notion.
    Черги перенаправлення завжди з kb.yaml — це конфіг, а не контент KB."""
    base = _yaml(CONFIG / "kb.yaml")
    runtime = os.environ.get("KB_RUNTIME_PATH")
    if runtime and Path(runtime).exists():
        synced = json.loads(Path(runtime).read_text(encoding="utf-8"))
        return {**base, "articles": synced["articles"], "source": synced.get("source", "runtime")}
    return {**base, "source": "kb.yaml"}


@lru_cache
def mock(name: str) -> dict:
    with (MOCKS / f"{name}.json").open(encoding="utf-8") as f:
        return json.load(f)


def load_requests() -> dict[int, str]:
    with (DATA / "requests.csv").open(encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)
        return {int(row[0]): row[1].strip() for row in reader if row}


def load_sample() -> dict:
    return _yaml(DEMO / "sample.yaml")


ROUTE_SEVERITY = {name: spec["severity"] for name, spec in policy()["routes"].items()}


def max_route(*routes: str | None) -> str:
    routes = [r for r in routes if r]
    return max(routes, key=lambda r: ROUTE_SEVERITY[r])
