"""Mutable GigaBuddy product-mode state.

This is the small domain reducer behind the GigaBuddy demo shell.  The gateway
transports actions; this module owns state shape, validation, bounded history,
and the novice-safe view projection.
"""

from __future__ import annotations

import copy
import pathlib
import time
from typing import Any, Callable, Dict

from ouroboros.utils import read_json_dict, update_json_locked, utc_now_iso

SCHEMA_VERSION = 1
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
MAX_TEXT_CHARS = 320
MAX_NOTE_CHARS = 600
MAX_SUMMARY_CHARS = 900
ALLOWED_OPS = frozenset({
    "get_state",
    "select_employee",
    "add_task",
    "approve_stage",
    "reject_stage",
    "rollback",
    "demo_accelerate",
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
        "mentor_notes": [],
        "behavior_versions": [behavior],
        "active_behavior_version_id": behavior["id"],
        "internal_signals": {
            "support_need": "internal_only",
            "confidence_risk": "hidden_from_novice",
        },
    }


def default_gigabuddy_state() -> Dict[str, Any]:
    """Return a fresh synthetic demo state with no real candidate data."""
    return {
        "schema_version": SCHEMA_VERSION,
        "active_employee_id": "alice-demo",
        "questionnaire_packages": {
            "people-culture-base": {
                "id": "people-culture-base",
                "title": "Люди и культура · базовый опросник",
                "domain": "HR / Люди и культура",
                "knowledge_base_hint": "Подгружается вместе с доменным пакетом БЗ в следующем инкременте",
                "diagnostic_policy": "ГигаБадди выводит уровень поддержки, автономности и стиль обучения сам; новичок не выбирает чувствительные ярлыки.",
                "questions": [
                    "Расскажи, какая часть новой роли сейчас кажется самой непонятной.",
                    "Представь запрос от внутреннего заказчика: с чего начнёшь безопасно?",
                    "Что поможет тебе быстрее войти в процесс: пример, чек-лист, схема или совместный разбор?",
                ],
            },
            "dev-transfer-base": {
                "id": "dev-transfer-base",
                "title": "Внутренний переход · базовый опросник",
                "domain": "Engineering / internal transfer",
                "knowledge_base_hint": "Будет связан с БЗ команды разработки",
                "diagnostic_policy": "Диагностика строится по ответам и выполненным задачам, без публичных психологических ярлыков.",
                "questions": [
                    "Какие системы и ограничения новой команды уже понятны?",
                    "Как бы ты проверил изменение перед выкладкой?",
                    "Где тебе полезнее challenge-mode, а где короткая подсказка?",
                ],
            },
        },
        "employees": {
            "alice-demo": _default_employee(
                "alice-demo",
                "Алиса",
                "HR · Люди и культура",
                avatar="🐾",
                theme="soft-cat",
                stage="advisor",
                progress=35,
                questionnaire_package_id="people-culture-base",
                tasks=[
                    _task("alice-1", "Познакомиться с процессом согласования вакансий", status="active"),
                    _task("alice-2", "Подготовить черновик ответа заказчику"),
                    _task("alice-3", "Найти нужный HR-регламент в базе знаний"),
                ],
            ),
            "leonid-demo": _default_employee(
                "leonid-demo",
                "Леонид",
                "Разработчик · внутренний переход",
                avatar="⌘",
                theme="strict-terminal",
                stage="assistant",
                progress=52,
                questionnaire_package_id="dev-transfer-base",
                tasks=[
                    _task("leo-1", "Собрать карту сервисов новой команды", status="active"),
                    _task("leo-2", "Проверить процесс code review и релиза"),
                ],
            ),
            "blank-demo": _default_employee(
                "blank-demo",
                "Новый сотрудник",
                "Новый контекст",
                avatar="✨",
                theme="neutral",
                stage="advisor",
                progress=0,
                questionnaire_package_id="people-culture-base",
                tasks=[_task("blank-1", "Провести первичное диагностическое интервью", status="active")],
            ),
        },
        "events": [],
        "updated_at": utc_now_iso(),
    }


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
            "theme": emp.get("theme", "neutral"),
        },
        "stage": {
            "id": stage_id,
            "label": STAGE_LABELS[stage_id],
            "next": STAGE_LABELS[next_id],
            "helpLevel": _stage_help(stage_id),
        },
        "progressPct": emp.get("progress_pct", 0),
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
    }


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
    _append_event(state, _event("rollback", emp["id"], "Откат поведения без потери прогресса", stage_from=old_stage, stage_to=emp["stage"]))
    return {"state": state, "audit": {"op": "rollback", "employee_id": emp["id"], "stage_from": old_stage, "stage_to": emp["stage"], "result": "success"}}


def _op_demo_accelerate(state: Dict[str, Any], payload: Dict[str, Any]) -> Dict[str, Any]:
    emp = _active_employee(state)
    current = _stage(emp.get("stage"))
    target = _stage(payload.get("stage"), NEXT_STAGE[current])
    emp["progress_pct"] = max(int(emp.get("progress_pct", 0) or 0), 72 if target != "partner" else 90)
    return _transition(state, target, _clip(payload.get("reason"), MAX_NOTE_CHARS) or "Быстрый виток демо", "demo_accelerate")


_OPS: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]]] = {
    "get_state": _op_get_state,
    "select_employee": _op_select_employee,
    "add_task": _op_add_task,
    "approve_stage": _op_approve_stage,
    "reject_stage": _op_reject_stage,
    "rollback": _op_rollback,
    "demo_accelerate": _op_demo_accelerate,
}

_ALLOWED_PAYLOAD_KEYS = {
    "get_state": frozenset(),
    "select_employee": frozenset({"employee_id"}),
    "add_task": frozenset({"title", "note"}),
    "approve_stage": frozenset({"stage", "reason"}),
    "reject_stage": frozenset({"reason", "task_title"}),
    "rollback": frozenset({"version_id"}),
    "demo_accelerate": frozenset({"stage", "reason"}),
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
