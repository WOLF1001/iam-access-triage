"""Phase 8 (code review) regressions for the HTTP service and hardening fixes."""
from __future__ import annotations

import importlib
import json
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from conftest import REQ, run_text
from triage import classify, config, kb_sync
from triage.act import ActionLog
from triage.dedup import DedupStore

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def service(monkeypatch):
    """Start tools/stand.py in service mode (TRIAGE_API_TOKEN set) on a random port."""
    monkeypatch.setenv("TRIAGE_API_TOKEN", "test-token")
    sys.path.insert(0, str(ROOT / "tools"))
    stand = importlib.reload(importlib.import_module("stand"))
    srv = ThreadingHTTPServer(("127.0.0.1", 0), stand.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()
    monkeypatch.delenv("TRIAGE_API_TOKEN")
    importlib.reload(stand)


def post(url, body, token=None):
    h = {"Content-Type": "application/json"}
    if token:
        h["X-Triage-Token"] = token
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, json.dumps(body).encode(), h))
        return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_service_mode_rejects_unauthenticated_requester(service):
    """Without auth anyone reaching the port could act as any Slack user (requester comes from the caller)."""
    code, _ = post(service + "/api/triage", {"text": "треба доступ до корп vpn", "requester": "U01"})
    assert code == 401
    code, r = post(service + "/api/triage", {"text": "треба доступ до корп vpn", "requester": "U01"}, "test-token")
    assert code == 200 and r["route"] == "AUTO_RESOLVE"


def test_service_mode_ignores_override_and_mode(service):
    body = {"text": "дайте доступ до tableau", "requester": "U01", "mode": "override",
            "override": json.dumps({"sub_requests": [{"summary": "x", "type": "how_to", "confidence": 1}]})}
    code, r = post(service + "/api/triage", body, "test-token")
    assert code == 200 and r["classification"]["classifier"] == "rules"


def test_requested_scope_is_sanitized():
    c = classify._validate({"sub_requests": [{"type": "how_to", "confidence": 1, "requested_scope": {"x": "y" * 5000}}]})
    assert c.sub_requests[0].requested_scope is None
    c = classify._validate({"sub_requests": [{"type": "how_to", "confidence": 1, "requested_scope": "a" * 500}]})
    assert len(c.sub_requests[0].requested_scope) == 100


def test_dedup_memory_is_bounded():
    store = DedupStore()
    for i in range(50):
        store.record(f"Ev{i}", f"u{i}@corp.example", {"decisions": [{"type": "access_request", "primary_app": "tableau"}]}, now=1000 + i)
    store.record("EvLate", "z@corp.example", {"decisions": []}, now=1000 + 30 * 86400)
    assert list(store.events) == ["EvLate"] and not store.requests and not store.seen_by


@pytest.mark.parametrize("url", ["https://evil.example/phish", "http://www.notion.so/x", "https://notion.so.evil.example/x"])
def test_kb_sync_rejects_non_notion_urls(tmp_path, monkeypatch, url):
    monkeypatch.setenv("KB_RUNTIME_PATH", str(tmp_path / "kb.json"))
    config.kb.cache_clear()
    rows = [{"article_id": aid, "title": a["title"], "summary": a["summary"], "status": "Published",
             "url": f"https://app.notion.com/p/{aid}"} for aid, a in config.kb()["articles"].items()]
    rows[0]["url"] = url
    with pytest.raises(kb_sync.SyncRejected, match="домені Notion"):
        kb_sync.sync(rows)
    config.kb.cache_clear()


def test_action_log_has_no_request_text(tmp_path):
    """Audit log keeps identities (needed for access audit) but never the free text of the request."""
    log = ActionLog(tmp_path / "a.log")
    for rid, text in REQ.items():
        run_text(text, req_id=rid, log=log)
    content = (tmp_path / "a.log").read_text(encoding="utf-8")
    leaked = [rid for rid, text in REQ.items() if len(text) > 25 and text[:25] in content]
    assert not leaked
