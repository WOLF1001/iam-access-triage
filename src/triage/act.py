"""Act-side (MOCK). Реальних змін немає — лише журнал того, що агент ЗРОБИВ БИ.

Кожен запис містить: який API/механізм був би викликаний, idempotency key,
які preconditions перевірено, і dry_run=true. Формат JSONL — щоб журнал
можна було відфільтрувати/порахувати і віддати в SIEM.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from . import catalog
from .policy import Decision

WOULD_CALL = {
    "add_birthright_group": "Okta: PUT /api/v1/groups/{groupId}/users/{userId}  (OAuth scope okta.groups.manage, resource set = allowlisted groups)",
    "resend_invite": "Asana: POST /workspaces/{gid}/addUser (повтор для вже погодженого approval_ref)",
    "readonly_diagnostic": "Okta: GET /api/v1/logs (read-only)",
}


class ActionLog:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("", encoding="utf-8")

    def write(self, entry: dict) -> dict:
        entry = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), "dry_run": True,
                 "mode": "SIMULATED", **entry}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry


def _idem(*parts) -> str:
    return hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16]


def execute(req_id: int, idx: int, d: Decision, requester: str | None, log: ActionLog) -> list[dict]:
    out = []
    base = {"request_id": req_id, "sub": idx, "route": d.route, "requester": requester}
    if d.action and d.action_done:
        params = {}
        if d.action == "add_birthright_group" and d.primary_app:
            params = {"group": catalog.get(d.primary_app).get("okta_group"), "user": requester}
        out.append(log.write({**base, "kind": "action", "action": d.action, "params": params,
                              "would_call": WOULD_CALL.get(d.action),
                              "preconditions": {k: v for k, v in (d.read.preconditions if d.read else {}).items()},
                              "idempotency_key": _idem(req_id, d.action, requester, params)}))
    if "APPROVAL_GATED" in (d.route, d.next_route):
        out.append(log.write({**base, "kind": "approval_request",
                              "status": "pending" if d.route == "APPROVAL_GATED" else "blocked_on_info",
                              "app": d.primary_app, "approvers": d.approvers,
                              "would_call": "Slack: chat.postMessage (Block Kit: Approve/Deny, TTL 72h) → approver DM",
                              "on_approve": "виконати dry-run план → підтвердити read-side, що зміна застосована"}))
    if d.route == "NEED_INFO":
        out.append(log.write({**base, "kind": "clarification", "questions": d.questions,
                              "would_call": "Slack: chat.postMessage(thread_ts) — бот чекає відповідь і перезапускає triage"}))
    if d.route in ("REROUTE",):
        out.append(log.write({**base, "kind": "reroute", "queue": d.queue,
                              "would_call": "Slack: chat.postMessage у канал черги з посиланням на тред"}))
    if d.route in ("HUMAN_REVIEW", "SECURITY_ESCALATION"):
        plan = d.read.dry_run_plan if d.read else []
        out.append(log.write({**base, "kind": "escalation", "queue": d.queue or "iam-review",
                              "priority": d.priority, "reasons": [r["signal"] for r in d.reasons],
                              "dry_run_plan_for_human": plan,
                              "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"
                                            + (" + PagerDuty" if d.route == "SECURITY_ESCALATION" else "")}))
    return out
