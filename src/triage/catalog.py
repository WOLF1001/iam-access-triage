"""Детермінований мапінг сирих згадок → app з каталогу.

LLM повертає лише сирі рядки ("табло", "клод-код"). Сюди LLM не має доступу:
якщо згадки немає в каталозі — app невідомий, і це сигнал unknown_app.
Матчинг: алиас на початку слова, перемагає найдовший алиас (щоб "claude api"
не плутався з "claude").
"""
from __future__ import annotations

import re

from . import config


def _alias_index() -> list[tuple[str, str]]:
    idx = []
    for app_id, spec in config.catalog().items():
        for a in spec.get("aliases", []):
            idx.append((a.lower(), app_id))
    idx.sort(key=lambda x: -len(x[0]))
    return idx


def resolve_apps(text: str) -> list[str]:
    """Повертає app_id у порядку появи, без дублікатів; довші алиаси «з'їдають» коротші."""
    low = text.lower()
    taken: list[tuple[int, int]] = []
    hits: list[tuple[int, str]] = []
    for alias, app_id in _alias_index():
        for m in re.finditer(r"(?<![\w])" + re.escape(alias), low):
            s, e = m.span()
            if any(s < te and e > ts for ts, te in taken):
                continue
            taken.append((s, e))
            hits.append((s, app_id))
    seen, out = set(), []
    for _, app_id in sorted(hits):
        if app_id not in seen:
            seen.add(app_id)
            out.append(app_id)
    return out


def get(app_id: str) -> dict:
    return config.catalog()[app_id]
