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

## What is live in v6.71.1

- Main chat branding changes to **ГигаБадди**.
- Subtitle appears: **персональный ИИ-наставник адаптации**.
- Novice-facing system chrome is hidden: developer header controls, budget pill, Swarm/Low/Max composer controls, navigation utilities and Projects.
- A separate adaptation-track sidecar appears in the main chat with synthetic demo state:
  - employee card;
  - current role/stage;
  - progress;
  - tasks;
  - next step;
  - readiness for transition;
  - behavior-version/rollback placeholder;
  - mentor/demo-accelerator notes.
- Stage model is present in code: **Советчик → Помощник → Партнёр**.
- Settings exposes a Product Mode segmented control under Behavior.
- Static tests pin that the overlay is reversible, ordinary mode remains default, `/api/state` is untouched, and `/panic` remains structurally available.

## Deliberate boundaries

This is presentation, not an authentication or security boundary. Emergency slash commands and owner/admin routes still exist. The novice shell hides confusing or dangerous controls from the product surface; it does not delete the underlying capabilities.

Sensitive diagnostics, such as anxiety/confidence risk, must not be shown to the novice as labels. They may inform support style internally, but outward language should describe the format of help, level of support, and work style.

## What remains prototype/demo in v6.71.1

- Employee state is synthetic and static; Alice's uploaded ODT files are not parsed yet.
- Telegram mentor commands are documented as product flow but not live-wired here.
- Rollback is represented as behavior-version UI/model placeholder; it does not yet mutate persisted employee behavior state.
- Background consciousness is not central to the MVP; proactive checks/digests should be deterministic/demo-controlled until the real state model exists.

## Demo accelerator vocabulary

The intended mentor/admin/demo-operator phrases are:

- **Быстрый виток** — fast-forward one stage.
- **Показать эволюцию** — show a transition sequence.
- **Откат к заботе** — return behavior style to the warm Advisor version.
- **Режим партнёра** — fast-forward to Partner style.
- **Наставник вмешивается** — add or adjust a mentor task in the track.

These must be authorized and audited when implemented live; they are not a hidden backdoor.

## Next implementation increment

1. Persist a real GigaBuddy employee/profile/track state model.
2. Add mentor/admin surfaces for stage approval, task injection, and behavior rollback.
3. Parse Alice's provided documents into demo data only after the generic shell is stable.
4. Wire Telegram mentor protocol through a reviewed transport skill or a demo/admin panel.
5. Replace static track data with generated diagnostic interview + track state.
