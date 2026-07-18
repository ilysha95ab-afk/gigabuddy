# GigaBuddy Product Mode

GigaBuddy ("ГигаБадди") is a reversible product-mode overlay for hackathon onboarding demos. It is built on top of the Ouroboros runtime; it does not replace `BIBLE.md`, `identity.md`, safety, review, or the developer/admin control plane.

## Activation

Set the owner/admin setting:

```json
{
  "OUROBOROS_PRODUCT_MODE": "gigabuddy"
}
```

Empty value means ordinary Ouroboros. For the demo, configure the mode before the novice arrives; a restart or UI reload is the safest activation path. The frontend reads `/api/settings` and applies `body.product-gigabuddy`; no frozen `/api/state` contract field is added in this first increment.

## What is live in v6.72.0

- Main chat branding changes to **ГигаБадди**.
- Subtitle appears: **персональный ИИ-наставник адаптации**.
- Novice-facing system chrome is hidden: developer header controls, budget pill, Swarm/Low/Max composer controls, navigation utilities and Projects.
- A separate adaptation-track sidecar appears in the main chat and loads mutable demo state from `data/state/gigabuddy/state.json`:
  - employee card and demo profile switcher;
  - current role/stage;
  - progress;
  - per-employee tasks;
  - next step;
  - readiness for transition;
  - behavior-version / rollback model;
  - mentor notes and bounded event history;
  - base questionnaire/domain-package summary.
- Stage model is present in code and state actions: **Советчик → Помощник → Партнёр**.
- Settings exposes a Product Mode segmented control under Behavior.
- Static tests pin that the overlay is reversible, ordinary mode remains default, `/api/state` is untouched, and `/panic` remains structurally available.
- A visible owner/admin return form asks for a four-digit PIN and calls the existing `/api/settings` seam with `_action: "gigabuddy_return"`. The server checks `GIGABUDDY_ADMIN_PIN`, clears product mode only on a correct PIN, and keeps submitted PIN values out of responses/audit payloads.

## 3-column layout and the isolated novice chat (v6.76.0, B1)

In product mode the main chat becomes one cohesive three-column layout (not a
panel floating over the developer chat):

- **Left — adaptation-track skeleton.** A static container (`[data-gigabuddy-track-slot]`)
  reserved for the future animated, "diveable" track (B2). It renders a
  placeholder in B1; no live data fetch.
- **Center — the novice's clean chat.** This is where the novice types. It is a
  separate chat thread from the developer's main Ouroboros chat.
- **Right — the decluttered adaptation panel** (`[data-gigabuddy-track-panel]`),
  now a grid column instead of an absolutely-positioned floating card.

On narrow screens the grid degrades to a single scrollable column (novice chat
first).

### Novice-thread partitioning (not memory isolation)

The novice thread is partitioned by **reusing the existing project/chat_id
thread-routing**, not a new chat store:

- `ouroboros/gigabuddy_state.py::ensure_novice_project(drive_root)` idempotently
  registers a `gigabuddy-novice` project through `projects_registry.create_project`
  (the single lifecycle/reservation SSOT). It is a registry bridge, never a
  reducer mutation, and fails soft to a zero descriptor.
- `ouroboros/gateway/state.py::api_state` calls it eagerly when product mode is
  active, BEFORE emitting `project_chat_ids`, so the novice chat_id is a
  REGISTERED project chat id on the very first `/api/state` poll (the durable
  ordering guarantee `web/app.js::renderProjectsNav` relies on to rebuild
  `state.projectChatIds`).
- `ouroboros/gateway/settings.py::_handle_gigabuddy_action` injects a camelCase
  `view.noviceChat = {chatId, projectId}` (the reducer/view stay pure).
- `web/modules/gigabuddy.js::refreshGigaBuddyPanel` is the single `get_state`
  fetch owner; from that one view it dispatches `ouro:gigabuddy-novice-chat`, and
  `web/app.js` mounts the isolated center chat via `createChatInstance` (project
  `chatId`), falling back to an explicit unavailable placeholder if registration
  failed.

This is **UI/history thread partitioning** — a focused novice room within ONE
unified Ouroboros awareness (BIBLE P1). It is NOT memory or privacy isolation:
the single Ouroboros identity/memory remains intact, and `reserved_project_chat_ids`
stays complete (it is the routing SSOT and is never filtered). No frozen
`/api/state` field, no `contracts.py` change, and no new frozen route is added.

Because registration is a real project, a `Новичок` row is visible in the
DEVELOPER sidebar when product mode is off — an honest artifact of a real
thread. The novice never sees it (product mode hides the Projects nav). This is
not activity-gated in B1.

Content that fills these columns — the in-chat onboarding questionnaire, the
knowledge-base "wiki" retrieval, and the adaptation methodology skill — is
deliberately deferred to later increments (B3 / C).

## Deliberate boundaries

This is presentation, not public authentication or a security boundary. Emergency slash commands and owner/admin routes still exist. The novice shell hides confusing or dangerous controls from the product surface; it does not delete the underlying capabilities.

The return PIN is a local owner/admin recovery gate for the visible GigaBuddy shell. Set `GIGABUDDY_ADMIN_PIN` in Settings → Secrets before enabling the mode. While GigaBuddy is active, generic settings saves cannot clear `OUROBOROS_PRODUCT_MODE` or overwrite `GIGABUDDY_ADMIN_PIN`; the server-side PIN action is the supported exit path. This prevents the visible return button from being mere UI theater, but it is still not a replacement for the normal network/password boundary.

Sensitive diagnostics, such as anxiety/confidence risk, must not be shown to the novice as labels. They may inform support style internally, but outward language should describe the format of help, level of support, and work style.

## Employee config schema (state + interface attributes)

Since v6.74.0 each employee entry in the state carries a full mutable config plus
interface personalization. `ouroboros/gigabuddy_state.py` owns the shape, string
caps, allow-lists, and the novice-safe view projection.

Employee state (per employee):

- `profile` — `name`, `role`, `department`, `experience`, `interests[]` (bounded).
- `stage` — current mentorship stage (`advisor` / `assistant` / `partner`).
- `track` — the adaptation track: an ordered list of stage entries
  (`id`, `label`, `title`, `status` ∈ `planned` / `active` / `done`) built for
  this specific newcomer. Progress is derived from the track (done = full,
  active = half).
- `progress_pct` — aggregated track progress metric.
- `behavior_versions` + `active_behavior_version_id` — behavior version model.
- `rollback_history` — internal record of behavior rollbacks (kept out of the
  novice view).
- `mentor_notes` — internal mentor text (kept out of the novice view).
- `internal_signals` — sensitive diagnostics (never shown to the novice).

Interface attributes (`interface`, hyper-personification — the shell adapts per
employee):

- `theme` — one of an allow-list (`neutral`, `soft-cat`, `strict-terminal`,
  `warm-sunrise`, `ocean-calm`); an unknown theme falls back to `neutral`.
- `accent_color` — a 3/6-digit hex color kept **inside the design system**; the
  default is the primary crimson `#c93545`, and an invalid value falls back to
  it, so a config can never inject arbitrary CSS.
- `mascot` — a short avatar/mascot glyph.
- `tone` — `formal` / `friendly` / `playful`.
- `layout` — an ordered list of visible panel sections; unknown identifiers are
  dropped and every known section is kept visible (a layout can reorder or hide
  sections but never blank the panel).

The novice-safe view (`build_gigabuddy_view`) surfaces `profile`, `interface`,
`track`, `stage`, and track-derived `progressPct`, but never `internal_signals`,
`mentor_notes`, or `rollback_history`. The frontend applies the interface block
to the product shell through the existing `/api/settings` seam: the panel refresh
sets `body[data-gigabuddy-theme]`, `body[data-gigabuddy-tone]`, and a validated
`--gigabuddy-accent` CSS custom property — no frozen gateway route and no
`contracts.py` edit are introduced. Because one employee = one config, a later
increment (config-per-employee switching) can load a config and change both
behavior and the visible appearance.

## Mutable state and mentor/admin actions

The live state file is runtime-local and synthetic by default:

```text
data/state/gigabuddy/state.json
```

It is not a public demo-data source and is not committed. `ouroboros/gigabuddy_state.py` owns the schema, default profiles, bounded event history, string caps, and the novice-safe view projection. The browser calls the existing settings seam with `_action: "gigabuddy"` and a whitelisted `op`; the gateway audits only reducer-supplied metadata, never task text, mentor notes, questionnaire text, PINs, or internal diagnostic labels.

Current reducer operations (available to the backend/admin/Telegram seam, not rendered as novice buttons):

- `select_employee` — switch demo profile (Alice → Leonid → blank/default and back).
- `add_task` — add a mentor task to the active employee's track.
- `approve_stage` — confirm stage transition.
- `reject_stage` — defer transition and optionally add another task.
- `rollback` — restore an earlier behavior version while preserving progress/tasks.
- `demo_accelerate` — fast-forward a demo stage with audited metadata.

The employee-facing side panel is deliberately read-mostly: it shows the current profile, role, tasks, questionnaire/domain package, and soft status copy. It does **not** expose profile switching, task injection, stage approval/rejection, rollback, or demo acceleration controls. Those actions belong to the mentor/admin/Telegram surface or to the owner after returning to ordinary Ouroboros mode.

## What remains prototype/demo in v6.72.0

- Employee state is mutable but still seeded with synthetic demo profiles; Alice's uploaded ODT files are not parsed yet.
- Telegram mentor commands are documented as product flow but not live-wired here.
- Background consciousness is not central to the MVP; proactive checks/digests should be deterministic/demo-controlled until the real state model is fed by actual domain packs.

## Demo accelerator vocabulary

The intended mentor/admin/demo-operator phrases are:

- **Быстрый виток** — fast-forward one stage.
- **Показать эволюцию** — show a transition sequence.
- **Откат к заботе** — return behavior style to the warm Advisor version.
- **Режим партнёра** — fast-forward to Partner style.
- **Наставник вмешивается** — add or adjust a mentor task in the track.

These must be authorized and audited when implemented live; they are not a hidden backdoor.

## Next implementation increment

1. Add a proper mentor/admin surface for stage approval, task injection, profile switching, behavior rollback, and demo acceleration (Telegram first; a clearly separated admin panel is acceptable for filming).
2. Parse Alice's provided documents into demo data only after the generic shell is stable.
3. Wire Telegram mentor protocol through a reviewed transport skill or a demo/admin panel.
4. Replace seed questionnaire text with generated diagnostic interview + domain knowledge package outputs.
5. Prepare judge-facing README/demo script/screenshots from synthetic data only.
