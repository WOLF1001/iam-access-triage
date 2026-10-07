"""Синхронізація KB з Notion (через n8n) і беклог kb_gap.

Notion — джерело правди для статей, але не для політики:
  * бот бере лише Status=Published;
  * article_id має бути slug і збігатися з тим, на що посилається каталог;
  * порожній або підозріло малий синк не замінює KB (збій Notion / права інтеграції
    не мають тихо вимкнути DOCS — fail-safe: лишається остання добра версія);
  * хто редагує Notion-базу, той фактично пише відповіді бота → див. critique.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from . import config

SLUG = re.compile(r"^[a-z0-9][a-z0-9\-]{1,62}$")
MIN_SHARE = 0.5          # новий набір має бути ≥ 50% від поточного, інакше — відмова
_lock = threading.Lock()
_gaps: dict[str, dict] = {}


class SyncRejected(ValueError):
    pass


def _clean(a: dict) -> dict | None:
    if str(a.get("status", "")).strip().lower() != "published":
        return None
    aid = str(a.get("article_id", "")).strip()
    title, summary = str(a.get("title", "")).strip(), str(a.get("summary", "")).strip()
    url = str(a.get("url", "")).strip()
    if not SLUG.match(aid):
        raise SyncRejected(f"невалідний article_id: {aid!r}")
    if not title or not summary:
        raise SyncRejected(f"{aid}: порожні title/summary")
    host = urlparse(url).hostname or ""
    allowed = os.environ.get("KB_URL_ALLOWED_HOSTS", "notion.so,www.notion.so,app.notion.com,notion.site").split(",")
    if urlparse(url).scheme != "https" or not any(host == h or host.endswith("." + h) for h in allowed):
        raise SyncRejected(f"{aid}: url має бути https на домені Notion ({host or url!r}) — бот не пересилає довільні посилання")
    kws = a.get("keywords") or []
    if isinstance(kws, str):
        kws = [k for k in (x.strip() for x in kws.split(",")) if k]
    return {"title": title[:200], "summary": summary[:1000], "url": url,
            "keywords": [str(k)[:80] for k in kws][:30]}


def sync(articles: list[dict], source: str = "notion") -> dict:
    """Валідує і атомарно замінює runtime-KB. Повертає звіт для n8n."""
    path = os.environ.get("KB_RUNTIME_PATH")
    if not path:
        raise SyncRejected("KB_RUNTIME_PATH не заданий — синк вимкнено")
    published: dict[str, dict] = {}
    dups: dict[str, int] = {}
    for a in articles:
        c = _clean(a)
        if c is None:
            continue
        aid = str(a["article_id"]).strip()
        if aid in published:
            dups[aid] = dups.get(aid, 1) + 1
        published[aid] = c
    if dups:   # report all of them at once, so a human fixes Notion in one pass
        raise SyncRejected("дубль article_id (Published): " + ", ".join(f"{k} ×{v}" for k, v in sorted(dups.items())))
    current = config.kb()["articles"]
    if not published:
        raise SyncRejected("0 Published-статей — відмовляюсь замінювати KB (збій Notion або прав інтеграції?)")
    if len(published) < MIN_SHARE * len(current):
        raise SyncRejected(f"{len(published)} статей проти {len(current)} поточних — схоже на неповний синк")
    referenced = {art for s in config.catalog().values() for art in s.get("kb", [])}
    missing_refs = sorted(referenced - set(published))
    payload = {"source": source, "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "articles": published}
    with _lock:
        tmp = Path(path).with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(path)
        config.kb.cache_clear()
    return {"accepted": len(published), "skipped_not_published": len(articles) - len(published),
            "catalog_refs_missing": missing_refs}


def record_gap(redacted_text: str, req_id: int | None) -> None:
    """kb_gap → беклог. Зберігаємо лише ВІДРЕДАГОВАНИЙ текст (у Notion піде тільки він)."""
    key = hashlib.sha256(redacted_text.strip().lower().encode()).hexdigest()[:12]
    with _lock:
        g = _gaps.setdefault(key, {"gap_id": key, "text": redacted_text[:500], "count": 0, "request_ids": []})
        g["count"] += 1
        if req_id and req_id not in g["request_ids"]:
            g["request_ids"].append(req_id)


def gaps() -> list[dict]:
    with _lock:
        return list(_gaps.values())


def ack_gaps(ids: list[str]) -> int:
    with _lock:
        return sum(1 for i in ids if _gaps.pop(i, None) is not None)
