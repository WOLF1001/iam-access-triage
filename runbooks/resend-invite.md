## Runbook: повторно надіслати інвайт за чинним апрувом

**Owner:** IAM | **Frequency:** за запитом (AUTO) | **Last Updated:** 2026-10-07 | **Дія в policy:** `resend_invite`

### Purpose

Інвайт прострочився, поки людина дійшла до пошти (#104 «інвайт у Асану деактивувався»). Апрув на цей доступ уже був, тому повтор — не нова видача. Новий апрув потрібен, якщо старий не підходить (див. передумови).

### Prerequisites — бот перевіряє ВСЕ

- [ ] Є pending / прострочений інвайт саме для автора (`asana.pending_invites[requester]`).
- [ ] У журналі апрувів є запис `approval_ref` цього інвайту, і він:
  - [ ] на **того самого суб'єкта** (`subject == requester`);
  - [ ] на **той самий застосунок** (`app == asana`);
  - [ ] **свіжіший за `resend_max_age_days` (30 днів)**. Старіший → новий апрув: за місяць людина могла змінити команду.
- [ ] Автор активний у HRIS, автор = суб'єкт, одна система в запиті, немає сигналів HUMAN / HUMAN-ONLY.

Якщо хоч одна умова не виконана — APPROVAL_GATED (новий апрув), а не AUTO. Ці перевірки додано після adversarial-рев'ю (GAP-3).

### Procedure

#### Step 1: Перечитати апрув із журналу
```
lookup approval_ref → {subject, app, role, approved_by, approved_at, via}
```
**Expected result:** усі три умови прив'язки виконано.
**If it fails:** APPROVAL_GATED, у внутрішній нотатці — яка саме умова не пройшла.

#### Step 2: Надіслати інвайт повторно
```
POST /workspaces/{workspace_gid}/addUser   {"user": "<email>"}
```
TODO(verify): семантика повторного інвайту для вже запрошеного користувача в Asana API.
**Expected result:** користувач у workspace (pending або active).
**If it fails:** 4xx → HUMAN_REVIEW; 429 → бекоф і одна повторна спроба.

#### Step 3: Записати дію
Журнал: `action = resend_invite`, `approval_ref`, `preconditions`, `idempotency_key`.

### Verification

- [ ] `GET /workspaces/{gid}/users` (або memberships) містить автора.
- [ ] Відповідь у треді: «Надіслав інвайт ще раз, прийми його протягом 7 днів».

### Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Інвайт знову прострочився | людина не встигла ще раз | повтор лише в межах `resend_max_age_days`, далі новий апрув |
| Апрув є, але на іншу людину чи інший app | інвайт переслали або підмінили | **не** AUTO; APPROVAL з поясненням |

### Rollback

```
POST /workspaces/{workspace_gid}/removeUser   {"user": "<email>"}
```
Повертає стан до «немає доступу». Перевірити читанням і записати в журнал з посиланням на початковий `idempotency_key`.

### Escalation

| Situation | Contact | Method |
|---|---|---|
| помилка API, апрув не прив'язується | IAM-інженер | DM + JSM |

### History

| Date | Run By | Notes |
|---|---|---|
| 2026-10-07 | бот (dry_run) | #104 у демо: апрув `APR-2026-0912` прив'язаний до суб'єкта + Asana, 7 днів |
