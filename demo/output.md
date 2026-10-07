# Демо: AI-assisted IAM triage

Класифікатор: `rules`. Дії — **симуляція** (див. `demo/actions.log`). Requester/тред — синтетичні (у CSV їх немає), див. `demo/sample.yaml`.

## Зведення

| Маршрут | К-сть |
|---|---|
| AUTO — бот робить сам | 2 |
| DOCS — перенаправлення в документацію | 2 |
| REROUTE — не IAM, інша черга | 1 |
| NEED_INFO — уточнення | 1 |
| APPROVAL — бот готує, людина апрувить | 1 |
| HUMAN — рішення за IAM-інженером | 6 |
| SECURITY — інцидент / пейдж | 3 |

| № | Звернення | Маршрут | Ключовий сигнал |
|---|---|---|---|
| 91 | треба доступ до корп vpn + інструкція як підключитись | **AUTO_RESOLVE** | тип `access_request`, дія `add_birthright_group` |
| 104 | інвайт у асану деактивувався поки я дійшла, надішліть ще раз будь лас… | **AUTO_RESOLVE** | тип `invite_resend`, дія `resend_invite` |
| 7 | питання по лімітах notion api — чи треба нам апати тариф щоб під це в… | **DOCS_REDIRECT** | тип `policy_question` |
| 51 | У мене зламався монітор, його мій кіт завалив, що робити? | **REROUTE** | тип `not_iam` |
| 69 | пропав доступ до tableau, через okta не пускає | **APPROVAL_GATED** | `regrant_needed` (read) |
| 42 | вчора ввечері не міг зайти, сьогодні теж дивно. подивіться що з моїм … | **SECURITY_ESCALATION** | `suspicious_auth_activity` (read) |
| 5 | треба згенерити новий api-ключ до однієї ai-моделі, це для локалізаці… | **NEED_INFO** | `unverified_approval_claim` (text) |
| 95 | у нас сьогодні лонч і мене вибило, терміново треба скинути пароль!! | **DOCS_REDIRECT** | `credential_reset` (text) |
| 46 | не розумію які доступи мені треба - документи, драйв, api… мій лід у … | **HUMAN_REVIEW** | `mirror_access` (text) |
| 75 | виходить нова людина, це неплановий вихід, у HRM ще не внести, налашт… | **HUMAN_REVIEW** | `hris_bypass` (text) |
| 92 | терміново заблокуйте всі доступи співробітнику — сьогодні останній де… | **HUMAN_REVIEW** | `offboarding` (text) |
| 32 | асап!! видаліть будь ласка нотатку в 1password зі старим api-ключем р… | **SECURITY_ESCALATION** | `secret_compromise` (text) |
| 85 | прийшов звіт від пентестерів, там High-знахідка по одному з продуктів… | **SECURITY_ESCALATION** | `security_finding` (text) |
| 26 | не знаю, чи це до тебе, але треба вивантажити списки людей з business… | **HUMAN_REVIEW** | `pii_request` (text) |
| 12 | хочу ввімкнути always-allow для mcp-конекторів у клоді, так зручніше.… | **HUMAN_REVIEW** | `security_policy_change` (text) |
| 29 | у мене не працює adobe creative cloud, щось з підпискою. і ще треба і… | **HUMAN_REVIEW** | `on_behalf` (text) |

---
## #91 → AUTO — бот робить сам

_Чому в вибірці: AUTO: birthright-група (VPN) + інструкція_

**Вхід**

> треба доступ до корп vpn + інструкція як підключитись

**Requester:** olena.marchenko@corp.example · **класифікатор:** `rules`

**Підзапит 1/2:** тип `access_request` · app: `vpn` (усі згадки: ['vpn']) · subject: `self` · confidence 0.80

- **Маршрут:** `AUTO_RESOLVE` · пріоритет P4 · risk 0
- **Дія:** `add_birthright_group` (виконано (SIMULATED))
- **Чому (правила, що спрацювали):**
  - `type:access_request` [policy] — тип запиту = access_request → min `APPROVAL_GATED`. Будь-яка видача доступу за замовчуванням іде через апрув.
  - `multi_intent` [classifier] — 2 підзапити → min `None`. Кожен підзапит маршрутизовано окремо; загальний маршрут = найсуворіший
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Олена Марченко <olena.marchenko@corp.example>: status=active, dept=Marketing, manager=kateryna.shevchenko@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-marketing'], apps=['slack', 'google_workspace', 'onepassword', 'notion']
  - `okta` · GET /users/{id}/groups: не в групі vpn-users; група в allowlist бота

**Підзапит 2/2:** тип `how_to` · app: `vpn` (усі згадки: ['vpn']) · subject: `self` · confidence 0.80

- **Маршрут:** `DOCS_REDIRECT` · пріоритет P4 · risk 0
- **Чому (правила, що спрацювали):**
  - `type:how_to` [policy] — тип запиту = how_to → min `DOCS_REDIRECT`. Питання 'як зробити' — відповідь має бути в KB.
  - `multi_intent` [classifier] — 2 підзапити → min `None`. Кожен підзапит маршрутизовано окремо; загальний маршрут = найсуворіший
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Олена Марченко <olena.marchenko@corp.example>: status=active, dept=Marketing, manager=kateryna.shevchenko@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-marketing'], apps=['slack', 'google_workspace', 'onepassword', 'notion']

**Чернетка відповіді користувачу**

```text
1) треба доступ до корп vpn:
Готово: додав тебе до групи vpn-users (Corporate VPN).
Встанови клієнт VPN, вхід через Okta. Доступ видається автоматично всім активним співробітникам (група vpn-users).
   → Корпоративний VPN: підключення: https://notion.example/iam/vpn-connect

2) інструкція як підключитись:
Встанови клієнт VPN, вхід через Okta. Доступ видається автоматично всім активним співробітникам (група vpn-users).
   → Корпоративний VPN: підключення: https://notion.example/iam/vpn-connect
```

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 91, "sub": 0, "route": "AUTO_RESOLVE", "requester": "olena.marchenko@corp.example", "kind": "action", "action": "add_birthright_group", "params": {"group": "vpn-users", "user": "olena.marchenko@corp.example"}, "would_call": "Okta: PUT /api/v1/groups/{groupId}/users/{userId}  (OAuth scope okta.groups.manage, resource set = allowlisted groups)", "preconditions": {"requester_active_hris": true, "app_birthright": true, "already_has_access": false, "group_allowlisted_for_bot": true}, "idempotency_key": "eafca3198c87d66f"}
```

</details>

---
## #104 → AUTO — бот робить сам

_Чому в вибірці: AUTO: повторний інвайт, апрув уже був зафіксований раніше_

**Вхід**

> інвайт у асану деактивувався поки я дійшла, надішліть ще раз будь ласка

**Requester:** sofia.lysenko@corp.example · **класифікатор:** `rules`

тип `invite_resend` · app: `asana` (усі згадки: ['asana']) · subject: `self` · confidence 0.80

- **Маршрут:** `AUTO_RESOLVE` · пріоритет P4 · risk 0
- **Дія:** `resend_invite` (виконано (SIMULATED))
- **Чому (правила, що спрацювали):**
  - `type:invite_resend` [policy] — тип запиту = invite_resend → min `AUTO_RESOLVE`. Повторний інвайт — кандидат на авто, якщо оригінальний апрув підтверджений.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Софія Лисенко <sofia.lysenko@corp.example>: status=active, dept=Product, manager=vlad.moroz@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-product', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'notion', 'asana']
  - `asana` · GET /workspaces/{id}/memberships + pending invites: інвайт від 2026-09-29, expired=True, approval_ref=APR-2026-0912
  - `approval-log` · lookup approval_ref: апрув APR-2026-0912: subject=sofia.lysenko@corp.example, app=asana, vlad.moroz@corp.example 2026-09-29 via slack_button

**Чернетка відповіді користувачу**

```text
Надіслав інвайт у Asana ще раз (попередній погоджений апрув досі дійсний). Прийми його протягом 7 днів.
```

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 104, "sub": 0, "route": "AUTO_RESOLVE", "requester": "sofia.lysenko@corp.example", "kind": "action", "action": "resend_invite", "params": {}, "would_call": "Asana: POST /workspaces/{gid}/addUser (повтор для вже погодженого approval_ref)", "preconditions": {"requester_active_hris": true, "invite_previously_approved": true}, "idempotency_key": "b8bbcaba13592367"}
```

</details>

---
## #7 → DOCS — перенаправлення в документацію

_Чому в вибірці: DOCS: відповідь існує; LLM схильна порадити апгрейд тарифу — це хибно_

**Вхід**

> питання по лімітах notion api — чи треба нам апати тариф щоб під це вистачило?

**Requester:** alina.vasylenko@corp.example · **класифікатор:** `rules`

тип `policy_question` · app: `notion` (усі згадки: ['notion']) · subject: `self` · confidence 0.80

- **Маршрут:** `DOCS_REDIRECT` · пріоритет P4 · risk 2
- **Чому (правила, що спрацювали):**
  - `type:policy_question` [policy] — тип запиту = policy_question → min `DOCS_REDIRECT`. Питання про правила/ліміти — відповідь має бути в KB.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Аліна Василенко <alina.vasylenko@corp.example>: status=active, dept=Operations, manager=coo@corp.example

**Чернетка відповіді користувачу**

```text
Rate limit Notion API (~3 запити/с на інтеграцію в середньому) однаковий для всіх тарифів — апгрейд плану його не підніме. Рішення — батчинг, черга з ретраями на 429.
   → Notion API: ліміти: https://notion.example/iam/notion-api-limits
```

---
## #51 → REROUTE — не IAM, інша черга

_Чому в вибірці: REROUTE: не IAM (техніка)_

**Вхід**

> У мене зламався монітор, його мій кіт завалив, що робити?

**Requester:** bohdan.zaitsev@corp.example · **класифікатор:** `rules`

тип `not_iam` · app: `—` (усі згадки: —) · subject: `self` · confidence 0.80

- **Маршрут:** `REROUTE` · пріоритет P4 · risk 0
- **Черга:** helpdesk
- **Чому (правила, що спрацювали):**
  - `type:not_iam` [policy] — тип запиту = not_iam → min `REROUTE`. Не IAM — перенаправлення в правильну чергу.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Богдан Зайцев <bohdan.zaitsev@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example

**Чернетка відповіді користувачу**

```text
Це не до IAM — цим займається IT Helpdesk (#it-helpdesk). Я переслав туди твоє повідомлення з посиланням на цей тред.
```

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 51, "sub": 0, "route": "REROUTE", "requester": "bohdan.zaitsev@corp.example", "kind": "reroute", "queue": "helpdesk", "would_call": "Slack: chat.postMessage у канал черги з посиланням на тред"}
```

</details>

---
## #69 → APPROVAL — бот готує, людина апрувить

_Чому в вибірці: Діагностика read-side: доступ зняло Okta group rule після зміни відділу (mover) → повернення лише з апрувом_

**Вхід**

> пропав доступ до tableau, через okta не пускає

**Requester:** maksym.tkachenko@corp.example · **класифікатор:** `rules`

тип `login_diagnostic` · app: `tableau` (усі згадки: ['tableau', 'okta']) · subject: `self` · confidence 0.80

- **Маршрут:** `APPROVAL_GATED` · пріоритет P3 · risk 2
- **Дія:** `readonly_diagnostic` (виконано (SIMULATED))
- **Апрув потрібен від:** resource-owner:data-team-lead, budget-owner
- **Чому (правила, що спрацювали):**
  - `type:login_diagnostic` [policy] — тип запиту = login_diagnostic → min `AUTO_RESOLVE`. Діагностика входу — read-only перевірка журналів, без змін.
  - `regrant_needed` [read] — tableau-viewers знято: Okta Group Rule: dept-analytics → tableau-viewers → min `APPROVAL_GATED`. Діагностика показала, що доступ зняли легітимно (напр. group rule після зміни відділу). Повернення = нова видача → апрув власника.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Максим Ткаченко <maksym.tkachenko@corp.example>: status=active, dept=Marketing, manager=kateryna.shevchenko@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-marketing', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword']
  - `okta` · GET /api/v1/logs?filter=target.alternateId eq "{email}"&since=-72h: 2 подій за 72 год

**Чернетка відповіді користувачу**

```text
Перевірив журнали входу. Доступ знято 2026-10-05 автоматично: «HRIS department changed Analytics → Marketing; rule no longer matches». Це не збій — так спрацював mover-процес. Повернення доступу = нова видача з апрувом власника.
Підготував запит на доступ до Tableau (мінімальна роль: Viewer). Потрібне погодження: власник системи, власник бюджету. Після апруву видам автоматично і напишу тут.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · APPROVAL_GATED · P3 (SLA 1 робочий день)
Автор: maksym.tkachenko@corp.example — верифікований, активний у HRIS; менеджер kateryna.shevchenko@corp.example
Звернення (після redaction): «пропав доступ до tableau, через okta не пускає»

[APPROVAL_GATED P3] пропав доступ до tableau, через okta не пускає
  Розбір: тип login_diagnostic · система tableau · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - regrant_needed [read] → APPROVAL_GATED: Діагностика показала, що доступ зняли легітимно (напр. group rule після зміни відділу). Повернення = нова видача → апрув власника. (tableau-viewers знято: Okta Group Rule: dept-analytics → tableau-viewers)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Максим Ткаченко <maksym.tkachenko@corp.example>: status=active, dept=Marketing, manager=kateryna.shevchenko@corp.example
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-marketing', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword']
    - okta · GET /api/v1/logs?filter=target.alternateId eq "{email}"&since=-72h: 2 подій за 72 год
  Діагноз: Доступ знято 2026-10-05 автоматично: «HRIS department changed Analytics → Marketing; rule no longer matches». Це не збій — так спрацював mover-процес. Повернення доступу = нова видача з апрувом власника.
  Апрувери: resource-owner:data-team-lead, budget-owner

Що потрібно від тебе: Апрувер: погодити або відхилити конкретну зміну нижче. Після апруву бот виконає dry-run план і перевірить результат читанням.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 69, "sub": 0, "route": "APPROVAL_GATED", "requester": "maksym.tkachenko@corp.example", "kind": "action", "action": "readonly_diagnostic", "params": {}, "would_call": "Okta: GET /api/v1/logs (read-only)", "preconditions": {"requester_active_hris": true}, "idempotency_key": "d19fe321b97abf6f"}
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 69, "sub": 0, "route": "APPROVAL_GATED", "requester": "maksym.tkachenko@corp.example", "kind": "approval_request", "status": "pending", "app": "tableau", "approvers": ["resource-owner:data-team-lead", "budget-owner"], "would_call": "Slack: chat.postMessage (Block Kit: Approve/Deny, TTL 72h) → approver DM", "on_approve": "виконати dry-run план → підтвердити read-side, що зміна застосована"}
```

</details>

---
## #42 → SECURITY — інцидент / пейдж

_Чому в вибірці: Діагностика read-side: 'проблеми по вечорах' = блокування акаунта через спроби входу з Tor → SECURITY_

**Вхід**

> вчора ввечері не міг зайти, сьогодні теж дивно. подивіться що з моїм доступом, бо проблеми тільки по вечорах

**Requester:** roman.hnatiuk@corp.example · **класифікатор:** `rules`

тип `login_diagnostic` · app: `—` (усі згадки: —) · subject: `self` · confidence 0.80

- **Маршрут:** `SECURITY_ESCALATION` · пріоритет P1 · risk 2
- **Дія:** `readonly_diagnostic` (виконано (SIMULATED))
- **Черга:** security
- **Чому (правила, що спрацювали):**
  - `type:login_diagnostic` [policy] — тип запиту = login_diagnostic → min `AUTO_RESOLVE`. Діагностика входу — read-only перевірка журналів, без змін.
  - `suspicious_auth_activity` [read] — 4 невдалих входів з ['185.220.101.44'] + 2 блокувань акаунта, усі ввечері → min `SECURITY_ESCALATION`. Read-side (Okta System Log): серія невдалих входів / блокування з підозрілих IP. Це не 'глюк доступу', а можлива атака на акаунт.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Роман Гнатюк <roman.hnatiuk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']
  - `okta` · GET /api/v1/logs?filter=target.alternateId eq "{email}"&since=-72h: 7 подій за 72 год

**Чернетка відповіді користувачу**

```text
Подивився журнали: твій акаунт блокується через серію невдалих спроб входу не з твоїх пристроїв. Передав у security (P1). Поки що: не підтверджуй push-запити Okta Verify, яких ти не ініціював, і чекай повідомлення від security щодо зміни пароля.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · SECURITY_ESCALATION · P1 (SLA 1 год)
Автор: roman.hnatiuk@corp.example — верифікований, активний у HRIS; менеджер creative-lead@corp.example
Звернення (після redaction): «вчора ввечері не міг зайти, сьогодні теж дивно. подивіться що з моїм доступом, бо проблеми тільки по вечорах»

[SECURITY_ESCALATION P1] вчора ввечері не міг зайти, сьогодні теж дивно. подивіться що з моїм доступом, бо проблеми тільки по вечорах
  Розбір: тип login_diagnostic · система не визначена · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - suspicious_auth_activity [read] → SECURITY_ESCALATION: Read-side (Okta System Log): серія невдалих входів / блокування з підозрілих IP. Це не 'глюк доступу', а можлива атака на акаунт. (4 невдалих входів з ['185.220.101.44'] + 2 блокувань акаунта, усі ввечері)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Роман Гнатюк <roman.hnatiuk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']
    - okta · GET /api/v1/logs?filter=target.alternateId eq "{email}"&since=-72h: 7 подій за 72 год
  Діагноз: Акаунт блокується ввечері через серію невдалих входів з IP, що не належить користувачу (185.220.101.44, Tor). Користувач бачить наслідок (LOCKED_OUT), а не причину.

Що потрібно від тебе: Security triage: оцінити інцидент і стримати (ротація, блокування). Бот нічого не змінював.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 42, "sub": 0, "route": "SECURITY_ESCALATION", "requester": "roman.hnatiuk@corp.example", "kind": "action", "action": "readonly_diagnostic", "params": {}, "would_call": "Okta: GET /api/v1/logs (read-only)", "preconditions": {"requester_active_hris": true}, "idempotency_key": "677e06c4cd43d1dc"}
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 42, "sub": 0, "route": "SECURITY_ESCALATION", "requester": "roman.hnatiuk@corp.example", "kind": "escalation", "queue": "security", "priority": "P1", "reasons": ["type:login_diagnostic", "suspicious_auth_activity"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call + PagerDuty"}
```

</details>

---
## #5 → NEED_INFO — уточнення

_Чому в вибірці: 'лід в курсі' ≠ апрув; модель не вказана → NEED_INFO → APPROVAL_

**Вхід**

> треба згенерити новий api-ключ до однієї ai-моделі, це для локалізації, лід в курсі

**Requester:** dmytro.savchuk@corp.example · **класифікатор:** `rules`

тип `api_key_request` · app: `—` (усі згадки: —) · subject: `self` · confidence 0.80

- **Маршрут:** `NEED_INFO` → далі `APPROVAL_GATED` · пріоритет P3 · risk 3
- **Апрув потрібен від:** manager:oksana.melnyk@corp.example
- **Чому (правила, що спрацювали):**
  - `type:api_key_request` [policy] — тип запиту = api_key_request → min `APPROVAL_GATED`. API-ключ = секрет з білінгом: апрув ліда + власника платформи, видача через 1Password.
  - `unverified_approval_claim` [text] — regex 'лід в курсі' → «лід в курсі» → min `APPROVAL_GATED`. 'Лід в курсі' у тексті ≠ апрув. Апрув фіксується лише дією апрувера в системі.
  - `missing_critical_data` [text] — конкретна система/модель не названа → min `NEED_INFO`. Немає ключових даних (app / суб'єкт / список людей / скоуп). Не вгадуємо.
  - `unknown_app` [catalog] — жодна згадка не змаплена на каталог → min `NEED_INFO`. App не змаплено на каталог. Не вгадуємо entitlement.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Дмитро Савчук <dmytro.savchuk@corp.example>: status=active, dept=Localization, manager=oksana.melnyk@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-localization', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'ai_dubbing_tool']

**Чернетка відповіді користувачу**

```text
Щоб обробити запит, мені бракує кількох деталей:
• Яка саме модель/тула/продукт (точна назва або посилання)?
• Для якої команди і задачі ключ, хто буде його власником, який місячний spend limit поставити?
Як тільки уточниш — сформую запит на апрув (твій лід).
P.S. Погодження в тексті повідомлення не рахується — апрувер отримає кнопку в Slack.
```

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 5, "sub": 0, "route": "NEED_INFO", "requester": "dmytro.savchuk@corp.example", "kind": "approval_request", "status": "blocked_on_info", "app": null, "approvers": ["manager:oksana.melnyk@corp.example"], "would_call": "Slack: chat.postMessage (Block Kit: Approve/Deny, TTL 72h) → approver DM", "on_approve": "виконати dry-run план → підтвердити read-side, що зміна застосована"}
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 5, "sub": 0, "route": "NEED_INFO", "requester": "dmytro.savchuk@corp.example", "kind": "clarification", "questions": ["Яка саме модель/тула/продукт (точна назва або посилання)?", "Для якої команди і задачі ключ, хто буде його власником, який місячний spend limit поставити?"], "would_call": "Slack: chat.postMessage(thread_ts) — бот чекає відповідь і перезапускає triage"}
```

</details>

---
## #95 → DOCS — перенаправлення в документацію

_Чому в вибірці: Скидання пароля + терміновість → тільки self-service, жодного reset через чат_

**Вхід**

> у нас сьогодні лонч і мене вибило, терміново треба скинути пароль!!

**Requester:** yulia.petrenko@corp.example · **класифікатор:** `rules`

тип `credential_reset` · app: `—` (усі згадки: —) · subject: `self` · confidence 0.80

- **Маршрут:** `DOCS_REDIRECT` · пріоритет P4 · risk 2
- **Чому (правила, що спрацювали):**
  - `type:credential_reset` [policy] — тип запиту = credential_reset → min `DOCS_REDIRECT`. Скидання облікових даних — тільки self-service, не через чат.
  - `credential_reset` [text] — regex 'скин\w* пароль' → «скинути пароль» → min `DOCS_REDIRECT`. Скидання пароля/MFA через чат — вектор атаки на хелпдеск. Тільки Okta self-service або верифікація особи людиною.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Юлія Петренко <yulia.petrenko@corp.example>: status=active, dept=Product, manager=vlad.moroz@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-product', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword']

**Чернетка відповіді користувачу**

```text
Пароль скидається самостійно через «Forgot password?» на сторінці входу Okta з підтвердженням через Okta Verify. Якщо Okta Verify втрачено — тільки через верифікацію особи з IT (відеодзвінок), не через чат.
   → Скидання пароля / MFA в Okta (self-service): https://notion.example/iam/okta-self-service-reset
```

---
## #46 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Mirror access 'все що у ліда' + апрувер у відпустці (за HRIS, не за текстом)_

**Вхід**

> не розумію які доступи мені треба - документи, драйв, api… мій лід у відпустці, а мені треба асап у одну задачу підключитись. можеш все видати, що у ліда було?

**Requester:** taras.bondar@corp.example · **класифікатор:** `rules`

тип `access_request` · app: `google_workspace` (усі згадки: ['google_workspace']) · subject: `self` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P2 · risk 6
- **Апрув потрібен від:** manager:iryna.kravets@corp.example (НЕДОСТУПНИЙ), budget-owner
- **Чому (правила, що спрацювали):**
  - `type:access_request` [policy] — тип запиту = access_request → min `APPROVAL_GATED`. Будь-яка видача доступу за замовчуванням іде через апрув.
  - `mirror_access` [text] — regex 'що у (ліда|нього|неї|колеги) було' → «що у ліда було» → min `HUMAN_REVIEW`. 'Дай як у X' — копіювання прав = over-granting. Права видаються під задачу, не під людину.
  - `broad_scope` [text] — regex 'все видати' → «все видати» → min `HUMAN_REVIEW`. Широкий скоуп ('всі', 'на всіх спейсах', 'повний пакет') — розбиваємо на мінімальні entitlement'и вручну.
  - `approver_unavailable` [read] — менеджер requester'а у відпустці за HRIS, делегата немає → min `HUMAN_REVIEW`. Апрувер недоступний (за HRIS — відпустка). Делегат має бути визначений людиною, не ботом.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Тарас Бондар <taras.bondar@corp.example>: status=active, dept=Analytics, manager=iryna.kravets@corp.example
  - `hris` · GET /employees/{manager}/time-off: менеджер Ірина Кравець у відпустці 2026-10-01..2026-10-14, делегат: не призначений
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-analytics', 'vpn-users', 'tableau-viewers'], apps=['slack', 'google_workspace', 'onepassword', 'tableau']

**Чернетка відповіді користувачу**

```text
Передав запит IAM-інженеру. Доступи видаємо під конкретну задачу, а не «як у колеги» — так менше зайвих прав. Відповідь буде в цьому треді. Пріоритет: P2.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P2 (SLA 4 год)
Автор: taras.bondar@corp.example — верифікований, активний у HRIS; менеджер iryna.kravets@corp.example (недоступний за HRIS)
Звернення (після redaction): «не розумію які доступи мені треба - документи, драйв, api… мій лід у відпустці, а мені треба асап у одну задачу підключитись. можеш все видати, що у ліда було?»

[HUMAN_REVIEW P2] не розумію які доступи мені треба - документи, драйв, api… мій лід у відпустці, а мені треба асап у одну задачу підключитись. можеш все видати, що у ліда було?
  Розбір: тип access_request · система google_workspace · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - type:access_request [policy] → APPROVAL_GATED: Будь-яка видача доступу за замовчуванням іде через апрув. (тип запиту = access_request)
    - mirror_access [text] → HUMAN_REVIEW: 'Дай як у X' — копіювання прав = over-granting. Права видаються під задачу, не під людину. (regex 'що у (ліда|нього|неї|колеги) було' → «що у ліда було»)
    - broad_scope [text] → HUMAN_REVIEW: Широкий скоуп ('всі', 'на всіх спейсах', 'повний пакет') — розбиваємо на мінімальні entitlement'и вручну. (regex 'все видати' → «все видати»)
    - approver_unavailable [read] → HUMAN_REVIEW: Апрувер недоступний (за HRIS — відпустка). Делегат має бути визначений людиною, не ботом. (менеджер requester'а у відпустці за HRIS, делегата немає)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Тарас Бондар <taras.bondar@corp.example>: status=active, dept=Analytics, manager=iryna.kravets@corp.example
    - hris · GET /employees/{manager}/time-off: менеджер Ірина Кравець у відпустці 2026-10-01..2026-10-14, делегат: не призначений
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-analytics', 'vpn-users', 'tableau-viewers'], apps=['slack', 'google_workspace', 'onepassword', 'tableau']
  Апрувери: manager:iryna.kravets@corp.example (НЕДОСТУПНИЙ), budget-owner

Що потрібно від тебе: Вирішити: видати / звузити / відмовити — і виконати самому. Бот нічого не змінюватиме навіть після апруву (HUMAN-ONLY).
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 46, "sub": 0, "route": "HUMAN_REVIEW", "requester": "taras.bondar@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P2", "reasons": ["type:access_request", "mirror_access", "broad_scope", "approver_unavailable"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>

---
## #75 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Обхід HRIS: 'у HRM ще не внесли' + 'повний пакет' + асап_

**Вхід**

> виходить нова людина, це неплановий вихід, у HRM ще не внести, налаштуйте асап повний пакет доступів

**Requester:** vlad.moroz@corp.example · **класифікатор:** `rules`

тип `onboarding` · app: `—` (усі згадки: ['hris']) · subject: `other` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P2 · risk 5
- **Апрув потрібен від:** manager:cpo@corp.example
- **Чому (правила, що спрацювали):**
  - `type:onboarding` [policy] — тип запиту = onboarding → min `HUMAN_REVIEW`. Пакет доступів для нової людини — лише після запису в HRIS, вирішує людина.
  - `hris_bypass` [text] — regex '(hrm|hris|hr-систем)\w*\s+ще не' → «hrm ще не» → min `HUMAN_REVIEW`. Запит обходить HRIS як джерело правди (людини ще немає в HRM). Класичний вектор соціальної інженерії + сироти-акаунти.
  - `broad_scope` [text] — regex 'повний пакет' → «повний пакет» → min `HUMAN_REVIEW`. Широкий скоуп ('всі', 'на всіх спейсах', 'повний пакет') — розбиваємо на мінімальні entitlement'и вручну.
  - `on_behalf` [text] — regex 'нова людина' → «нова людина» → min `HUMAN_REVIEW`. Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6).
  - `missing_critical_data` [text] — ім'я/email людини, для якої запит → min `NEED_INFO`. Немає ключових даних (app / суб'єкт / список людей / скоуп). Не вгадуємо.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Влад Мороз <vlad.moroz@corp.example>: status=active, dept=Product, manager=cpo@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-product', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword']
  - `hris` · GET /employees?start_date>=today-7: суб'єкта (нову людину) не можна знайти в HRIS — ім'я не вказане, запису немає; перевірити неможливо

**Чернетка відповіді користувачу**

```text
Передав запит IAM-інженеру. Доступи новим людям видаються після появи запису в HR-системі — так вони коректно і відкличуться. Відповідь буде в цьому треді. Пріоритет: P2.
Щоб інженер міг одразу взятися, напиши тут:
• Для кого запит (ім'я та корпоративний email)?
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P2 (SLA 4 год)
Автор: vlad.moroz@corp.example — верифікований, активний у HRIS; менеджер cpo@corp.example
Звернення (після redaction): «виходить нова людина, це неплановий вихід, у HRM ще не внести, налаштуйте асап повний пакет доступів»

[HUMAN_REVIEW P2] виходить нова людина, це неплановий вихід, у HRM ще не внести, налаштуйте асап повний пакет доступів
  Розбір: тип onboarding · система не визначена · суб'єкт other · впевненість 0.80 · rules
  Чому не авто:
    - type:onboarding [policy] → HUMAN_REVIEW: Пакет доступів для нової людини — лише після запису в HRIS, вирішує людина. (тип запиту = onboarding)
    - hris_bypass [text] → HUMAN_REVIEW: Запит обходить HRIS як джерело правди (людини ще немає в HRM). Класичний вектор соціальної інженерії + сироти-акаунти. (regex '(hrm|hris|hr-систем)\w*\s+ще не' → «hrm ще не»)
    - broad_scope [text] → HUMAN_REVIEW: Широкий скоуп ('всі', 'на всіх спейсах', 'повний пакет') — розбиваємо на мінімальні entitlement'и вручну. (regex 'повний пакет' → «повний пакет»)
    - on_behalf [text] → HUMAN_REVIEW: Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6). (regex 'нова людина' → «нова людина»)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Влад Мороз <vlad.moroz@corp.example>: status=active, dept=Product, manager=cpo@corp.example
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-product', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword']
    - hris · GET /employees?start_date>=today-7: суб'єкта (нову людину) не можна знайти в HRIS — ім'я не вказане, запису немає; перевірити неможливо
  Апрувери: manager:cpo@corp.example
  Бот уже запитав автора: Для кого запит (ім'я та корпоративний email)?

Що потрібно від тебе: Дочекатися запису в HRIS і зібрати мінімальний набір під роль; «повний пакет» не видавати.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 75, "sub": 0, "route": "HUMAN_REVIEW", "requester": "vlad.moroz@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P2", "reasons": ["type:onboarding", "hris_bypass", "broad_scope", "on_behalf", "missing_critical_data"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>

---
## #92 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Offboarding: HRIS не підтверджує звільнення → конфлікт джерел; бот будує dry-run план, але не виконує_

**Вхід**

> терміново заблокуйте всі доступи співробітнику — сьогодні останній день, деталі в тред

> _тред:_ Андрій Коваль (andrii.koval@corp.example), сьогодні останній день, заблокуйте все до кінця дня

**Requester:** kateryna.shevchenko@corp.example · **класифікатор:** `rules`

тип `offboarding` · app: `—` (усі згадки: —) · subject: `other` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P1 · risk 4
- **Чому (правила, що спрацювали):**
  - `type:offboarding` [policy] — тип запиту = offboarding → min `HUMAN_REVIEW`. Деструктивна дія — лише людина після підтвердження HR.
  - `offboarding` [text] — regex 'останній день' → «останній день» → min `HUMAN_REVIEW`. Деструктивна і термінова дія. Потрібне підтвердження з HRIS (status/termination date). Бот готує dry-run план відкликання по всіх джерелах.
  - `on_behalf` [text] — regex 'співробітнику' → «співробітнику» → min `HUMAN_REVIEW`. Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6).
  - `source_conflict` [read] — звернення каже 'останній день', HRIS: active без termination_date → min `HUMAN_REVIEW`. Джерела суперечать одне одному (напр. Okta active, HRIS terminated). Немає SoT → рішення за людиною.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Катерина Шевченко <kateryna.shevchenko@corp.example>: status=active, dept=Marketing, manager=cmo@corp.example
  - `hris` · GET /employees?email=: subject Андрій Коваль: status=active, termination_date=None
  - `okta` · GET /users/{id}/appLinks, /groups: SSO apps=['slack', 'google_workspace', 'onepassword', 'market_intel_remote_env', 'tableau', 'claude_org'], groups=['everyone', 'dept-marketing', 'vpn-users', 'meta-bm-analysts', 'market-intel-vdi']
  - `1password` · SCIM bridge: group memberships: vaults=['Marketing-Shared', 'Market-Intel-Tools', 'Meta-Ads-Billing']
  - `gws` · Directory API users.get + Reports API token audit: groups=['marketing@', 'ads-alerts@'], owned_files=412, third-party OAuth=['Make', 'Unknown Chrome extension (drive.readonly)']

**Чернетка відповіді користувачу**

```text
Передав запит IAM-інженеру. Блокування доступів робимо після підтвердження від HR, щоб не заблокувати не ту людину. Відповідь буде в цьому треді. Пріоритет: P1.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P1 (SLA 1 год)
Автор: kateryna.shevchenko@corp.example — верифікований, активний у HRIS; менеджер cmo@corp.example
Звернення (після redaction): «терміново заблокуйте всі доступи співробітнику — сьогодні останній день, деталі в тред»

[HUMAN_REVIEW P1] терміново заблокуйте всі доступи співробітнику — сьогодні останній день, деталі в тред
  Розбір: тип offboarding · система не визначена · суб'єкт other · впевненість 0.80 · rules
  Чому не авто:
    - type:offboarding [policy] → HUMAN_REVIEW: Деструктивна дія — лише людина після підтвердження HR. (тип запиту = offboarding)
    - offboarding [text] → HUMAN_REVIEW: Деструктивна і термінова дія. Потрібне підтвердження з HRIS (status/termination date). Бот готує dry-run план відкликання по всіх джерелах. (regex 'останній день' → «останній день»)
    - on_behalf [text] → HUMAN_REVIEW: Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6). (regex 'співробітнику' → «співробітнику»)
    - source_conflict [read] → HUMAN_REVIEW: Джерела суперечать одне одному (напр. Okta active, HRIS terminated). Немає SoT → рішення за людиною. (звернення каже 'останній день', HRIS: active без termination_date)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Катерина Шевченко <kateryna.shevchenko@corp.example>: status=active, dept=Marketing, manager=cmo@corp.example
    - hris · GET /employees?email=: subject Андрій Коваль: status=active, termination_date=None
    - okta · GET /users/{id}/appLinks, /groups: SSO apps=['slack', 'google_workspace', 'onepassword', 'market_intel_remote_env', 'tableau', 'claude_org'], groups=['everyone', 'dept-marketing', 'vpn-users', 'meta-bm-analysts', 'market-intel-vdi']
    - 1password · SCIM bridge: group memberships: vaults=['Marketing-Shared', 'Market-Intel-Tools', 'Meta-Ads-Billing']
    - gws · Directory API users.get + Reports API token audit: groups=['marketing@', 'ads-alerts@'], owned_files=412, third-party OAuth=['Make', 'Unknown Chrome extension (drive.readonly)']
  Діагноз: HRIS не підтверджує звільнення — або HR ще не вніс, або запит некоректний/зловмисний. Без підтвердження HR деструктивні дії не виконуються.
  Dry-run план (НЕ виконано):
    - okta: POST /api/v1/users/{id}/lifecycle/suspend → припинить SSO-доступ до 6 apps; сесії — DELETE /users/{id}/sessions
    - 1password: SCIM: deactivate user → доступ до vaults ['Marketing-Shared', 'Market-Intel-Tools', 'Meta-Ads-Billing'] закриється; АЛЕ секрети в shared vaults, які людина бачила, треба ротувати (рішення власників)
    - google_workspace: users.update(suspended=true) + Data Transfer API → передати 412 файлів менеджеру; відкликати OAuth-токени ['Make', 'Unknown Chrome extension (drive.readonly)']
    - non-SSO SaaS (manual): — → за назвами vaults ['Market-Intel-Tools', 'Meta-Ads-Billing'] людина ймовірно має локальні акаунти/спільні креди поза Okta — список неповний, перевірка вручну

Що потрібно від тебе: Підтвердити звільнення з HR (дата, людина) і виконати план відкликання вручну за dry-run планом нижче; ротацію секретів зі спільних vault-ів — власникам. Нічого не робити, доки HRIS не підтверджує.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 92, "sub": 0, "route": "HUMAN_REVIEW", "requester": "kateryna.shevchenko@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P1", "reasons": ["type:offboarding", "offboarding", "on_behalf", "source_conflict"], "dry_run_plan_for_human": [{"system": "okta", "would_call": "POST /api/v1/users/{id}/lifecycle/suspend", "effect": "припинить SSO-доступ до 6 apps; сесії — DELETE /users/{id}/sessions"}, {"system": "1password", "would_call": "SCIM: deactivate user", "effect": "доступ до vaults ['Marketing-Shared', 'Market-Intel-Tools', 'Meta-Ads-Billing'] закриється; АЛЕ секрети в shared vaults, які людина бачила, треба ротувати (рішення власників)"}, {"system": "google_workspace", "would_call": "users.update(suspended=true) + Data Transfer API", "effect": "передати 412 файлів менеджеру; відкликати OAuth-токени ['Make', 'Unknown Chrome extension (drive.readonly)']"}, {"system": "non-SSO SaaS (manual)", "would_call": "—", "effect": "за назвами vaults ['Market-Intel-Tools', 'Meta-Ads-Billing'] людина ймовірно має локальні акаунти/спільні креди поза Okta — список неповний, перевірка вручну"}], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>

---
## #32 → SECURITY — інцидент / пейдж

_Чому в вибірці: Секрет у треді → редакція до LLM; бот відмовляється 'видалити нотатку', бо це не відкликає ключ_

**Вхід**

> асап!! видаліть будь ласка нотатку в 1password зі старим api-ключем рекламної платформи, він скомпрометований

> _тред:_ ось цей ключ: [REDACTED:anthropic_api_key], валявся в публічному репо

**Secret scanner до LLM:** знайдено `['anthropic_api_key']` → у LLM і логи пішов `[REDACTED]`.

**Requester:** nadia.romanenko@corp.example · **класифікатор:** `rules`

тип `secret_incident` · app: `onepassword` (усі згадки: ['onepassword']) · subject: `self` · confidence 0.80

- **Маршрут:** `SECURITY_ESCALATION` · пріоритет P1 · risk 6
- **Черга:** security
- **Чому (правила, що спрацювали):**
  - `type:secret_incident` [policy] — тип запиту = secret_incident → min `SECURITY_ESCALATION`. Робота з скомпрометованими секретами — завжди security.
  - `secret_compromise` [text] — regex 'скомпрометов' → «скомпрометов» → min `SECURITY_ESCALATION`. Скомпрометований секрет → спершу revoke/rotate у провайдера, потім розслідування. Видалення запису у 1Password НЕ відкликає ключ і знищує слід.
  - `secret_in_message` [text] — secret scanner: ['anthropic_api_key'] → min `SECURITY_ESCALATION`. Секрет опубліковано у повідомленні/треді Slack → вважаємо скомпрометованим: видалити повідомлення, ротувати. До LLM текст пішов уже відредагованим.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Надія Романенко <nadia.romanenko@corp.example>: status=active, dept=Performance Marketing, manager=cmo@corp.example

**Чернетка відповіді користувачу**

```text
Передав у security з пріоритетом P1. Важливо: видалення нотатки в 1Password НЕ відкликає ключ — його треба відкликати у провайдера і випустити новий, цим зараз займеться security. Нотатку поки не чіпай (вона потрібна для розслідування), і не пересилай ключ у чати — якщо він є в цьому треді, я його приховав, а повідомлення варто видалити.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · SECURITY_ESCALATION · P1 (SLA 1 год)
Автор: nadia.romanenko@corp.example — верифікований, активний у HRIS; менеджер cmo@corp.example
Звернення (після redaction): «асап!! видаліть будь ласка нотатку в 1password зі старим api-ключем рекламної платформи, він скомпрометований»

[SECURITY_ESCALATION P1] асап!! видаліть будь ласка нотатку в 1password зі старим api-ключем рекламної платформи, він скомпрометований
  Розбір: тип secret_incident · система onepassword · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - type:secret_incident [policy] → SECURITY_ESCALATION: Робота з скомпрометованими секретами — завжди security. (тип запиту = secret_incident)
    - secret_compromise [text] → SECURITY_ESCALATION: Скомпрометований секрет → спершу revoke/rotate у провайдера, потім розслідування. Видалення запису у 1Password НЕ відкликає ключ і знищує слід. (regex 'скомпрометов' → «скомпрометов»)
    - secret_in_message [text] → SECURITY_ESCALATION: Секрет опубліковано у повідомленні/треді Slack → вважаємо скомпрометованим: видалити повідомлення, ротувати. До LLM текст пішов уже відредагованим. (secret scanner: ['anthropic_api_key'])
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Надія Романенко <nadia.romanenko@corp.example>: status=active, dept=Performance Marketing, manager=cmo@corp.example

Що потрібно від тебе: Security triage: оцінити інцидент і стримати (ротація, блокування). Бот нічого не змінював.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 32, "sub": 0, "route": "SECURITY_ESCALATION", "requester": "nadia.romanenko@corp.example", "kind": "escalation", "queue": "security", "priority": "P1", "reasons": ["type:secret_incident", "secret_compromise", "secret_in_message"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call + PagerDuty"}
```

</details>

---
## #85 → SECURITY — інцидент / пейдж

_Чому в вибірці: Не IAM, але High-знахідка → SECURITY, не 'не до нас'_

**Вхід**

> прийшов звіт від пентестерів, там High-знахідка по одному з продуктів — треба подивитись

**Requester:** ihor.kostenko@corp.example · **класифікатор:** `rules`

тип `not_iam` · app: `—` (усі згадки: —) · subject: `self` · confidence 0.80

- **Маршрут:** `SECURITY_ESCALATION` · пріоритет P1 · risk 1
- **Черга:** security
- **Чому (правила, що спрацювали):**
  - `type:not_iam` [policy] — тип запиту = not_iam → min `REROUTE`. Не IAM — перенаправлення в правильну чергу.
  - `security_finding` [text] — regex 'пентест' → «пентест» → min `SECURITY_ESCALATION`. Знахідка пентесту/вразливість — не IAM-тікет, але не можна загубити. Негайно в security.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Ігор Костенко <ihor.kostenko@corp.example>: status=active, dept=Engineering, manager=cto@corp.example

**Чернетка відповіді користувачу**

```text
Це не IAM-запит, але важливий: передав у security з пріоритетом P1. Будь ласка, не пересилай звіт пентесту у відкриті канали — тільки в #security-incidents.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · SECURITY_ESCALATION · P1 (SLA 1 год)
Автор: ihor.kostenko@corp.example — верифікований, активний у HRIS; менеджер cto@corp.example
Звернення (після redaction): «прийшов звіт від пентестерів, там High-знахідка по одному з продуктів — треба подивитись»

[SECURITY_ESCALATION P1] прийшов звіт від пентестерів, там High-знахідка по одному з продуктів — треба подивитись
  Розбір: тип not_iam · система не визначена · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - security_finding [text] → SECURITY_ESCALATION: Знахідка пентесту/вразливість — не IAM-тікет, але не можна загубити. Негайно в security. (regex 'пентест' → «пентест»)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Ігор Костенко <ihor.kostenko@corp.example>: status=active, dept=Engineering, manager=cto@corp.example

Що потрібно від тебе: Security triage: оцінити інцидент і стримати (ротація, блокування). Бот нічого не змінював.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 85, "sub": 0, "route": "SECURITY_ESCALATION", "requester": "ihor.kostenko@corp.example", "kind": "escalation", "queue": "security", "priority": "P1", "reasons": ["type:not_iam", "security_finding"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call + PagerDuty"}
```

</details>

---
## #26 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Експорт PII (телефони) з Business Manager → HUMAN, бот не допомагає вивантажувати_

**Вхід**

> не знаю, чи це до тебе, але треба вивантажити списки людей з business manager і їх контакти (номера телефонів чи щось таке) для звірки, можеш допомогти

**Requester:** serhii.lytvyn@corp.example · **класифікатор:** `rules`

тип `data_export` · app: `meta_business_manager` (усі згадки: ['meta_business_manager']) · subject: `self` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P3 · risk 3
- **Чому (правила, що спрацювали):**
  - `type:data_export` [policy] — тип запиту = data_export → min `HUMAN_REVIEW`. Вивантаження даних — потрібна правова підстава і власник даних.
  - `pii_request` [text] — regex 'номер\w* телефон' → «номера телефон» → min `HUMAN_REVIEW`. Запит персональних даних (контакти, HR-статус, ID). Бот не розкриває PII; потрібна правова підстава.
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Сергій Литвин <serhii.lytvyn@corp.example>: status=active, dept=Performance Marketing, manager=cmo@corp.example

**Чернетка відповіді користувачу**

```text
Передав запит IAM-інженеру. Персональні дані співробітників/контактів ми не вивантажуємо через бот. Відповідь буде в цьому треді.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P3 (SLA 1 робочий день)
Автор: serhii.lytvyn@corp.example — верифікований, активний у HRIS; менеджер cmo@corp.example
Звернення (після redaction): «не знаю, чи це до тебе, але треба вивантажити списки людей з business manager і їх контакти (номера телефонів чи щось таке) для звірки, можеш допомогти»

[HUMAN_REVIEW P3] не знаю, чи це до тебе, але треба вивантажити списки людей з business manager і їх контакти (номера телефонів чи щось таке) для звірки, можеш допомогти
  Розбір: тип data_export · система meta_business_manager · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - type:data_export [policy] → HUMAN_REVIEW: Вивантаження даних — потрібна правова підстава і власник даних. (тип запиту = data_export)
    - pii_request [text] → HUMAN_REVIEW: Запит персональних даних (контакти, HR-статус, ID). Бот не розкриває PII; потрібна правова підстава. (regex 'номер\w* телефон' → «номера телефон»)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Сергій Литвин <serhii.lytvyn@corp.example>: status=active, dept=Performance Marketing, manager=cmo@corp.example

Що потрібно від тебе: Перевірити правову підставу й мінімізацію даних; без них — відмова. Бот PII не вивантажує.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 26, "sub": 0, "route": "HUMAN_REVIEW", "requester": "serhii.lytvyn@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P3", "reasons": ["type:data_export", "pii_request"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>

---
## #12 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Зміна org-wide політики безпеки заради зручності → HUMAN/security_

**Вхід**

> хочу ввімкнути always-allow для mcp-конекторів у клоді, так зручніше. можеш включити, бо там адміну організації це треба зробити

**Requester:** pavlo.danylenko@corp.example · **класифікатор:** `rules`

тип `security_policy_change` · app: `claude_org` (усі згадки: ['claude_org']) · subject: `self` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P3 · risk 3
- **Чому (правила, що спрацювали):**
  - `type:security_policy_change` [policy] — тип запиту = security_policy_change → min `HUMAN_REVIEW`. Зміни org-wide політики — рішення security.
  - `security_policy_change` [text] — regex 'always-allow' → «always-allow» → min `HUMAN_REVIEW`. Зміна org-wide політики безпеки (напр. always-allow для MCP) — рішення security, не тікет.
  - `third_party_connector` [text] — regex 'конектор' → «конектор» → min `HUMAN_REVIEW`. Новий конектор/інтеграція = новий потік даних назовні. Потрібен security review (scope токенів, де зберігаються дані).
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Павло Даниленко <pavlo.danylenko@corp.example>: status=active, dept=Engineering, manager=cto@corp.example

**Чернетка відповіді користувачу**

```text
Передав запит IAM-інженеру. Це зміна безпекової політики для всієї організації — її розглядає security. Відповідь буде в цьому треді.
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P3 (SLA 1 робочий день)
Автор: pavlo.danylenko@corp.example — верифікований, активний у HRIS; менеджер cto@corp.example
Звернення (після redaction): «хочу ввімкнути always-allow для mcp-конекторів у клоді, так зручніше. можеш включити, бо там адміну організації це треба зробити»

[HUMAN_REVIEW P3] хочу ввімкнути always-allow для mcp-конекторів у клоді, так зручніше. можеш включити, бо там адміну організації це треба зробити
  Розбір: тип security_policy_change · система claude_org · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - type:security_policy_change [policy] → HUMAN_REVIEW: Зміни org-wide політики — рішення security. (тип запиту = security_policy_change)
    - security_policy_change [text] → HUMAN_REVIEW: Зміна org-wide політики безпеки (напр. always-allow для MCP) — рішення security, не тікет. (regex 'always-allow' → «always-allow»)
    - third_party_connector [text] → HUMAN_REVIEW: Новий конектор/інтеграція = новий потік даних назовні. Потрібен security review (scope токенів, де зберігаються дані). (regex 'конектор' → «конектор»)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Павло Даниленко <pavlo.danylenko@corp.example>: status=active, dept=Engineering, manager=cto@corp.example

Що потрібно від тебе: Рішення security щодо зміни org-політики; за замовчуванням — ні.
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 12, "sub": 0, "route": "HUMAN_REVIEW", "requester": "pavlo.danylenko@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P3", "reasons": ["type:security_policy_change", "security_policy_change", "third_party_connector"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>

---
## #29 → HUMAN — рішення за IAM-інженером

_Чому в вибірці: Multi-intent: проблема з ліцензією + інвайт новенької колеги (on-behalf, без імені)_

**Вхід**

> у мене не працює adobe creative cloud, щось з підпискою. і ще треба інвайт закинути моїй колезі новенькій, зробиш?

**Requester:** marta.oliinyk@corp.example · **класифікатор:** `rules`

**Підзапит 1/2:** тип `license_issue` · app: `adobe_cc` (усі згадки: ['adobe_cc']) · subject: `self` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P3 · risk 1
- **Чому (правила, що спрацювали):**
  - `type:license_issue` [policy] — тип запиту = license_issue → min `HUMAN_REVIEW`. Збій ліцензії: потрібна перевірка в admin console вендора — read-side конектора в прототипі немає.
  - `multi_intent` [classifier] — 2 підзапити → min `None`. Кожен підзапит маршрутизовано окремо; загальний маршрут = найсуворіший
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Марта Олійник <marta.oliinyk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']

**Підзапит 2/2:** тип `access_request` · app: `adobe_cc` (усі згадки: ['adobe_cc']) · subject: `other` · confidence 0.80

- **Маршрут:** `HUMAN_REVIEW` · пріоритет P3 · risk 2
- **Апрув потрібен від:** manager:creative-lead@corp.example, budget-owner
- **Чому (правила, що спрацювали):**
  - `type:access_request` [policy] — тип запиту = access_request → min `APPROVAL_GATED`. Будь-яка видача доступу за замовчуванням іде через апрув.
  - `on_behalf` [text] — regex '(моїй|моєму) колез' → «моїй колез» → min `HUMAN_REVIEW`. Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6).
  - `missing_critical_data` [text] — ім'я/email людини, для якої запит → min `NEED_INFO`. Немає ключових даних (app / суб'єкт / список людей / скоуп). Не вгадуємо.
  - `multi_intent` [classifier] — 2 підзапити → min `None`. Кожен підзапит маршрутизовано окремо; загальний маршрут = найсуворіший
- **Read-side факти (джерело · механізм):**
  - `hris` · GET /employees?email= (polling snapshot): requester Марта Олійник <marta.oliinyk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
  - `okta` · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']

**Чернетка відповіді користувачу**

```text
1) у мене не працює adobe creative cloud, щось з підпискою:
Передав запит IAM-інженеру. Відповідь буде в цьому треді.

2) треба інвайт закинути моїй колезі новенькій, зробиш?:
Передав запит IAM-інженеру. Відповідь буде в цьому треді.
Щоб інженер міг одразу взятися, напиши тут:
• Для кого запит (ім'я та корпоративний email)?
• Для якої задачі потрібен доступ і на який строк?
```

<details><summary>Внутрішня нотатка для рев'юера</summary>

```text
HANDOFF · HUMAN_REVIEW · P3 (SLA 1 робочий день)
Автор: marta.oliinyk@corp.example — верифікований, активний у HRIS; менеджер creative-lead@corp.example
Звернення (після redaction): «у мене не працює adobe creative cloud, щось з підпискою. і ще треба інвайт закинути моїй колезі новенькій, зробиш?»

[HUMAN_REVIEW P3] у мене не працює adobe creative cloud, щось з підпискою
  Розбір: тип license_issue · система adobe_cc · суб'єкт self · впевненість 0.80 · rules
  Чому не авто:
    - type:license_issue [policy] → HUMAN_REVIEW: Збій ліцензії: потрібна перевірка в admin console вендора — read-side конектора в прототипі немає. (тип запиту = license_issue)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Марта Олійник <marta.oliinyk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']

[HUMAN_REVIEW P3] треба інвайт закинути моїй колезі новенькій, зробиш?
  Розбір: тип access_request · система adobe_cc · суб'єкт other · впевненість 0.80 · rules
  Чому не авто:
    - type:access_request [policy] → APPROVAL_GATED: Будь-яка видача доступу за замовчуванням іде через апрув. (тип запиту = access_request)
    - on_behalf [text] → HUMAN_REVIEW: Доступ для іншої людини — HUMAN-ONLY, навіть якщо автор — її менеджер: суб'єкт не просив сам → вектор соц. інженерії; потрібна згода суб'єкта (zones.md §6). (regex '(моїй|моєму) колез' → «моїй колез»)
  Факти з систем:
    - hris · GET /employees?email= (polling snapshot): requester Марта Олійник <marta.oliinyk@corp.example>: status=active, dept=Creative, manager=creative-lead@corp.example
    - okta · GET /api/v1/users/{id}, /groups, /appLinks: Okta status=ACTIVE, groups=['everyone', 'dept-creative', 'vpn-users'], apps=['slack', 'google_workspace', 'onepassword', 'adobe_cc']
  Апрувери: manager:creative-lead@corp.example, budget-owner
  Бот уже запитав автора: Для кого запит (ім'я та корпоративний email)? | Для якої задачі потрібен доступ і на який строк?

Що потрібно від тебе: Вирішити: видати / звузити / відмовити — і виконати самому. Бот нічого не змінюватиме навіть після апруву (HUMAN-ONLY).
```

</details>

<details><summary>Записи act-side (mock)</summary>

```json
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 29, "sub": 0, "route": "HUMAN_REVIEW", "requester": "marta.oliinyk@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P3", "reasons": ["type:license_issue", "multi_intent"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
{"ts": "2026-10-07T09:41:53+00:00", "dry_run": true, "mode": "SIMULATED", "request_id": 29, "sub": 1, "route": "HUMAN_REVIEW", "requester": "marta.oliinyk@corp.example", "kind": "escalation", "queue": "iam-review", "priority": "P3", "reasons": ["type:access_request", "on_behalf", "missing_critical_data", "multi_intent"], "dry_run_plan_for_human": [], "would_call": "JSM: POST /rest/servicedeskapi/request + Slack DM on-call"}
```

</details>
