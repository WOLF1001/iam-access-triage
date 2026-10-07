# AI-артефакти

- `prompts/classify_v1_naive.md` — перша версія: LLM сама обирає маршрут. Відкинута (див. `naive_vs_policy.md` після запуску `tools/compare_naive.py`).
- `../prompts/classify_v2.md` — робоча версія: LLM лише парсить, маршрут — policy engine.
- `01-task-analysis.md` — розбір завдання і «пасток» датасету разом з AI.
- `session-01-cowork.md` — журнал першої сесії з Claude (Cowork): запити, рішення, корекції.
- `ai-mistakes.md` — місця, де AI помилявся, і як це зловлено.
- `02-architecture-review.md` — архітектурне рев'ю (сесія 2): принципи, 5 знайдених дір, тестова стратегія, прихований сенс завдання.
- `AI_USAGE.md` — підсумок блоку d: де AI допомагав, де я свідомо його не пускав, де він помилявся (лог по фазах).
- `claude-code/` — як я керував Claude Code: `CLAUDE.md` (золоті правила й робочий процес для асистента), власні команди `/check`, `/next`, `/ai-mistake`, дозволи `settings.json`.
- `PROGRESS.md` — робочий журнал сесій, черга задач і час.
- `ollama-gpu-setup.md` — інструкція, за якою Claude Code на іншому ПК налаштував локальну LLM на GPU.

