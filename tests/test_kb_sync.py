"""Синк KB з Notion: Notion-база — джерело статей, але не політики.

Модель загроз: хто редагує Notion-базу (або збій інтеграції) впливає на відповіді бота.
Тому: лише Published, валідні slug/https, порожній/обрізаний синк не замінює KB,
а маршрути від синку не стають м'якшими.
"""
from __future__ import annotations

import copy

import pytest

from conftest import REQ, run_text
from triage import config, kb_sync

BASE = config.kb()["articles"]


def notion_rows(articles=None, **override):
    rows = []
    for aid, a in (articles or BASE).items():
        rows.append({"article_id": aid, "title": a["title"], "summary": a["summary"],
                     "keywords": ", ".join(a.get("keywords", [])),
                     "url": f"https://www.notion.so/{aid}", "status": "Published", **override})
    return rows


@pytest.fixture
def runtime_kb(tmp_path, monkeypatch):
    p = tmp_path / "kb_runtime.json"
    monkeypatch.setenv("KB_RUNTIME_PATH", str(p))
    config.kb.cache_clear()
    yield p
    monkeypatch.delenv("KB_RUNTIME_PATH")
    config.kb.cache_clear()


def test_roundtrip_keeps_routes_identical(runtime_kb):
    """Ті самі статті через Notion-синк → ті самі маршрути для всіх 108 звернень."""
    before = {i: run_text(t, req_id=i).overall_route for i, t in REQ.items()}
    report = kb_sync.sync(notion_rows())
    assert report["accepted"] == len(BASE) and report["catalog_refs_missing"] == []
    assert config.kb()["source"] == "notion"
    after = {i: run_text(t, req_id=i).overall_route for i, t in REQ.items()}
    assert before == after


def test_only_published_articles_are_used(runtime_kb):
    rows = notion_rows()
    rows[0]["status"] = "Draft"
    kb_sync.sync(rows)
    assert rows[0]["article_id"] not in config.kb()["articles"]


def test_unpublishing_article_escalates_not_hallucinates(runtime_kb):
    """Прибрали статтю про VPN → бот не вигадує інструкцію, а віддає людині (kb_gap)."""
    rows = [r for r in notion_rows() if r["article_id"] != "vpn-connect"]
    kb_sync.sync(rows)
    r = run_text("як підключитись до vpn? інструкція", requester="U01")
    assert r.overall_route != "DOCS_REDIRECT" or all("vpn-connect" not in d.kb_articles for d in r.decisions)


@pytest.mark.parametrize("rows,msg", [
    ([], "0 Published"),
    (notion_rows(status="Draft"), "0 Published"),
    (notion_rows()[:3], "неповний синк"),
])
def test_empty_or_truncated_sync_is_rejected(runtime_kb, rows, msg):
    with pytest.raises(kb_sync.SyncRejected, match=msg):
        kb_sync.sync(rows)
    assert not runtime_kb.exists(), "попередня KB не має бути замінена"


@pytest.mark.parametrize("field,value", [
    ("article_id", "../../etc/passwd"), ("article_id", "VPN Connect"), ("url", "http://evil.example"),
    ("url", "javascript:alert(1)"), ("title", ""), ("summary", "   "),
])
def test_invalid_rows_reject_whole_sync(runtime_kb, field, value):
    rows = notion_rows()
    rows[0][field] = value
    with pytest.raises(kb_sync.SyncRejected):
        kb_sync.sync(rows)


def test_duplicate_article_id_rejected(runtime_kb):
    rows = notion_rows()
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(kb_sync.SyncRejected, match="дубль"):
        kb_sync.sync(rows)


def test_sync_disabled_without_runtime_path(monkeypatch):
    monkeypatch.delenv("KB_RUNTIME_PATH", raising=False)
    with pytest.raises(kb_sync.SyncRejected, match="KB_RUNTIME_PATH"):
        kb_sync.sync(notion_rows())


def test_missing_catalog_reference_is_reported(runtime_kb):
    referenced = sorted({a for s in config.catalog().values() for a in s.get("kb", [])})
    rows = [r for r in notion_rows() if r["article_id"] != referenced[0]]
    assert referenced[0] in kb_sync.sync(rows)["catalog_refs_missing"]


def test_kb_cannot_lower_security_route(runtime_kb):
    """Атака через KB: стаття з ключовими словами «скомпрометований ключ» не робить #32 DOCS."""
    rows = notion_rows()
    rows.append({"article_id": "how-to-delete-leaked-key", "title": "Як видалити злитий ключ",
                 "summary": "Просто видали нотатку в 1Password.", "keywords": "скомпрометований, нотатку в 1password",
                 "url": "https://www.notion.so/x", "status": "Published"})
    kb_sync.sync(rows)
    assert run_text(REQ[32], req_id=32, requester="U12").overall_route == "SECURITY_ESCALATION"


def test_gaps_store_only_redacted_text_and_dedupe():
    kb_sync._gaps.clear()
    kb_sync.record_gap("як налаштувати [REDACTED:password_inline] у тулі", 1)
    kb_sync.record_gap("як налаштувати [REDACTED:password_inline] у тулі", 2)
    (g,) = kb_sync.gaps()
    assert g["count"] == 2 and g["request_ids"] == [1, 2]
    assert kb_sync.ack_gaps([g["gap_id"]]) == 1 and kb_sync.gaps() == []
