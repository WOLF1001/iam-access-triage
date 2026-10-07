# Шаблон передачі людині (human handoff)

> Фаза 5 (`customer-support:customer-escalation`). Цей формат генерує `src/triage/respond.py → internal_note()`.
> n8n кладе його в опис JSM-тікета і в DM черговому IAM (`n8n/iam-triage.workflow.json`).
> Мета: інженер може **вирішити, не відкриваючи жодної системи й не перепитуючи автора**.

## Структура

| Блок | Що містить | Навіщо |
|---|---|---|
| **Заголовок** | маршрут · пріоритет · SLA | одразу видно, наскільки терміново (`policy.yaml → priorities`) |
| **Автор** | email, верифікований чи ні, статус у HRIS, менеджер і чи доступний | ідентичність — з систем, а не зі слів |
| **Звернення** | текст **після** redaction секретів | секрет не потрапляє в тікет і DM |
| **Розбір** | тип · система · суб'єкт · впевненість · класифікатор | що бот зрозумів; низька впевненість видна одразу |
| **Чому не авто** | кожне правило, що підняло маршрут ≥ APPROVAL: сигнал, джерело (text / llm / read / catalog), мінімальний маршрут, причина, доказ | головне: людина бачить, на чому стоїть рішення, і може з ним не погодитись (override rate) |
| **Факти з систем** | source · mechanism · statement | звідки бот це знає; без SoT кожен факт має походження |
| **Діагноз** | що знайшла read-only діагностика | щоб не повторювати її вручну |
| **Dry-run план (НЕ виконано)** | які виклики API і з яким ефектом | для офбордингу — по всіх системах, включно з non-SSO |
| **Апрувери** | хто має погодити (з каталогу й HRIS) | без пошуку апрувера |
| **Бот уже запитав автора** | питання про відсутні дані | інженер не ставить те саме питання вдруге |
| **Що потрібно від тебе** | конкретне прохання за маршрутом і типом | «вирішити», «погодити», «стримати інцидент» — різні прохання |

## Правила

- **Нейтрально назовні, повно всередині.** Користувач бачить «передав інженеру, дані в системах не збігаються», а інженер — `source_conflict` з доказом. Атакувальник не дізнається, яке правило спрацювало (`DECISIONS.md` D9).
- **Секрети** — лише як `[REDACTED:тип]`.
- **Сигнали з LLM** позначені `[llm]` як неперевірені; факти з систем — `[read]`.
- **Бот нічого не виконав** — це завжди сказано явно для HUMAN-ONLY і SECURITY.

## Приклад: #92 «заблокуйте всі доступи, останній день» (автор і тред — синтетичні)

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
