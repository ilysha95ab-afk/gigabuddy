"""GigaBuddy reversible self-evolution — pure helpers.

This module owns the SHAPE and REVERSIBILITY of GigaBuddy evolution proposals,
kept OUT of the already-large ``gigabuddy_state`` reducer (P7). It is
deliberately pure: it holds no state, does no IO, and — critically — never
imports the private validators back from ``gigabuddy_state`` at module import
time (that direction would be a circular import, since ``gigabuddy_state``
imports THIS module). Validators are passed IN as a small callable bundle.

The evolution model is a bounded, per-employee proposal ledger that stays
STRICTLY inside the GigaBuddy soft layer:

- ``interface`` depth  — mutate the presentation block (theme/accent/mascot/tone/
  layout), reversible in-state by a deep-copied ``pre_image``.
- ``role_tempo`` depth — advance the adaptation stage (Советчик→Помощник→
  Партнёр), reversible in-state by the same ``pre_image``.
- ``ui`` depth         — a mentor-approved SUGGESTION for an owner code edit.
  It is proposal-only: approving it stamps a git-command hint and moves the
  status to ``approved``; it never mutates state and never claims an applied
  code change. The actual UI code change is an owner-landed, reviewed git edit.

Per-novice branch rule (v6.87.6): structural ui-depth work lands in a dedicated
git branch named after the novice — ``gigabuddy-<employee_id>`` (e.g.
``gigabuddy-alisa_20260714``) — never directly on the shared working branch.

Reversibility is IN-STATE (the ``pre_image``), NOT a repo git tag: runtime
approvals write ``data/state/gigabuddy/state.json`` outside the repo. A git tag
is the owner's code-release recovery point for the reducer diff, not a
per-approval runtime artifact. See docs/gigabuddy_product_mode.md.
"""

from __future__ import annotations

import copy
from typing import Any, Callable, Dict, List, Mapping

# The three evolution depths. The reducer VALIDATES a DECLARED depth (chosen by
# the LLM/persona/mentor surface); it never text-classifies a request into a
# depth (BIBLE P5). ``interface`` and ``role_tempo`` are APPLYABLE (live-state,
# pre_image-reversible); ``ui`` is proposal-only.
EVOLUTION_DEPTHS = ("ui", "role_tempo", "interface")
APPLYABLE_DEPTHS = ("interface", "role_tempo")
PROPOSAL_SOURCES = ("novice_request", "gigabuddy_decision")
PROPOSAL_STATUSES = ("proposed", "approved", "applied", "reverted")

MAX_EVOLUTION_PROPOSALS = 24
_MAX_ID_CHARS = 64
_MAX_TAG_CHARS = 80

# The interface-payload keys an evolution proposal may carry. Each is validated
# through the passed-in soft-layer validator, so a proposal can NEVER inject
# arbitrary CSS/code/settings — only bounded, allow-listed presentation values.
_INTERFACE_PAYLOAD_KEYS = ("theme", "accent_color", "mascot", "tone", "layout")


class EvolutionError(ValueError):
    """User-correctable evolution proposal validation error."""


def _clip(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _depth(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    if candidate not in EVOLUTION_DEPTHS:
        raise EvolutionError(
            f"Unknown evolution depth: {candidate!r}. Allowed: {', '.join(EVOLUTION_DEPTHS)}."
        )
    return candidate


def _source(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in PROPOSAL_SOURCES else "gigabuddy_decision"


def _status(value: Any) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in PROPOSAL_STATUSES else "proposed"


def validate_evolution_payload(
    depth: str,
    payload: Any,
    validators: Mapping[str, Callable[..., Any]],
) -> Dict[str, Any]:
    """Return a bounded, validated proposal payload for ``depth``.

    ``validators`` is a callable bundle supplied by the reducer:
    ``theme``/``accent``/``mascot``/``tone``/``layout``/``stage``. Passing them
    in (rather than importing the private ``gigabuddy_state`` validators here)
    keeps this module import-cycle free.

    A payload can only ever carry bounded, allow-listed soft-layer values — an
    unknown key is rejected, and every accepted value is run through the
    corresponding validator so arbitrary CSS/code/settings can never enter.
    """
    depth = _depth(depth)
    if not isinstance(payload, dict):
        payload = {}

    if depth == "interface":
        unknown = sorted(set(payload) - set(_INTERFACE_PAYLOAD_KEYS))
        if unknown:
            raise EvolutionError(
                f"Unsupported interface evolution fields: {', '.join(unknown)}."
            )
        out: Dict[str, Any] = {}
        if "theme" in payload:
            out["theme"] = validators["theme"](payload.get("theme"))
        if "accent_color" in payload:
            out["accent_color"] = validators["accent"](payload.get("accent_color"))
        if "mascot" in payload:
            out["mascot"] = validators["mascot"](payload.get("mascot"))
        if "tone" in payload:
            out["tone"] = validators["tone"](payload.get("tone"))
        if "layout" in payload:
            out["layout"] = validators["layout"](payload.get("layout"))
        if not out:
            raise EvolutionError("An interface evolution must change at least one field.")
        return out

    if depth == "role_tempo":
        # Optional explicit target stage; the reducer defaults to NEXT_STAGE when
        # absent. Validate against the real stage set only.
        unknown = sorted(set(payload) - {"stage"})
        if unknown:
            raise EvolutionError(
                f"Unsupported role_tempo evolution fields: {', '.join(unknown)}."
            )
        out = {}
        if "stage" in payload:
            out["stage"] = validators["stage"](payload.get("stage"))
        return out

    # ui depth: a bounded human-readable label + optional note. It NEVER carries
    # code/CSS — it is only a suggestion the owner will implement by hand.
    unknown = sorted(set(payload) - {"label", "note"})
    if unknown:
        raise EvolutionError(f"Unsupported ui evolution fields: {', '.join(unknown)}.")
    out = {}
    if "label" in payload:
        out["label"] = _clip(payload.get("label"), 160)
    if "note" in payload:
        out["note"] = _clip(payload.get("note"), 320)
    return out


def normalize_evolution_proposal(raw: Any) -> Dict[str, Any] | None:
    """Normalize one stored proposal, dropping anything malformed.

    An unknown depth drops the whole proposal (returns None) rather than
    raising, so a corrupt persisted row can never crash normalization of live
    state — it is simply forgotten.
    """
    if not isinstance(raw, dict):
        return None
    try:
        depth = _depth(raw.get("depth"))
    except EvolutionError:
        return None
    pid = _clip(raw.get("id"), _MAX_ID_CHARS)
    if not pid:
        return None
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    pre_image = raw.get("pre_image")
    proposal: Dict[str, Any] = {
        "id": pid,
        "depth": depth,
        "payload": copy.deepcopy(payload),
        "source": _source(raw.get("source")),
        "status": _status(raw.get("status")),
        "git_tag_hint": _clip(raw.get("git_tag_hint"), _MAX_TAG_CHARS),
        "baseline_tag": _clip(raw.get("baseline_tag"), _MAX_TAG_CHARS),
        "created_at": _clip(raw.get("created_at"), _MAX_TAG_CHARS),
    }
    # pre_image is an opaque, deep-copied snapshot; it is preserved as-is only
    # when the proposal has actually been applied (an applied proposal without a
    # pre_image would be un-revertable, so drop a nonsense one).
    if isinstance(pre_image, dict) and proposal["status"] in {"applied", "reverted"}:
        proposal["pre_image"] = copy.deepcopy(pre_image)
    return proposal


def normalize_evolution_proposals(raw: Any) -> List[Dict[str, Any]]:
    """Normalize + bound a proposal list (most-recent-kept)."""
    if not isinstance(raw, list):
        return []
    out: List[Dict[str, Any]] = []
    for item in raw:
        norm = normalize_evolution_proposal(item)
        if norm is not None:
            out.append(norm)
    return out[-MAX_EVOLUTION_PROPOSALS:]


def build_pre_image(emp: Dict[str, Any]) -> Dict[str, Any]:
    """Deep-copy the exact effective-state fields a revert must restore.

    ``track`` is REQUIRED: ``build_gigabuddy_view`` derives ``progressPct`` from
    ``track`` when it is non-empty, and a ``role_tempo`` apply mutates ``track``
    via ``_sync_track_to_stage`` inside the stage transition. Restoring only
    ``progress_pct`` without ``track`` would leave the novice-visible progress
    evolved. ``behavior_versions`` is intentionally NOT snapshotted — it is a
    bounded append-only audit log; ``active_behavior_version_id`` points the
    effective state back to the pre-evolution version.
    """
    return {
        "interface": copy.deepcopy(emp.get("interface") or {}),
        "stage": str(emp.get("stage") or "advisor"),
        "active_behavior_version_id": str(emp.get("active_behavior_version_id") or "v1"),
        "progress_pct": int(emp.get("progress_pct", 0) or 0),
        "track": copy.deepcopy(emp.get("track") or []),
    }


def apply_pre_image(emp: Dict[str, Any], pre_image: Any) -> None:
    """Restore an employee's effective state from a ``build_pre_image`` snapshot.

    Mutates ``emp`` in place. Safe against a missing/partial snapshot: only the
    keys present are restored. The reducer re-normalizes afterwards, so shapes
    are re-validated by the allow-list projection.
    """
    if not isinstance(pre_image, dict):
        raise EvolutionError("This evolution has no reversible snapshot to restore.")
    if "interface" in pre_image:
        emp["interface"] = copy.deepcopy(pre_image["interface"])
    if "stage" in pre_image:
        emp["stage"] = str(pre_image["stage"] or emp.get("stage") or "advisor")
    if "active_behavior_version_id" in pre_image:
        emp["active_behavior_version_id"] = str(
            pre_image["active_behavior_version_id"] or emp.get("active_behavior_version_id") or "v1"
        )
    if "progress_pct" in pre_image:
        try:
            emp["progress_pct"] = max(0, min(100, int(pre_image["progress_pct"])))
        except (TypeError, ValueError):
            pass
    if "track" in pre_image:
        emp["track"] = copy.deepcopy(pre_image["track"])


def git_tag_hint(employee_id: str, ordinal: int) -> str:
    """The owner-facing annotated-tag name for an approved evolution step."""
    return f"giga-evo-{_clip(employee_id, 40) or 'novice'}-{max(1, int(ordinal))}"
