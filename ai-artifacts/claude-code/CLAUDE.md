> **Копія робочого контексту Claude Code** для рев'юерів (локально лежить у корені репо, де його читає Claude Code).
> Посилання `@TASK.md` — на копію тексту завдання, яку в репо не включено.

# CLAUDE.md — iam-triage

Контекст для Claude Code (і для колеги-інженера, який підхоплює проєкт).
Повний текст завдання: @TASK.md · журнал прогресу: @ai-artifacts/PROGRESS.md · ключові рішення: @docs/DECISIONS.md · зони: @docs/zones.md · ADR: docs/adr/

## Що це

Прототип **AI-assisted triage** потоку запитів на доступи (тестове завдання IAM Engineer, HOLYWATER TECH).
Бюджет — ~8 год, 3 календарні дні. Оцінюють межу «бот робить сам / перенаправляє / віддає людині», чесність критики, безпеку, практичний досвід інтеграцій, зрілість роботи з AI.

Мова документації й чернеток — **українська**, англійські терміни ок. Коментарі в коді — українська або англійська.

## Золоті правила архітектури (не порушувати)

1. **LLM — парсер, не суддя.** LLM повертає структуру (тип, сирі згадки систем, сигнали, missing info). Маршрут обирає лише `src/triage/policy.py` за `config/policy.yaml`.
2. **Правила тільки підвищують маршрут.** Жоден сигнал не може знизити severity. LLM може додати сигнал, але не прибрати regex-сигнал.
3. **Межі зон — `docs/zones.md`; для критичних систем HUMAN-ONLY ширше, а не вужче** (on_behalf, фінанси, prod, SoD). **AUTO лише з allowlist** (`resend_invite`, `add_birthright_group`, `readonly_diagnostic`) і лише коли preconditions підтверджені **read-side**, а не текстом звернення чи LLM.
4. **NEED_INFO — gate перед апрувом:** якщо бракує критичних даних, спершу питаємо, а не створюємо апрув «наосліп».
5. **Fail-closed:** невалідний вихід LLM, низька впевненість, недоступність API → вгору по спектру.
6. **Секрети редагуються до LLM і до логів** (`src/triage/redact.py`). Ніколи не логувати сирий текст до редакції.
7. **Act-side — тільки mock.** Жодних реальних кредів, токенів, викликів до живих систем. Усі дії → `demo/actions*.log` з `dry_run: true`.
8. **DOCS лише якщо стаття існує в KB** (`config/kb.yaml` або синхронізована з Notion, `Status=Published`). Бот не генерує інструкцій «з голови»; немає статті → `kb_gap` → людина.
9. **Мапінг на app — детермінований** (`src/triage/catalog.py`, алиаси з `config/app_catalog.yaml`). Невідома система → `unknown_app` → NEED_INFO. Не вгадувати.

## Команди

```bash
pip install -r requirements.txt
python run_demo.py                      # вибірка (demo/sample.yaml), rules-класифікатор, без ключа
python run_demo.py --all                # + demo/full_run.md по всіх 108 зверненнях
python run_demo.py --classifier llm     # Claude API (ANTHROPIC_API_KEY), кеш → cache/llm_cache.json
python run_demo.py --classifier replay  # тільки з кешу, офлайн
python run_demo.py --ids 32 46          # окремі звернення
python tools/compare_naive.py           # наївна LLM vs policy → ai-artifacts/naive_vs_policy.md
pytest -q                               # інваріанти безпеки — мають бути зелені ЗАВЖДИ
python tools/stand.py                   # веб-стенд localhost:8765 (+ LLM-override для атак GAP-1/2)
colima start && docker compose up -d --build   # n8n :5678 + triage-сервіс :8765 (n8n кличе http://triage:8765)
python tools/build_n8n_workflow.py      # → n8n/iam-triage.workflow.json; імпорт/публікація — див. docstring
python tools/build_n8n_kb_sync.py       # → n8n/kb-sync.workflow.json (Notion ⇄ triage); підключення — notion/README.md
python tools/export_kb_csv.py           # config/kb.yaml → notion/iam_kb.csv для імпорту в Notion
```

Модель за замовчуванням: `ANTHROPIC_MODEL=claude-haiku-4-5` (перевизначається env).

## Карта коду

| Етап | Файл | Що робить |
|---|---|---|
| redact | `src/triage/redact.py` | secret scanner (regex) до LLM і логів |
| classify | `src/triage/classify.py` | `rules` / `llm` (tool use, строга схема, кеш) / `replay`; валідація fail-closed |
| text signals | `src/triage/signals.py` | детерміновані regex-детектори ризик-сигналів і missing data |
| catalog | `src/triage/catalog.py` + `config/app_catalog.yaml` | сирі згадки → app_id (найдовший алиас) |
| read-side | `src/triage/readside.py` + `mocks/*.json` | Slack → HRIS → Okta → 1Password → GWS → Asana; факти з `source` + `mechanism` |
| policy | `src/triage/policy.py` + `config/policy.yaml` | базовий маршрут типу → hard rules → AUTO preconditions → NEED_INFO gate → KB check → апрувери/черга/ризик |
| act (mock) | `src/triage/act.py` | JSONL-журнал: action / approval_request / clarification / reroute / escalation |
| respond | `src/triage/respond.py` | чернетки з шаблонів + KB; нейтральні формулювання для користувача; внутрішня нотатка |
| report | `src/triage/report.py` | `demo/output*.md`, `demo/full_run*.md` |
| dedup | `src/triage/dedup.py` | ретрай Slack за `event_id`, повтор (автор + тип + система), патерни; стан — у сервісі |
| KB sync | `src/triage/kb_sync.py` | Notion → KB (лише Published, домени Notion, атомарно), беклог `kb_gap` |
| сервіс | `tools/stand.py` | HTTP API + веб-стенд; сервісний режим = `TRIAGE_API_TOKEN` (без override, класифікатор обирає сервіс) |

Маршрути (severity ↑): `DOCS_REDIRECT 0` → `AUTO_RESOLVE 1` / `REROUTE 1` → `NEED_INFO 2` → `APPROVAL_GATED 3` → `HUMAN_REVIEW 4` → `SECURITY_ESCALATION 5`.

## Робочий процес

- Після будь-якої зміни в `config/*.yaml` або `src/triage/*`: `pytest -q` → `python run_demo.py --all` → `git diff demo/` і перевірити, чи не змінились маршрути там, де не мали.
- Новий кейс у демо → додати в `demo/sample.yaml` (з `why_picked`) і очікуваний маршрут у `EXPECTED` у `tests/test_policy.py`.
- **Блок d (робота з AI) — частина здачі.** Якщо AI (ти) згенерував хибне правило/код/факт і це виявлено — додай рядок у `ai-artifacts/ai-mistakes.md` (що, як виявлено, як виправлено). Не причісуй історію.
- Коміти — маленькі, по логічних кроках, з префіксами `feat:`, `fix:`, `docs:`, `ai:`, `test:`. Історія комітів сама є артефактом процесу.
- Не вигадувати факти про API вендорів. Якщо не впевнений — позначити `TODO(verify)` і додати в `ai-artifacts/PROGRESS.md` → «Перевірити в доках».
- `cache/llm_cache.json` комітимо (для `--classifier replay` у рев'юерів).
- `demo/sample.yaml`: requester і thread **синтетичні** (у CSV їх немає) — завжди зазначати це в документах.

## Стан і наступні кроки

Див. @ai-artifacts/PROGRESS.md — це живий файл, оновлюй його в кінці кожної сесії.
