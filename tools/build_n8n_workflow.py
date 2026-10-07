"""Генерує n8n/iam-triage.workflow.json (джерело правди — цей файл, а не експорт із UI: експорт містить email власника).

    python tools/build_n8n_workflow.py
    docker compose exec n8n sh -c "n8n import:workflow --input=/workflows/iam-triage.workflow.json && n8n publish:workflow --id=iamTriageMain01"
    docker compose restart n8n
"""
import json
import sys
import uuid

OUT = sys.argv[1] if len(sys.argv) > 1 else str(__import__("pathlib").Path(__file__).resolve().parents[1] / "n8n" / "iam-triage.workflow.json")
WEBHOOK_ID = "5f0c1a52-7c1e-4d55-9a3b-iamtriage001"[:36]

nodes, conns = [], {}


def node(name, typ, ver, pos, params, **extra):
    n = {"parameters": params, "name": name, "type": typ, "typeVersion": ver, "position": pos,
         "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "iam-triage/" + name))}
    n.update(extra)
    nodes.append(n)
    return name


def link(src, dst, out=0):
    m = conns.setdefault(src, {"main": []})["main"]
    while len(m) <= out:
        m.append([])
    m[out].append({"node": dst, "type": "main", "index": 0})


def code(name, pos, js):
    return node(name, "n8n-nodes-base.code", 2, pos, {"jsCode": js})


def sticky(name, pos, w, h, content, color=1):
    node(name, "n8n-nodes-base.stickyNote", 1, pos, {"content": content, "width": w, "height": h, "color": color})


# ---------------------------------------------------------------- вхід
wh = node("Slack event (webhook)", "n8n-nodes-base.webhook", 2, [0, 300],
          {"httpMethod": "POST", "path": "iam-triage", "responseMode": "responseNode", "options": {}},
          webhookId="7d4d0b8e-5b6a-4a39-9d4e-1a2b3c4d5e6f")

norm = code("Normalize Slack event", [180, 300], r"""
// Формат Slack Events API: { event_id, event: { user, text, channel, ts, thread_ts } }.
// requester береться ЛИШЕ з event.user (підписано Slack), ніколи з тексту.
const b = $input.first().json.body ?? {};
const e = b.event ?? {};
if (!e.text || !e.user) {
  return [{ json: { valid: false, error: 'Очікується Slack event: { event: { user, text, channel, ts } }' } }];
}
return [{ json: {
  valid: true,
  event_id: b.event_id ?? null,
  id: Number(b.request_id ?? 0),          // № з датасету — лише для демо
  text: e.text,
  requester: e.user,
  thread: b.thread_context ?? null,        // у проді: conversations.replies(thread_ts)
  channel: e.channel ?? 'C-IAM-HELP',
  thread_ts: e.thread_ts ?? e.ts ?? null,
}}];
""")

triage = node("Triage service (policy)", "n8n-nodes-base.httpRequest", 4.2, [560, 300], {
    "method": "POST", "url": "http://triage:8765/api/triage",
    "sendBody": True, "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify({ id: $json.id, event_id: $json.event_id, text: $json.text, requester: $json.requester, thread: $json.thread }) }}",
    "sendHeaders": True, "headerParameters": {"parameters": [{"name": "X-Triage-Token", "value": "={{ $env.TRIAGE_API_TOKEN }}"}]},
    "options": {"timeout": 15000}}, onError="continueErrorOutput")

ROUTES = [("DOCS_REDIRECT", "DOCS"), ("AUTO_RESOLVE", "AUTO"), ("REROUTE", "REROUTE"), ("NEED_INFO", "NEED_INFO"),
          ("APPROVAL_GATED", "APPROVAL"), ("HUMAN_REVIEW", "HUMAN"), ("SECURITY_ESCALATION", "SECURITY")]
sw = node("Route", "n8n-nodes-base.switch", 3.2, [760, 260], {
    "rules": {"values": [{
        "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                       "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, r)), "leftValue": "={{ $json.route }}",
                                       "rightValue": r, "operator": {"type": "string", "operation": "equals"}}],
                       "combinator": "and"},
        "renameOutput": True, "outputKey": key} for r, key in ROUTES]},
    "options": {"fallbackOutput": "extra", "renameFallbackOutput": "UNKNOWN → human"}})

COMMON = r"""
const r = $input.first().json;
const ev = $('Normalize Slack event').first().json;
const reply = { api: 'chat.postMessage', channel: ev.channel, thread_ts: ev.thread_ts, text: r.draft };
const done = (outbox) => [{ json: { route: r.route, dry_run: true, event_id: ev.event_id,
  outbox: r.dedup?.replayed_event ? [] : outbox,          // Slack retry: already handled, post nothing again
  replayed_event: !!r.dedup?.replayed_event, repeat_of: r.dedup?.repeat_of ?? null, act_log: r.actions } }];
"""

BRANCH = {
    "DOCS": ("Reply with KB link", "return done([reply]);"),
    "AUTO": ("Reply + allowlisted action", r"""
// Дію вже виконав сервіс (симуляція, allowlist + read-side preconditions) — тут лише повідомлення.
return done([reply]);"""),
    "REROUTE": ("Forward to queue", r"""
const q = r.decisions.find(d => d.queue)?.queue ?? 'helpdesk';
return done([reply, { api: 'chat.postMessage', channel: `#${q}`,
  text: `Перенаправлено з IAM: «${r.redacted_text}» (тред ${ev.channel}/${ev.thread_ts})` }]);"""),
    "NEED_INFO": ("Ask clarifying questions", r"""
// Тред чекає відповіді автора; нове повідомлення в треді → цей самий воркфлоу з thread_context.
return done([reply]);"""),
    "APPROVAL": ("Request approval (Block Kit)", r"""
const d = r.decisions.find(x => x.route === 'APPROVAL_GATED' || x.next_route === 'APPROVAL_GATED');
const approvers = d?.approvers ?? [];
const value = JSON.stringify({ event_id: ev.event_id, app: d?.primary_app, requester: r.requester, approvers });
return done([reply, ...approvers.map(a => ({
  api: 'chat.postMessage', channel: `DM:${a}`,
  text: `Запит на доступ: ${d?.primary_app ?? '?'} для ${r.requester}`,
  blocks: [
    { type: 'section', text: { type: 'mrkdwn', text: `*${r.requester}* просить *${d?.primary_app ?? '?'}*\n>${r.redacted_text}` } },
    { type: 'actions', elements: [
      { type: 'button', style: 'primary', text: { type: 'plain_text', text: 'Approve' }, action_id: 'iam_approve', value },
      { type: 'button', style: 'danger',  text: { type: 'plain_text', text: 'Deny' },    action_id: 'iam_deny',    value },
    ]},
  ],
}))]);"""),
    "HUMAN": ("Escalate to IAM engineer", r"""
return done([reply,
  { api: 'JSM: POST /rest/servicedeskapi/request', queue: 'iam-review', summary: r.redacted_text.slice(0, 120), description: r.internal_note },
  { api: 'chat.postMessage', channel: 'DM:iam-oncall', text: r.internal_note }]);"""),
    "SECURITY": ("Page security", r"""
return done([reply,
  { api: 'chat.postMessage', channel: '#security', text: r.internal_note },
  { api: 'PagerDuty Events v2: trigger', severity: 'critical', summary: `IAM triage: ${r.redacted_text.slice(0, 100)}` }]);"""),
    "UNKNOWN → human": ("Unknown route → human", r"""
return done([{ ...reply, text: 'Передав запит IAM-інженеру.' },
  { api: 'chat.postMessage', channel: 'DM:iam-oncall', text: `Невідомий маршрут від сервісу: ${r.route}` }]);"""),
}

respond = node("Respond (ack)", "n8n-nodes-base.respondToWebhook", 1.1, [1380, 300],
               {"respondWith": "firstIncomingItem", "options": {}})

order = [k for _, k in ROUTES] + ["UNKNOWN → human"]
for i, key in enumerate(order):
    name, js = BRANCH[key]
    code(name, [1060, i * 140 - 260], COMMON + js)
    link(sw, name, i)
    link(name, respond)

failc = code("Triage unavailable → human", [760, 640], r"""
// Fail-closed: сервіс рішень недоступний або повернув помилку → нічого не виконуємо, людина.
const ev = $('Normalize Slack event').first().json;
return [{ json: { route: 'HUMAN_REVIEW', dry_run: true, event_id: ev.event_id, reason: 'triage_service_error',
  outbox: [
    { api: 'chat.postMessage', channel: ev.channel, thread_ts: ev.thread_ts, text: 'Передав запит IAM-інженеру. Відповідь буде в цьому треді.' },
    { api: 'chat.postMessage', channel: 'DM:iam-oncall', text: `triage-сервіс недоступний: ${String($input.first().json.error?.message ?? 'unknown error').slice(0, 200)}` },
  ] } }];
""")

valid = node("Valid Slack event?", "n8n-nodes-base.if", 2.2, [360, 300], {
    "conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
                   "conditions": [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, "valid")), "leftValue": "={{ $json.valid }}",
                                   "rightValue": "", "operator": {"type": "boolean", "operation": "true", "singleValue": True}}],
                   "combinator": "and"}, "options": {}})
bad = node("Respond 400", "n8n-nodes-base.respondToWebhook", 1.1, [600, 480],
           {"respondWith": "json", "responseBody": "={{ JSON.stringify({ error: $json.error }) }}", "options": {"responseCode": 400}})
link(wh, norm)
link(norm, valid)
link(valid, triage, 0)
link(valid, bad, 1)
link(triage, sw, 0)
link(triage, failc, 1)
link(failc, respond)

sticky("Note: як це в проді", [-40, -420], 760, 380, """## IAM triage — оркестрація в n8n
**n8n** = канал і інтеграції. **triage-сервіс** = рішення (policy-as-code, `pytest`).
n8n не вирішує маршрут — лише виконує те, що повернув сервіс.

**Демо:** Webhook імітує Slack Events API. Усі вихідні виклики — `outbox` з `dry_run: true`.\n\n**Секрети:** n8n бачить СИРИЙ текст до редакції → збереження даних виконань вимкнено (settings воркфлоу + env інстансу).

**Прод (чого тут немає):**
- Slack Trigger замість Webhook: перевірка `X-Slack-Signature`, `url_verification`.
- Slack чекає ack ~3 с, інакше ретраїть подію → відповідати одразу, обробляти асинхронно; дедуп за `event_id`.
- Кнопки Approve/Deny → окремий воркфлоу (Slack interactivity): перевірити, що натиснув саме очікуваний апрувер, апрув → (subject, app, TTL).
- Креди Okta/1Password на ЗАПИС — лише в окремому act-воркфлоу з allowlist; цей воркфлоу їх не має.""", color=5)

sticky("Note: fail-closed", [480, 560], 520, 200, """### Fail-closed
Сервіс недоступний / 4xx / 5xx / таймаут → гілка помилки HTTP-вузла → людина.
Невідомий маршрут → fallback-вихід Switch → людина.""", color=3)

wf = {"name": "IAM triage — Slack → policy → route", "nodes": nodes, "connections": conns,
      "settings": {"executionOrder": "v1",
                   # Сирий текст Slack (можливо з секретами) приходить у n8n ДО редакції в triage-сервісі.
                   # Дані виконань не зберігаємо; аудит — redacted act-журнал сервісу.
                   "saveDataSuccessExecution": "none", "saveDataErrorExecution": "none",
                   "saveManualExecutions": False, "saveExecutionProgress": False}, "pinData": {}, "active": False,
      "id": "iamTriageMain01"}
json.dump(wf, open(OUT, "w"), ensure_ascii=False, indent=2)
print(OUT, len(nodes), "nodes")
