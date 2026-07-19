"""GigaBuddy mentor-side evolution-approval context (transport-neutral).

The evolution engine (``gigabuddy_evolution`` + the reducer ops in
``gigabuddy_state``) is transport-neutral: ``propose_evolution`` STAGES a
proposal, ``approve_evolution`` APPLIES it (interface/role_tempo) or records the
owner git-command hint (ui), ``revert_evolution`` restores the pre_image. None of
them notify anyone. This module owns the small MENTOR-side wiring that closes the
loop over whatever chat transport is active (the Telegram bridge simply mirrors
``chat.outbound`` to the mentor and injects the mentor's reply back):

- the agent, running in the MENTOR/owner thread (product mode ON, but NOT the
  novice thread), is told which proposals are pending and how to act on the
  mentor's да/нет reply via the ``gigabuddy_action`` tool.

This is a role/behaviour overlay on the ONE Ouroboros awareness (BIBLE P1), NOT
memory isolation, and it never touches the NOVICE persona (the newcomer must
never see evolution/dev internals). Kept in its own module so the already-large
``gigabuddy_state`` reducer stays under the size budget (P7), mirroring the
``gigabuddy_profile`` / ``gigabuddy_knowledge`` sibling pattern.
"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any, Dict, List

log = logging.getLogger(__name__)

# A hard cap so a runaway proposal ledger can never blow up the mentor context
# section (the reducer already bounds the stored list to MAX_EVOLUTION_PROPOSALS;
# this is a second, display-side guard).
_MAX_SHOWN_PROPOSALS = 8


def _product_mode_is_gigabuddy() -> bool:
    return os.environ.get("OUROBOROS_PRODUCT_MODE", "").strip().lower() == "gigabuddy"


def _describe_proposal(proposal: Dict[str, Any]) -> str:
    """One compact human line for a pending proposal (mentor-facing, RU)."""
    depth = str(proposal.get("depth") or "").strip()
    payload = proposal.get("payload") or {}
    pid = str(proposal.get("id") or "").strip()
    source = str(proposal.get("source") or "").strip()
    source_ru = {
        "novice_request": "по запросу новичка",
        "gigabuddy_decision": "по решению ГигаБадди",
    }.get(source, source or "")
    if depth == "interface":
        bits = []
        if payload.get("theme"):
            bits.append(f"тема «{payload['theme']}»")
        if payload.get("accent_color"):
            bits.append(f"акцент {payload['accent_color']}")
        if payload.get("mascot"):
            bits.append(f"маскот «{payload['mascot']}»")
        if payload.get("tone"):
            bits.append(f"тон {payload['tone']}")
        if payload.get("layout"):
            bits.append(f"раскладка {payload['layout']}")
        desc = ", ".join(bits) or "оформление интерфейса"
        depth_ru = "интерфейс"
    elif depth == "role_tempo":
        target = payload.get("stage")
        desc = f"переход стадии{' → ' + str(target) if target else ' (следующая стадия)'}"
        depth_ru = "темп роли"
    else:  # ui
        label = payload.get("label") or "правка UI"
        note = payload.get("note")
        desc = f"{label}" + (f" — {note}" if note else "")
        depth_ru = "UI (правит владелец руками)"
    tail = f" · {source_ru}" if source_ru else ""
    return f"  - `{pid}` [{depth_ru}]: {desc}{tail}"


def pending_evolution_proposals(drive_root: pathlib.Path | str) -> List[Dict[str, Any]]:
    """The active employee's ``status=="proposed"`` proposals (fail-soft [])."""
    try:
        from ouroboros.gigabuddy_state import _active_employee, load_gigabuddy_state

        state = load_gigabuddy_state(drive_root)
        emp = _active_employee(state)
        out = [
            p for p in (emp.get("evolution_proposals") or [])
            if isinstance(p, dict) and str(p.get("status") or "") == "proposed"
        ]
        return out[-_MAX_SHOWN_PROPOSALS:]
    except Exception:
        log.debug("GigaBuddy pending proposals unavailable", exc_info=True)
        return []


def build_gigabuddy_mentor_section(drive_root: pathlib.Path | str) -> str:
    """Mentor-side evolution-approval context, or "" when there is nothing to do.

    Lists the pending proposals for the active employee and tells the agent to
    surface them to the mentor and act on the reply through ``gigabuddy_action``.
    Returns "" (no section) when no proposals are pending, so the mentor thread
    is untouched in the common case. Fail-soft: any error yields "".
    """
    try:
        pending = pending_evolution_proposals(drive_root)
        if not pending:
            return ""
        lines = "\n".join(_describe_proposal(p) for p in pending)
        return (
            "## ГигаБадди: ожидают одобрения наставника\n\n"
            "Ты сейчас в чате наставника/владельца (не в чате новичка). По ГигаБадди "
            "есть предложения эволюции, ожидающие твоего/наставнического решения:\n"
            f"{lines}\n\n"
            "### Как вести одобрение (транспорт — обычный чат, зеркалится в Telegram)\n"
            "- Чтобы уведомить наставника — просто напиши сообщение в этом чате: оно "
            "уйдёт наставнику по активному транспорту (Telegram-мост зеркалит ответы "
            "агента). Спроси кратко: «<кто> просит: <что>. Глубина: <interface|"
            "role_tempo|ui>. Одобрить? да/нет» и укажи `id` предложения.\n"
            "- Если наставник отвечает **да** — вызови инструмент `gigabuddy_action` с "
            "`op=\"approve_evolution\"` и `payload={\"proposal_id\": \"<id>\"}`. Для "
            "`interface`/`role_tempo` изменение применится и станет обратимым в состоянии; "
            "для `ui` — зафиксируется как одобренная подсказка для ручной правки владельца.\n"
            "- Если **нет** — ничего не применяй; предложение остаётся `proposed` "
            "(позже возможен `revert` уже применённого).\n"
            "- Никогда не показывай эти служебные детали НОВИЧКУ — только наставнику.\n"
        )
    except Exception:
        log.debug("GigaBuddy mentor section skipped on error", exc_info=True)
        return ""


def gigabuddy_mentor_section(task: Dict[str, Any], drive_root: pathlib.Path | str) -> str:
    """Mentor-side section for a task, or "" unless this is the mentor thread.

    Gated on: product mode == gigabuddy AND the task's resolved project id is NOT
    the novice thread (the mentor/owner works from ordinary Ouroboros, switched to
    GigaBuddy — that is NOT the novice room). Off entirely in ordinary Ouroboros
    (product off) and inside the novice thread (which gets the newcomer persona,
    never evolution chrome). Fail-soft: any error yields "".
    """
    try:
        if not _product_mode_is_gigabuddy():
            return ""
        from ouroboros.gigabuddy_state import is_novice_project_id
        from ouroboros.project_facts import resolve_project_id

        if is_novice_project_id(resolve_project_id(task)):
            return ""
        return build_gigabuddy_mentor_section(drive_root)
    except Exception:
        log.debug("GigaBuddy mentor section gate skipped on error", exc_info=True)
        return ""
