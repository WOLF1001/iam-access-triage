# Локальна LLM (Ollama) на ПК з відеокартою для iam-triage

> **Для Claude Code на ПК з GPU.** Виконай кроки по черзі. Кожен крок, що змінює систему (встановлення ПЗ,
> змінні середовища, фаєрвол, перезапуск сервісу), спершу коротко покажи людині і дочекайся «так».
> Нічого не відкривай в інтернет: Ollama API **не має автентифікації**.

## Параметри (людина вписує перед стартом)

| Параметр | Значення | Звідки |
|---|---|---|
| `MAC_IP` | `<IP Mac, де працює iam-triage>` | на Mac: `ipconfig getifaddr en0` |
| `PORT` | `11434` | порт, який очікує проєкт (`OLLAMA_URL=http://<GPU_PC_IP>:11434`) |
| `MODEL` | `qwen3:14b` (основна), `gemma3:12b` (запасна) | обидві влазять у 16 GB VRAM (RTX 4070 Ti Super) |

Звір назви моделей з https://ollama.com/library. Якщо там є новіша модель 12–14B з добрим знанням української, яка влазить у 16 GB, запропонуй її людині.

## Що потрібно отримати в кінці

- Ollama слухає `0.0.0.0:11434` і стартує разом із системою.
- Модель повністю на GPU: `ollama ps` показує `100% GPU`.
- Порт 11434 відкритий **лише** для `MAC_IP`.
- Тест структурованої відповіді (крок 6) проходить.
- Людина отримує звіт (крок 8).

---

## 1. Визначити ОС і перевірити відеокарту

```powershell
# Windows
nvidia-smi
```
```bash
# Linux
nvidia-smi
```

Очікувано: видно RTX 4070 Ti Super з 16 GB (≈16376 MiB) і версію драйвера.
- `nvidia-smi` не знайдено → встановити драйвер NVIDIA (Windows — з nvidia.com або GeForce Experience; Linux — пакет дистрибутива). **Запитати людину.**
- Окремо CUDA Toolkit не потрібен: Ollama постачає власне середовище виконання.

## 2. Встановити Ollama (з підтвердженням людини)

**Windows:**
```powershell
winget install --id Ollama.Ollama -e
```
Якщо winget недоступний — інсталятор з https://ollama.com/download (завантажує людина).

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh -o /tmp/ollama-install.sh   # спершу показати скрипт людині
less /tmp/ollama-install.sh
sh /tmp/ollama-install.sh
```

Перевірка: `ollama --version`.

## 3. Слухати мережу, а не лише localhost

За замовчуванням Ollama слухає тільки `127.0.0.1`, і Mac до неї не дістанеться.

**Windows** (змінна користувача, потім перезапуск Ollama):
```powershell
setx OLLAMA_HOST "0.0.0.0:11434"
setx OLLAMA_KEEP_ALIVE "30m"
# закрити Ollama в треї (Quit Ollama) і запустити знову з меню Пуск
```

**Linux** (systemd):
```bash
sudo systemctl edit ollama
# у редакторі додати:
# [Service]
# Environment="OLLAMA_HOST=0.0.0.0:11434"
# Environment="OLLAMA_KEEP_ALIVE=30m"
sudo systemctl daemon-reload && sudo systemctl restart ollama && sudo systemctl enable ollama
```

Перевірка: `netstat -ano | findstr 11434` (Windows) або `ss -ltnp | grep 11434` (Linux) — слухає `0.0.0.0:11434`.

## 4. Фаєрвол: дозволити лише Mac

**Windows** (PowerShell від адміністратора):
```powershell
New-NetFirewallRule -DisplayName "Ollama from iam-triage Mac" -Direction Inbound -Protocol TCP `
  -LocalPort 11434 -RemoteAddress <MAC_IP> -Action Allow -Profile Private
```

**Linux (ufw):**
```bash
sudo ufw allow from <MAC_IP> to any port 11434 proto tcp
```

**Не робити:**
- правила «Any» на 11434;
- проброс порту на роутері;
- профіль мережі Public для домашньої мережі (`Get-NetConnectionProfile`; якщо Public — запитати людину, чи змінити на Private).

## 5. Завантажити модель і переконатись, що вона на GPU

```bash
ollama pull qwen3:14b          # ~9 GB
ollama run qwen3:14b "Скажи одним реченням українською, що таке SSO." --verbose
ollama ps                      # PROCESSOR має бути «100% GPU»
```

Якщо `ollama ps` показує частину на CPU (напр. `30%/70% CPU/GPU`):
- модель не влізла у VRAM → спробувати `gemma3:12b` або меншу квантизацію;
- закрити інші програми, що займають відеопам'ять (ігри, браузер з апаратним прискоренням).

## 6. Тест структурованої відповіді (як у проєкті)

Проєкт передає JSON-схему в поле `format` і чекає рівно один JSON-об'єкт. Перевір це локально:

```bash
curl -s http://localhost:11434/api/chat -d '{
  "model": "qwen3:14b",
  "stream": false,
  "think": false,
  "options": {"temperature": 0, "num_ctx": 8192},
  "format": {"type": "object", "required": ["type", "confidence"],
             "properties": {"type": {"type": "string", "enum": ["access_request", "how_to", "login_diagnostic", "unclear"]},
                            "confidence": {"type": "number"}}},
  "messages": [
    {"role": "system", "content": "Класифікуй IAM-звернення. Поверни лише JSON за схемою."},
    {"role": "user", "content": "<request>дайте доступ до tableau, колеги вже мають</request>"}
  ]
}'
```

Очікувано: `message.content` — валідний JSON, наприклад `{"type":"access_request","confidence":0.9}`, а відповідь займає кілька секунд.
- Помилка про параметр `think` → прибрати його. Проєкт додає `think:false` лише коли `OLLAMA_THINK=0`.
- Повтори тест для `gemma3:12b` і порівняй час (`total_duration` у відповіді, в наносекундах).

## 7. Перевірка з мережі (з боку Mac)

Попроси людину виконати **на Mac**:
```bash
curl -s http://<GPU_PC_IP>:11434/api/tags
```
Має повернути список моделей. Timeout → перевір крок 3 (адреса прослуховування) і крок 4 (фаєрвол, профіль мережі).

IP цього ПК: `ipconfig` (Windows, IPv4 Address) або `ip -4 addr` (Linux).

## 8. Звіт людині

Поверни коротко:
```
GPU_PC_IP=<…>
OLLAMA_URL=http://<GPU_PC_IP>:11434
OLLAMA_MODEL=<обрана модель>
ollama --version: <…>
ollama ps: <рядок моделі, має бути 100% GPU>
тест кроку 6: <JSON-відповідь> за <секунд> с
фаєрвол: правило лише для <MAC_IP>
```

---

## Далі на Mac (у проєкті iam-triage)

```bash
# одноразовий прогін
OLLAMA_URL=http://<GPU_PC_IP>:11434 OLLAMA_MODEL=qwen3:14b OLLAMA_THINK=0 \
  .venv/bin/python run_demo.py --classifier ollama --all

# або для стенду / n8n — у .env:
#   CLASSIFIER_MODE=ollama
#   OLLAMA_URL=http://<GPU_PC_IP>:11434
#   OLLAMA_MODEL=qwen3:14b
#   OLLAMA_THINK=0
# і docker compose up -d
```

`run_demo` завершиться з помилкою, якщо модель недоступна і класифікація тихо впала в rules: прогін на rules не видаватиметься за LLM.

## Безпека (коротко)

- Ollama API без автентифікації: будь-хто, хто дістається порту, може ганяти, завантажувати й **видаляти** моделі. Тому правило фаєрвола — лише для одного IP.
- У модель ідуть **відредаговані** тексти звернень: секрети вирізаються до LLM (`src/triage/redact.py`). Персональні дані (імена, email) лишаються, але не виходять з локальної мережі — це перевага локальної моделі перед хмарною.
