# Roadmap

Дорожная карта wtftools. Что сделано, что планируется, что точно не входит.

## Текущий статус

**Версия:** 0.2.0 · 734 теста · 92.6% покрытие · ruff clean · 19 subcommands + `wtfd` daemon.

Фактически закрыты обе фазы из PROJECT.md (Phase 1 «CLI с 20+ checks» и Phase 2 «daemon + fleet management»). Готово к первому публичному релизу.

---

## Сделано

### Phase 1 — CLI (PROJECT.md: «1 мес, 500 GitHub stars»)
- ✓ `wtf` — одна команда, параллельные checks (38 встроенных), per-check timeout
- ✓ 6 output форматов: text / json / csv / plain / html / prometheus
- ✓ Plugin система (bash + Python SDK), 5 готовых примеров
- ✓ Snapshot / history / diff
- ✓ LLM-summary через `wtf explain --llm ollama|claude|openai|auto`
- ✓ Конфиг-файл с per-host порогами + `--ignore`
- ✓ Distribution: PyPI, debian packaging, Docker, systemd unit, MOTD installer

### Phase 2 — Fleet (PROJECT.md: «3 мес, $500 MRR за fleet management»)
- ✓ `wtfd` daemon с HTTP API (GET `/audit.json` / `/audit.prom` / `/history` / `/snapshot/N`, POST `/run-now`)
- ✓ `wtf fleet` — параллельный pull с N peer'ов, агрегация, prometheus output, `--watch`, `--run-now`
- ✓ `wtf compare HOSTA HOSTB` — config-drift между двумя серверами
- ✓ Bearer-token auth для daemon endpoints
- ✓ Multi-host fleet snapshot diff (через `wtf diff --against`)

### Обвязка
- ✓ Man page (`wtf.1`)
- ✓ Bash completion со всеми subcommands и динамическим дополнением
- ✓ JSON Schema для `audit-v1.json` и `fleet-v1.json`
- ✓ GitHub Actions: CI (3.10/3.11/3.12) + release workflow (PyPI + GHCR на tag)
- ✓ Документы: README, QUICKSTART (5-мин), PLUGIN_GUIDE, CONTRIBUTING, CHANGELOG

---

## Что планируется на v0.2.x — v0.3.0

### Hard-must перед публичным релизом
- [ ] **`git init` + первый commit.** Сейчас репозиторий не инициализирован (`git remote -v` → fatal).
- [ ] **Создать `git tag v0.2.0`** → release workflow автоматически опубликует на PyPI и GHCR.
- [ ] **Реальный PyPI namespace.** Имя `wtftools` нужно проверить и зарезервировать.
- [ ] **GitHub repo `wachawo/wtftools`** — создать публичный, залить код.
- [ ] **`GitHub secret PYPI_API_TOKEN`** — настроить для release workflow.

### Полезное, если будет внешний feedback
- [ ] **Homebrew formula.** В README упомянута, отсутствует. Несложно, ~15 строк Ruby.
- [ ] **Asciinema demo embedded в README.** Картинка ≠ видео demo; demo продаёт лучше.
- [ ] **OpenAPI-описание для wtfd HTTP API.** JSON Schema есть для outputs, OpenAPI для endpoints — нет.
- [ ] **Quickstart docker-compose** для wtfd + grafana + prometheus.
- [ ] **Pre-commit hook** для plugin authors: проверка exit-code контракта.

### Идеи без commit
- [ ] **TUI dashboard** через `curses` (`wtf tui`) — interactive drill-down. Niche.
- [ ] **`wtf fleet --save` + `wtf fleet --diff`** — snapshot всего парка, diff по времени.
- [ ] **Поддержка дополнительных alert каналов**: shell-template для Slack, Telegram, PagerDuty (примеры в `examples/alerts/`).

---

## Сознательно НЕ входит

Из PROJECT.md Phase 3 («12 мес, $25K MRR, Kubernetes-aware checks»):
- ✗ **Kubernetes node/pod checks.** Огромный scope, тянет за собой kubectl-зависимости и RBAC-флоу.
- ✗ **Marketplace для плагинов.** Преждевременно — сначала нужно сообщество.
- ✗ **Self-hosted dashboard с UI.** Prometheus + Grafana уже это закрывают через `wtfd /audit.prom`.
- ✗ **SSO / SAML / SOC2-reports.** Enterprise-фичи без enterprise-customer'а.
- ✗ **Multi-fleet aggregation** (fleet of fleets). Решается на уровне Prometheus federation.

---

## Принципы для будущих изменений

1. **Никаких heavy-weight зависимостей.** Stdlib + опциональный psutil. Всё что добавляется должно быть `pip install` без compile-step.
2. **Graceful degradation.** Если бинаря/сокета нет — `[SKIP]`, не `[FAIL]`. Проверять через `shutil.which`, `os.path.exists`.
3. **Параллельность по умолчанию.** Audit и fleet — обе через `ThreadPoolExecutor`. Не блокировать UI.
4. **Stable public API.** `from wtftools import run_audit, CheckResult, summarize` — гарантированная совместимость в minor versions.
5. **Без AI-меток в публичных артефактах.** Коммиты, PR, code-комментарии — без `Co-Authored-By` и подобного.
6. **Тесты с каждой новой фичей.** Coverage ≥80% — porog, требуемый CI.
7. **Один CHANGELOG entry на feature.** В формате Keep-a-Changelog.

---

## История итераций (для рефлексии)

С нуля до v0.2.0 — 18 итераций. Ключевые milestones:

| Иттерация | Что добавлено                                                       |
|-----------|---------------------------------------------------------------------|
| 1         | Каркас: info / audit / crontab, ~20 чеков                          |
| 2         | Параллельность не было, ещё sequential                              |
| 4         | **Параллельные checks** + PSI + kernel-taint + cert-expiry          |
| 5         | LLM `explain`, conntrack, journal-disk, man-page                   |
| 6         | **Snapshot / diff / history**, docker check, NTP drift, prometheus  |
| 8         | HTTP/TCP probes, SMART, `wtf diff` standalone                       |
| 9         | **`wtfd` daemon** с HTTP API                                        |
| 10        | LLM bridge (ollama/claude/openai), HTML output, fail2ban            |
| 11        | **`wtf fleet`** + Dockerfile                                        |
| 12        | `wtf init` wizard, examples/plugins, JSON Schemas, CI release       |
| 13        | `wtf compare HOSTA HOSTB`, doctor update-check                      |
| 14        | `wtf events` timeline, POST `/run-now`                              |
| 15        | watch-режимы для fleet и events, QUICKSTART                         |
| 16        | Plugin SDK (Python), PLUGIN_GUIDE                                   |
| 17        | v0.2.0 bump, stable public API через `__getattr__`                  |
| 18        | Maintenance pass: 142 ruff issues → 0, 2 реальных bug-fix          |

Иттерации 14-18 признаны как scope creep / polish — реальный feature work закончился к 13-й.

---

## Maintenance mode

После v0.2.0 проект переходит в **maintenance mode**:
- Bug fixes по issues — да.
- Новые built-in checks — только если 2+ пользователя независимо попросят.
- Refactor существующего кода — только при реальном bottleneck с benchmark'ом.
- Кардинальные новые subcommands — отдельный обсуждённый release (v0.3.0+).

Цикл «спросить ИИ что добавить» больше не запускается. Feature direction должен идти от реальных пользователей.
