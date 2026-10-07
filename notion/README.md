# Notion «IAM KB» — база знань для маршруту DOCS

Notion — джерело **статей**, не політики. Бот перенаправляє лише на статті зі `Status = Published`,
а `article_id` має збігатися з тим, на що посилається `config/app_catalog.yaml`.

## Поля бази

| Поле | Тип | Навіщо |
|---|---|---|
| Title | title | заголовок у відповіді бота |
| article_id | text | стабільний ключ (slug); на нього посилається каталог і policy |
| Summary | text | коротка відповідь, яку бот цитує |
| Keywords | text (через кому) | детермінований матчинг звернення → стаття |
| Apps | text | до яких app з каталогу стосується |
| Status | text / select | `Published` — бот використовує; `Draft` — беклог (сюди падають kb_gap) |
| Owner, Last reviewed | text / date | хто відповідає за актуальність |

## Підключення (≈10 хв, кроки людини — токени Claude не вводить)

1. Notion → **Import → CSV** → `notion/iam_kb.csv` (генерується `python tools/export_kb_csv.py`). Перейменуй базу на «IAM KB».
2. https://www.notion.so/my-integrations → **New integration** (Internal), capabilities: *Read content*, *Insert content*.
3. На сторінці бази: **••• → Connections → додати інтеграцію** (без цього API бачить 0 сторінок → синк відхиляється 409).
4. ID бази — 32 hex з URL → у `.env`: `NOTION_KB_DATABASE_ID=…` → `docker compose up -d`.
5. n8n → **Credentials → Create → Notion API** → вставити секрет інтеграції. ID credential підв'язується: `python tools/build_n8n_kb_sync.py --credential-id <id> --credential-name "<назва>"` (ID — не секрет, але свій для кожного інстансу n8n).
6. Воркфлоу «IAM KB sync» → у трьох Notion-вузлах вибрати credential (або `python tools/build_n8n_kb_sync.py --credential-id <id>` і реімпорт) → **Run now** → **Publish**.

## Що відбувається

- кожні 15 хв: схема бази → сторінки → `POST triage:8765/api/kb/sync` (токен `KB_SYNC_TOKEN`) → сервіс валідує й **атомарно** замінює KB;
- порожній / обрізаний (<50%) / невалідний синк → 409 → KB лишається попередньою, DM IAM;
- `kb_gap` → `GET /api/kb/gaps` → Draft-сторінка в Notion (лише відредагований текст) → `ack`.

## Ризики (у critique)

- Хто має право редагувати базу, той пише відповіді бота. Права на «IAM KB» — як на код: обмежене коло, історія змін.
- Notion-інтеграція з *Insert content* може створювати сторінки — тримати її підключеною лише до цієї бази.
