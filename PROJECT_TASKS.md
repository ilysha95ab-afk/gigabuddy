# GigaBuddy — Roadmap / Дорожная карта проекта

> Единый чеклист всех задач проекта GigaBuddy (не только текущего релиза).
> Ставим `[x]` по мере продвижения. Сверять с live runtime и git-историей, не с памятью.
>
> **Проект:** SnakeWatch хакатон — GigaBuddy (Ouroboros Onboarding Mentor).
> **Репозиторий:** приватный `ilysha95ab-afk/gigabuddy`, ветка `ouroboros`.
> **Последнее обновление:** 2026-07-18 · актуальный HEAD `4094f55` (v6.73.0).

---

## ✅ Сделано (реализовано и в проде)

- [x] **Safety Supervisor fix** — `ouroboros/llm.py`, распознавание cloud.ru value-rejection (`response_format.type: Input should be 'json_schema'`) → one-shot strip-and-retry.
  _v6.72.0, commit `b335c78`_
- [x] **Git/GitHub путь** — приватный репо `ilysha95ab-afk/gigabuddy`, ветка `ouroboros` запушена и проверена (`git ls-remote`).
- [x] **Vision model настроен** — OpenRouter `gpt-4o`, проверен реальным анализом скриншота.
- [x] **GigaBuddy product-mode shell** — бренд «ГигаБадди», subtitle «персональный ИИ-наставник адаптации», боковая панель адаптационного трека (Советчик → Помощник → Партнёр), скрытие novice-facing developer chrome, кнопка Panic сохранена.
  _v6.71.1, commit `d6b6869`_
- [x] **PIN-return escape hatch** — выход из product mode через 4-значный `GIGABUDDY_ADMIN_PIN`: `_handle_gigabuddy_return_action` + `_generic_gigabuddy_settings_guard`, `POST /api/settings` `_action=gigabuddy_return` (проверка PIN только на сервере).
  _v6.71.2, commit `22b41f9`_
- [x] **Mutable GigaBuddy state reducer** — `ouroboros/gigabuddy_state.py`: синтетические профили сотрудников (alice-demo / leonid-demo / blank-demo), стадии наставничества advisor → assistant → partner, задачи, пакеты опросника, novice-safe view projection. Действия: `get_state` / `select_employee` / `add_task` / `approve_stage` / `reject_stage` / `rollback` / `demo_accelerate`. Mentor/admin-кнопки убраны из UI новичка (наставник взаимодействует через Telegram / PIN-return). 35 тестов.
  _v6.73.0, commit `4094f55`_
- [x] **Устойчивое состояние GigaBuddy + interface-атрибуты (пункт 1 плана).** Конфиг сотрудника расширен до полного состояния: `profile` (имя/роль/отдел/опыт/интересы), стадия, адаптационный `track` (этапы advisor → assistant → partner со статусами), прогресс (выводится из трека), версия поведения, `rollback_history`, mentor notes — ПЛЮС блок `interface` для гиперперсонификации (тема, акцентный цвет в рамках дизайн-системы, маскот, тон, layout). Правая панель (`web/modules/gigabuddy.js`) читает живое состояние вместо статики; интерфейсные атрибуты применяются к product-mode оболочке через существующий settings-seam (`data-gigabuddy-theme/tone` + CSS-переменная `--gigabuddy-accent`), без frozen-роутов и правки `contracts.py`. Границы соблюдены: чувствительные `internal_signals`, mentor notes и rollback history не попадают в novice-view; значения валидируются (allow-list тем/тонов, hex-only акцент). Тесты и docs обновлены.
  _v6.74.0_

---

## ⬜ Не сделано (осталось)

- [ ] **Диагностическое интервью → построение персонального адаптационного трека.** GigaBuddy проводит опрос новичка и строит индивидуальный трек онбординга (какие задачи, в каком порядке, какой уровень поддержки). Чувствительные выводы (напр. тревожность) — только внутренние, новичку не показывать.
- [ ] **Telegram mentor protocol.** Наставник общается с GigaBuddy через Telegram (одобрение переходов между стадиями, постановка задач, просмотр прогресса) — вне UI новичка.
- [x] **UI-персонализация под интересы новичка (основа).** Interface-атрибуты в конфиге сотрудника (тема/акцент/маскот/тон/layout) применяются к оболочке через settings-seam; пример: кошачья тема для Алисы. «Гиперперсональный агент как базовый минимум Сбера». _v6.74.0._ Дальше — диагностический вывод интересов из интервью (пункт ниже).
- [ ] **Demo accelerator: end-to-end сценарий < 3 минут.** Полный демо-прогон (онбординг → интервью → трек → эволюция стадии → результат) уложить в 3 минуты. **30 % оценки хакатона** — наивысший приоритет из оставшегося.
- [ ] **README / презентация проекта для хакатона SnakeWatch.** Описание продукта, архитектуры, демо-инструкция, скриншоты.

---

## Прогресс

**6 / 11 задач готово.** Ядро продукта (product-mode shell, безопасный выход, мутабельное состояние, инфраструктура: safety/git/vision) собрано. Осталась продуктовая начинка для демо: интервью → трек, Telegram-протокол, персонализация, demo accelerator и презентация.
