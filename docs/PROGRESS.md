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

## Далі (за пріоритетом)

| # | Задача | Оцінка | Примітки |
|---|---|---|---|
| 1 | Прогін з реальною LLM: `--classifier llm`, закомітити `cache/llm_cache.json`, `demo/output_llm.md` | 20 хв | потрібен `ANTHROPIC_API_KEY` |
| 2 | `tools/compare_naive.py` → `ai-artifacts/naive_vs_policy.md`; кращі розбіжності — в `ai-mistakes.md` | 20 хв | головний доказ для блоку d |
| 3 | `docs/architecture.md`: схема (mermaid), read-side vs act-side таблиця по системах, обґрунтування стеку (Python core vs n8n), як лягає на n8n + Slack | 1 год | |
| 4 | `docs/critique.md`: де ламається, що не автоматизувати, ризики САМЕ цього рішення, чого бракує до проду, фрагментованість джерел | 1–1.5 год | **найважливіший блок** |
| 5 | `docs/real-integrations.md` (блок e): лише реальний досвід, конкретні граблі | 1 год | матеріал — у CLAUDE.local.md; не вигадувати |
| 6 | Демо-запис (Loom 3–5 хв) + лінк у README | 30 хв | |
| 7 | (опц.) `n8n/workflow.json`: Slack trigger → HTTP → Python service → Slack reply | 1 год | тільки якщо лишиться час |
| 8 | (опц.) «Як колега запускає і розвиває без мене» — розділ у README | 20 хв | частково вже покрито CLAUDE.md |

## Перевірити в доках (TODO verify)

- App Store Connect API: чи можна обмежити team API key конкретними apps (ми стверджуємо, що ні).
- 1Password service accounts: обмеження на типи vault'ів і зміну доступів після створення.
- Notion API: rate limit ~3 req/s не залежить від тарифу.
- Okta: деталі scopes для OAuth service app (`okta.groups.manage`) і resource sets для custom admin role.
- Anthropic: актуальна назва моделі Haiku для `ANTHROPIC_MODEL`.

## Відомі обмеження прототипу (матеріал для critique.md)

- Rules-класифікатор грубий; у повному прогоні частина типів неточна (напр. #16 BigQuery «не розумію де ліміт» → APPROVAL замість NEED_INFO).
- Read-side — моки з ідеальними даними; у реальності HRIS має затримку polling, GWS Reports API — години.
- Немає довгоживучого стану треду: уточнення (NEED_INFO) не перезапускає triage автоматично.
- Немає дедуплікації повторних звернень (5/36, 17/86 …).
- Апрувер = «менеджер з HRIS»; делегування/заміщення не моделюється.

## Журнал часу

| Сесія | Що | Час |
|---|---|---|
| 1 (Cowork) | розбір завдання, каталог, policy, моки, код, тести, демо, GitHub | ~3 год |
