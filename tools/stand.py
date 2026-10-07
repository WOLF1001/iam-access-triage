#!/usr/bin/env python3
"""Локальний тестовий стенд: веб-UI поверх того самого pipeline, що й run_demo.py.

    python tools/stand.py            # http://localhost:8765

Нічого не виконує насправді: act-side пише в тимчасовий журнал з dry_run=true.
Режим «LLM-override» підставляє довільний вихід класифікатора (JSON) — щоб
руками відтворити атаки з tests/test_adversarial_llm.py (GAP-1, GAP-2).
Лише stdlib; локально слухає тільки 127.0.0.1 (STAND_HOST — для контейнера).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import hmac  # noqa: E402

from triage import classify, config, kb_sync, pipeline  # noqa: E402
from triage.dedup import DedupStore  # noqa: E402
from triage.act import ActionLog  # noqa: E402
from triage.classify import Classification, SubRequest  # noqa: E402

PORT = int(os.environ.get("STAND_PORT", "8765"))
HOST = os.environ.get("STAND_HOST", "127.0.0.1")   # у контейнері — 0.0.0.0 (мережа compose), локально — лише loopback
HTML = Path(__file__).with_name("stand.html")
# Хто може писати в KB, той пише відповіді бота → синк лише з токеном (n8n отримує його з env).
KB_SYNC_TOKEN = os.environ.get("KB_SYNC_TOKEN", "")
DEDUP = DedupStore()
# Service mode (container / prod): the caller (n8n) must authenticate, because `requester` comes from the caller —
# without a token anyone who can reach the port could act as any Slack user. Dev mode (no token): local UI only.
TRIAGE_API_TOKEN = os.environ.get("TRIAGE_API_TOKEN", "")
DEV_MODE = not TRIAGE_API_TOKEN


def _users() -> list[dict]:
    hris = {e["email"]: e for e in config.mock("hris")["employees"]}
    out = []
    for sid, u in config.mock("slack_users")["users"].items():
        e = hris.get(u["email"], {})
        out.append({"id": sid, "email": u["email"], "name": e.get("name") or u["email"],
                    "dept": e.get("department"), "external": u["is_stranger"]})
    return out


def _bootstrap() -> dict:
    sample = {c["id"]: c for c in config.load_sample()["cases"]}
    golden_p = ROOT / "tests" / "golden_routes.json"
    golden = json.loads(golden_p.read_text(encoding="utf-8")) if golden_p.exists() else {}
    reqs = [{"id": i, "text": t, "sample": i in sample, "why": sample.get(i, {}).get("why_picked"),
             "requester": sample.get(i, {}).get("requester"), "thread": sample.get(i, {}).get("thread"),
             "route": golden.get(str(i), {}).get("route")} for i, t in config.load_requests().items()]
    routes = [{"id": k, "severity": v["severity"], "desc": v["desc"]} for k, v in config.policy()["routes"].items()]
    return {"requests": reqs, "users": _users(), "routes": routes,
            "llm_available": bool(os.environ.get("ANTHROPIC_API_KEY")),
            "ollama": os.environ.get("OLLAMA_URL") and os.environ.get("OLLAMA_MODEL", "qwen3:14b"),
            "default_mode": os.environ.get("CLASSIFIER_MODE", "rules"),
            "dev_mode": DEV_MODE,
            "types": classify.TYPES, "llm_signals": classify.LLM_SIGNALS,
            "kb": {"source": config.kb().get("source"), "articles": len(config.kb()["articles"])}}


def _override_classifier(raw: dict):
    """LLM-override: вихід «LLM» задає користувач. Проходить ту саму валідацію, що й справжній."""
    c = classify._validate(raw)
    c.classifier = "llm-override (ручний JSON)"
    return lambda text, thread, mode: c


def triage(body: dict) -> dict:
    text = (body.get("text") or "").strip()
    if not text:
        raise ValueError("порожній текст")
    event_id = body.get("event_id")
    cached = DEDUP.cached(event_id)
    if cached:   # Slack retry of the same event: same answer, no second run, no new actions
        return {**cached, "dedup": {**cached.get("dedup", {}), "replayed_event": True}}
    # n8n/Slack do not choose the classifier — the service does (CLASSIFIER_MODE). Only the local dev UI may override.
    mode = (body.get("mode") if DEV_MODE else None) or os.environ.get("CLASSIFIER_MODE", "rules")
    if mode not in ("rules", "llm", "ollama", "replay", "override"):
        raise ValueError(f"невідомий mode: {mode}")
    orig = classify.classify
    try:
        if mode == "override":
            classify.classify = _override_classifier(json.loads(body.get("override") or "{}"))
            run_mode = "llm"
        else:
            run_mode = mode
        with tempfile.TemporaryDirectory() as td:
            log = ActionLog(Path(td) / "actions.log")
            r = pipeline.run_one(int(body.get("id") or 0), text, requester_slack=body.get("requester") or None,
                                 thread=(body.get("thread") or "").strip() or None, mode=run_mode, log=log)
            actions = [json.loads(x) for x in log.path.read_text(encoding="utf-8").splitlines()]
    finally:
        classify.classify = orig
    if any(x["signal"] == "kb_gap" for d in r.decisions for x in d.reasons):
        kb_sync.record_gap(r.redacted_text, r.req_id or None)
    result = {
        "route": r.overall_route,
        "redacted_text": r.redacted_text, "thread_redacted": r.thread_redacted,
        "redaction_findings": r.redaction_findings, "requester": r.requester,
        "classification": r.classification.to_dict(),
        "decisions": [{**d.to_dict(),
                       "facts": [f.to_dict() for f in (d.read.facts if d.read else [])],
                       "diagnosis": d.read.diagnosis if d.read else [],
                       "dry_run_plan": d.read.dry_run_plan if d.read else [],
                       "preconditions": d.read.preconditions if d.read else {}} for d in r.decisions],
        "draft": r.draft, "internal_note": r.internal_note, "actions": actions,
    }
    result["dedup"] = {**DEDUP.record(event_id, r.requester, result), "replayed_event": False}
    return result


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, HTML.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/bootstrap":
            self._json(200, _bootstrap())
        elif self.path == "/api/kb/gaps":   # тексти звернень (відредаговані) — теж лише з токеном
            if not self._authorized():
                return self._json(401, {"error": "KB_SYNC_TOKEN не заданий або X-KB-Sync-Token невірний"})
            self._json(200, {"gaps": kb_sync.gaps()})
        else:
            self._json(404, {"error": "not found"})

    def _triage_authorized(self) -> bool:
        if DEV_MODE:
            return True
        return hmac.compare_digest(self.headers.get("X-Triage-Token", ""), TRIAGE_API_TOKEN)

    def _authorized(self) -> bool:
        got = self.headers.get("X-KB-Sync-Token", "")
        return bool(KB_SYNC_TOKEN) and hmac.compare_digest(got, KB_SYNC_TOKEN)

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        except json.JSONDecodeError as e:
            return self._json(400, {"error": f"invalid JSON: {e}"})
        if self.path == "/api/triage":
            if not self._triage_authorized():
                return self._json(401, {"error": "X-Triage-Token невірний або відсутній"})
            try:
                return self._json(200, triage(body))
            except Exception as e:  # стенд — показуємо помилку в UI, не падаємо
                return self._json(400, {"error": f"{type(e).__name__}: {e}"})
        if self.path in ("/api/kb/sync", "/api/kb/gaps/ack"):
            if not self._authorized():
                return self._json(401, {"error": "KB_SYNC_TOKEN не заданий або X-KB-Sync-Token невірний"})
            try:
                if self.path == "/api/kb/sync":
                    return self._json(200, kb_sync.sync(body.get("articles") or [], body.get("source", "notion")))
                return self._json(200, {"acked": kb_sync.ack_gaps(body.get("gap_ids") or [])})
            except kb_sync.SyncRejected as e:
                sys.stderr.write(f"stand: kb sync rejected: {e}\n")   # reason only, no article content
                return self._json(409, {"error": str(e)})
        return self._json(404, {"error": "not found"})

    def log_message(self, fmt, *args):
        sys.stderr.write("stand: " + fmt % args + "\n")


if __name__ == "__main__":
    try:
        server = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError as e:
        if e.errno in (48, 98):   # EADDRINUSE (macOS / Linux)
            sys.exit(f"Порт {PORT} зайнятий — стенд, мабуть, уже запущений: http://localhost:{PORT}\n"
                     f"Інший порт: STAND_PORT=8766 python tools/stand.py · хто тримає: lsof -i :{PORT}")
        raise
    print(f"IAM triage stand → http://localhost:{PORT}")
    server.serve_forever()
