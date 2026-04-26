# Git Flow — Engineering Guideline
**Проект:** v0-syntecho-client-portal
**Стек:** Next.js · TypeScript · Docker · AWS EC2 · PostgreSQL RDS
**Тип разработки:** AI-driven (v0.ai + Claude)

---

## Структура веток

| Ветка | Назначение | Среда | Naming |
|---|---|---|---|
| `feature/xxx` | рабочая ветка AI-агента | — | `feature/<short-description>` |
| `develop` | интеграция всех фич | EC2 dev | — |
| `main` | production | EC2 prod | — |
| `hotfix/xxx` | срочный фикс от main | — | `hotfix/<short-description>` |

---

## Allowed / Forbidden

### Запрещено
- прямой `push` в `develop` и `main` — для всех, включая AI-агентов
- force push и удаление защищённых веток
- merge без прохождения всех обязательных проверок
- AI-агент не может открывать PR напрямую в `main`
- AI conflict resolution без повторного прогона всех checks
- merge в `main` без PR и owner approval

### Разрешено
- AI-агент создаёт `feature/xxx` и открывает PR в `develop`
- owner открывает или approve'ит PR `develop → main` после проверки dev-среды
- hotfix открывается только от `main`

---

## Branch Protection

Настроить обязательно для `develop` и `main` в GitHub:

- `require pull request before merging`
- `require all status checks to pass`
- `require branch to be up to date before merge`
- `restrict direct push`
- `restrict force push`
- `restrict delete branch`
- `require at least 1 approval` — для `main`
- `require conversation resolution before merge`

---

## Merge Strategy

| PR | Стратегия |
|---|---|
| `feature/*` → `develop` | squash merge |
| `develop` → `main` | merge commit |
| `hotfix/*` → `main` | merge commit |
| `hotfix/*` → `develop` | merge commit |

Squash merge для feature-веток убирает шумную историю AI-генерированных коммитов.

---

## Обязательные проверки для PR в develop

```
build          — сборка Next.js приложения
lint           — ESLint
typecheck      — TypeScript strict check
tests          — unit and smoke tests
security scan  — Snyk / Trivy / GitHub Dependabot alerts
secret scan    — поиск утечек ключей и токенов
migration check — prisma validate
```

> После **AI conflict resolution** все проверки перезапускаются автоматически. Merge только после зелёного статуса.

---

## Процесс деплоя

### develop → EC2 dev
После merge PR в `develop` GitHub Actions автоматически:
1. Прогоняет все проверки
2. Собирает Docker image с тегом `develop-<short_sha>`
3. Пушит в AWS ECR
4. Деплоит на EC2 dev

### main → EC2 prod
После merge owner `develop → main` через PR GitHub Actions:
1. Собирает Docker image с тегом `prod-<short_sha>`
2. Пушит в AWS ECR
3. Применяет миграции БД (`prisma migrate deploy`)
4. Деплоит на EC2 prod

> Каждый деплой привязан к immutable Docker image tag по commit SHA.

---

## Миграции базы данных (PostgreSQL RDS)

- Миграции идут в том же PR что и код
- На `develop` — применяются автоматически после успешных checks
- На `main` — применяются как отдельный шаг deploy job, после approve owner
- AI-агент может создавать миграции, но owner обязан проверить их перед merge в `main`
- Все миграции должны быть **forward-only** и по возможности **backward-compatible / low-downtime**
- Разрушающие изменения схемы делаются минимум в два этапа

---

## Rollback

### Откат на develop (сломанная фича)
```bash
git revert -m 1 <merge-commit-hash>
git push origin develop
```

### Откат production (аварийный)
Production rollback выполняется путём redeploy предыдущего стабильного ECR image tag.

Точные команды хранятся отдельно в ops runbook с учётом полного runtime (env vars, volumes, network, compose setup).

---

## Hotfix процесс

```
main
 └── hotfix/xxx    ← ветвиться от main
       ├── фикс + PR
       ├── merge → main      ← деплой в prod
       └── merge → develop   ← обязательно, иначе баг вернётся
```

---

## Разрешение конфликтов

1. Скачать конфликтующий файл
2. Вставить в Claude с описанием конфликта
3. Получить resolved версию
4. Запушить в ветку
5. Все CI проверки перезапускаются — merge только после зелёного статуса

---
