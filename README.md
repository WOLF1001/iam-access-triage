# iam-triage — AI-assisted triage потоку запитів на доступи

Прототип для тестового завдання HOLYWATER TECH · IAM Engineer.

**Головна ідея:** LLM — це парсер, а не суддя. Вона розбирає «брудний» текст звернення в структуру (тип, згадки систем, сигнали, чого бракує). Маршрут обирає **детермінований policy engine** (`config/policy.yaml`) на основі трьох незалежних джерел сигналів:

| Джерело | Що дає | Чому окремо |
|---|---|---|
| `text` — regex-детектори | секрети, offboarding, «як у ліда», «лід в курсі», терміновість… | LLM не може «забути» сигнал: вона лише додає, не прибирає |
| `llm` — Claude (tool use, строга схема) | тип, підзапити, сирі згадки систем, уточнення | розуміє розмиті формулювання |
| `read` — Okta / HRIS / 1Password / GWS / Slack (моки) | хто автор, чи активний, чи менеджер у відпустці, що в System Log | правда з систем, а не зі слів користувача |

## Швидкий старт

```bash
pip install -r requirements.txt

python run_demo.py                          # вибірка 16 кейсів, rules-класифікатор, БЕЗ ключа
python run_demo.py --all                    # + розподіл маршрутів по всіх 108 зверненнях
pytest -q                                   # інваріанти безпеки (132 тести)

export ANTHROPIC_API_KEY=sk-ant-...
python run_demo.py --classifier llm         # Claude; відповіді кешуються в cache/llm_cache.json
python run_demo.py --classifier replay      # тільки з кешу — офлайн і відтворювано
python tools/compare_naive.py               # наївна LLM (сама обирає маршрут) vs policy → ai-artifacts/
```

Результати: `demo/output.md` (вхід → вихід для кожного кейсу), `demo/actions.log` (журнал імітованих дій, JSONL), `demo/full_run.md` (усі звернення).

## Спектр маршрутів

```
DOCS_REDIRECT  → AUTO_RESOLVE / REROUTE → NEED_INFO → APPROVAL_GATED → HUMAN_REVIEW → SECURITY_ESCALATION
  відповідь є     бот робить сам /         уточнення   бот готує,       рішення за       інцидент,
  в KB            не IAM — інша черга                  людина апрувить  інженером        пейдж
```

Правила тільки **підвищують** маршрут. AUTO можливий лише для дії з allowlist (`resend_invite`, `add_birthright_group`, `readonly_diagnostic`), і лише коли всі preconditions підтверджені **read-side**, а не текстом звернення.

## Структура

```
config/      app_catalog.yaml (app → власник, ризик, механізм read/act, апрув), policy.yaml, kb.yaml
mocks/       read-side джерела: okta, hris, 1password, gws, slack_users, asana, approvals
src/triage/  redact → classify → readside → policy → act (mock) → respond → report
prompts/     робочий промпт класифікатора
demo/        sample.yaml (вибірка + синтетичні автори), output.md, actions.log, full_run.md
tests/       інваріанти: «що система НЕ робить за жодних умов»
tools/       compare_naive.py — генерує артефакт «де LLM помиляється, якщо дати їй вирішувати»
docs/        architecture.md, critique.md, real-integrations.md
ai-artifacts/ промпти, ітерації, нотатки роботи з AI
```

## Чесні припущення

- У CSV немає автора і треду звернення. Для демо вони синтетичні (`demo/sample.yaml`), а для повного прогону автор — «типовий активний співробітник» `UGEN`.
- Act-side — тільки журнал: що і яким API бот **зробив би**, з `dry_run: true`.
- Посилання на KB — заглушки `notion.example`.
- `rules`-класифікатор — baseline і fallback. Він навмисно грубий: показує, скільки дає сама policy без LLM.
