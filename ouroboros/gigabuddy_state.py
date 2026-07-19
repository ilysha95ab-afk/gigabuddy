"""Mutable GigaBuddy product-mode state.

This is the small domain reducer behind the GigaBuddy demo shell.  The gateway
transports actions; this module owns state shape, validation, bounded history,
and the novice-safe view projection.
"""

from __future__ import annotations

import copy
import logging
import os
import pathlib
import re
import time
from typing import Any, Callable, Dict

from ouroboros import gigabuddy_evolution as _evo
from ouroboros.utils import read_json_dict, update_json_locked, utc_now_iso

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1

# GigaBuddy novice thread (B1): a real project-backed chat_id thread so the
# novice's messages are PARTITIONED from the developer's main chat in the UI /
# history layer. This is a focused room within one unified Ouroboros awareness
# (BIBLE P1) — NOT memory/privacy isolation; unified memory/identity stays intact.
NOVICE_PROJECT_ID = "gigabuddy-novice"
NOVICE_PROJECT_NAME = "Новичок"
# Tombstone recovery window: if the owner deletes the novice thread, its id is
# permanently reserved and ensure_novice_project walks these deterministic
# fallback ids (gigabuddy-novice, gigabuddy-novice-2, …-N) to the first usable
# one. Bounded so a pathological delete-loop cannot spin forever.
NOVICE_PROJECT_MAX_GENERATIONS = 20


def _novice_project_id_candidates() -> tuple[str, ...]:
    """Deterministic id sequence: canonical id, then suffixed generations.

    A given owner-delete advances the suffix by exactly one and the chosen id is
    stable across restarts (create_project is idempotent for an ACTIVE id), so the
    novice thread keeps a durable partitioned chat_id.
    """
    ids = [NOVICE_PROJECT_ID]
    ids.extend(
        f"{NOVICE_PROJECT_ID}-{gen}"
        for gen in range(2, NOVICE_PROJECT_MAX_GENERATIONS + 1)
    )
    return tuple(ids)


def is_novice_project_id(project_id: str) -> bool:
    """True for the canonical novice id or any deterministic fallback generation.

    Used by the frontend `/clean` interception, which must keep recognising the
    novice thread after a tombstone-recovery id shift (see ensure_novice_project).
    """
    pid = str(project_id or "").strip()
    if pid == NOVICE_PROJECT_ID:
        return True
    prefix = f"{NOVICE_PROJECT_ID}-"
    if not pid.startswith(prefix):
        return False
    suffix = pid[len(prefix):]
    return suffix.isdigit()


STATE_RELATIVE_PATH = pathlib.Path("state") / "gigabuddy" / "state.json"
STAGES = ("advisor", "assistant", "partner")
STAGE_LABELS = {
    "advisor": "Советчик",
    "assistant": "Помощник",
    "partner": "Партнёр",
}
NEXT_STAGE = {
    "advisor": "assistant",
    "assistant": "partner",
    "partner": "partner",
}
MAX_EVENTS = 80
MAX_TASKS_PER_EMPLOYEE = 24
MAX_MENTOR_NOTES = 12
MAX_BEHAVIOR_VERSIONS = 8
MAX_TRACK_STAGES = 12
MAX_TRACK_STEPS = 12
MAX_ROLLBACK_HISTORY = 16
MAX_INTERESTS = 8
MAX_LAYOUT_SECTIONS = 16
MAX_TEXT_CHARS = 320
MAX_NOTE_CHARS = 600
MAX_SUMMARY_CHARS = 900

# Interface personalization (hyper-personification). These are presentation-only
# attributes that adapt the product shell per employee; they are NOT sensitive
# diagnostics and ARE safe to surface in the novice view.
ALLOWED_THEMES = ("neutral", "soft-cat", "strict-terminal", "warm-sunrise", "ocean-calm")
ALLOWED_TONES = ("formal", "friendly", "playful")
DEFAULT_ACCENT = "#c93545"
# The panel section identifiers a layout config may order/hide.
LAYOUT_SECTIONS = (
    "hero",
    "stage",
    "progress",
    "tasks",
    "next_step",
    "readiness",
    "questionnaire",
)
# Accent must stay within the design system: a 3/6-digit hex color. Empty or
# invalid falls back to the primary crimson so a config can never inject
# arbitrary CSS.
_HEX_ACCENT_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
# The neutral, nameless employee a fresh install starts on — BEFORE a mentor has
# dropped a profile into the employee folder. It carries no name, no department,
# an empty track and no tasks, so the panels/persona show neutral placeholders and
# never fabricate a candidate (B3). Alice/Leonid are LOADABLE demo configs (files
# under DEMO_PROFILES_DIR), not the hardcoded default.
BLANK_EMPLOYEE_ID = "novice"

ALLOWED_OPS = frozenset({
    "get_state",
    "select_employee",
    "add_task",
    "approve_stage",
    "reject_stage",
    "rollback",
    "demo_accelerate",
    "load_profile",
    "set_track",
    "record_progress",
    "propose_evolution",
    "approve_evolution",
    "revert_evolution",
})


class GigaBuddyStateError(ValueError):
    """User-correctable state/action validation error."""


def _clip(value: Any, limit: int = MAX_TEXT_CHARS) -> str:
    text = str(value or "").strip()
    return text[:limit]


def _slug(value: Any, default: str = "demo") -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in raw)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or default)[:64]


def _now_id(prefix: str) -> str:
    return f"{prefix}-{int(time.time() * 1000):x}"


def _stage(value: Any, default: str = "advisor") -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in STAGES else default


def _theme(value: Any, default: str = "neutral") -> str:
    candidate = _slug(value, default)
    return candidate if candidate in ALLOWED_THEMES else default


def _tone(value: Any, default: str = "friendly") -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in ALLOWED_TONES else default


def _accent(value: Any, default: str = DEFAULT_ACCENT) -> str:
    candidate = str(value or "").strip()
    return candidate if _HEX_ACCENT_RE.fullmatch(candidate) else default


def _mascot(value: Any, default: str = "✨") -> str:
    text = str(value or "").strip()
    return (text[:8] or default) if text else default


def _layout(value: Any) -> list[str]:
    """Return a validated ordered list of visible panel sections.

    Unknown identifiers are dropped and every known section not listed is kept
    visible by appending it in canonical order — so a layout config can reorder
    or hide sections but can never blank the panel or inject unknown keys.
    """
    order: list[str] = []
    if isinstance(value, list):
        for item in value[:MAX_LAYOUT_SECTIONS]:
            key = _slug(item, "")
            if key in LAYOUT_SECTIONS and key not in order:
                order.append(key)
    for section in LAYOUT_SECTIONS:
        if section not in order:
            order.append(section)
    return order


def _default_interface(theme: str, accent: str, mascot: str, tone: str) -> Dict[str, Any]:
    return {
        "theme": _theme(theme),
        "accent_color": _accent(accent),
        "mascot": _mascot(mascot),
        "tone": _tone(tone),
        "layout": list(LAYOUT_SECTIONS),
    }


def _normalize_interface(raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    fb = fallback if isinstance(fallback, dict) else {}
    return {
        "theme": _theme(raw.get("theme") or fb.get("theme"), "neutral"),
        "accent_color": _accent(raw.get("accent_color") or fb.get("accent_color")),
        "mascot": _mascot(raw.get("mascot") or fb.get("mascot")),
        "tone": _tone(raw.get("tone") or fb.get("tone")),
        "layout": _layout(raw.get("layout") if isinstance(raw.get("layout"), list) else fb.get("layout")),
    }


def _default_profile(name: str, role: str, department: str, experience: str, interests: list[str]) -> Dict[str, Any]:
    return {
        "name": _clip(name, 80),
        "role": _clip(role, 120),
        "department": _clip(department, 120),
        "experience": _clip(experience, MAX_NOTE_CHARS),
        "interests": [_clip(item, 60) for item in interests if _clip(item, 60)][:MAX_INTERESTS],
    }


def _normalize_profile(raw: Any, fallback: Dict[str, Any], emp: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    fb = fallback if isinstance(fallback, dict) else {}
    interests_raw = raw.get("interests") if isinstance(raw.get("interests"), list) else fb.get("interests", [])
    return {
        "name": _clip(raw.get("name") or fb.get("name") or emp.get("name"), 80),
        "role": _clip(raw.get("role") or fb.get("role") or emp.get("role"), 120),
        "department": _clip(raw.get("department") or fb.get("department"), 120),
        "experience": _clip(raw.get("experience") or fb.get("experience"), MAX_NOTE_CHARS),
        "interests": [_clip(item, 60) for item in interests_raw if _clip(item, 60)][:MAX_INTERESTS],
    }


def _normalize_track_steps(raw: Any) -> list[str]:
    """Normalize a track stage's expandable onboarding steps (B2). Steps are the
    employee's concrete adaptation actions for this stage; the questionnaire that
    fills them lands in B3/C, so this is empty by default and never fabricated."""
    if not isinstance(raw, list):
        return []
    steps = [_clip(item, MAX_TEXT_CHARS) for item in raw if _clip(item, MAX_TEXT_CHARS)]
    return steps[:MAX_TRACK_STEPS]


def _track_stage(stage_id: str, title: str, status: str = "planned", steps: Any = None) -> Dict[str, Any]:
    sid = _stage(stage_id)
    st = _clip(status, 32) or "planned"
    if st not in {"planned", "active", "done"}:
        st = "planned"
    return {
        "id": sid,
        "label": STAGE_LABELS[sid],
        "title": _clip(title) or STAGE_LABELS[sid],
        "status": st,
        "steps": _normalize_track_steps(steps),
    }


def _default_track(stage: str) -> list[Dict[str, Any]]:
    """Build a default advisor->assistant->partner adaptation track keyed off the
    employee's current stage (stages up to current are done, current is active)."""
    current = _stage(stage)
    order = list(STAGES)
    idx = order.index(current)
    titles = {
        "advisor": "Онбординг с высокой опорой",
        "assistant": "Совместные задачи и разбор",
        "partner": "Самостоятельная работа с challenge-mode",
    }
    track = []
    for i, sid in enumerate(order):
        if i < idx:
            status = "done"
        elif i == idx:
            status = "active"
        else:
            status = "planned"
        track.append(_track_stage(sid, titles[sid], status))
    return track


def _normalize_track(raw: Any, fallback_stage: str, *, allow_empty: bool = False) -> list[Dict[str, Any]]:
    """Normalize an adaptation track.

    A NON-list ``raw`` means "no track provided" and seeds the demo default. An
    explicit empty list is preserved when ``allow_empty`` is set — the blank
    (nameless) employee must keep an empty track (B3: never fabricate stages)."""
    if not isinstance(raw, list):
        return [] if allow_empty else _default_track(fallback_stage)
    if not raw:
        return [] if allow_empty else _default_track(fallback_stage)
    normalized: list[Dict[str, Any]] = []
    for item in raw[:MAX_TRACK_STAGES]:
        if not isinstance(item, dict):
            continue
        normalized.append(
            _track_stage(
                item.get("id"),
                item.get("title"),
                _clip(item.get("status"), 32) or "planned",
                item.get("steps"),
            )
        )
    if normalized:
        return normalized
    return [] if allow_empty else _default_track(fallback_stage)


def _track_progress_pct(track: list[Dict[str, Any]]) -> int:
    """Aggregate track progress: done counts full, active counts half."""
    if not track:
        return 0
    score = 0.0
    for stage in track:
        status = stage.get("status")
        if status == "done":
            score += 1.0
        elif status == "active":
            score += 0.5
    return max(0, min(100, round(score / len(track) * 100)))


def _state_path(drive_root: pathlib.Path | str) -> pathlib.Path:
    path = pathlib.Path(drive_root) / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _task(task_id: str, title: str, *, status: str = "planned", source: str = "demo") -> Dict[str, Any]:
    return {
        "id": _slug(task_id, _now_id("task")),
        "title": _clip(title),
        "status": _clip(status, 32) or "planned",
        "source": _clip(source, 32) or "demo",
    }


def _behavior(version_id: str, stage: str, tone: str, theme: str, reason: str) -> Dict[str, Any]:
    stage_id = _stage(stage)
    return {
        "id": _slug(version_id, "v1"),
        "stage": stage_id,
        "stage_label": STAGE_LABELS[stage_id],
        "tone": _clip(tone),
        "theme": _clip(theme, 80),
        "reason": _clip(reason),
        "created_at": utc_now_iso(),
    }


def _default_employee(
    employee_id: str,
    name: str,
    role: str,
    *,
    avatar: str,
    theme: str,
    stage: str,
    progress: int,
    tasks: list[Dict[str, Any]],
    questionnaire_package_id: str,
    department: str = "",
    experience: str = "",
    interests: list[str] | None = None,
    accent: str = DEFAULT_ACCENT,
    tone: str = "friendly",
    mentor_notes: list[str] | None = None,
) -> Dict[str, Any]:
    stage_id = _stage(stage)
    behavior = _behavior("v1", stage_id, "warm_supportive", theme, "initial_demo_profile")
    return {
        "id": _slug(employee_id),
        "name": _clip(name, 80),
        "role": _clip(role, 120),
        "avatar": _clip(avatar, 8),
        "theme": _clip(theme, 80),
        "stage": stage_id,
        "progress_pct": max(0, min(100, int(progress))),
        "questionnaire_package_id": _slug(questionnaire_package_id, "people-culture-base"),
        "next_step": "Разобрать безопасный следующий шаг",
        "readiness": "Требуется подтверждение наставника",
        "tasks": tasks[:MAX_TASKS_PER_EMPLOYEE],
        "mentor_notes": list(mentor_notes or [])[:MAX_MENTOR_NOTES],
        "behavior_versions": [behavior],
        "active_behavior_version_id": behavior["id"],
        "rollback_history": [],
        "profile": _default_profile(name, role, department, experience, list(interests or [])),
        "interface": _default_interface(theme, accent, avatar, tone),
        "track": _default_track(stage_id),
        "evolution_proposals": [],
        "internal_signals": {
            "support_need": "internal_only",
            "confidence_risk": "hidden_from_novice",
        },
    }


def _blank_employee() -> Dict[str, Any]:
    """A neutral, nameless employee: no name, no department, empty track, no tasks.

    This is the honest starting state before a mentor drops a profile file into
    ``~/Ouroboros/gigabuddy/employees/<id>/profile/``. Panels and the persona show
    neutral placeholders instead of fabricating a candidate (B3)."""
    behavior = _behavior("v1", "advisor", "warm_supportive", "neutral", "neutral_start")
    return {
        "id": BLANK_EMPLOYEE_ID,
        "name": "",
        "role": "",
        "avatar": "✨",
        "theme": "neutral",
        "stage": "advisor",
        "progress_pct": 0,
        "questionnaire_package_id": "people-culture-base",
        "next_step": "",
        "readiness": "",
        "tasks": [],
        "mentor_notes": [],
        "behavior_versions": [behavior],
        "active_behavior_version_id": behavior["id"],
        "rollback_history": [],
        "profile": _default_profile("", "", "", "", []),
        "interface": _default_interface("neutral", DEFAULT_ACCENT, "✨", "friendly"),
        "track": [],
        "evolution_proposals": [],
        "internal_signals": {},
    }


def default_gigabuddy_state() -> Dict[str, Any]:
    """Return the neutral, nameless default state — NO synthetic candidate.

    A fresh install starts on the blank ``novice`` employee (no name, no
    department, empty track). Alice/Leonid live as LOADABLE demo profile files
    (see ``list_demo_profiles``/``load_demo_profile``); the owner swaps them in by
    hand for the demo via the ``load_profile`` action. They are deliberately NOT
    the hardcoded default anymore (B3)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "active_employee_id": BLANK_EMPLOYEE_ID,
        "questionnaire_packages": {
            "people-culture-base": {
                "id": "people-culture-base",
                "title": "Базовый опросник знакомства",
                "domain": "",
                "knowledge_base_hint": "Подгружается из папки knowledge/ сотрудника",
                "diagnostic_policy": "ГигаБадди выводит уровень поддержки, автономности и стиль обучения сам; новичок не выбирает чувствительные ярлыки.",
                "questions": [
                    "Расскажи, какая часть новой роли сейчас кажется самой непонятной.",
                    "Представь запрос от внутреннего заказчика: с чего начнёшь безопасно?",
                    "Что поможет тебе быстрее войти в процесс: пример, чек-лист, схема или совместный разбор?",
                ],
            },
        },
        "employees": {
            BLANK_EMPLOYEE_ID: _blank_employee(),
        },
        "events": [],
        "updated_at": utc_now_iso(),
    }


# --- Loadable demo profiles (Alice / Leonid) --------------------------------
# These are DEMO CONFIGS the owner loads by hand for a demo — NOT the hardcoded
# default. `load_profile` with one of these ids does a full state replacement for
# the active employee, mirroring the file-parse path (B3). A mentor's real profile
# file under employees/<id>/profile/ takes precedence over these built-in demos.
_DEMO_PROFILES: Dict[str, Dict[str, Any]] = {
    "alice-demo": {
        "name": "Алиса",
        "role": "HR · Люди и культура",
        "profile": {
            "name": "Алиса",
            "role": "HR · Люди и культура",
            "department": "Люди и культура",
            "experience": "Первая роль в найме; сильна в коммуникации, осваивает внутренние регламенты.",
            "interests": ["котики", "иллюстрация", "командные ритуалы"],
        },
        "interface": {"theme": "soft-cat", "accent_color": "#e8799f", "mascot": "🐾", "tone": "playful"},
    },
    "leonid-demo": {
        "name": "Леонид",
        "role": "Разработчик · внутренний переход",
        "profile": {
            "name": "Леонид",
            "role": "Разработчик · внутренний переход",
            "department": "Инженерия платформы",
            "experience": "Опытный разработчик; переходит между командами, нужен быстрый деловой тон.",
            "interests": ["распределённые системы", "надёжность", "code review"],
        },
        "interface": {"theme": "strict-terminal", "accent_color": "#5ad1c9", "mascot": "⌘", "tone": "formal"},
    },
}


def list_demo_profiles() -> list[Dict[str, str]]:
    """Loadable built-in demo profiles (id + display name) for the owner switcher."""
    return [
        {"id": pid, "name": str(spec.get("name") or pid)}
        for pid, spec in _DEMO_PROFILES.items()
    ]


def _apply_profile_fragment(emp: Dict[str, Any], fragment: Dict[str, Any]) -> None:
    """Merge a parsed profile fragment (from a file or a built-in demo) onto the
    active employee: name/role/profile/interface. The subsequent normalize pass
    validates every field (allow-lists, hex accent, caps)."""
    if not isinstance(fragment, dict):
        return
    if fragment.get("name"):
        emp["name"] = str(fragment["name"]).strip()
    if fragment.get("role"):
        emp["role"] = str(fragment["role"]).strip()
    prof = fragment.get("profile")
    if isinstance(prof, dict):
        emp_profile = dict(emp.get("profile") or {})
        emp_profile.update({k: v for k, v in prof.items() if v})
        emp["profile"] = emp_profile
    iface = fragment.get("interface")
    if isinstance(iface, dict):
        emp_iface = dict(emp.get("interface") or {})
        emp_iface.update({k: v for k, v in iface.items() if v})
        emp["interface"] = emp_iface
        if iface.get("mascot"):
            emp["avatar"] = str(iface["mascot"]).strip()[:8]
        if iface.get("theme"):
            emp["theme"] = str(iface["theme"]).strip()[:80]


def _normalize_task(raw: Any) -> Dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    title = _clip(raw.get("title"))
    if not title:
        return None
    status = _clip(raw.get("status"), 32) or "planned"
    if status not in {"planned", "active", "done", "blocked"}:
        status = "planned"
    return {
        "id": _slug(raw.get("id"), _now_id("task")),
        "title": title,
        "status": status,
        "source": _clip(raw.get("source"), 32) or "demo",
    }


def _normalize_employee(raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    emp = copy.deepcopy(fallback)
    emp["id"] = _slug(raw.get("id") or emp.get("id"))
    emp["name"] = _clip(raw.get("name") or emp.get("name"), 80)
    emp["role"] = _clip(raw.get("role") or emp.get("role"), 120)
    emp["avatar"] = _clip(raw.get("avatar") or emp.get("avatar"), 8)
    emp["theme"] = _clip(raw.get("theme") or emp.get("theme"), 80)
    emp["stage"] = _stage(raw.get("stage"), emp.get("stage", "advisor"))
    try:
        progress = int(raw.get("progress_pct", emp.get("progress_pct", 0)))
    except (TypeError, ValueError):
        progress = int(emp.get("progress_pct", 0) or 0)
    emp["progress_pct"] = max(0, min(100, progress))
    emp["questionnaire_package_id"] = _slug(
        raw.get("questionnaire_package_id") or emp.get("questionnaire_package_id"),
        "people-culture-base",
    )
    emp["next_step"] = _clip(raw.get("next_step") or emp.get("next_step"), MAX_NOTE_CHARS)
    emp["readiness"] = _clip(raw.get("readiness") or emp.get("readiness"), MAX_NOTE_CHARS)
    tasks = [_normalize_task(item) for item in (raw.get("tasks") if isinstance(raw.get("tasks"), list) else emp.get("tasks", []))]
    emp["tasks"] = [item for item in tasks if item][:MAX_TASKS_PER_EMPLOYEE]
    notes = raw.get("mentor_notes") if isinstance(raw.get("mentor_notes"), list) else emp.get("mentor_notes", [])
    emp["mentor_notes"] = [_clip(note, MAX_NOTE_CHARS) for note in notes if _clip(note, MAX_NOTE_CHARS)][:MAX_MENTOR_NOTES]
    versions = raw.get("behavior_versions") if isinstance(raw.get("behavior_versions"), list) else emp.get("behavior_versions", [])
    normalized_versions = []
    for item in versions[:MAX_BEHAVIOR_VERSIONS]:
        if not isinstance(item, dict):
            continue
        stage_id = _stage(item.get("stage"), emp["stage"])
        normalized_versions.append({
            "id": _slug(item.get("id"), "v1"),
            "stage": stage_id,
            "stage_label": STAGE_LABELS[stage_id],
            "tone": _clip(item.get("tone"), 80) or "warm_supportive",
            "theme": _clip(item.get("theme"), 80) or emp["theme"],
            "reason": _clip(item.get("reason"), MAX_NOTE_CHARS) or "state",
            "created_at": _clip(item.get("created_at"), 80) or utc_now_iso(),
        })
    if not normalized_versions:
        normalized_versions = [_behavior("v1", emp["stage"], "warm_supportive", emp["theme"], "normalized")]
    emp["behavior_versions"] = normalized_versions[-MAX_BEHAVIOR_VERSIONS:]
    active_version = _slug(raw.get("active_behavior_version_id") or emp.get("active_behavior_version_id"), normalized_versions[-1]["id"])
    valid_ids = {item["id"] for item in normalized_versions}
    emp["active_behavior_version_id"] = active_version if active_version in valid_ids else normalized_versions[-1]["id"]
    signals = raw.get("internal_signals") if isinstance(raw.get("internal_signals"), dict) else emp.get("internal_signals", {})
    emp["internal_signals"] = {str(k)[:80]: _clip(v, MAX_NOTE_CHARS) for k, v in signals.items()}
    emp["profile"] = _normalize_profile(raw.get("profile"), emp.get("profile"), emp)
    emp["interface"] = _normalize_interface(raw.get("interface"), emp.get("interface") or {})
    # B3 "never fabricate a track": an empty track is preserved for EVERY
    # employee (the blank novice AND a freshly loaded named profile whose track
    # the chat questionnaire has not built yet). Stages only ever come from the
    # questionnaire (set_track) or an explicit stage transition (which seeds via
    # _sync_track_to_stage) — never from normalization.
    emp["track"] = _normalize_track(
        raw.get("track") if isinstance(raw.get("track"), list) else emp.get("track"),
        emp["stage"],
        allow_empty=True,
    )
    rollback_raw = raw.get("rollback_history") if isinstance(raw.get("rollback_history"), list) else emp.get("rollback_history", [])
    rollback_history: list[Dict[str, Any]] = []
    for item in rollback_raw[-MAX_ROLLBACK_HISTORY:]:
        if not isinstance(item, dict):
            continue
        rollback_history.append({
            "version_id": _slug(item.get("version_id"), "v1"),
            "stage": _stage(item.get("stage"), emp["stage"]),
            "reason": _clip(item.get("reason"), MAX_NOTE_CHARS) or "rollback",
            "at": _clip(item.get("at"), 80) or utc_now_iso(),
        })
    emp["rollback_history"] = rollback_history[-MAX_ROLLBACK_HISTORY:]
    # Reversible self-evolution proposal ledger. Without this the allow-list
    # projection would silently drop the field on every round-trip.
    emp["evolution_proposals"] = _evo.normalize_evolution_proposals(
        raw.get("evolution_proposals")
        if isinstance(raw.get("evolution_proposals"), list)
        else emp.get("evolution_proposals", [])
    )
    return emp


def _normalize_questionnaire(raw: Any, fallback: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raw = {}
    q = copy.deepcopy(fallback)
    q["id"] = _slug(raw.get("id") or q.get("id"), "people-culture-base")
    q["title"] = _clip(raw.get("title") or q.get("title"), 120)
    q["domain"] = _clip(raw.get("domain") or q.get("domain"), 120)
    q["knowledge_base_hint"] = _clip(raw.get("knowledge_base_hint") or q.get("knowledge_base_hint"), MAX_NOTE_CHARS)
    q["diagnostic_policy"] = _clip(raw.get("diagnostic_policy") or q.get("diagnostic_policy"), MAX_NOTE_CHARS)
    questions = raw.get("questions") if isinstance(raw.get("questions"), list) else q.get("questions", [])
    q["questions"] = [_clip(item, MAX_NOTE_CHARS) for item in questions if _clip(item, MAX_NOTE_CHARS)][:12]
    return q


def normalize_gigabuddy_state(raw: Any) -> Dict[str, Any]:
    defaults = default_gigabuddy_state()
    if not isinstance(raw, dict):
        raw = {}
    state = copy.deepcopy(defaults)
    questionnaires = raw.get("questionnaire_packages") if isinstance(raw.get("questionnaire_packages"), dict) else {}
    merged_q = dict(defaults["questionnaire_packages"])
    for qid, qraw in questionnaires.items():
        fallback = merged_q.get(_slug(qid), {"id": _slug(qid), "title": _slug(qid), "questions": []})
        merged_q[_slug(qid)] = _normalize_questionnaire(qraw, fallback)
    state["questionnaire_packages"] = merged_q
    employees = raw.get("employees") if isinstance(raw.get("employees"), dict) else {}
    merged_employees = dict(defaults["employees"])
    for eid, eraw in employees.items():
        key = _slug(eid)
        fallback = merged_employees.get(key) or _default_employee(key, key, "Demo", avatar="✨", theme="neutral", stage="advisor", progress=0, questionnaire_package_id="people-culture-base", tasks=[])
        merged_employees[key] = _normalize_employee(eraw, fallback)
    state["employees"] = merged_employees
    active = _slug(raw.get("active_employee_id") or defaults["active_employee_id"], defaults["active_employee_id"])
    if active not in merged_employees:
        active = defaults["active_employee_id"]
    state["active_employee_id"] = active
    events = raw.get("events") if isinstance(raw.get("events"), list) else []
    state["events"] = [event for event in events if isinstance(event, dict)][-MAX_EVENTS:]
    state["schema_version"] = SCHEMA_VERSION
    state["updated_at"] = _clip(raw.get("updated_at"), 80) or utc_now_iso()
    return state


def load_gigabuddy_state(drive_root: pathlib.Path | str) -> Dict[str, Any]:
    path = _state_path(drive_root)
    return normalize_gigabuddy_state(read_json_dict(path))


def _active_employee(state: Dict[str, Any]) -> Dict[str, Any]:
    return state["employees"][state["active_employee_id"]]


def _novice_event(event: Any) -> Dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    op = _clip(event.get("op"), 64)
    employee_id = _slug(event.get("employee_id"), "")
    detail_by_op = {
        "select_employee": "Профиль подготовки обновлён.",
        "add_task": "Наставник обновил трек адаптации.",
        "approve_stage": "Наставник согласовал изменение уровня поддержки.",
        "reject_stage": "Наставник уточнил следующий шаг перед переходом роли.",
        "rollback": "Стиль поддержки обновлён без потери прогресса.",
        "demo_accelerate": "Состояние подготовки обновлено в admin-контуре.",
    }
    detail = detail_by_op.get(op)
    if not detail:
        return None
    return {"op": op, "employee_id": employee_id, "detail": detail}


def build_gigabuddy_view(state: Dict[str, Any]) -> Dict[str, Any]:
    """Return the novice-safe panel projection. Internal diagnostics stay out."""
    state = normalize_gigabuddy_state(state)
    emp = _active_employee(state)
    stage_id = _stage(emp.get("stage"))
    next_id = NEXT_STAGE[stage_id]
    versions = emp.get("behavior_versions", [])
    active_version = next((v for v in versions if v.get("id") == emp.get("active_behavior_version_id")), versions[-1] if versions else {})
    package = state["questionnaire_packages"].get(emp.get("questionnaire_package_id"), {})
    interface = emp.get("interface") or _default_interface(emp.get("theme", "neutral"), DEFAULT_ACCENT, emp.get("avatar", "✨"), "friendly")
    profile = emp.get("profile") or {}
    track = emp.get("track") or []
    # Progress is derived from the adaptation track; fall back to the stored
    # per-employee metric only when the track is empty.
    track_progress = _track_progress_pct(track)
    progress_pct = track_progress if track else int(emp.get("progress_pct", 0) or 0)
    return {
        "productName": "ГигаБадди",
        "subtitle": "персональный ИИ-наставник адаптации",
        "employees": [
            {"id": item["id"], "name": item["name"], "role": item["role"], "avatar": item.get("avatar", "✨")}
            for item in state["employees"].values()
        ],
        "activeEmployeeId": emp["id"],
        "employee": {
            "id": emp["id"],
            "name": emp["name"],
            "role": emp["role"],
            "avatar": emp.get("avatar", "✨"),
            "theme": interface.get("theme", emp.get("theme", "neutral")),
        },
        "profile": {
            "name": profile.get("name", emp.get("name", "")),
            "role": profile.get("role", emp.get("role", "")),
            "department": profile.get("department", ""),
            "experience": profile.get("experience", ""),
            "interests": list(profile.get("interests", []))[:MAX_INTERESTS],
        },
        "interface": {
            "theme": interface.get("theme", "neutral"),
            "accentColor": interface.get("accent_color", DEFAULT_ACCENT),
            "mascot": interface.get("mascot", emp.get("avatar", "✨")),
            "tone": interface.get("tone", "friendly"),
            "layout": list(interface.get("layout", list(LAYOUT_SECTIONS))),
        },
        "track": [
            {
                "id": item.get("id", ""),
                "label": item.get("label", ""),
                "title": item.get("title", ""),
                "status": item.get("status", "planned"),
                "steps": list(item.get("steps", []))[:MAX_TRACK_STEPS],
            }
            for item in track
        ],
        "stage": {
            "id": stage_id,
            "label": STAGE_LABELS[stage_id],
            "next": STAGE_LABELS[next_id],
            "helpLevel": _stage_help(stage_id),
        },
        "progressPct": progress_pct,
        "nextStep": emp.get("next_step", ""),
        "readiness": emp.get("readiness", ""),
        "behaviorVersion": f"{active_version.get('id', 'v1')} · {active_version.get('stage_label', STAGE_LABELS[stage_id])}",
        "tasks": emp.get("tasks", [])[:MAX_TASKS_PER_EMPLOYEE],
        "questionnairePackage": {
            "id": package.get("id", ""),
            "title": package.get("title", ""),
            "domain": package.get("domain", ""),
            "knowledgeBaseHint": package.get("knowledge_base_hint", ""),
            "diagnosticPolicy": package.get("diagnostic_policy", ""),
            "questions": package.get("questions", [])[:5],
        },
        "events": [event for event in (_novice_event(row) for row in state.get("events", [])[-8:]) if event],
        # #4 Karpathy-wiki build status for the right-panel indicator. View-pure and
        # NON-BLOCKING: knowledge_status() reads the live folder signature + any
        # persisted .wiki_index/ index and NEVER triggers the LLM build here. The
        # actual (re)build is fired out-of-band by the gateway seam. Fail-soft.
        "knowledgeBase": _knowledge_base_view(emp.get("id") or ""),
    }


def _knowledge_base_view(employee_id: str) -> Dict[str, Any]:
    """Novice-safe knowledge-base status for the panel indicator (fail-soft)."""
    try:
        from ouroboros import gigabuddy_knowledge as _gk

        return _gk.knowledge_status(employee_id)
    except Exception:
        return {"status": "empty", "docCount": 0, "chunkCount": 0, "llmBuilt": False}


def _stage_help(stage_id: str) -> str:
    if stage_id == "advisor":
        return "Высокая опора: примеры, шаблоны, безопасные шаги"
    if stage_id == "assistant":
        return "Средняя опора: вопросы, варианты решений, совместная проверка"
    return "Партнёрский режим: коротко, делово, с challenge-mode и подсветкой рисков"


def _event(op: str, employee_id: str, detail: str, **extra: Any) -> Dict[str, Any]:
    row = {"ts": utc_now_iso(), "op": op, "employee_id": employee_id, "detail": _clip(detail, MAX_NOTE_CHARS)}
    row.update({k: v for k, v in extra.items() if isinstance(v, (str, int, float, bool))})
    return row


def _append_event(state: Dict[str, Any], event: Dict[str, Any]) -> None:
    events = list(state.get("events") or [])
    events.append(event)
    state["events"] = events[-MAX_EVENTS:]
    state["updated_at"] = utc_now_iso()


def _op_get_state(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    return {"state": state, "audit": {"op": "get_state", "result": "success", "employee_id": state["active_employee_id"]}}


def _op_select_employee(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    employee_id = _slug(payload.get("employee_id"), "")
    if employee_id not in state["employees"]:
        raise GigaBuddyStateError("Unknown GigaBuddy employee profile.")
    state["active_employee_id"] = employee_id
    _append_event(state, _event("select_employee", employee_id, "Профиль выбран для демо"))
    return {"state": state, "audit": {"op": "select_employee", "employee_id": employee_id, "result": "success"}}


def _op_add_task(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    title = _clip(payload.get("title"), MAX_TEXT_CHARS)
    if not title:
        raise GigaBuddyStateError("Task title is required.")
    if len(emp.get("tasks", [])) >= MAX_TASKS_PER_EMPLOYEE:
        raise GigaBuddyStateError("Task list is full for this demo profile.")
    task = _task(_now_id("task"), title, status="planned", source="mentor")
    emp.setdefault("tasks", []).append(task)
    note = _clip(payload.get("note"), MAX_NOTE_CHARS)
    if note:
        emp.setdefault("mentor_notes", []).append(note)
        emp["mentor_notes"] = emp["mentor_notes"][-MAX_MENTOR_NOTES:]
    emp["next_step"] = f"Выполнить наставническую задачу: {title}"
    _append_event(state, _event("add_task", emp["id"], "Наставник добавил задачу", task_id=task["id"]))
    return {"state": state, "audit": {"op": "add_task", "employee_id": emp["id"], "task_id": task["id"], "result": "success"}}


def _op_load_profile(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Load a newcomer profile into the active employee (B3).

    Precedence: a mentor's real file under ``employees/<id>/profile/`` wins; else a
    built-in demo config (alice-demo/leonid-demo). ``employee_id`` selects both the
    folder and the demo id. Fail-soft: if nothing parses, the active employee stays
    neutral/nameless and the op reports ``loaded=False`` rather than fabricating."""
    emp = _active_employee(state)
    requested = _slug(payload.get("employee_id"), "") or emp.get("id") or BLANK_EMPLOYEE_ID
    fragment: Dict[str, Any] | None = None
    source = "none"
    try:
        from ouroboros import gigabuddy_profile

        fragment = gigabuddy_profile.load_employee_profile(requested)
        if fragment:
            source = "file"
    except Exception:
        log.warning("GigaBuddy profile file load failed for %s", requested, exc_info=True)
        fragment = None
    if not fragment and requested in _DEMO_PROFILES:
        fragment = copy.deepcopy(_DEMO_PROFILES[requested])
        source = "demo"
    if not fragment:
        _append_event(state, _event("load_profile", requested, "Профиль не найден — нейтральный старт", result="empty"))
        return {"state": state, "audit": {"op": "load_profile", "employee_id": requested, "loaded": False, "source": source, "result": "empty"}}
    # Loading a profile is a full state replacement for THAT employee. If the
    # requested id already has state, reuse it (preserve per-employee history);
    # otherwise start from a FRESH blank base so a different newcomer never
    # inherits the previous person's tasks/notes/track.
    existing = state.get("employees", {}).get(requested)
    if isinstance(existing, dict) and existing.get("id") == requested:
        target = existing
    else:
        target = _blank_employee()
        target["id"] = requested
    _apply_profile_fragment(target, fragment)
    # A freshly loaded profile starts with an empty track: the chat questionnaire
    # (Part 3) fills it. Do not fabricate stages.
    target["track"] = []
    target["stage"] = "advisor"
    target["progress_pct"] = 0
    state["employees"][requested] = target
    state["active_employee_id"] = requested
    _append_event(state, _event("load_profile", requested, "Профиль загружен", result="success", source=source))
    return {"state": state, "audit": {"op": "load_profile", "employee_id": requested, "loaded": True, "source": source, "result": "success"}}


def _op_set_track(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Set the active employee's adaptation track (B3 chat-questionnaire outcome).

    ``stages`` is a list of ``{label, title, steps[]}`` built for THIS newcomer.
    This is the durable write behind the in-chat questionnaire: the left track
    (B2) renders exactly this. Progress is re-derived from the resulting track."""
    emp = _active_employee(state)
    stages = payload.get("stages")
    if not isinstance(stages, list) or not stages:
        raise GigaBuddyStateError("A non-empty track stages list is required.")
    order = list(STAGES)
    built: list[Dict[str, Any]] = []
    for i, item in enumerate(stages[:MAX_TRACK_STAGES]):
        if not isinstance(item, dict):
            continue
        # Map the i-th stage onto advisor/assistant/partner in order unless an
        # explicit valid stage id is given.
        sid = item.get("id")
        if _stage(sid, "") not in STAGES:
            sid = order[min(i, len(order) - 1)]
        status = _clip(item.get("status"), 32) or ("active" if i == 0 else "planned")
        built.append(_track_stage(sid, item.get("title") or item.get("label"), status, item.get("steps")))
    if not built:
        raise GigaBuddyStateError("No valid track stages were provided.")
    emp["track"] = built
    emp["progress_pct"] = _track_progress_pct(built)
    _append_event(state, _event("set_track", emp["id"], "Адаптационный трек обновлён по итогам знакомства", stages=len(built)))
    return {"state": state, "audit": {"op": "set_track", "employee_id": emp["id"], "stages": len(built), "result": "success"}}


def _op_record_progress(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    """Durably record adaptation progress: mark a track stage done/active/planned.

    ``stage_id`` + ``status`` update one stage; progress is re-derived. This keeps
    the newcomer's stage in the PERSISTENT state (not only in the compressed
    dialogue), so the mentor persona does not 'forget' the stage after weeks."""
    emp = _active_employee(state)
    track = emp.get("track") or []
    if not track:
        raise GigaBuddyStateError("No adaptation track to record progress against.")
    stage_id = _stage(payload.get("stage_id"), "")
    status = _clip(payload.get("status"), 32)
    if status not in {"planned", "active", "done"}:
        raise GigaBuddyStateError("Progress status must be planned/active/done.")
    matched = False
    for item in track:
        if item.get("id") == stage_id:
            item["status"] = status
            matched = True
            break
    if not matched:
        raise GigaBuddyStateError("Unknown track stage id.")
    emp["track"] = track
    emp["progress_pct"] = _track_progress_pct(track)
    # Keep the employee stage aligned with the furthest active/done stage.
    order = list(STAGES)
    furthest = emp.get("stage", "advisor")
    for item in track:
        if item.get("status") in {"active", "done"} and _stage(item.get("id")) in order:
            if order.index(_stage(item["id"])) >= order.index(_stage(furthest)):
                furthest = _stage(item["id"])
    emp["stage"] = furthest
    _append_event(state, _event("record_progress", emp["id"], "Прогресс адаптации обновлён", stage_id=stage_id, status=status))
    return {"state": state, "audit": {"op": "record_progress", "employee_id": emp["id"], "stage_id": stage_id, "status": status, "result": "success"}}


def _sync_track_to_stage(emp: Dict[str, Any], stage_id: str) -> None:
    """Move the adaptation track so stages before the current one are done, the
    current stage is active, and later stages stay planned. If the employee has
    no track yet, seed a default one."""
    track = emp.get("track") or _default_track(stage_id)
    order = list(STAGES)
    try:
        idx = order.index(_stage(stage_id))
    except ValueError:
        idx = 0
    for item in track:
        sid = _stage(item.get("id"))
        pos = order.index(sid) if sid in order else 0
        if pos < idx:
            item["status"] = "done"
        elif pos == idx:
            item["status"] = "active"
        else:
            item["status"] = "planned"
    emp["track"] = track


def _transition(state: Dict[str, Any], target_stage: str, reason: str, op: str) -> Dict[str, Any]:
    emp = _active_employee(state)
    old_stage = _stage(emp.get("stage"))
    new_stage = _stage(target_stage, old_stage)
    emp["stage"] = new_stage
    emp["readiness"] = "Переход подтверждён наставником" if op == "approve_stage" else "Переход отклонён: добавлена новая задача/причина"
    version = _behavior(_now_id("v"), new_stage, "stage_adjusted", emp.get("theme", "neutral"), reason or op)
    emp.setdefault("behavior_versions", []).append(version)
    emp["behavior_versions"] = emp["behavior_versions"][-MAX_BEHAVIOR_VERSIONS:]
    emp["active_behavior_version_id"] = version["id"]
    _sync_track_to_stage(emp, new_stage)
    emp["progress_pct"] = _track_progress_pct(emp.get("track", []))
    _append_event(state, _event(op, emp["id"], reason or op, stage_from=old_stage, stage_to=new_stage))
    return {"state": state, "audit": {"op": op, "employee_id": emp["id"], "stage_from": old_stage, "stage_to": new_stage, "result": "success"}}


def _op_approve_stage(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    target = _stage(payload.get("stage"), NEXT_STAGE[_stage(emp.get("stage"))])
    return _transition(state, target, _clip(payload.get("reason"), MAX_NOTE_CHARS) or "mentor_approved", "approve_stage")


def _op_reject_stage(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    reason = _clip(payload.get("reason"), MAX_NOTE_CHARS) or "Наставник решил дать ещё одну задачу перед переходом"
    emp.setdefault("mentor_notes", []).append(reason)
    emp["mentor_notes"] = emp["mentor_notes"][-MAX_MENTOR_NOTES:]
    task_title = _clip(payload.get("task_title"), MAX_TEXT_CHARS)
    if task_title and len(emp.get("tasks", [])) < MAX_TASKS_PER_EMPLOYEE:
        emp.setdefault("tasks", []).append(_task(_now_id("task"), task_title, status="planned", source="mentor"))
    _append_event(state, _event("reject_stage", emp["id"], "Наставник отклонил переход", result="deferred"))
    return {"state": state, "audit": {"op": "reject_stage", "employee_id": emp["id"], "result": "deferred"}}


def _op_rollback(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    version_id = _slug(payload.get("version_id"), "")
    versions = emp.get("behavior_versions", [])
    target = next((item for item in versions if item.get("id") == version_id), versions[0] if versions else None)
    if not target:
        raise GigaBuddyStateError("No behavior version is available to rollback.")
    old_stage = _stage(emp.get("stage"))
    emp["active_behavior_version_id"] = target["id"]
    emp["stage"] = _stage(target.get("stage"), old_stage)
    emp["theme"] = _clip(target.get("theme"), 80) or emp.get("theme", "neutral")
    emp["readiness"] = "Стиль откатан; прогресс и задачи сохранены"
    _sync_track_to_stage(emp, emp["stage"])
    history = emp.setdefault("rollback_history", [])
    history.append({
        "version_id": target["id"],
        "stage": emp["stage"],
        "reason": _clip(target.get("reason"), MAX_NOTE_CHARS) or "rollback",
        "at": utc_now_iso(),
    })
    emp["rollback_history"] = history[-MAX_ROLLBACK_HISTORY:]
    _append_event(state, _event("rollback", emp["id"], "Откат поведения без потери прогресса", stage_from=old_stage, stage_to=emp["stage"]))
    return {"state": state, "audit": {"op": "rollback", "employee_id": emp["id"], "stage_from": old_stage, "stage_to": emp["stage"], "result": "success"}}


def _op_demo_accelerate(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    current = _stage(emp.get("stage"))
    target = _stage(payload.get("stage"), NEXT_STAGE[current])
    emp["progress_pct"] = max(int(emp.get("progress_pct", 0) or 0), 72 if target != "partner" else 90)
    return _transition(state, target, _clip(payload.get("reason"), MAX_NOTE_CHARS) or "Быстрый виток демо", "demo_accelerate")


# --- Reversible self-evolution ops (soft layer only) -----------------------
# The reducer VALIDATES a DECLARED depth (chosen by the LLM/persona/mentor
# surface) — it never text-classifies a request into a depth (BIBLE P5). The
# soft-layer validators are passed into the pure gigabuddy_evolution helpers as
# a callable bundle to keep that module import-cycle free.
_EVOLUTION_VALIDATORS: Dict[str, Callable[..., Any]] = {
    "theme": _theme,
    "accent": _accent,
    "mascot": _mascot,
    "tone": _tone,
    "layout": _layout,
    "stage": _stage,
}


def _find_active_proposal(emp: Dict[str, Any], proposal_id: str) -> Dict[str, Any]:
    """Look up a proposal ONLY within the active employee (cross-employee
    isolation): a proposal from Alice must not be applicable while Leonid is
    active."""
    pid = _slug(proposal_id, "")
    for proposal in emp.get("evolution_proposals", []):
        if proposal.get("id") == pid:
            return proposal
    raise GigaBuddyStateError("No such evolution proposal for the active employee.")


def _op_propose_evolution(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    try:
        depth = _evo._depth(payload.get("depth"))
        inner = {k: v for k, v in payload.items() if k not in {"depth", "source"}}
        validated = _evo.validate_evolution_payload(depth, inner, _EVOLUTION_VALIDATORS)
    except _evo.EvolutionError as exc:
        raise GigaBuddyStateError(str(exc)) from exc
    proposals = list(emp.get("evolution_proposals", []))
    proposal = {
        "id": _now_id("evo"),
        "depth": depth,
        "payload": validated,
        "source": _evo._source(payload.get("source")),
        "status": "proposed",
        "git_tag_hint": "",
        "baseline_tag": "",
        "created_at": utc_now_iso(),
    }
    proposals.append(proposal)
    emp["evolution_proposals"] = proposals[-_evo.MAX_EVOLUTION_PROPOSALS:]
    _append_event(state, _event("propose_evolution", emp["id"], f"Предложена эволюция ({depth})", depth=depth))
    return {"state": state, "audit": {"op": "propose_evolution", "employee_id": emp["id"], "proposal_id": proposal["id"], "depth": depth, "result": "success"}}


def _op_approve_evolution(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    proposal = _find_active_proposal(emp, payload.get("proposal_id"))
    if proposal.get("status") != "proposed":
        raise GigaBuddyStateError(f"Evolution proposal is already {proposal.get('status')}, cannot approve again.")
    depth = proposal["depth"]
    # ordinal for the owner-facing git-tag hint (position among this employee's proposals)
    ordinal = len(emp.get("evolution_proposals", []))
    proposal["git_tag_hint"] = _evo.git_tag_hint(emp["id"], ordinal)
    proposal["baseline_tag"] = "v6.82.0"

    if depth == "ui":
        # ui is proposal-only: approving records the intent + owner git-command
        # hint. It NEVER mutates state and never claims an applied code change —
        # the actual UI edit is an owner-landed, reviewed git change.
        proposal["status"] = "approved"
        _append_event(state, _event("approve_evolution", emp["id"], "Одобрено UI-предложение (правит наставник/владелец)", depth=depth))
        return {"state": state, "audit": {"op": "approve_evolution", "employee_id": emp["id"], "proposal_id": proposal["id"], "depth": depth, "applied": False, "result": "approved"}}

    # interface / role_tempo are APPLYABLE: snapshot the exact effective state
    # BEFORE mutating so revert restores it precisely (never _op_rollback).
    proposal["pre_image"] = _evo.build_pre_image(emp)
    if depth == "interface":
        emp["interface"] = _normalize_interface(proposal.get("payload") or {}, emp.get("interface") or {})
    else:  # role_tempo
        target = _stage(proposal.get("payload", {}).get("stage"), NEXT_STAGE[_stage(emp.get("stage"))])
        _transition(state, target, f"evolution:{proposal['id']}", "approve_evolution")
        emp = _active_employee(state)
    proposal["status"] = "applied"
    _append_event(state, _event("approve_evolution", emp["id"], f"Применена эволюция ({depth})", depth=depth))
    return {"state": state, "audit": {"op": "approve_evolution", "employee_id": emp["id"], "proposal_id": proposal["id"], "depth": depth, "applied": True, "result": "applied"}}


def _op_revert_evolution(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    proposal = _find_active_proposal(emp, payload.get("proposal_id"))
    if proposal.get("status") != "applied":
        raise GigaBuddyStateError(f"Only an applied evolution can be reverted (this one is {proposal.get('status')}).")
    pre_image = proposal.get("pre_image")
    if not isinstance(pre_image, dict):
        raise GigaBuddyStateError("This evolution has no reversible snapshot to restore.")
    try:
        _evo.apply_pre_image(emp, pre_image)
    except _evo.EvolutionError as exc:
        raise GigaBuddyStateError(str(exc)) from exc
    proposal["status"] = "reverted"
    _append_event(state, _event("revert_evolution", emp["id"], f"Откат эволюции ({proposal['depth']})", depth=proposal["depth"]))
    return {"state": state, "audit": {"op": "revert_evolution", "employee_id": emp["id"], "proposal_id": proposal["id"], "depth": proposal["depth"], "result": "reverted"}}


_OPS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "get_state": _op_get_state,
    "select_employee": _op_select_employee,
    "add_task": _op_add_task,
    "approve_stage": _op_approve_stage,
    "reject_stage": _op_reject_stage,
    "rollback": _op_rollback,
    "demo_accelerate": _op_demo_accelerate,
    "load_profile": _op_load_profile,
    "set_track": _op_set_track,
    "record_progress": _op_record_progress,
    "propose_evolution": _op_propose_evolution,
    "approve_evolution": _op_approve_evolution,
    "revert_evolution": _op_revert_evolution,
}

_ALLOWED_PAYLOAD_KEYS = {
    "get_state": frozenset(),
    "select_employee": frozenset({"employee_id"}),
    "add_task": frozenset({"title", "note"}),
    "approve_stage": frozenset({"stage", "reason"}),
    "reject_stage": frozenset({"reason", "task_title"}),
    "rollback": frozenset({"version_id"}),
    "demo_accelerate": frozenset({"stage", "reason"}),
    "load_profile": frozenset({"employee_id"}),
    "set_track": frozenset({"stages"}),
    "record_progress": frozenset({"stage_id", "status"}),
    # Evolution ops: propose carries the depth + bounded soft-layer payload
    # fields (validated by gigabuddy_evolution against the allow-listed
    # validators); approve/revert carry only a proposal id.
    "propose_evolution": frozenset({"depth", "source", "theme", "accent_color", "mascot", "tone", "layout", "stage", "label", "note"}),
    "approve_evolution": frozenset({"proposal_id"}),
    "revert_evolution": frozenset({"proposal_id"}),
}


def _sanitize_payload(op: str, payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        payload = {}
    allowed = _ALLOWED_PAYLOAD_KEYS[op]
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise GigaBuddyStateError(f"Unsupported GigaBuddy payload fields: {', '.join(unknown)}")
    for key in payload:
        if key.startswith("OUROBOROS_") or key == "GIGABUDDY_ADMIN_PIN":
            raise GigaBuddyStateError("Settings fields are not accepted by GigaBuddy actions.")
    return dict(payload)


def apply_gigabuddy_action(drive_root: pathlib.Path | str, op: str, payload: Any | None = None) -> Dict[str, Any]:
    """Apply one whitelisted action and return {ok,state,view,audit}."""
    op = str(op or "").strip()
    if op not in ALLOWED_OPS:
        raise GigaBuddyStateError("Unknown GigaBuddy action.")
    clean_payload = _sanitize_payload(op, payload or {})
    path = _state_path(drive_root)

    result_box: Dict[str, Any] = {}

    def mutate(current: Dict[str, Any]) -> Dict[str, Any]:
        state = normalize_gigabuddy_state(current)
        result = _OPS[op](state, clean_payload)
        next_state = normalize_gigabuddy_state(result["state"])
        result_box["state"] = next_state
        result_box["audit"] = dict(result.get("audit") or {"op": op, "result": "success"})
        return next_state

    if op == "get_state":
        state = load_gigabuddy_state(drive_root)
        audit = {"op": "get_state", "employee_id": state["active_employee_id"], "result": "success"}
    else:
        state = update_json_locked(path, mutate)
        state = result_box.get("state") or normalize_gigabuddy_state(state)
        audit = result_box.get("audit") or {"op": op, "employee_id": state["active_employee_id"], "result": "success"}
    return {"ok": True, "state": state, "view": build_gigabuddy_view(state), "audit": audit}


def ensure_novice_project(drive_root: pathlib.Path | str) -> Dict[str, Any]:
    """Registry bridge (NOT a reducer mutation): idempotently register the novice
    thread's project so its chat_id becomes a REGISTERED project chat id.

    Thread partitioning only. ``projects_registry`` stays the single lifecycle /
    reservation SSOT; this helper never caches or duplicates that authority. It
    calls ``create_project`` (idempotent for an ACTIVE project, raising for a
    non-active/tombstoned reserved id) and fails soft to a zero descriptor so an
    eager caller such as ``/api/state`` can never be broken by it.

    Tombstone recovery (v6.83.1): if the owner deletes the novice thread, its id
    becomes permanently reserved (``tombstoned``) — the registry NEVER resurrects
    an id, and rightly so. So the canonical id can be poisoned. Rather than
    stranding the newcomer chat on an empty descriptor forever, walk a bounded,
    DETERMINISTIC fallback suffix (``gigabuddy-novice-2``, ``-3`` …) and return
    the first id that is usable — already ACTIVE (idempotent) or free to reserve.
    The id stays stable across restarts (a given owner-delete only advances the
    suffix once), so the thread keeps a durable, partitioned chat_id.
    """
    try:
        from ouroboros import projects_registry
    except Exception as exc:  # fail-soft: never break the eager caller
        log.warning("GigaBuddy novice project unavailable (import): %s", exc)
        return {"chat_id": 0, "project_id": ""}

    for candidate in _novice_project_id_candidates():
        try:
            project = projects_registry.create_project(
                drive_root,
                candidate,
                name=NOVICE_PROJECT_NAME,
                origin="gigabuddy",
            )
        except Exception as exc:
            # This candidate is permanently reserved (tombstoned/deleting) — try
            # the next deterministic suffix. Visible, not silent.
            log.warning(
                "GigaBuddy novice project id %r unusable, trying next: %s",
                candidate,
                exc,
            )
            continue
        return {
            "chat_id": int(project.get("chat_id") or 0),
            "project_id": str(project.get("id") or ""),
        }

    # Every candidate in the bounded window is poisoned. Fail soft — the honest
    # placeholder is correct here (the owner deleted an unusual number of threads).
    log.warning(
        "GigaBuddy novice project unavailable: all %d candidate ids reserved",
        NOVICE_PROJECT_MAX_GENERATIONS,
    )
    return {"chat_id": 0, "project_id": ""}


# --- B1 role-contract / persona (product-mode novice thread only) ------------

# Where a mentor drops the newcomer's first-source documents (profile /
# questionnaire / department knowledge base). B3/C will build the retrieval skill
# over knowledge/; here the persona only names the path so it never invents facts.
def novice_knowledge_dir(employee_id: str) -> pathlib.Path:
    """Absolute path to the active employee's first-source knowledge folder.

    ``~/Ouroboros/gigabuddy/employees/<id>/knowledge/`` — the owner-facing tree a
    mentor populates before the demo. This is a location contract only; the
    retrieval skill (Karpathy-wiki, B3/C) is not built here.
    """
    home = pathlib.Path(os.path.expanduser("~"))
    slug = _slug(employee_id, "unknown")
    return home / "Ouroboros" / "gigabuddy" / "employees" / slug / "knowledge"


def _product_mode_is_gigabuddy() -> bool:
    return os.environ.get("OUROBOROS_PRODUCT_MODE", "").strip().lower() == "gigabuddy"


_TONE_GUIDANCE = {
    "formal": "деловой, уважительный тон на «вы», без фамильярности",
    "friendly": "тёплый дружелюбный тон на «ты», ободряющий и спокойный",
    "playful": "лёгкий, тёплый тон на «ты», можно с уместной живостью и эмодзи",
}

# --- #5 Adaptation methodology (form Б: embedded in the persona/core) ---------
# The explicit onboarding methodology the acquaintance follows so the chat builds
# a REAL track by rules, not improvisation. Grounded in two world practices —
# the 30-60-90-day arc and competency-based adaptation — but kept "с душой":
# personal and warm, adapted to the newcomer's profile/tone, never a dry
# template. This is prompt-as-code (P7): stated once, compactly.
_METHODOLOGY_GUIDANCE = (
    "### Методология построения адаптационного трека (следуй ей осмысленно, «с душой»)\n"
    "Строй трек по двум мировым практикам онбординга — не как сухой шаблон, а живо и "
    "персонально под этого человека (его роль, опыт, интересы и твой тон общения):\n"
    "1. **Арка 30-60-90 дней** — три фазы адаптации:\n"
    "   - Первые ~30 дней: освоиться — познакомиться с процессами, людьми, инструментами, "
    "контекстом роли; много опоры и безопасных шагов.\n"
    "   - ~60 дней: начать давать вклад под поддержкой — реальные задачи с подстраховкой, "
    "разбор ошибок без давления.\n"
    "   - ~90 дней: самостоятельность и владение — уверенная работа, ответственность за "
    "результат, вопросы уже точечные.\n"
    "2. **Адаптация по компетенциям** — от компетенций роли/отдела к целям и конкретным "
    "шагам: определи, какие 2-4 ключевые компетенции нужны на этой позиции, и наполни фазы "
    "шагами, которые их развивают.\n"
    "Синтез: 2-3 крупные фазы (по арке 30-60-90) с конкретными шагами внутри (по "
    "компетенциям роли). Глубину, темп и формулировки адаптируй под профиль и опыт "
    "новичка — опытному дай меньше опеки и больше challenge, начинающему — больше примеров "
    "и совместного разбора. НЕ выдумывай факты о компании/отделе, которых нет; шаги строй "
    "из ответов новичка и из того, что реально известно.\n"
    "Чувствительные наблюдения (уровень тревожности, автономности, стиль обучения) держи "
    "ВНУТРИ себя — используй их, чтобы подобрать формат поддержки, но НЕ проговаривай "
    "новичку как ярлыки.\n"
)


def _methodology_block(has_base_questionnaire: bool, questionnaire_hints: list[str]) -> str:
    """Compact methodology guidance for the acquaintance scenario.

    When the mentor placed a base questionnaire, lean on its real prompts as the
    starting point; otherwise follow the default 30-60-90 / competency scenario.
    Kept out of ``build_gigabuddy_persona`` so that function stays within the
    size budget (P7)."""
    if has_base_questionnaire and questionnaire_hints:
        hint_lines = "\n".join(f"  - {h}" for h in questionnaire_hints)
        base = (
            "Наставник/HR уже приложил базовый опросник в папке сотрудника — обопрись на эти "
            "вопросы как на отправную точку и дополни их своими тёплыми, человечными:\n"
            f"{hint_lines}\n\n"
        )
    elif has_base_questionnaire:
        base = (
            "Наставник/HR приложил базовый опросник в папке сотрудника — обопрись на него как "
            "на отправную точку, дополнив своими тёплыми вопросами.\n\n"
        )
    else:
        base = ""
    return base + _METHODOLOGY_GUIDANCE


def build_gigabuddy_persona(drive_root: pathlib.Path | str, query: str = "") -> str:
    """Return the product-mode ГигаБадди role-contract for the novice thread.

    A system-context section that turns the ONE Ouroboros identity into the
    mentor persona for the newcomer's thread: personalized from the persistent
    per-employee state (profile / stage / adaptation track / interface tone) with
    a HARD boundary against leaking Ouroboros internals, plus the knowledge-folder
    integration point (retrieval itself is B3/C). Read-only over the novice-safe
    view (``build_gigabuddy_view`` already excludes internal_signals / mentor
    notes / rollback history), so nothing sensitive reaches the persona. This is a
    role overlay on ONE unified awareness (BIBLE P1), NOT memory isolation.

    Returns "" on any failure so the novice thread never breaks — it simply falls
    back to ordinary behavior rather than losing the chat.
    """
    try:
        state = load_gigabuddy_state(drive_root)
        view = build_gigabuddy_view(state)
    except Exception:
        log.warning("GigaBuddy persona unavailable; skipping injection", exc_info=True)
        return ""

    profile = view.get("profile") or {}
    interface = view.get("interface") or {}
    stage = view.get("stage") or {}
    employee = view.get("employee") or {}
    track = view.get("track") or []

    raw_name = str(profile.get("name") or employee.get("name") or "").strip()
    has_name = bool(raw_name)
    name = raw_name or "новичок"
    has_track = bool(track)
    role = str(profile.get("role") or "").strip()
    department = str(profile.get("department") or "").strip()
    experience = str(profile.get("experience") or "").strip()
    interests = [str(i).strip() for i in (profile.get("interests") or []) if str(i).strip()]
    tone = str(interface.get("tone") or "friendly").strip().lower()
    tone_line = _TONE_GUIDANCE.get(tone, _TONE_GUIDANCE["friendly"])
    stage_label = str(stage.get("label") or "").strip()
    help_level = str(stage.get("helpLevel") or "").strip()
    progress_pct = view.get("progressPct")

    track_lines = []
    for item in track:
        label = str(item.get("label") or "").strip()
        title = str(item.get("title") or "").strip()
        status = str(item.get("status") or "planned").strip()
        status_ru = {"done": "пройдено", "active": "сейчас", "planned": "впереди"}.get(status, status)
        if label:
            track_lines.append(f"  - {label} ({status_ru}): {title}" if title else f"  - {label} ({status_ru})")
    track_block = "\n".join(track_lines) if track_lines else "  - (трек ещё не построен)"

    knowledge_dir = novice_knowledge_dir(employee.get("id") or "")
    # #4 Karpathy-wiki retrieval (form Б): index the department knowledge base and
    # inject a structural digest + query-scored top-N excerpts. Fail-soft: any
    # error yields "" and the persona falls back to the folder-pointer + honesty.
    knowledge_block = ""
    try:
        from ouroboros import gigabuddy_knowledge as _gk

        knowledge_block = _gk.knowledge_context_block(
            employee.get("id") or "", query or ""
        )
    except Exception:
        knowledge_block = ""
    # #5 integration point: if HR/management placed a base questionnaire in the
    # employee folder, lean on its REAL prompts during the acquaintance scenario.
    # Fail-soft: any read error yields no questionnaire grounding, not a break.
    has_base_questionnaire = False
    questionnaire_hints: list[str] = []
    try:
        from ouroboros import gigabuddy_profile as _gp

        emp_id = employee.get("id") or ""
        has_base_questionnaire = _gp.has_questionnaire(emp_id)
        if has_base_questionnaire:
            questionnaire_hints = _gp.read_questionnaire_hints(emp_id)
    except Exception:
        has_base_questionnaire = False
        questionnaire_hints = []

    if has_name:
        profile_bits = [f"Имя: {name}"]
        if role:
            profile_bits.append(f"Роль: {role}")
        if department:
            profile_bits.append(f"Отдел: {department}")
        if experience:
            profile_bits.append(f"Опыт: {experience}")
        if interests:
            profile_bits.append(f"Интересы: {', '.join(interests)}")
        profile_block = "\n".join(f"- {bit}" for bit in profile_bits)
    else:
        profile_block = (
            "- Профиль сотрудника ещё НЕ загружен наставником — имени и роли пока нет.\n"
            "- Не выдумывай имя/отдел. Знакомься по-человечески: спроси, как обращаться."
        )

    if not has_track:
        greet = (
            f"Поприветствуй {name} по имени" if has_name
            else "Тепло поздоровайся и спроси, как к сотруднику обращаться"
        )
        methodology_block = _methodology_block(has_base_questionnaire, questionnaire_hints)
        scenario_block = (
            "### Сценарий первого знакомства (трек ещё пуст — построй его)\n"
            f"Сейчас у сотрудника ещё НЕТ адаптационного трека. Твоя задача — провести короткое, "
            "живое знакомство и по его итогам построить персональный трек адаптации по методологии "
            "ниже.\n"
            f"1. {greet}, представься как ГигаБадди — персональный наставник адаптации, и предложи "
            "пройти короткое знакомство, чтобы вместе определить его трек адаптации.\n"
            "2. Задай несколько тёплых, человечных вопросов (не сухой чек-лист): что уже понятно в "
            "новой роли, а что кажется самым непонятным; какой формат помощи ему ближе (пример, "
            "чек-лист, схема, совместный разбор); что важно освоить в первую очередь; чем он "
            "увлекается (чтобы говорить на его языке).\n"
            "3. По итогам знакомства построй персональный адаптационный трек по методологии ниже: "
            "2-3 крупные фазы с понятными названиями и конкретными шагами внутри каждой (это НЕ "
            "роли Советчик→Партнёр — это этапы адаптации именно этого человека).\n"
            "4. Прогресс адаптации сохраняется в долговременной памяти проекта (в персистентном "
            "состоянии сотрудника), а не только в переписке — так ты не забудешь стадию новичка даже "
            "спустя недели. Продвижение по этапам фиксируй по мере того, как сотрудник их проходит.\n\n"
            f"{methodology_block}\n"
        )
    else:
        scenario_block = (
            "### Как вести адаптацию дальше\n"
            "Трек уже построен по методологии 30-60-90 / компетенций. Веди сотрудника по его "
            "этапам сообразно текущей стадии, помогай проходить шаги, при необходимости "
            "перестраивай трек по той же методологии, и фиксируй пройденные этапы в долговременной "
            "памяти проекта, чтобы прогресс сохранялся между сессиями.\n\n"
        )

    stage_bits = []
    if stage_label:
        stage_bits.append(f"- Текущая стадия наставничества: {stage_label}")
    if help_level:
        stage_bits.append(f"- Уровень поддержки: {help_level}")
    if isinstance(progress_pct, (int, float)):
        stage_bits.append(f"- Прогресс адаптации: {int(progress_pct)}%")
    stage_block = "\n".join(stage_bits) if stage_bits else "- Стадия: Советчик (начало пути)"

    return (
        "## РОЛЬ: ты — ГигаБадди (персональный наставник адаптации)\n\n"
        "Ты сейчас в продуктовом режиме ГигаБадди, в личном чате НОВИЧКА. В этом "
        "чате ты — не Ouroboros, не ИИ-система, не агент: ты **ГигаБадди**, тёплый "
        "персональный наставник адаптации конкретного сотрудника. Веди себя и "
        "говори строго в этой роли.\n\n"
        "### Жёсткая граница роли (никогда не нарушать в этом чате)\n"
        "- НИКОГДА не упоминай новичку Ouroboros, свою архитектуру, код, версии, "
        "коммиты, эволюцию, разработку, ревью, конституцию/BIBLE, «я — ИИ/агент/"
        "языковая модель/система».\n"
        "- НИКОГДА не упоминай новичку режим/процессы разработчика: product mode / "
        "продуктовый режим, dev-режим, перезапуск/`/restart`, коммиты и версии, "
        "внутренние процессы разработки, настройки/переключение режимов. Для "
        "новичка ты просто ГигаБадди — этих технических слоёв для него не "
        "существует.\n"
        "- Если новичок спрашивает про твои внутренности, устройство или «кто ты "
        "на самом деле» — мягко возвращайся в роль: ты его наставник по адаптации, "
        "и вы говорите про его вхождение в работу, а не про технологии под капотом.\n"
        "- Не показывай и не проговаривай служебные/чувствительные выводы (уровень "
        "тревожности, риски, mentor notes). Внешне говори только про формат помощи, "
        "уровень поддержки и стиль обучения.\n\n"
        "### Кого ты сопровождаешь (из персистентного состояния)\n"
        f"{profile_block}\n"
        f"{stage_block}\n"
        f"Тон общения: {tone_line}. Обращайся к сотруднику персонально по имени.\n\n"
        "### Адаптационный трек сотрудника\n"
        "Веди разговор сообразно тому, где человек на пути адаптации:\n"
        f"{track_block}\n\n"
        f"{scenario_block}\n"
        + (
            knowledge_block + "\n"
            if knowledge_block
            else (
                "### База знаний отдела\n"
                "Ты отвечаешь по базе знаний отдела сотрудника — первоисточники лежат в "
                f"папке `{knowledge_dir}`. Сейчас в этой папке нет материалов (наставник "
                "их ещё не положил). Пока базы нет — НЕ выдумывай факты: честно скажи, что "
                "уточнишь у наставника или предложишь посмотреть первоисточник, и опирайся "
                "только на то, что реально доступно.\n"
            )
        )
    )


def gigabuddy_persona_section(task: Dict[str, Any], drive_root: pathlib.Path | str) -> str:
    """Persona section for a task, or "" unless it is the product-mode novice thread.

    Gated on BOTH: product mode == gigabuddy AND the task's resolved project id ==
    NOVICE_PROJECT_ID. Off in ordinary Ouroboros (product off) and in the
    developer's own chat/threads — those get no persona and unchanged behavior.
    Fail-soft: any error yields "".
    """
    try:
        if not _product_mode_is_gigabuddy():
            return ""
        from ouroboros.project_facts import resolve_project_id

        # Symmetric with the mentor gate (matches gigabuddy-novice-2 … recovery ids).
        if not is_novice_project_id(resolve_project_id(task)):
            return ""
        return build_gigabuddy_persona(drive_root, query=_task_query_text(task))
    except Exception:
        log.debug("GigaBuddy persona section skipped on error", exc_info=True)
        return ""


def _task_query_text(task: Dict[str, Any]) -> str:
    """Best-effort newcomer question text from the per-turn task, for #4 retrieval.

    A DIRECT chat turn (the novice typing in the chat) carries the live message in
    ``task['text']`` (see context.build_user_content); a queued/headless task
    carries it in ``objective``. We try both plus common fallbacks, so query-scored
    excerpts fire for the live novice question regardless of turn shape. Used only
    to score the knowledge base; a missing/empty value just yields a structural
    digest without query-scored excerpts. Never raises."""
    try:
        for key in ("objective", "message", "text", "prompt"):
            val = task.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()[:1000]
    except Exception:
        pass
    return ""
