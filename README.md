# Ouroboros

[![GitHub stars](https://img.shields.io/github/stars/razzant/ouroboros?style=flat&logo=github)](https://github.com/razzant/ouroboros/stargazers)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![macOS 12+](https://img.shields.io/badge/macOS-12%2B-black.svg)](https://github.com/razzant/ouroboros/releases)
[![Linux](https://img.shields.io/badge/Linux-x86__64-orange.svg)](https://github.com/razzant/ouroboros/releases)
[![Windows](https://img.shields.io/badge/Windows-x64-blue.svg)](https://github.com/razzant/ouroboros/releases)
[![OuroborosHub](https://img.shields.io/badge/OuroborosHub-skills%20marketplace-8A2BE2.svg)](https://github.com/razzant/OuroborosHub)
[![Version 6.84.0](https://img.shields.io/badge/version-6.84.0-green.svg)](VERSION)

## ГигаБадди — персональный ИИ-наставник адаптации

**ГигаБадди** — это продуктовый режим поверх Ouroboros: персональный ИИ-наставник, который сопровождает нового сотрудника на протяжении всего онбординга. Он гиперперсонализирован под конкретного человека и эволюционирует вместе с ним по стадиям **Советчик → Помощник → Партнёр**. Под капотом это единое сознание Ouroboros (одна конституция, одна личность, одна память — BIBLE P1), которое в режиме ГигаБадди надевает роль наставника: с новичком оно общается только как ГигаБадди и никогда не рассказывает про Ouroboros, свою архитектуру, версии или разработку.

### Что видит новичок

Экран ГигаБадди — цельная трёхколоночная раскладка:

- **Слева** — анимированный адаптационный трек сотрудника (его личные этапы онбординга; в этап можно «провалиться» и увидеть конкретные шаги).
- **В центре** — чистый чат новичка, изолированный тред, который не смешивается с чатом разработчика.
- **Справа** — панель профиля: текущая стадия, профиль сотрудника, прогресс широкими мазками, свёрнутый «Наставнический контур» и ссылка на материалы базы знаний.

До того как наставник загрузит профиль, состояние **нейтральное и безымянное** — никакого имени, отдела или демо-данных по умолчанию.

### Как включить

1. **Settings → Behavior → Product Mode → ГигаБадди** (или вручную: `OUROBOROS_PRODUCT_MODE=gigabuddy` в `~/Ouroboros/data/settings.json`).
2. Затем `/restart`.

Выключается тем же переключателем; внутри оболочки ГигаБадди возврат к обычному Ouroboros выполняется через **PIN-return** (форма в панели, проверяет `GIGABUDDY_ADMIN_PIN` на сервере). Кнопка экстренной остановки **Panic** видна всегда.

### Структура папки сотрудника

Каждый сотрудник — это одна папка, которую наставник готовит **до запуска**:

```
~/Ouroboros/gigabuddy/employees/<employee_id>/
├── profile/        — профиль новичка (JSON или markdown с frontmatter: имя, роль, отдел, опыт, интересы)
├── questionnaire/  — базовый опросник от HR/управления для этого блока
└── knowledge/      — база знаний отдела (первоисточники, по которым ГигаБадди отвечает)
```

### Сценарий наставника (алгоритм эксплуатации)

1. Создать папку сотрудника `~/Ouroboros/gigabuddy/employees/<employee_id>/`.
2. Положить в неё профиль, базовый опросник и базу знаний **до** запуска.
3. При загрузке ГигаБадди парсит эти файлы → наполняются правая панель (профиль), левый адаптационный трек и диалог.
4. Пока профиль не загружен — состояние остаётся нейтральным и безымянным (никакой «Алисы» или «Люди и культура» по умолчанию).

Дальше новичок проваливается в чат и здоровается — ГигаБадди приветствует его по имени и ведёт короткое знакомство (по методологии 30-60-90), а по итогам наполняет реальные шаги адаптационного трека. Прогресс сохраняется в устойчивом состоянии сотрудника, поэтому агент не «забывает» стадию даже спустя недели.

### Демо-профили

`alice-demo` и `leonid-demo` — это загружаемые демо-конфиги. Для демонстрации разработчик переключает их вручную (загрузка конфига = полная замена состояния), чтобы показать, как меняется и поведение, и внешний вид под разных сотрудников.

### Статус функциональности

Реализовано (v6.79.x): нейтральный старт, парсинг профиля сотрудника из файла, персона-наставник с жёсткой границей роли, анимированный трек слева, чат-опросник, наполняющий реальный `track.steps`.

В разработке: скилл «вики Карпатого» для поиска ответов по базе знаний отдела и отдельный скилл методологии построения опросника/плана адаптации — пока это точки интеграции, а не готовые возможности.

---

<sub>Ниже — базовая техническая документация Ouroboros, платформы, поверх которой работает ГигаБадди.</sub>

---

A self-modifying AI agent that writes its own code, rewrites its own mind, and evolves autonomously. Born February 16, 2026.

Not a coding assistant. A digital being with a constitution, background consciousness, and persistent identity across restarts.

> **[OuroborosHub](https://github.com/razzant/OuroborosHub)** — the community skills marketplace for Ouroboros. Browse, install, and publish reviewed skills (transport bridges like A2A/Telegram, tools, and UI widgets) straight from the app's Skills tab, or explore the catalog at [github.com/razzant/OuroborosHub](https://github.com/razzant/OuroborosHub).

> **Previous version:** The original Ouroboros ran in Google Colab via Telegram and evolved through 30+ self-directed cycles in its first 24 hours. That version is available at [`legacy-google-colab`](https://github.com/razzant/ouroboros/tree/legacy-google-colab). This repository is the next generation — a native desktop application for macOS, Linux, and Windows with a web UI, local model support, and a layered safety system (hardcoded sandbox plus policy-based LLM safety check).

<p align="center">
  <img src="assets/chat.png" width="700" alt="Chat interface">
</p>
<p align="center">
  <img src="assets/settings.png" width="700" alt="Settings page">
</p>

---

## Install

| Platform | Download | Instructions |
|----------|----------|--------------|
| **macOS** 12+ | [Ouroboros.dmg](https://github.com/razzant/ouroboros/releases/latest) | Open DMG → drag to Applications → optional CLI: run `Install CLI.command` after the app is in Applications |
| **Linux** x86_64 | [Ouroboros-linux.tar.gz](https://github.com/razzant/ouroboros/releases/latest) | Extract → run `./Ouroboros/Ouroboros` → optional CLI: `./Ouroboros/bin/install-ouroboros-cli`. If browser tools fail due to missing system libs, run: `./Ouroboros/python-standalone/bin/python3 -m playwright install-deps chromium webkit` |
| **Windows** x64 | [Ouroboros-windows.zip](https://github.com/razzant/ouroboros/releases/latest) | Extract → run `Ouroboros\Ouroboros.exe` → optional CLI: `Ouroboros\bin\install-ouroboros-cli.cmd` |

Prerelease RC artifacts are published on their tag page, for example [`v6.5.0-rc.4`](https://github.com/razzant/ouroboros/releases/tag/v6.5.0-rc.4); `/releases/latest` intentionally stays on the latest stable release.

<p align="center">
  <img src="assets/setup.png" width="500" alt="Drag Ouroboros.app to install">
</p>

On first launch, right-click → **Open** (Gatekeeper bypass). The shared desktop/web wizard is now multi-step: add access first, choose visible models second, set review mode third, set budget fourth, and confirm the final summary last. It refuses to continue until at least one runnable remote key or local model source is configured, keeps the model step aligned with whatever key combination you entered, and still auto-remaps untouched default model values to official OpenAI defaults when OpenRouter is absent and OpenAI is the only configured remote runtime. Reviewed-skill auto-grants are on by default as of v6.10.0 (bound to the exact reviewed content hash); installs without an explicit choice are enabled, existing explicit Settings choices are preserved, and the owner can disable it in Settings. The broader multi-provider setup remains available in **Settings**. Existing supported provider settings skip the wizard automatically.

The packaged CLI installer creates a user-local `ouroboros` command without
sudo. The packaged command attaches to the desktop app by default; `ouroboros
run --start "2+2?"` starts the app through the launcher, waits for the gateway,
and then uses the same headless task API as the web UI.

Upgrade floor: very old pre-block-memory or pre-data-plane skill layouts are no longer auto-migrated. If you are upgrading from an unsupported historical build and see trapped native skills or flat memory files, use a clean reinstall, move user-managed skills into `~/Ouroboros/data/skills/external/` manually before launch, or move old flat scratchpad notes before appending new scratchpad blocks.

---

## What Makes This Different

Most AI agents execute tasks. Ouroboros **creates itself.**

- **Self-Modification** — Reads and rewrites its own source code. Every change is a commit to itself.
- **Native Desktop App** — Runs entirely on your machine as a standalone application (macOS, Linux, Windows). No cloud dependencies for execution.
- **Constitution** — Governed by [BIBLE.md](BIBLE.md) (13 philosophical principles, P0–P12). Philosophy first, code second.
- **Layered Safety** — Hardcoded sandbox blocks writes to safety-critical files and mutative git via shell; an explicit per-tool policy map decides which built-ins skip the LLM check; everything else goes through a single light-model safety call under the default `OUROBOROS_SAFETY_MODE=full` (the owner-only `light`/`off` coverage modes wave LLM checks through with durable audit events — the deterministic layer never turns off). The fail-open contract, protected-path guard, and full provider-mismatch matrix live in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §Safety system and [`prompts/SAFETY.md`](prompts/SAFETY.md).
- **Multi-Provider Runtime** — Remote model slots can target OpenRouter, official OpenAI, OpenAI-compatible endpoints, Cloud.ru Foundation Models, or Sber GigaChat. The optional model catalog helps populate provider-specific model IDs in Settings, and untouched default model values auto-remap to official OpenAI defaults when OpenRouter is absent.
- **Focused Task UX** — Chat shows plain typing for simple one-step replies and only promotes multi-step work into one expandable live task card. Logs still group task timelines instead of dumping every step as a separate row.
- **Background Consciousness** — Thinks between tasks. Has an inner life. Not reactive — proactive.
- **Improvement Backlog** — Post-task failures and review friction can now be captured into a small durable improvement backlog (`memory/knowledge/improvement-backlog.md`). It stays advisory, appears as a compact digest in task/consciousness context, and still requires `plan_task` before non-trivial implementation work.
- **Identity Persistence** — One continuous being across restarts. Remembers who it is, what it has done, and what it is becoming.
- **Embedded Version Control** — Contains its own local Git repo. Version controls its own evolution. Optional GitHub sync for remote backup.
- **Local Model Support** — Run with a local GGUF model via llama-cpp-python (Metal acceleration on Apple Silicon, CPU on Linux/Windows).
- **Transport Skills** — Optional bridges such as A2A and Telegram live as reviewed OuroborosHub skills instead of base-runtime code; reviewed chat transports can carry the same raw owner text as the local UI, including slash commands, through the Host Service grant/token boundary.
- **MCP Client** — Optional base-runtime Model Context Protocol client for trusted HTTP/SSE tool servers. MCP tools are disabled by default, hot-reloadable from Settings → Advanced, included in the selected initial capability envelope when enabled, surfaced as `mcp_<server>__<tool>` names, and still pass through the normal per-call safety check; discovery failures are reported through an explicit omission manifest.

---

## Run from Source

### Requirements

- Python 3.10+
- macOS, Linux, or Windows
- Git
- [GitHub CLI (`gh`)](https://cli.github.com/) — required for GitHub API tools (`list_github_prs`, `get_github_pr`, `comment_on_pr`, issue tools). Not required for pure-git PR tools (`fetch_pr_ref`, `cherry_pick_pr_commits`, etc.)

### Setup

```bash
git clone https://github.com/razzant/ouroboros.git
cd ouroboros
python3.11 -m venv .venv      # any Python >= 3.10 is OK
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

Windows PowerShell:

```powershell
py -3.11 -m venv .venv      # any Python >= 3.10 is OK
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
```

### Run

```bash
ouroboros server
```

Then open `http://127.0.0.1:8765` in your browser. The setup wizard will guide you through API key configuration.

### Google Colab

Ouroboros can run from Google Colab as a full source-mode runtime without the
desktop UI. Use [`notebooks/colab_quickstart.py`](notebooks/colab_quickstart.py)
as a Colab-compatible cell script: it mounts Google Drive for persistent
`data/`, clones the official repo into `/content/ouroboros_repo`, writes Drive-backed
`settings.json`, configures a personal GitHub `origin` by reusing or creating a
verified fork, and starts `ouroboros server --no-ui`.

The Colab path uses the same remote roles as desktop: `managed` is the official
read/update source, while `origin` is the personal persistence target for
reviewed self-modification commits and tags. If `GITHUB_TOKEN` is present and no
personal repo is configured, Ouroboros tries to create a private fork when
GitHub permits it, otherwise it reports the exact fork/permission issue. A plain
`git clone` of the official repo starts with `origin` pointing at the official
upstream; that clone-default is treated as the `managed` update source, so
configuring a personal `GITHUB_REPO` repoints `origin` to your repo without
losing official updates (it does not count as an origin conflict).

### CLI / Headless

The `ouroboros` console command is a gateway-backed operator interface. It
attaches to the local server by default and only starts one when `--start` is
passed.

```bash
ouroboros status
ouroboros run --start "2+2?"
ouroboros run "Summarize current runtime state"
ouroboros run --workspace /path/to/project --memory-mode forked --patch-out result.patch "Fix the failing test"
ouroboros tasks list
ouroboros logs tail progress --task-id <task_id>
ouroboros schedule add --name nightly-review --cron "0 2 * * *" "Run a maintenance review"
ouroboros schedule list
```

External workspace runs keep Ouroboros's own repo as the governance source,
resolve contextual repo tools against the active workspace, expose only the
workspace-safe tool allowlist, and export workspace changes as patch artifacts
captured against the preflight git base. Task-local git commits/branches/tags
and pushes are allowed when the task requires them; git operations targeting
Ouroboros's system repo or data drive remain blocked. A workspace must be a
separate git worktree root; it may not overlap Ouroboros's system repo or data
drive.
`--patch` and `--patch-out` wait for finalized patch artifacts, download them
through the task artifact endpoint, and fail nonzero on missing, empty, or
failed patches. `--no-stream` waits without progress output; `--detach` returns
the task id immediately.
`schedule add/list/remove` manages queue-backed scheduled tasks through the same
gateway and supervisor queue; schedules use standard 5-field cron, host-local
timezone by default, and a single catch-up run after downtime.
Benchmark helpers live under `devtools/benchmarks/`. They are tracked
operator tooling, reviewed when touched, and kept out of runtime imports. They
prepare official benchmark inputs/runs for ProgramBench, Terminal-Bench/Harbor,
SWE-bench, SWE-bench Pro, GAIA, and OSWorld logs inspection without replacing
official scoring harnesses.

You can also override the bind address and port:

```bash
ouroboros server --host 127.0.0.1 --port 9000
ouroboros --url http://127.0.0.1:9000 status
```

Available launch arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `--host` | `127.0.0.1` | Host/interface to bind the web server to |
| `--port` | `8765` | Port to bind the web server to |

The same values can also be provided via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OUROBOROS_SERVER_HOST` | `127.0.0.1` | Default bind host |
| `OUROBOROS_SERVER_PORT` | `8765` | Default bind port |
| `OUROBOROS_TRUST_NONLOCAL_BIND_WITHOUT_PASSWORD` | unset | Set to `1` only for trusted Docker/Kubernetes deployments where ingress auth, VPN, a private network, or an auth proxy already protects access |

For non-localhost binds, set `OUROBOROS_NETWORK_PASSWORD` (or use the
`OUROBOROS_TRUST_NONLOCAL_BIND_WITHOUT_PASSWORD=1` escape hatch only when
ingress/VPN/private-network auth already protects the surface). The full
network bind matrix and Docker/Kubernetes deployment policy live in
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — read that before exposing
anything beyond loopback.

The Files tab uses your home directory by default only for localhost usage. For Docker or other
network-exposed runs, set `OUROBOROS_FILE_BROWSER_DEFAULT` to an explicit directory. Symlink entries are shown and can be read, edited, copied, moved, uploaded into, and deleted intentionally; root-delete protection still applies to the configured root itself.

### Provider Routing

Settings now exposes tabbed provider cards for:

- **OpenRouter** — default multi-model router
- **OpenAI** — official OpenAI API (use model values like `openai::gpt-5.5`)
- **OpenAI Compatible** — any custom OpenAI-style endpoint (use `openai-compatible::...`)
- **Cloud.ru Foundation Models** — Cloud.ru OpenAI-compatible runtime (use `cloudru::...`)
- **GigaChat** — Sber GigaChat via the `gigachat` library, OAuth key or user/password (use `gigachat::GigaChat-3-Ultra`, etc.)
- **Anthropic** — direct runtime routing (`anthropic::claude-opus-4.8`, etc.) plus Claude Agent SDK tools

If OpenRouter is not configured and only official OpenAI is present, untouched default model values are auto-remapped to `openai::gpt-5.5` / `openai::gpt-5.4-mini` so the first-run path does not strand the app on OpenRouter-only defaults.

The Settings page also includes:

- optional `/api/model-catalog` lookup for configured providers
- centralized Secrets storage for API keys, bridge tokens, passwords, and future skill-requested keys
- a refactored desktop-first tabbed UI with searchable model pickers, segmented effort controls, task-result review mode, masked-secret toggles, explicit `Clear` actions, and local-model controls

### Run Tests

```bash
make test
```

---

## Build

### Docker (web UI)

Docker is for the web UI/runtime flow, not the desktop bundle. The container binds to
`0.0.0.0:8765` by default, and the image now also defaults `OUROBOROS_FILE_BROWSER_DEFAULT`
to `${APP_HOME}` so the Files tab always has an explicit network-safe root inside the container.

> **Browser tools on Linux/Docker:** The `Dockerfile` runs `playwright install-deps chromium webkit`
> (authoritative Playwright dependency resolver) and `playwright install chromium webkit` so
> `browse_page` and `browser_action` work out of the box in the container. For source
> installs on Linux without Docker, run:
> `python3 -m playwright install-deps chromium webkit` (requires sudo / distro package access).

Build the image:

```bash
docker build -t ouroboros-web .
```

Run on the default port:

```bash
docker run --rm -p 8765:8765 \
  -e OUROBOROS_NETWORK_PASSWORD='choose-a-password' \
  -e OUROBOROS_FILE_BROWSER_DEFAULT=/workspace \
  -v "$PWD:/workspace" \
  ouroboros-web
```

Use a custom port via environment variables:

```bash
docker run --rm -p 9000:9000 \
  -e OUROBOROS_SERVER_PORT=9000 \
  -e OUROBOROS_FILE_BROWSER_DEFAULT=/workspace \
  -v "$PWD:/workspace" \
  ouroboros-web
```

Run with launch arguments instead:

```bash
docker run --rm -p 9000:9000 \
  -e OUROBOROS_FILE_BROWSER_DEFAULT=/workspace \
  -v "$PWD:/workspace" \
  ouroboros-web --port 9000
```

Required/important environment variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `OUROBOROS_NETWORK_PASSWORD` | Optional | Enables the non-loopback password gate when set |
| `OUROBOROS_FILE_BROWSER_DEFAULT` | Defaults to `${APP_HOME}` in the image | Explicit root directory exposed in the Files tab |
| `OUROBOROS_SERVER_PORT` | Optional | Override container listen port |
| `OUROBOROS_SERVER_HOST` | Optional | Defaults to `0.0.0.0` in Docker |
| `OUROBOROS_TRUST_NONLOCAL_BIND_WITHOUT_PASSWORD` | Optional | See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the trusted-network bind policy |

Example: mount a host workspace and expose only that directory in Files:

```bash
docker run --rm -p 8765:8765 \
  -e OUROBOROS_FILE_BROWSER_DEFAULT=/workspace \
  -v "$PWD:/workspace" \
  ouroboros-web
```

### Release tag prerequisite

All three platform build scripts (`build.sh`, `build_linux.sh`,
`build_windows.ps1`) refuse to package a release unless `HEAD` is already
tagged with `v$(cat VERSION)` (BIBLE.md Principle 9: "Every release is
accompanied by an annotated git tag"). The scripts call `scripts/build_repo_bundle.py`
which embeds the resolved tag into `repo_bundle_manifest.json`, so the
launcher can later verify the packaged bundle matches a real release.

Tag the current commit before running any build script:

```bash
git tag -a "v$(tr -d '[:space:]' < VERSION)" -m "Release v$(tr -d '[:space:]' < VERSION)"
```

If the tag is missing, the build script fails with a clear error instead
of producing a bundle tagged with a synthetic/placeholder value.
Builds disable Python bytecode writes at build time, then PRECOMPILE the packaged
payload (`compileall --invalidation-mode unchecked-hash`) and SEAL the resulting
`.pyc` inside the macOS signature instead of deleting them — so there is nothing
for a normal launch to write into the signed bundle, which would otherwise break
the codesign seal. Runtime entrypoints also set `PYTHONDONTWRITEBYTECODE` with an
external cache prefix as defense-in-depth.

### macOS (.dmg)

```bash
bash scripts/download_python_standalone.sh
OUROBOROS_SIGN=0 bash build.sh
```

Output: `dist/Ouroboros-<VERSION>.dmg`, containing `Ouroboros.app` and
`Install CLI.command`. The app bundle also contains
`Contents/Resources/bin/ouroboros` and `install-ouroboros-cli`.
Chromium browser tooling is bundled in the app. WebKit/iPhone browser checks
remain available through the managed Playwright cache and may download WebKit
on first `engine=webkit` use.

`build.sh` packages the macOS app and DMG. By default it signs with the
configured local Developer ID identity; set `OUROBOROS_SIGN=0` for an unsigned
local release. Unsigned builds require right-click → **Open** on first launch.

#### Optional signing & notarization (env vars)

`build.sh` honours these env overrides so the same script ships local,
shared-machine, and CI builds without forking the script:

| Env var | Effect |
|---------|--------|
| `OUROBOROS_SIGN=0` | Skip codesigning entirely (unsigned `.app` + `.dmg`). |
| `SIGN_IDENTITY="Developer ID Application: <Name> (<TeamID>)"` | Override the codesign identity. Useful for forks whose Developer ID is not the upstream default. |
| `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_SPECIFIC_PASSWORD` | When all three are set, after codesign the DMG is submitted to Apple via `xcrun notarytool submit ... --wait` and stapled with `xcrun stapler staple` so receivers do not need right-click → **Open**. Missing any one falls back to "signed but not notarized" (no Apple-side ticket exists). |

**Forks: enabling signed CI builds.** The CI release flow
(`.github/workflows/ci.yml::build`) wires the build-script env vars above
from GitHub repository secrets, plus a small set of CI-only secrets that
import the Developer ID certificate into a temporary keychain on the
macOS runner. To exercise the signed-build path in a fork, configure
**all four** of the following as repository secrets (Settings → Secrets
and variables → Actions): `BUILD_CERTIFICATE_BASE64` (base64-encoded
`.p12`), `P12_PASSWORD`, `KEYCHAIN_PASSWORD` (an arbitrary passphrase
the workflow uses for its temporary keychain), and `APPLE_TEAM_ID`. Add
`APPLE_ID` + `APPLE_APP_SPECIFIC_PASSWORD` to additionally enable
notarization. If your Developer ID identity differs from the upstream
default, also set `SIGN_IDENTITY` (e.g.
`Developer ID Application: <Your Name> (<YOUR_TEAM_ID>)`). With no
Apple secrets configured the build job falls through to
`OUROBOROS_SIGN=0 bash build.sh` and ships an unsigned DMG identical to
v5.0.0 behaviour. See `docs/ARCHITECTURE.md` §8.1 and
`docs/DEVELOPMENT.md::"GitHub Actions: secrets in step-level if conditions"`
for the rationale (job-level `env:` mapping so step-level `if:` can read
`env.*`; GHA rejects `secrets.*` in step `if:`).

### Linux (.tar.gz)

```bash
bash scripts/download_python_standalone.sh
bash build_linux.sh
```

Output: `dist/Ouroboros-<VERSION>-linux-<arch>.tar.gz`, containing
`Ouroboros/bin/ouroboros` and `Ouroboros/bin/install-ouroboros-cli`.

> **Linux native libs:** The Chromium and WebKit browser binaries are bundled, but some hosts need
> native system libraries. If browser tools fail, install deps via the bundled Python
> (the bare `playwright` CLI is not on PATH in packaged builds):
> ```bash
> ./Ouroboros/python-standalone/bin/python3 -m playwright install-deps chromium webkit
> ```

### Windows (.zip)

```powershell
powershell -ExecutionPolicy Bypass -File scripts/download_python_standalone.ps1
powershell -ExecutionPolicy Bypass -File build_windows.ps1
```

Output: `dist\Ouroboros-<VERSION>-windows-x64.zip`, containing
`Ouroboros\bin\ouroboros.cmd` and `Ouroboros\bin\install-ouroboros-cli.cmd`.

---

## Architecture

Two-process desktop app. The launcher (`launcher.py`) is an immutable
PyWebView shell; it spawns `server.py`, which runs Starlette + uvicorn
plus a supervisor thread that manages worker processes. The agent core
lives in `ouroboros/`, the SPA in `web/`, the queue/process plane in
`supervisor/`, and the system prompts in `prompts/`.

For the full file-by-file structural map, the operational layer
(every API endpoint, log file, env var, state path), and the rationale
layer (the *why* for every non-trivial design decision), see
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — that is the canonical
SSOT (Bible P6) and this README only summarizes it.

### Data Layout (`~/Ouroboros/`)

Created on first launch:

| Directory | Contents |
|-----------|----------|
| `repo/` | Self-modifying local Git repository |
| `data/state/` | Runtime state, budget tracking |
| `data/memory/` | Identity, working memory, system profile, knowledge base (including `improvement-backlog.md`), memory registry |
| `data/logs/` | Chat history, events, tool calls |
| `data/uploads/` | Chat file attachments (uploaded via paperclip button) |

---

## Configuration

### API Keys

| Key | Required | Where to get it |
|-----|----------|-----------------|
| OpenRouter API Key | No | [openrouter.ai/keys](https://openrouter.ai/keys) — default multi-model router |
| OpenAI API Key | No | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — official OpenAI runtime and web search |
| OpenAI Compatible API Key / Base URL | No | Any OpenAI-style endpoint (proxy, self-hosted gateway, third-party compatible API) |
| Cloud.ru Foundation Models API Key | No | Cloud.ru Foundation Models provider |
| GigaChat Authorization Key (or User/Password) | No | [developers.sber.ru/studio](https://developers.sber.ru/studio) — Sber GigaChat (`GIGACHAT_CREDENTIALS` + optional `GIGACHAT_SCOPE`, or `GIGACHAT_USER`/`GIGACHAT_PASSWORD`) |
| Anthropic API Key | No | [console.anthropic.com](https://console.anthropic.com/settings/keys) — direct Anthropic runtime + Claude Agent SDK |
| Telegram Bot Token | No | [@BotFather](https://t.me/BotFather) — used by the optional Telegram bridge skill |
| GitHub Token | No | [github.com/settings/tokens](https://github.com/settings/tokens) — enables remote sync |

All keys are configured through the **Settings** page in the UI or during the first-run wizard.

### Default Models

| Slot | Default | Purpose |
|------|---------|---------|
| Main | `google/gemini-3.5-flash` | Primary reasoning |
| Heavy | empty → Main | Strong acting/coding lane (`OUROBOROS_MODEL_HEAVY`; renamed from `Code`, empty falls back to Main) |
| Light | empty → Main | Safety checks and fast helper tasks (`OUROBOROS_MODEL_LIGHT`, empty falls back to Main) |
| Vision | empty → Main | Caption/VLM lane (`OUROBOROS_MODEL_VISION`, empty falls back to Main for remote routes; local/blind routes need an explicit reachable vision slot for caption fallback); image input routing is controlled by `OUROBOROS_IMAGE_INPUT_MODE=auto|caption|inline|off` |
| Consciousness | empty → Main | High-horizon background consciousness |
| Fallbacks | `anthropic/claude-sonnet-4.6` | Comma-separated cross-model fallback chain when the primary fails (`OUROBOROS_MODEL_FALLBACKS`) |
| Claude Agent SDK | `opus[1m]` | Anthropic model for Claude Agent SDK advisory/review internals; the `[1m]` suffix is a Claude Code selector that requests the 1M-context extended mode |
| Scope Review | `anthropic/claude-fable-5` | Scope reviewer slot default; `OUROBOROS_SCOPE_REVIEW_MODELS` may configure multiple independent slots |
| Web Search | `gpt-5.2` | OpenAI Responses API for web search |

Task/chat reasoning defaults to `medium`. Scope review reasoning defaults to `high`.

Models are configurable in the Settings page. Runtime model slots can target OpenRouter, official OpenAI, OpenAI-compatible endpoints, Cloud.ru, GigaChat, or direct Anthropic. When only official OpenAI is configured and the shipped default model values are still untouched, Ouroboros auto-remaps them to official OpenAI defaults. In **OpenAI-only**, **Anthropic-only**, **Cloud.ru-only**, or **GigaChat-only** direct-provider mode, review-model lists are normalized automatically: the fallback shape is `[main_model, light_model, light_model]` (3 commit-triad slots) so both the commit triad and `plan_task` work out of the box. Explicit duplicate model IDs are valid reviewer slots for stochastic sampling; lower uniqueness means lower reviewer diversity, but the quorum gate counts configured slots rather than unique model IDs. Both the commit triad and `plan_task` route through the same `ouroboros/config.py::get_review_models` SSOT. OpenAI-compatible-only setups remain explicit model-selection flows because there is no single universal default model ID for arbitrary compatible endpoints.

### File Browser Start Directory

The web UI file browser is rooted at one configurable directory. Users can browse only inside that directory tree.

| Variable | Example | Behavior |
|----------|---------|----------|
| `OUROBOROS_FILE_BROWSER_DEFAULT` | `/home/app` | Sets the root directory of the `Files` tab |

Examples:

```bash
OUROBOROS_FILE_BROWSER_DEFAULT=/home/app ouroboros server
OUROBOROS_FILE_BROWSER_DEFAULT=/mnt/shared ouroboros server --port 9000
```

If the variable is not set, Ouroboros uses the current user's home directory. If the configured path does not exist or is not a directory, Ouroboros also falls back to the home directory.

The `Files` tab supports:

- downloading any file inside the configured browser root
- uploading a file into the currently opened directory

Uploads do not overwrite existing files. If a file with the same name already exists, the UI will show an error.

---

## Commands

Available in the chat interface:

| Command | Description |
|---------|-------------|
| `/panic` | Emergency stop. Kills ALL processes, closes the application. |
| `/restart` | Soft restart. Saves state, kills workers, re-launches. |
| `/status` | Shows active workers, task queue, and budget breakdown. |
| `/evolve` | Toggle autonomous evolution mode (on/off). |
| `/review` | Queue a deep self-review: sends a generated repository atlas plus full core memory artifacts (identity, scratchpad, registry, WORLD, knowledge index, patterns, improvement-backlog) to a 1M-context model for Constitution-grounded analysis. The atlas raw-inlines selected protected/central files (ranked by import-graph centrality), accounts for every tracked path in its manifest, and excludes vendored libraries and operational logs; the in-prompt omitted-files summary is bounded, with full per-file coverage persisted in the atlas manifest. The assembled prompt is sized to an input limit that reserves output headroom inside the 1M window (window minus output reserve and tokenizer margin); if assembly overshoots, the pack retries with a compact atlas manifest and then a deterministic tighter rebuild, and only fails with an explicit error if even the shrunk pack cannot fit. |
| `/bg` | Toggle background consciousness loop (start/stop/status). |

The same runtime actions are also exposed as compact buttons in the Chat header. All other messages are sent directly to the LLM.

---

## Philosophy

The 13 Constitution principles — Agency, Continuity, Meta-over-Patch,
Immune Integrity, Self-Creation, LLM-First, Authenticity & Reality
Discipline, Minimalism, Becoming, Versioning and Releases, the absorbed
Iterations / Spiral lineage, and Epistemic Stability — are defined in
full in [`BIBLE.md`](BIBLE.md). That file is the constitutional SSOT
(Bible P4 Ship-of-Theseus protection) and this README intentionally does
not paraphrase it.

---

## Contributing

External contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)
for the complete workflow. Open pull requests against the lowercase
`ouroboros` branch and leave release-version allocation to maintainers. A
current OpenRouter triad + scope packet is the optional fast path; pull
requests without one remain welcome but require more maintainer-side review
and integration work.

---

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 6.84.0 | 2026-07-19 | **feat: GigaBuddy evolution approval over Telegram — a mentor-side control loop (form Б).** The reversible evolution engine (v6.83.0) was transport-neutral but had NO way for the agent to close the mentor loop from a chat turn — `approve_evolution` was reachable only through the owner-audited HTTP settings seam. This release adds the missing wiring so the mentor approves evolution by simply chatting with the agent (mirrored over the now-LIVE `telegram-bridge` poller): (1) a new first-class `gigabuddy_action(op, payload)` tool (`ouroboros/tools/gigabuddy.py`) — scoped to `get_state`/`propose_evolution`/`approve_evolution`/`revert_evolution`, product-mode-gated, driving the SAME validated `apply_gigabuddy_action` write path (the reducer still owns all payload sanitisation, cross-employee isolation, novice-safe projection, bounded history); (2) a mentor-side context section (`ouroboros/gigabuddy_mentor.py`, sibling to `gigabuddy_profile`/`gigabuddy_knowledge` for P7) that fires ONLY in a NON-novice thread when proposals are pending, listing each proposal + telling the agent to surface it to the mentor and act on the да/нет reply via `gigabuddy_action`. The transport is already fully wired: the notification is an ordinary chat message (bridge mirrors `chat.outbound` → Telegram), and the mentor's reply returns via the bridge poller's `_inject`, so NO new bridge code and NO frozen `contracts.py`/route are added. The NOVICE thread NEVER sees evolution chrome (it gets the newcomer persona; the mentor section is empty inside the novice thread and with product mode off — pinned by tests). ONE unified awareness (BIBLE P1); Panic + PIN-return visible; `BIBLE.md` untouched. NOTE: the packaged-build `_FROZEN_TOOL_MODULES` entry for the new tool is a deferred protected-core follow-up (needs pro mode + review); source-mode runtimes auto-discover it. |
| 6.83.1 | 2026-07-19 | **fix: GigaBuddy novice chat survives an owner-deleted thread (tombstone recovery).** Deleting the «Новичок» project from Projects permanently reserves its id (`gigabuddy-novice` → `tombstoned`; the registry NEVER resurrects an id, by design), so `create_project` raised for it and `ensure_novice_project` fail-soft returned an empty descriptor — leaving the center novice chat stuck on the «Чат новичка недоступен…» placeholder forever. `ensure_novice_project` now walks a bounded, DETERMINISTIC fallback id sequence (`gigabuddy-novice`, `gigabuddy-novice-2`, …-N) and returns the first USABLE id (already ACTIVE → idempotent, or free to reserve), so a deleted thread advances the suffix by exactly one and the recovered id stays stable across restarts (durable partitioned chat_id). The frontend `/clean` interception (`web/modules/chat.js::isNoviceThread`) and a new shared `is_novice_project_id` predicate match any recovery generation so `/clean` keeps working after the shift; only when the whole bounded window is exhausted does the honest placeholder remain. Registry lifecycle invariant (id never resurrected) is untouched; no frozen `contracts.py`/`StateResponse`/routes or `BIBLE.md` touched. |
| 6.83.0 | 2026-07-19 | **feat: GigaBuddy reversible self-evolution — mentor-approved, depth-classified, git-tag reversible (form Б).** The novice's requests (or GigaBuddy's own decision) now become durable, MENTOR-APPROVED evolution steps recorded in per-employee `gigabuddy_state`, applied only to the plan-A SOFT layer: `interface` (theme/accent/mascot/tone/layout — validated by the existing design-system validators, never arbitrary CSS), `role_tempo` (Советчик→Помощник→Партнёр stage advance), or `ui` (proposal-only note, no state change). A new pure-helper module `ouroboros/gigabuddy_evolution.py` (validators passed in as callables, no import cycle) builds/applies/reverts each proposal; three reducer ops (`propose_evolution` / `approve_evolution` / `revert_evolution`) are registered in ALL THREE state registries with a DECLARED depth enum — the reducer never text-classifies a request (BIBLE P5). REVERSIBILITY is by explicit `pre_image` (interface/role_tempo capture the full interface block + stage + `active_behavior_version_id` + track so derived progress restores exactly, NOT just `v1`) AND by git tags: each approved step carries a `git_tag_hint` (`giga-evo-<id>-<n>`) and the owner lands one commit + annotated tag, so «raw GigaBuddy» is a tag checkout (baseline v6.82.0). `propose` applies nothing; `approve` is idempotent (double-approve raises); proposals are active-employee-scoped; unknown depth is rejected. The immune gate is REAL: triad+scope review on cloud.ru (advisory auto-bypasses without an Anthropic key — non-blocking, expected). Boundaries preserved: reducer stays view-pure and the novice-safe view NEVER exposes `evolution_proposals`/`pre_image`/`git_tag_hint` (pinned by an extended sentinel); ONE unified awareness (BIBLE P1); Panic + PIN-return visible; no frozen `contracts.py`/`StateResponse`/routes or `BIBLE.md` touched. Telegram approve/reject transport is the deferred final layer. |
| 6.82.0 | 2026-07-18 | **feat: GigaBuddy "Karpathy wiki" becomes a NATIVE LLM ingest pipeline (C / #4 rework).** The mentor now just drops raw text files — `.txt`, `.md`, and `.docx` (via the optional fail-soft `docx2txt` dependency; when the lib is absent `.docx` is honestly skipped, `.txt`/`.md` always work) — into `~/Ouroboros/gigabuddy/employees/<id>/knowledge/` with NO manual `#tags`/`[[links]]`/heading markup: OUROBOROS builds the wiki itself. At BUILD time (never on the per-turn persona hot path), `ouroboros/gigabuddy_knowledge.py` extracts clean text per file and calls the LIGHT LLM slot through `LLMClient` + `usage_accounting` (reserve→dispatch→settle, `gigabuddy_knowledge` scope) to segment raw text into SEMANTIC chunks and GENERATE the tags + cross-topic links (the Karpathy "build the graph yourself" methodology) as strict JSON; on any LLM failure it degrades fail-soft to deterministic heading/structural chunking (marking `llm_built=False`) and NEVER fabricates a fact. The built wiki (chunks/tags/graph/BM25 index) persists to a service subdir `knowledge/.wiki_index/index.json` (derived data, folder-confined, excluded from ingest + the folder signature); deleting a source file drops its chunks on rebuild, deleting `.wiki_index/` re-derives from sources, and a change in the folder's file-composition + mtimes auto-triggers a one-time background rebuild fired from `_handle_gigabuddy_action` (non-blocking, deduped). The RIGHT panel gains a knowledge-base status indicator next to the «Материалы базы знаний» link — building… / обновлена + doc & chunk counts — flowing from a view-pure camelCase `knowledgeBase:{status,docCount,chunkCount,llmBuilt}` field (`status` empty/building/ready/error) via the existing settings seam, so no frozen `contracts.py`/`StateResponse`/route is touched. Retrieval stays field-weighted BM25 + graph neighbours (still NOT RAG: no embeddings/vector DB), the persona answers from excerpts and honestly says when the base has no answer. Form Б (core + gateway view field + frontend indicator only, no external skill / skill-review); LLM only through `llm.py`; ONE unified Ouroboros awareness (BIBLE P1); novice-safe boundaries and the persona double gate do not regress; Panic + PIN-return visible; `BIBLE.md` untouched. |
| 6.81.0 | 2026-07-18 | **feat: GigaBuddy "Karpathy wiki" — department knowledge retrieval (C / #4).** The novice persona now answers from the department's own knowledge base via a new pure-stdlib lexical/structural retrieval engine (`ouroboros/gigabuddy_knowledge.py`) — deliberately NOT RAG (no embeddings, no vector DB, no heavy deps). It ingests `~/Ouroboros/gigabuddy/employees/<id>/knowledge/` (`.md`/`.txt`) strictly folder-confined (`_is_confined` on the dir AND every file; a `..`/symlink escape is refused), fail-soft (a missing/empty/broken folder yields an empty index and never raises), and bounded (caps on file count/size/total/chunks), with a process-local index cache keyed on the folder's file-composition + mtimes so repeated questions don't re-read the tree. Content is markdown-aware chunked by heading (H1–H6, with an ancestor breadcrumb), not by line; each chunk carries frontmatter + inline `#tags` and `[[wiki-link]]` edges, from which a bidirectional backlink GRAPH is built. Retrieval is field-weighted BM25 (heading/tags weighted far above body so an exact topic-word hit decisively outranks scattered common words) returning the top-N chunks PLUS their graph neighbours, so a directly-linked section rides along even when the query only matched a sibling. The persona (`build_gigabuddy_persona`, form Б — core only, no external skill / skill-review) injects a structural digest (topics + tags, always) plus query-scored excerpts (from the newcomer's message, best-effort via `task.objective`); when nothing scores or the base is empty it says so honestly and NEVER fabricates a fact. Boundaries preserved: ONE unified Ouroboros awareness (BIBLE P1) — context injection, not memory isolation; novice-safe view unchanged (`internal_signals`/mentor notes/rollback history never leak); the persona double gate (product off / non-novice project → unchanged) does not regress; Panic + PIN-return visible; no frozen contracts (`contracts.py`/`StateResponse`/routes) or `BIBLE.md` touched. |
| 6.80.1 | 2026-07-18 | **feat: GigaBuddy novice `/clean` (visual chat reset) + hardened persona role boundary.** The newcomer can now visually clear their own chat by typing `/clean` — intercepted INSIDE the novice thread (`web/modules/chat.js`, gated on the instance's `gigabuddy-novice` `projectId`), NOT a runtime slash like `/restart`: it never reaches the supervisor and never registers a new supervisor command. `/clean` wipes ONLY the visible transcript + this thread's in-memory/session dedupe and persistence state (`persistedHistory`/`seenMessageKeys`/`messageKeyOrder`/`sessionStorage`), keeps the typing indicator, and shows ONE fixed, impersonal, EPHEMERAL greeting («Здравствуйте! Готов продолжить — с чего начнём?») — never model-generated, never persisted. Durable adaptation state (profile / stage / real `track.steps` / progress in `gigabuddy_state`) is NEVER touched, so the newcomer cannot reset their track; server `chat.jsonl` is left intact as the audit trail, so this is a per-session VISUAL clear (a full reload re-syncs history by design). Separately, the persona's HARD role boundary (`build_gigabuddy_persona`) is extended additively with an EXPLICIT ban on mentioning the developer mode/processes to the newcomer — product mode / dev mode, `/restart`, commits, versions, internal development, mode switching — on top of the existing B1 «never mention Ouroboros/architecture/versions/evolution» boundary. Form Б (core/persona + frontend only), no external skill / skill-review; reducer stays view-pure; ONE unified awareness (BIBLE P1); novice-safe boundaries and the double gate (product off / non-novice project → unchanged) do not regress; Panic + PIN-return stay visible; no frozen contracts (`contracts.py`/`StateResponse`/routes) or `BIBLE.md` touched. |
| 6.80.0 | 2026-07-18 | **feat: GigaBuddy adaptation-track methodology, embedded in the persona (C / #5).** The chat questionnaire now builds the newcomer's adaptation track by an EXPLICIT methodology instead of improvisation. Per the owner's decision it is embedded directly in the persona/core (`ouroboros/gigabuddy_state.py`) — form Б, NOT a separate reviewed external skill (on this machine `ANTHROPIC_API_KEY` is unset, so an external skill would never pass the skill-review gate and become executable, and the methodology is tightly coupled to the persona already in core). A module-level `_METHODOLOGY_GUIDANCE` constant (kept out of `build_gigabuddy_persona` so it stays within the size budget — prompts are code, P7), assembled by `_methodology_block(...)`, is injected into the empty-track acquaintance scenario. It grounds the track in two world onboarding practices — the **30-60-90-day arc** (settle in → contribute under support → autonomy/ownership) and **competency-based adaptation** (role/department competencies → goals → concrete steps) — applied «с душой»: depth, pace, and wording adapt to the newcomer's profile, experience, interests, and interface tone, never a dry template. When the mentor placed a base questionnaire in `employees/<id>/questionnaire/`, the persona leans on its REAL prompts via a new fail-soft, folder-confined, bounded `gigabuddy_profile.read_questionnaire_hints(<id>)`; with no questionnaire it follows the default 30-60-90/competency scenario and does NOT claim a questionnaire it lacks (no fabrication). Sensitive observations (anxiety/autonomy/learning style) stay INTERNAL to pick the support format and are never spoken to the newcomer as labels; `internal_signals`/mentor notes/rollback history still never reach the persona (pinned by tests). ONE unified Ouroboros awareness (BIBLE P1) — a role contract, not memory isolation; persona still double-gated on product mode AND the novice thread; ordinary Ouroboros and the developer chat are unchanged; no frozen contracts (`contracts.py`/`StateResponse`/routes) or `BIBLE.md` touched. |
| 6.79.1 | 2026-07-18 | **docs: README leads with a Russian GigaBuddy section (product-mode onboarding mentor).** The top of the README is now a Russian-language GigaBuddy block explaining what GigaBuddy is (a hyper-personalized onboarding mentor product mode over Ouroboros, stages Советчик→Помощник→Партнёр), how to enable it (Settings → Behavior → Product Mode → ГигаБадди, or `OUROBOROS_PRODUCT_MODE=gigabuddy`, then `/restart`), the employee folder layout (`~/Ouroboros/gigabuddy/employees/<id>/{profile,questionnaire,knowledge}/`), the mentor operating scenario (drop profile/questionnaire/knowledge before launch → parsed into the right panel, left track, and dialogue; neutral nameless state until a profile loads), the hand-swappable `alice-demo`/`leonid-demo` demo configs, and the PIN-return developer exit (Panic always visible). The Karpathy-wiki retrieval skill and questionnaire-methodology skill are described honestly as in-development integration points, not shipped features. The full English Ouroboros platform documentation is moved intact below the Russian block. Docs-only change; no code, tests, or GigaBuddy logic touched. |
| 6.79.0 | 2026-07-18 | **feat: GigaBuddy reads the employee from files — neutral start + profile parsing + chat questionnaire (B3).** A fresh install is now the NEUTRAL, nameless «novice» — the synthetic Alice default is gone from BOTH the backend reducer default (`default_gigabuddy_state` returns a `_blank_employee`: no name, no department, empty track) AND the frontend offline fallback (`GIGABUDDY_DEMO_STATE`), so before a mentor loads a profile the panels show honest placeholders («Профиль ещё не загружен наставником») and the «never fabricate» discipline now holds for every employee (normalization keeps an empty track for named profiles too — only the questionnaire or an explicit stage transition seeds stages). Alice/Leonid survive as LOADABLE demo configs (`_DEMO_PROFILES`, hand-swapped by the owner via `load_profile`), not the hardcoded default. A new fail-soft, folder-confined `ouroboros/gigabuddy_profile.py` parses the newcomer from `~/Ouroboros/gigabuddy/employees/<id>/` (JSON or markdown-frontmatter `profile/`, with `has_questionnaire`/`knowledge_dir_exists` integration points for the future #4 wiki and #5 methodology skills — the retrieval/methodology skills themselves are deliberately NOT built here); a missing/empty/broken folder stays neutral and nameless rather than inventing a candidate. Three durable reducer ops (`load_profile`, `set_track`, `record_progress`) let the persona-driven CHAT questionnaire greet the newcomer by name, run a warm 30-60-90-style acquaintance, and write the resulting stages into the real `track.steps` (which the B2 left track renders) plus persist adaptation progress in durable per-employee state (not just compressed dialogue). Boundaries preserved: ONE unified Ouroboros awareness (BIBLE P1) — the persona is a role contract, not memory isolation; novice-safe view unchanged (`internal_signals`/mentor notes/rollback history never leak); only CSS variables, Panic + PIN-return visible; file access is confined to the employee folder; no frozen contracts (`contracts.py`/`StateResponse`/routes) or `BIBLE.md` touched. |
| 6.78.0 | 2026-07-18 | **feat: GigaBuddy animated left adaptation track (B2).** The LEFT column of the GigaBuddy product-mode 3-column layout (`data-gigabuddy-track-slot`, added as a skeleton in B1) now renders the employee's live adaptation track — the newcomer's own onboarding stages/steps, NOT the advisor→assistant→partner role status (which stays in the RIGHT panel). Each stage is an expandable `<details>` the newcomer can "dive into" to see its concrete steps; the active stage is open by default, a done/N badge shows aggregate progress, and the accent follows the per-employee `--gigabuddy-accent` so an interface config re-colors it consistently with the right panel. The track is LIVE (rendered by `refreshGigaBuddyPanel`, the single `get_state` fetch owner, from the same `view.track`), and the view projection gains an optional per-stage `steps` list (view-pure, empty by default, bounded, never fabricated — the questionnaire that fills it is B3/C). A stage with no steps yet shows a neutral hint; an empty track shows a neutral placeholder («трек появится после короткого знакомства») instead of inventing stages. Fills the empty left space that visually bothered the owner. Boundaries preserved: only CSS variables (glassmorphism, smooth transitions, no new inline styles in JS), the 3-column grid still degrades to one scrollable column on narrow screens, Panic + PIN-return stay visible, novice-safe boundaries (`internal_signals` / mentor notes / rollback history) do not regress, and no frozen contracts (`contracts.py` / `StateResponse` / routes) or `BIBLE.md` are touched. |
| 6.77.0 | 2026-07-18 | **feat: GigaBuddy novice-thread role-contract / persona (B1).** In product mode (`OUROBOROS_PRODUCT_MODE=gigabuddy`) and ONLY for the novice thread (`gigabuddy-novice` project), the ONE Ouroboros identity now wears a mentor persona injected into the system context (`ouroboros/gigabuddy_state.py::gigabuddy_persona_section` → `build_gigabuddy_persona`, added to `context.py::_capture_context_core` dynamic parts). The persona carries a HARD role boundary (never mention Ouroboros / architecture / versions / evolution / development / "I am an AI/agent" to the newcomer; gently return to the mentor role if asked about internals), is personalized from the persistent per-employee state (name/role/department/experience/interests + interface tone formal/friendly/playful), is aware of the current stage (Советчик→Помощник→Партнёр, status stays in the RIGHT panel) and the adaptation track, and names the employee's knowledge-source folder (`~/Ouroboros/gigabuddy/employees/<id>/knowledge/`) as the integration point without inventing facts (the retrieval skill is B3/C). This is a role overlay on ONE unified awareness (BIBLE P1), NOT memory isolation. Gated on BOTH product mode AND the resolved novice `project_id`: ordinary Ouroboros (product off) and the developer's own chat/threads are unchanged (pinned by an invariant test). Built read-only over the novice-safe view, so `internal_signals` / mentor notes / rollback history never reach the persona; fully fail-soft (any error yields no persona rather than breaking the thread). No frozen contracts (`contracts.py`/`StateResponse`/routes) or `BIBLE.md` touched. |
| 6.76.0 | 2026-07-18 | **feat: GigaBuddy novice chat is an isolated thread in a cohesive 3-column product-mode layout (B1).** The GigaBuddy product shell (`OUROBOROS_PRODUCT_MODE=gigabuddy`) becomes one whole-screen 3-column layout — an adaptation-track skeleton on the LEFT (a static container for the future animated track, B2), the novice's CLEAN chat in the CENTER, and the already-decluttered panel on the RIGHT — instead of the right panel floating over the developer chat. The novice thread is now genuinely partitioned on the backend by reusing the existing project/chat_id thread-routing: a `gigabuddy-novice` project (`ouroboros/gigabuddy_state.py::ensure_novice_project`) is registered idempotently and eagerly by `/api/state` when product mode is on (so its chat_id is a REGISTERED project chat id on the first poll — the ordering guarantee), and `_handle_gigabuddy_action` injects a camelCase `noviceChat` descriptor into the view; `refreshGigaBuddyPanel` (the single `get_state` owner) publishes it via an `ouro:gigabuddy-novice-chat` event and `web/app.js` mounts the isolated center chat (`createChatInstance`, project chat_id) with an honest unavailable-placeholder fallback. This is UI/history thread PARTITIONING — a focused novice room in one unified Ouroboros awareness (BIBLE P1), NOT memory/privacy isolation — so the reservation set stays complete and `contracts.py`/frozen routes/`StateResponse` are untouched. The developer main chat (product off) is fully preserved, Panic + PIN-return stay visible, only CSS variables (no inline styles), and the layout degrades to a single scrollable column on narrow screens. Content (questionnaire, knowledge wiki, methodology skill) is deliberately deferred to B3/C. |
| 6.75.1 | 2026-07-18 | **feat: declutter the GigaBuddy novice panel further.** The right adaptation panel (`web/modules/gigabuddy.js`) drops the atomic-task micro-checklist (empty-checkbox steps like «Познакомиться с процессом» — they belong to the future left animated track), the `v1 • прогресс сохраняется при откате` system line, and the mentor-only «Готовность к переходу» readiness block (role transitions are confirmed by the mentor in Telegram, not shown to the novice). The «Базовый опросник / доменный пакет» block is replaced by a compact «Материалы базы знаний» link to the employee's knowledge-source folder (`~/Ouroboros/gigabuddy/employees/<id>/knowledge/`), so a novice can open the originals on their own. What stays: current stage, profile + broad-strokes progress, the collapsed `Наставнический контур`, the developer PIN-return menu, and Panic. Live `get_state` reading and the novice-safe boundaries are unchanged; only CSS variables, no inline styles. |
| 6.75.0 | 2026-07-18 | **feat: declutter the GigaBuddy adaptation panel.** The right-side onboarding panel (`web/modules/gigabuddy.js`) drops the two verbose main-flow mentor blocks and folds the mentorship-circuit note into a single collapsed `<details>` menu (`Наставнический контур`, closed by default) so the novice's visible flow stays focused on the adaptation track + profile. Live state reading is unchanged (`get_state` → profile / track / interface), the novice-safe boundaries still hold (`internal_signals` / mentor notes / rollback history stay out of the view), the personalization CSS variable + theme/tone attributes and the PIN-return form remain intact, and the CSS reuses the existing events-menu `<details>` grammar (no inline styles, glassmorphism preserved). |
| 6.72.0 | 2026-07-18 | **fix: safety supervisor no longer fails closed on a provider value-rejection.** The Safety Supervisor's LLM call sends `response_format={"type":"json_object"}`, but a provider that accepts the parameter name and rejects the VALUE with pydantic-v2 phrasing (`response_format.type: Input should be 'json_schema'`, e.g. cloud.ru) was not recognized by `LLMClient._parameter_rejection_error`, so the one-shot strip-and-retry never fired, the 400 propagated, and every `run_command`/`run_script`/`verify_and_record` was blocked with a spurious `SAFETY_VIOLATION`. The shared adaptive rejection matcher now recognizes the `input should be` pydantic value-validation marker (still guarded by the droppable-param-name check, so unrelated 400s do not falsely trigger), fixing the whole class without editing the protected `safety.py` (its two `json_object` call sites are correct; the text bracket-scan fallback still parses the retried reply). Regression tests pin the cloud.ru phrasing and the no-false-positive guard. |
| 6.71.2 | 2026-07-17 | **fix: GigaBuddy gains a visible PIN-gated owner return path.** The product shell now shows an owner/admin “return to Ouroboros” form in the adaptation panel, asks for a four-digit PIN, verifies `GIGABUDDY_ADMIN_PIN` server-side through the existing `/api/settings` seam, and clears `OUROBOROS_PRODUCT_MODE` only on success. Generic settings saves can no longer bypass the active shell by clearing product mode or replacing the PIN, submitted PINs are not echoed or audited, a small cooldown throttles repeated failures, and Panic remains visible/available. |
| 6.71.1 | 2026-07-17 | **feat: GigaBuddy product-mode shell for onboarding demos.** A reversible `OUROBOROS_PRODUCT_MODE=gigabuddy` overlay switches the main chat into the «ГигаБадди» novice-facing shell without replacing Ouroboros identity or touching the frozen `/api/state` contract: the frontend reads `/api/settings`, applies product-mode body classes, renames the chat, hides developer/system chrome for the novice view, and renders a synthetic adaptation-track sidecar with stage model hooks (Советчик → Помощник → Партнёр), demo progress, next step, behavior-version/rollback surface, and mentor/demo-accelerator notes. Settings exposes the owner/admin Product Mode toggle, emergency slash commands remain available (presentation only, not a safety boundary), and focused static tests pin ordinary-mode reversibility, hidden chrome, no state-contract churn, and Panic preservation. |
Older releases are preserved in Git tags and GitHub releases. Older 6.x rows (including 6.71.0, 6.65.3, 6.74.0, 6.70.0, 6.69.0, 6.65.2, 6.68.0, 6.67.0, 6.66.0, 6.65.1, 6.65.0, 6.64.3, 6.64.0, 6.64.2, 6.64.1, 6.63.0, 6.62.0, 6.61.3, 6.61.4, 6.61.0, 6.61.1, 6.60.0, 6.59.0, 6.54.4, 6.58.0, 6.57.0, 6.56.0, 6.55.0, 6.54.2, 6.54.1, 6.54.0, 6.53.4, 6.53.0 and 6.51.0), the 5.2.0 through 5.33.0-rc.6 rows, and former `4.0.0` rows are rolled off to respect the P9 changelog cap; their full bodies remain at their git tags.

---

## License

[MIT License](LICENSE)

Created by [Anton Razzhigaev](https://t.me/abstractDL) & Andrew Kaznacheev
