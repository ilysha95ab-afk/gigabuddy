"""GigaBuddy per-employee novice chat projects (v6.87.4).

Each newcomer gets their OWN Project (named after them) so their dialogue is
stored separately: switching employees switches the mounted center chat to that
employee's project and the previous person's history stays put. The legacy
single ``gigabuddy-novice`` project (``ensure_novice_project`` in
``gigabuddy_state``) is untouched — this module only adds the per-employee
deterministic id family ``gigabuddy-novice-<employee_id>`` with the same
bounded tombstone-recovery walk (``-2`` … ``-20``). Fail-soft everywhere: a
registry failure yields the zero descriptor, never an exception, so the eager
``/api/state`` / gigabuddy action seam can never be broken by it.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, Dict

log = logging.getLogger(__name__)

# Same recovery window as gigabuddy_state.NOVICE_PROJECT_MAX_GENERATIONS. Kept
# local to avoid growing the (full) state module; the two must stay in step.
MAX_GENERATIONS = 20

_SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


def _slug(value: Any, default: str = "unknown") -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch in _SLUG_KEEP else "-" for ch in raw)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or default)[:64]


def employee_project_id_candidates(employee_id: str) -> tuple[str, ...]:
    """Deterministic id sequence for one employee: canonical, then generations."""
    base = f"gigabuddy-novice-{_slug(employee_id)}"
    ids = [base]
    ids.extend(f"{base}-{gen}" for gen in range(2, MAX_GENERATIONS + 1))
    return tuple(ids)


def ensure_employee_project(
    drive_root: pathlib.Path | str,
    employee_id: str,
    display_name: str,
) -> Dict[str, Any]:
    """Idempotently register the per-employee novice project; zero descriptor on
    any failure. ``create_project`` is conditionally idempotent (raises on a
    tombstoned reserved id), so the try/except + deterministic suffix walk is
    mandatory, mirroring ``ensure_novice_project``.
    """
    try:
        from ouroboros import projects_registry
    except Exception as exc:  # fail-soft: never break the eager caller
        log.warning("GigaBuddy employee project unavailable (import): %s", exc)
        return {"chat_id": 0, "project_id": ""}

    name = (str(display_name or "").strip() or "Новичок")[:80]
    for candidate in employee_project_id_candidates(employee_id):
        try:
            project = projects_registry.create_project(
                drive_root,
                candidate,
                name=name,
                origin="gigabuddy",
            )
        except Exception as exc:
            # Permanently reserved (tombstoned/deleting) — next deterministic id.
            log.warning(
                "GigaBuddy employee project id %r unusable, trying next: %s",
                candidate,
                exc,
            )
            continue
        return {
            "chat_id": int(project.get("chat_id") or 0),
            "project_id": str(project.get("id") or ""),
        }

    log.warning(
        "GigaBuddy employee project unavailable: all %d candidate ids reserved",
        MAX_GENERATIONS,
    )
    return {"chat_id": 0, "project_id": ""}
