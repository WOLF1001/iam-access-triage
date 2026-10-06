# CLAUDE.md — iam-triage

Контекст для Claude Code (і для колеги-інженера, який підхоплює проєкт).
Повний текст завдання: @TASK.md · журнал прогресу: @docs/PROGRESS.md · ключові рішення: @docs/DECISIONS.md

## Що це

Прототип **AI-assisted triage** потоку запитів на доступи (тестове завдання IAM Engineer, HOLYWATER TECH).
Бюджет — ~8 год, 3 календарні дні. Оцінюють межу «бот робить сам / перенаправляє / віддає людині», чесність критики, безпеку, практичний досвід інтеграцій, зрілість роботи з AI.

Мова документації й чернеток — **українська**, англійські терміни ок. Коментарі в коді — українська або англійська.

## Золоті правила архітектури (не порушувати)

1. **LLM — парсер, не суддя.** LLM повертає структуру (тип, сирі згадки систем, сигнали, missing info). Маршрут обирає лише `src/triage/policy.py` за `config/policy.yaml`.
2. **Правила тільки підвищують маршрут.** Жоден сигнал не може знизити severity. LLM може додати сигнал, але не прибрати regex-сигнал.
3. **AUTO лише з allowlist** (`resend_invite`, `add_birthright_group`, `readonly_diagnostic`) і лише коли preconditions підтверджені **read-side**, а не текстом звернення чи LLM.
4. **NEED_INFO — gate перед апрувом:** якщо бракує критичних даних, спершу питаємо, а не створюємо апрув «наосліп».
5. **Fail-closed:** невалідний вихід LLM, низька впевненість, недоступність API → вгору по спектру.
6. **Секрети редагуються до LLM і до логів** (`src/triage/redact.py`). Ніколи не логувати сирий текст до редакції.
7. **Act-side — тільки mock.** Жодних реальних кредів, токенів, викликів до живих систем. Усі дії → `demo/actions*.log` з `dry_run: true`.
8. **DOCS лише якщо стаття існує в `config/kb.yaml`.** Бот не генерує інструкцій «з голови»; немає статті → `kb_gap` → людина.
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

Маршрути (severity ↑): `DOCS_REDIRECT 0` → `AUTO_RESOLVE 1` / `REROUTE 1` → `NEED_INFO 2` → `APPROVAL_GATED 3` → `HUMAN_REVIEW 4` → `SECURITY_ESCALATION 5`.

## Робочий процес

- Після будь-якої зміни в `config/*.yaml` або `src/triage/*`: `pytest -q` → `python run_demo.py --all` → `git diff demo/` і перевірити, чи не змінились маршрути там, де не мали.
- Новий кейс у демо → додати в `demo/sample.yaml` (з `why_picked`) і очікуваний маршрут у `EXPECTED` у `tests/test_policy.py`.
- **Блок d (робота з AI) — частина здачі.** Якщо AI (ти) згенерував хибне правило/код/факт і це виявлено — додай рядок у `ai-artifacts/ai-mistakes.md` (що, як виявлено, як виправлено). Не причісуй історію.
- Коміти — маленькі, по логічних кроках, з префіксами `feat:`, `fix:`, `docs:`, `ai:`, `test:`. Історія комітів сама є артефактом процесу.
- Не вигадувати факти про API вендорів. Якщо не впевнений — позначити `TODO(verify)` і додати в `docs/PROGRESS.md` → «Перевірити в доках».
- `cache/llm_cache.json` комітимо (для `--classifier replay` у рев'юерів).
- `demo/sample.yaml`: requester і thread **синтетичні** (у CSV їх немає) — завжди зазначати це в документах.

## Стан і наступні кроки

Див. @docs/PROGRESS.md — це живий файл, оновлюй його в кінці кожної сесії.
