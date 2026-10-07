"""Golden snapshot маршрутів усіх 108 звернень (rules-класифікатор).

Не «правильні відповіді», а зафіксований стан: будь-яка правка regex / YAML,
що змінює маршрут хоч одного звернення, падає тут — і зміна має бути свідомою.
Оновити після рев'ю диффу:
    UPDATE_GOLDEN=1 pytest tests/test_golden.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from conftest import REQ, run_text

GOLDEN = Path(__file__).with_name("golden_routes.json")


def snapshot() -> dict[str, dict]:
    out = {}
    for rid, text in REQ.items():
        r = run_text(text, req_id=rid)
        out[str(rid)] = {"route": r.overall_route,
                         "subs": [[d.sub.type, d.route, d.next_route, d.primary_app] for d in r.decisions]}
    return out


def test_routes_match_golden():
    current = snapshot()
    if os.environ.get("UPDATE_GOLDEN") or not GOLDEN.exists():
        GOLDEN.write_text(json.dumps(current, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
    diff = {k: (golden.get(k), v) for k, v in current.items() if golden.get(k) != v}
    assert not diff, "Маршрути змінились (golden → current):\n" + "\n".join(
        f"  #{k}: {g and g['route']} → {c['route']}   {c['subs']}" for k, (g, c) in diff.items())
