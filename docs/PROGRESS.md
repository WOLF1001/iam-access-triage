# Прогрес

Оновлюється наприкінці кожної робочої сесії.

## Зроблено

- [x] Розбір завдання і пасток датасету з AI → `ai-artifacts/01-task-analysis.md`
- [x] Каталог 33 застосунків з read/act-механізмами, власниками, ризиком, нюансами → `config/app_catalog.yaml`
- [x] Policy: 7 маршрутів, базові маршрути для 21 типу, ~28 hard rules, allowlist AUTO, пороги → `config/policy.yaml`
- [x] Mock KB (21 стаття) і черги перенаправлення → `config/kb.yaml`
- [x] Read-side моки: Slack, HRIS, Okta (users + System Log), 1Password, GWS, Asana, approvals → `mocks/`
- [x] Пайплайн redact → classify → read-side → policy → act(mock) → respond → report
- [x] Демо на 16 кейсах (усі 7 маршрутів) → `demo/output.md`, `demo/actions.log`
- [x] Повний прогін 108 звернень (rules) → `demo/full_run.md`
- [x] 132 тести-інваріанти → `tests/test_policy.py`
- [x] Наївний промпт v1 + робочий v2 → `ai-artifacts/prompts/`, `prompts/`
- [x] Журнал помилок AI під час розробки (6 шт.) → `ai-artifacts/ai-mistakes.md`
- [x] Репозиторій на GitHub (private)
- [x] Архітектурне рев'ю + 190 нових тестів (інваріанти, adversarial LLM / hypothesis, golden snapshot 108) → `ai-artifacts/02-architecture-review.md`; знайдено 5 дір (GAP-1..5, xfail)

- [x] Тестовий веб-стенд `tools/stand.py` (+ LLM-override для атак)
- [x] Docker (Colima) + `docker-compose.yml`: n8n 2.42.3 + triage-сервіс; n8n → `http://triage:8765/api/triage` перевірено
- [x] n8n-воркфлоу `n8n/iam-triage.workflow.json` (генератор `tools/build_n8n_workflow.py`): Webhook(Slack event) → валідація → triage → Switch(7 маршрутів + fallback) → outbox (dry_run) → ack; fail-closed при недоступності сервісу; 16/16 демо-кейсів через n8n = прямий пайплайн; дані виконань не зберігаються (секрети до redaction)

- [x] Notion «IAM KB»: CSV для імпорту (`notion/`), `/api/kb/sync` (токен, лише Published, атомарно, відмова на порожній/обрізаний синк), беклог `kb_gap`; n8n-воркфлоу «KB sync» (`n8n/kb-sync.workflow.json`); +17 тестів (`tests/test_kb_sync.py`, вкл. «отруєння» KB)
- [x] Notion підключено наживо: 21 стаття синхронізована в сервіс (джерело `notion`, посилання на реальні сторінки), kb_gap → Draft у Notion → ack; «KB sync» опубліковано (кожні 15 хв)

- [x] GAP-1..5 закрито (ADR-010 / D10): заземлення виходу LLM, прив'язка апруву, Unicode-нормалізація, монотонність kb_gap; 347 passed, golden без змін
- [x] Класифікатор `ollama` (локальна LLM на власному GPU) — та сама схема/валідація/кеш/fail-closed

- [x] `docs/critique.md` (чернетка): TL;DR, фрагментованість джерел, що не автоматизувати, ризики саме цього рішення, чого бракує до проду
- [x] `docs/architecture.md`: 3 mermaid-схеми (перевірено рендер), спектр маршрутів і межі, пороги, read/act-side по системах + довгий хвіст 33 app, стек і відкинуті альтернативи, безпекова модель

- [x] `docs/real-integrations.md` (блок e): кейс Device Inventory Reconciler (мок-дані), граблі цього прототипу (n8n, Notion, Docker)

- [x] Фази 1–5 промпта «довести до рівня»: `docs/process/current-state.md`, `docs/zones.md`, `docs/adr/0001–0003`, `docs/architecture.md` (§7–9), розширення HUMAN-ONLY (on_behalf, financial_data, prod_access, sod_conflict), пріоритети P1–P4 і дедуп (`src/triage/dedup.py`), `kb/` (5 статей), `runbooks/` (3), `templates/human-handoff.md`, `AI_USAGE.md`; 392 тести

- [x] Фази 6–9: golden set 30 граничних кейсів (`tests/golden/`), RACI (`docs/process/raci.md`), рев'ю коду (автентифікація викликача, override лише в dev, паролі в прозі, allowlist доменів KB, межі пам'яті дедупу), README як рішення; 497 тестів

## Далі (за пріоритетом)

| # | Задача | Оцінка | Примітки |
|---|---|---|---|
| 1 | Прогін з реальною LLM: `--classifier llm`, закомітити `cache/llm_cache.json`, `demo/output_llm.md` | 20 хв | потрібен `ANTHROPIC_API_KEY` |
| 2 | `tools/compare_naive.py` → `ai-artifacts/naive_vs_policy.md`; кращі розбіжності — в `ai-mistakes.md` | 20 хв | головний доказ для блоку d |
| 6 | Демо-запис (Loom 3–5 хв) + лінк у README | 30 хв | |
| 7 | n8n: воркфлоу апруву (Slack interactivity → перевірка апрувера → act) | 45 хв | основний воркфлоу вже є |
| 8 | (опц.) «Як колега запускає і розвиває без мене» — розділ у README | 20 хв | частково вже покрито CLAUDE.md |

## Перевірити в доках (TODO verify)

- App Store Connect API: чи можна обмежити team API key конкретними apps (ми стверджуємо, що ні).
- 1Password service accounts: обмеження на типи vault'ів і зміну доступів після створення.
- Notion API: rate limit ~3 req/s не залежить від тарифу.
- Okta: деталі scopes для OAuth service app (`okta.groups.manage`) і resource sets для custom admin role.
- Anthropic: актуальна назва моделі Haiku для `ANTHROPIC_MODEL`.
- Slack Events API: таймаут ack (~3 с) і семантика ретраїв (`X-Slack-Retry-Num`) — на цьому стоїть вимога «ack одразу + дедуп за event_id».
- Notion API: `Notion-Version: 2022-06-28` vs data sources (2025-09-03) — чи працює `/databases/{id}/query` для нових баз.
- n8n: чи `saveDataSuccessExecution: none` гарантує відсутність сирих даних на диску (спостерігали залишок у SQLite WAL).

## Відомі обмеження прототипу (матеріал для critique.md)

- Rules-класифікатор грубий; у повному прогоні частина типів неточна (напр. #16 BigQuery «не розумію де ліміт» → APPROVAL замість NEED_INFO).
- Read-side — моки з ідеальними даними; у реальності HRIS має затримку polling, GWS Reports API — години.
- Немає довгоживучого стану треду: уточнення (NEED_INFO) не перезапускає triage автоматично.
- Немає дедуплікації повторних звернень (5/36, 17/86 …).
- Апрувер = «менеджер з HRIS»; делегування/заміщення не моделюється.
- Хто редагує Notion «IAM KB», той пише відповіді бота (KB poisoning). Policy від KB не залежить (тест #32), але DOCS-відповіді — так.
- `N8N_BLOCK_ENV_ACCESS_IN_NODE=false` → редактор воркфлоу бачить env n8n (там лише KB_SYNC_TOKEN).
- n8n бачить сирий текст до redaction; навіть з вимкненим збереженням виконань байти тимчасово потрапляють у SQLite WAL. n8n з кредами на запис = найпривілейованіший компонент.

## Журнал часу

| Сесія | Що | Час |
|---|---|---|
| 1 (Cowork, 6.10 вечір) | розбір завдання, каталог, policy, моки, код, тести, демо, GitHub | |
| 2 (Claude Code, 7.10) | архітектурне рев'ю, тести, GAP-фікси, стенд, Docker + n8n, Notion, Ollama, документи | |
| **Разом (факт)** | | **~5 год** |
