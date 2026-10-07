# iam-triage — AI-assisted triage потоку запитів на доступи

Прототип для тестового завдання HOLYWATER TECH · IAM Engineer.

**Ідея в одному реченні:** LLM розбирає «брудний» текст звернення в структуру, а маршрут обирає детермінована policy. Правила можуть лише підняти маршрут. Бот діє сам тільки там, де факт підтверджує система, а не текст звернення.

## Де що лежить (за пунктами здачі)

| Пункт здачі | Де |
|---|---|
| a. Архітектура: схема, рішення, стек, read-side / act-side | [`docs/architecture.md`](docs/architecture.md) · рішення — [`docs/DECISIONS.md`](docs/DECISIONS.md) |
| Прототип | `src/triage/` (сервіс рішень), `config/` (policy, каталог 33 app, KB), `n8n/` (воркфлоу), `docker-compose.yml`, `tools/stand.py` (веб-стенд) |
| b. Демо на вибірці | [`demo/output.md`](demo/output.md) — 16 кейсів «вхід → вихід → чому» · [`demo/actions.log`](demo/actions.log) — журнал імітованих дій · [`demo/full_run.md`](demo/full_run.md) — усі 108 · запис — TODO(Loom) |
| c. Критика й обмеження | [`docs/critique.md`](docs/critique.md) |
| d. Робота з AI | [`ai-artifacts/`](ai-artifacts/) — розбір завдання, промпти v1→v2, рев'ю, [13 помилок AI і як їх зловлено](ai-artifacts/ai-mistakes.md) |
| e. Досвід реальних інтеграцій | [`docs/real-integrations.md`](docs/real-integrations.md) |
| Як колега запускає і розвиває | [`CLAUDE.md`](CLAUDE.md) (контекст, правила, карта коду, робочий процес) + розділ нижче |

## Результат коротко

Розподіл маршрутів на всіх 108 зверненнях датасету (автор — «типовий співробітник», rules-класифікатор):

| DOCS | AUTO | REROUTE | NEED_INFO | APPROVAL | HUMAN | SECURITY |
|---|---|---|---|---|---|---|
| 16 | 1 | 10 | 27 | 18 | 33 | 3 |

- **Повністю знімається з людини ~25%** звернень (DOCS + REROUTE + AUTO). Ще 27 повертаються автору з конкретними питаннями до того, як дійти до апрувера. Решта — людина, але з готовим пакетом: факти з систем, dry-run план, апрувери. Чесний розбір — у `critique.md`.
- **Безпека перевірена тестами, а не лише задекларована.** 347 тестів:
  - property-based «LLM як противник» (hypothesis);
  - metamorphic «додали ризик — маршрут не знизився»;
  - секрети не виходять за межу redaction;
  - golden snapshot усіх 108 маршрутів.

  Adversarial-тести знайшли в першій версії 5 дір, зокрема критичну: LLM могла «розбити» запит на адмінку в 1Password на безневинні підзапити й отримати AUTO. Усі закрито, історія — в `ai-artifacts/02-architecture-review.md` і в git log.

Приклади з демо (`demo/output.md`):

| № | Звернення (скорочено) | Маршрут | За яким сигналом |
|---|---|---|---|
| 91 | доступ до корп VPN + інструкція | AUTO | birthright-група в allowlist бота, автор активний у HRIS |
| 5 | новий API-ключ до однієї AI-моделі, «лід в курсі» | NEED_INFO → APPROVAL | «лід в курсі» ≠ апрув; модель не названа |
| 69 | пропав доступ до Tableau | APPROVAL | System Log: доступ зняло group rule після зміни відділу — повернення = нова видача |
| 42 | не можу зайти по вечорах | SECURITY | System Log: невдалі входи з Tor + блокування акаунта |
| 46 | дайте все, що було у ліда, лід у відпустці | HUMAN | «як у X» = over-granting; апрувер у відпустці за HRIS, а не за текстом |
| 92 | заблокуйте всі доступи, останній день | HUMAN | HRIS не підтверджує звільнення → конфлікт джерел; бот будує dry-run план, але не діє |
| 32 | видаліть нотатку зі скомпрометованим ключем | SECURITY | видалення нотатки не відкликає ключ; секрет із треду вирізано до LLM |

## Швидкий старт

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                         # 347 тестів, ~5 с
.venv/bin/python run_demo.py --all                    # демо 16 кейсів + розподіл по 108 (без ключа)
.venv/bin/python tools/stand.py                       # веб-стенд http://localhost:8765
```

Веб-стенд: обираєш звернення й автора (від автора залежать факти HRIS / Okta) і бачиш маршрут, сигнали з джерелами, факти read-side, чернетку відповіді й журнал дій. Режим «LLM-override» дозволяє вручну відтворити атаки на класифікатор.

**У їхньому стеку (n8n + Slack-подія + Notion):**

```bash
cp .env.example .env                                  # KB_SYNC_TOKEN, NOTION_KB_DATABASE_ID, CLASSIFIER_MODE
colima start                                          # або Docker Desktop
docker compose up -d --build                          # n8n :5678 + triage-сервіс :8765
python tools/build_n8n_workflow.py                    # імпорт і публікація — див. docstring файлу
```

Notion-база знань — [`notion/README.md`](notion/README.md) (імпорт CSV, інтеграція, синк кожні 15 хв).

**Класифікатор:**

| Режим | Що | Вартість |
|---|---|---|
| `--classifier rules` | детермінований baseline і fallback | $0 |
| `--classifier llm` | Claude Haiku 4.5, tool use зі строгою схемою (`ANTHROPIC_API_KEY`) | ≈ $0.4 за повний прогін |
| `--classifier ollama` | локальна модель (`OLLAMA_URL`, `OLLAMA_MODEL`) | $0, дані не виходять із мережі |
| `--classifier replay` | лише з кешу `cache/llm_cache.json` — офлайн і відтворювано | $0 |

Якщо LLM тихо деградувала на rules (ключ, ліміт, мережа), `run_demo` скаже про це й завершиться з помилкою, а не видасть rules-прогін за LLM.

## Спектр маршрутів

```
DOCS_REDIRECT → AUTO_RESOLVE / REROUTE → NEED_INFO → APPROVAL_GATED → HUMAN_REVIEW → SECURITY_ESCALATION
відповідь у KB   бот робить сам /          уточнення   бот готує,       рішення          інцидент,
                 не IAM — інша черга                   людина апрувить  інженера         пейдж
```

AUTO — лише три дії з allowlist (`add_birthright_group`, `resend_invite`, `readonly_diagnostic`). Для них потрібні передумови з read-side: автор = суб'єкт, активний у HRIS, одна система в запиті, апрув прив'язаний до людини й застосунку. Межі й пороги — `docs/architecture.md` §2.

## Структура

```
src/triage/   redact → classify (rules / Claude / Ollama) → заземлення → catalog → readside → policy → act (mock) → respond
config/       policy.yaml (маршрути, hard rules, allowlist, пороги) · app_catalog.yaml (33 app) · kb.yaml (фікстура KB)
mocks/        read-side: okta, hris, 1password, gws, slack_users, asana, approvals
n8n/          воркфлоу: triage (Slack-подія → маршрут → дія) · KB sync (Notion ⇄ сервіс)
notion/       CSV для імпорту бази знань + інструкція
tools/        stand.py (веб-стенд / HTTP-сервіс) · build_n8n_*.py · export_kb_csv.py · compare_naive.py
tests/        інваріанти, adversarial, KB sync, golden snapshot
demo/         sample.yaml (вибірка + синтетичні автори) · output.md · actions.log · full_run.md
docs/         architecture · critique · real-integrations · DECISIONS · PROGRESS
ai-artifacts/ розбір завдання, промпти, рев'ю, помилки AI, журнал сесій
```

## Як колега розвиває агента без мене

- **Новий застосунок:** додати в `config/app_catalog.yaml` аліаси, механізм, власника, ризик і тип апруву. Мапінг детермінований: без запису в каталозі бот поверне `unknown_app` → NEED_INFO.
- **Нове правило:** `config/policy.yaml` → `hard_rules` (сигнал → мінімальний маршрут). Детектор додати в `src/triage/signals.py`.
- **Нова стаття KB:** у Notion зі `Status = Published` — підтягнеться за 15 хв.
- **Після будь-якої зміни:** `pytest -q` → `run_demo.py --all` → переглянути diff маршрутів. Якщо змінився golden snapshot, зміна має бути свідомою (`UPDATE_GOLDEN=1`).
- Повний контекст для людини чи AI-асистента — `CLAUDE.md`.

## Чесні припущення

- **Автора й треду в CSV немає.** У демо вони синтетичні (`demo/sample.yaml`), у повному прогоні автор — «типовий співробітник». Маршрут залежить від автора, тож для #104, #69, #42 він різний у демо і в повному прогоні.
- **Read-side** (Okta, HRIS, 1Password, GWS) — моки. **Act-side** — журнал `dry_run: true`: що і яким API бот зробив би.
- **Живі інтеграції:** n8n (локально) і Notion (база знань, синк, чернетки статей).
- **LLM на повному датасеті ще не проганялась** — TODO: Claude або локальна модель. `rules` — навмисно грубий baseline: показує, скільки дає сама policy без LLM.

## Час

Фактично **~5 годин** за орієнтиру ~8 (вечір 6.10 і 7.10). AI-асистенти (Claude) використовувались на всіх етапах; як саме і де вони помилялися — `ai-artifacts/`.

Пріоритети під обмеження часу:
1. безпека рішення і тести на неї;
2. критика;
3. живі інтеграції в їхньому стеку (n8n, Notion);
4. полірування.

Свідомо не зроблено: воркфлоу апруву (Slack interactivity → виконання), стан треду для NEED_INFO, дедуп звернень — див. `docs/critique.md` §4.
