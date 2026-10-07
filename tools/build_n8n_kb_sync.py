#!/usr/bin/env python3
"""Генерує n8n/kb-sync.workflow.json: Notion «IAM KB» → triage-сервіс, і kb_gap → Draft-сторінки в Notion.

    python tools/build_n8n_kb_sync.py [--credential-id ID]
    docker compose exec n8n sh -c "n8n import:workflow --input=/workflows/kb-sync.workflow.json"

Notion-ключ (internal integration secret) додається ЛЮДИНОЮ в n8n → Credentials («Notion API»);
у репо його немає. ID бази — NOTION_KB_DATABASE_ID у .env (не секрет).
TODO(verify): Notion-Version 2022-06-28 vs data sources API (2025-09-03) — чи лишається /databases/{id}/query.
"""
from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "n8n" / "kb-sync.workflow.json"
NOTION_VERSION = "2022-06-28"

nodes: list[dict] = []
conns: dict = {}


def node(name, typ, ver, pos, params, **extra):
    nodes.append({"parameters": params, "name": name, "type": typ, "typeVersion": ver, "position": pos,
                  "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "iam-kb-sync/" + name)), **extra})
    return name


def link(src, dst, out=0):
    m = conns.setdefault(src, {"main": []})["main"]
    while len(m) <= out:
        m.append([])
    m[out].append({"node": dst, "type": "main", "index": 0})


def code(name, pos, js):
    return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})


def http(name, pos, method, url, *, notion=False, body=None, token=False, cred=None, on_error=None):
    headers = []
    if notion:
        headers.append({"name": "Notion-Version", "value": NOTION_VERSION})
    if token:
        headers.append({"name": "X-KB-Sync-Token", "value": "={{ $env.KB_SYNC_TOKEN }}"})
    p = {"method": method, "url": url, "options": {"timeout": 20000}}
    if notion:
        p.update({"authentication": "predefinedCredentialType", "nodeCredentialType": "notionApi"})
    if headers:
        p.update({"sendHeaders": True, "headerParameters": {"parameters": headers}})
    if body:
        p.update({"sendBody": True, "specifyBody": "json", "jsonBody": body})
    extra = {}
    if notion and cred:
        extra["credentials"] = {"notionApi": cred}
    if on_error:
        extra["onError"] = on_error
    return node(name, "n8n-nodes-base.httpRequest", 4.2, pos, p, **extra)


def build(cred: dict | None) -> dict:
    sched = node("Every 15 min", "n8n-nodes-base.scheduleTrigger", 1.2, [0, 200],
                 {"rule": {"interval": [{"field": "minutes", "minutesInterval": 15}]}})
    manual = node("Run now (manual)", "n8n-nodes-base.manualTrigger", 1, [0, 380], {})
    cfg = code("Config", [220, 290], r"""
const databaseId = ($env.NOTION_KB_DATABASE_ID ?? '').replace(/-/g, '').trim();
if (!/^[0-9a-f]{32}$/i.test(databaseId)) {
  throw new Error('NOTION_KB_DATABASE_ID у .env не задано або невалідний (32 hex з URL бази)');
}
return [{ json: { databaseId } }];
""")
    schema = http("Notion: KB schema", [440, 290], "GET",
                  "=https://api.notion.com/v1/databases/{{ $json.databaseId }}", notion=True, cred=cred)
    query = http("Notion: query KB", [660, 200], "POST",
                 "=https://api.notion.com/v1/databases/{{ $('Config').first().json.databaseId }}/query",
                 notion=True, cred=cred, body='={{ JSON.stringify({ page_size: 100 }) }}')
    mapper = code("Map Notion → KB articles", [880, 200], r"""
// Notion-сторінки → статті. Тип властивостей не припускаємо (CSV-імпорт дає text/select/status).
const plain = (p) => {
  if (!p) return '';
  switch (p.type) {
    case 'title': return p.title.map(t => t.plain_text).join('');
    case 'rich_text': return p.rich_text.map(t => t.plain_text).join('');
    case 'select': return p.select?.name ?? '';
    case 'status': return p.status?.name ?? '';
    case 'multi_select': return p.multi_select.map(o => o.name).join(', ');
    case 'date': return p.date?.start ?? '';
    case 'url': return p.url ?? '';
    default: return '';
  }
};
const res = $input.first().json;
if (res.has_more) throw new Error('KB > 100 сторінок — потрібна пагінація; синк зупинено, лишається попередня KB');
const titleKey = Object.keys(res.results[0]?.properties ?? {}).find(k => res.results[0].properties[k].type === 'title');
const articles = res.results.filter(p => !p.archived && !p.in_trash).map(p => ({
  article_id: plain(p.properties['article_id']),
  title: plain(p.properties[titleKey]),
  summary: plain(p.properties['Summary']),
  keywords: plain(p.properties['Keywords']),
  status: plain(p.properties['Status']),
  url: p.url,
}));
return [{ json: { source: 'notion', articles } }];
""")
    sync = http("Triage: replace KB", [1100, 200], "POST", "http://triage:8765/api/kb/sync", token=True,
                body="={{ JSON.stringify({ source: 'notion', articles: $json.articles }) }}", on_error="continueErrorOutput")
    ok = code("Sync report", [1320, 120], r"""
// accepted / skipped_not_published / catalog_refs_missing — на останнє варто дивитись людині.
return $input.all();
""")
    alert = code("Sync rejected → alert IAM", [1320, 300], r"""
// 409 від сервісу (порожній/обрізаний/невалідний синк) → KB НЕ замінено, лишилась попередня. Людині — DM.
const e = $input.first().json.error ?? {};
return [{ json: { dry_run: true, outbox: [{ api: 'chat.postMessage', channel: 'DM:iam-oncall',
  text: `KB sync з Notion відхилено: ${String(e.message ?? e).slice(0, 300)}` }] } }];
""")

    gaps = http("Triage: kb_gap backlog", [660, 420], "GET", "http://triage:8765/api/kb/gaps", token=True)
    split = code("One item per gap", [880, 420], r"""
return ($input.first().json.gaps ?? []).map(g => ({ json: g }));
""")
    draft = http("Notion: create Draft", [1100, 420], "POST", "https://api.notion.com/v1/pages", notion=True, cred=cred,
                 body=r"""={{ (() => {
  const schema = $('Notion: KB schema').first().json.properties;
  const val = (name, text) => {
    const t = schema[name]?.type;
    if (!t) return undefined;
    if (t === 'title') return { title: [{ text: { content: text } }] };
    if (t === 'rich_text') return { rich_text: [{ text: { content: text } }] };
    if (t === 'select') return { select: { name: text } };
    if (t === 'status') return { status: { name: text } };
    return undefined;
  };
  const titleKey = Object.keys(schema).find(k => schema[k].type === 'title');
  const props = {
    [titleKey]: val(titleKey, `KB gap: ${$json.text.slice(0, 80)}`),
    Summary: val('Summary', `Бот не знайшов статті (${$json.count}×, звернення ${$json.request_ids.join(', ') || '—'}). Відредагований текст: ${$json.text}`),
    Status: val('Status', 'Draft'),
    Owner: val('Owner', 'IAM'),
  };
  Object.keys(props).forEach(k => props[k] === undefined && delete props[k]);
  return JSON.stringify({ parent: { database_id: $('Config').first().json.databaseId }, properties: props });
})() }}""")
    ack = http("Triage: ack gap", [1320, 420], "POST", "http://triage:8765/api/kb/gaps/ack", token=True,
               body="={{ JSON.stringify({ gap_ids: [$('One item per gap').item.json.gap_id] }) }}")

    for a, b, o in [(sched, cfg, 0), (manual, cfg, 0), (cfg, schema, 0), (schema, query, 0), (schema, gaps, 0),
                    (query, mapper, 0), (mapper, sync, 0), (sync, ok, 0), (sync, alert, 1),
                    (gaps, split, 0), (split, draft, 0), (draft, ack, 0)]:
        link(a, b, o)

    node("Note", "n8n-nodes-base.stickyNote", 1, [-40, -260], {"width": 760, "height": 420, "color": 5, "content": """## KB sync: Notion → triage-сервіс
**Notion = джерело статей, не політики.** Бот бере лише `Status = Published`; DOCS лише на існуючий `article_id`.

**Вгору (кожні 15 хв):** схема бази → усі сторінки → сервіс валідує (slug, https, без дублів) і **атомарно** замінює KB.
Порожній/обрізаний синк (<50% поточних) → 409 → KB не чіпаємо, DM IAM (збій Notion не вимикає DOCS тихо).

**Вниз:** `kb_gap` (бот не знайшов статті → людина) → Draft-сторінка в Notion = беклог KB. У Notion іде лише ВІДРЕДАГОВАНИЙ текст.

**Секрети:** Notion-ключ — у n8n Credentials (додає людина). `KB_SYNC_TOKEN` — з env.
**Ризик:** хто редагує Notion-базу, той пише відповіді бота → права на базу = як на код (review, історія змін)."""})

    return {"name": "IAM KB sync — Notion ⇄ triage", "nodes": nodes, "connections": conns,
            "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "none",
                         "saveDataErrorExecution": "all", "saveManualExecutions": True},
            "pinData": {}, "active": False, "id": "iamKbSyncNotion1"}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--credential-id")
    ap.add_argument("--credential-name", default="Notion IAM KB")
    a = ap.parse_args()
    cred = {"id": a.credential_id, "name": a.credential_name} if a.credential_id else None
    OUT.write_text(json.dumps(build(cred), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(nodes)} nodes" + (" (credential підв'язано)" if cred else " (credential — вибрати в UI)"))
