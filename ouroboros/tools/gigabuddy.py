"""GigaBuddy mentor-control tool.

The evolution engine (``gigabuddy_evolution`` + the reducer ops) is only
reachable, until now, through the owner-audited HTTP settings seam
(``gateway/settings.py::_handle_gigabuddy_action``). That is fine for the web
UI, but the MENTOR approves evolution by CHATTING with the agent (mirrored over
the Telegram bridge), so the agent needs a first-class tool to close the loop:
surface a proposal, and on the mentor's да/нет reply call
``approve_evolution``/``revert_evolution``.

This tool is the SAME write path (``apply_gigabuddy_action``) the settings seam
uses — the reducer still owns all validation, payload sanitisation, cross-employee
isolation, novice-safe projection, and bounded history. The tool adds only a
product-mode gate (it is a GigaBuddy control surface) and a compact,
LLM-friendly result. It is deliberately owner/mentor-side: the NOVICE persona
never sees it (the novice thread gets the newcomer persona, not evolution chrome).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)

# The ops the agent may drive. Read + the three evolution ops. Deliberately NOT
# the full reducer op set (stage approve/reject, task add, profile load, …) —
# those are owner/UI concerns, kept on the settings seam; the agent-facing tool
# is scoped to the evolution-approval protocol plus a read.
_ALLOWED_OPS = ("get_state", "propose_evolution", "approve_evolution", "revert_evolution")


def _product_mode_is_gigabuddy() -> bool:
    return os.environ.get("OUROBOROS_PRODUCT_MODE", "").strip().lower() == "gigabuddy"


def _pending_summary(view: Dict[str, Any], state: Dict[str, Any]) -> str:
    """Compact pending-proposal summary for the tool result (never leaks to novice —
    this is the mentor tool). Reads proposals from raw state (they are excluded
    from the novice-safe view by design)."""
    try:
        from ouroboros.gigabuddy_state import _active_employee

        emp = _active_employee(state)
        pending: List[Dict[str, Any]] = [
            {"id": p.get("id"), "depth": p.get("depth"), "status": p.get("status")}
            for p in (emp.get("evolution_proposals") or [])
            if isinstance(p, dict)
        ]
        return json.dumps(pending, ensure_ascii=False)
    except Exception:
        return "[]"


def _gigabuddy_action(ctx: ToolContext, op: str, payload: Any = None) -> str:
    op = str(op or "").strip()
    if op not in _ALLOWED_OPS:
        return (f"⚠️ TOOL_ARG_ERROR (gigabuddy_action): op must be one of {_ALLOWED_OPS}. "
                "Stage/task/profile ops stay on the settings/UI seam.")
    if not _product_mode_is_gigabuddy():
        return ("⚠️ GIGABUDDY_PRODUCT_MODE_OFF: gigabuddy_action only runs when product mode "
                "is 'gigabuddy'. This is the mentor-side evolution-approval control.")
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        return "⚠️ TOOL_ARG_ERROR (gigabuddy_action): payload must be an object."
    try:
        from ouroboros.gigabuddy_state import GigaBuddyStateError, apply_gigabuddy_action

        drive_root = ctx.drive_root
        result = apply_gigabuddy_action(drive_root, op, payload)
    except Exception as exc:  # includes GigaBuddyStateError (user-correctable)
        # GigaBuddyStateError carries a clean user-facing message; other errors
        # are surfaced compactly without a stack dump into the transcript.
        return f"⚠️ GIGABUDDY_ACTION_FAILED ({op}): {exc}"

    audit = result.get("audit") or {}
    state = result.get("state") or {}
    view = result.get("view") or {}
    pending = _pending_summary(view, state)
    return (
        f"OK: gigabuddy_action {op} → {json.dumps(audit, ensure_ascii=False)}\n"
        f"pending_proposals={pending}"
    )


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "gigabuddy_action",
            {
                "name": "gigabuddy_action",
                "description": (
                    "MENTOR-side GigaBuddy evolution-approval control (only in product "
                    "mode 'gigabuddy'). op: get_state (inspect current employee + pending "
                    "proposals) | propose_evolution (stage a soft-layer proposal; applies "
                    "nothing) | approve_evolution (apply interface/role_tempo, or record a "
                    "ui git-hint) | revert_evolution (restore a previously applied proposal). "
                    "payload for propose_evolution carries depth + bounded soft-layer fields; "
                    "approve/revert carry only {proposal_id}. Use this to close the mentor "
                    "да/нет approval loop that arrives over the chat/Telegram transport. "
                    "Never expose it or its details to the novice."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "op": {
                            "type": "string",
                            "enum": list(_ALLOWED_OPS),
                        },
                        "payload": {
                            "type": "object",
                            "description": (
                                "Op payload. propose_evolution: {depth: interface|role_tempo|ui, "
                                "and for interface theme/accent_color/mascot/tone/layout; for "
                                "role_tempo optional stage; for ui label/note; optional source}. "
                                "approve_evolution/revert_evolution: {proposal_id}."
                            ),
                        },
                    },
                    "required": ["op"],
                },
            },
            lambda ctx, op, payload=None: _gigabuddy_action(ctx, op, payload),
            timeout_sec=20,
        ),
    ]


__all__ = ["get_tools"]
