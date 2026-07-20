"""GigaBuddy mentor notification for evolution requests (v6.87.6).

Kept OUT of the already-full ``gigabuddy_state`` reducer (module-size gate) and
out of the deliberately-pure ``gigabuddy_evolution`` helpers: this is the ONE
IO seam — a fail-soft ping to the mentor that a novice requested an evolution.
It uses the EXISTING LocalChatBridge outbound channel (``send_message`` →
``CHAT_OUTBOUND``), which the telegram-bridge skill forwards to the bound
external (Telegram) chat. No new dependency, no direct Telegram API.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, Dict

log = logging.getLogger(__name__)


def describe_evolution_proposal(depth: str, payload: Dict[str, Any]) -> str:
    """Short human-readable summary of a validated proposal for the mentor ping."""
    if depth == "ui":
        label = str(payload.get("label") or "").strip()
        note = str(payload.get("note") or "").strip()
        return (label + (f" — {note}" if note else "")).strip(" —") or "изменение интерфейса"
    parts = [f"{key}: {value}" for key, value in payload.items()]
    return ", ".join(parts) if parts else depth


def notify_mentor_evolution_request(
    drive_root: pathlib.Path | str,
    emp: Dict[str, Any],
    depth: str,
    payload: Dict[str, Any],
) -> bool:
    """Fail-soft: ping the mentor that a novice requested an evolution.

    Returns False when the bridge is absent (e.g. a worker process) or no
    external owner chat is bound yet — the journal event recorded by the op
    remains the source of truth either way. Never raises.
    """
    try:
        from supervisor.message_bus import try_get_bridge

        bridge = try_get_bridge()
        if bridge is None:
            return False
        from ouroboros.utils import read_json_dict

        st = read_json_dict(pathlib.Path(drive_root) / "state" / "state.json") or {}
        chat_id = int(st.get("owner_external_chat_id") or 0)
        if not chat_id:
            return False
        name = str((emp.get("profile") or {}).get("name") or emp.get("id") or "Новичок").strip()
        desc = describe_evolution_proposal(depth, payload)
        bridge.send_message(chat_id, f"{name} просит эволюцию: {desc}. Одобряешь?")
        return True
    except Exception:
        log.debug("GigaBuddy mentor evolution notify skipped", exc_info=True)
        return False
