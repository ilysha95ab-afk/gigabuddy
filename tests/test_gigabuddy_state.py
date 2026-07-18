import json

import pytest

from ouroboros.gigabuddy_state import (
    GigaBuddyStateError,
    STATE_RELATIVE_PATH,
    apply_gigabuddy_action,
    build_gigabuddy_view,
    default_gigabuddy_state,
    load_gigabuddy_state,
)


def test_gigabuddy_state_first_write_creates_parent_and_returns_view(tmp_path):
    result = apply_gigabuddy_action(tmp_path, "add_task", {"title": "Сделать пробную задачу"})
    assert result["ok"] is True
    assert (tmp_path / STATE_RELATIVE_PATH).is_file()
    assert result["view"]["employee"]["name"] == "Алиса"
    assert any(task["title"] == "Сделать пробную задачу" for task in result["view"]["tasks"])


def test_gigabuddy_employee_switch_preserves_per_employee_state(tmp_path):
    apply_gigabuddy_action(tmp_path, "add_task", {"title": "Алисина задача"})
    switched = apply_gigabuddy_action(tmp_path, "select_employee", {"employee_id": "leonid-demo"})
    assert switched["view"]["employee"]["name"] == "Леонид"
    assert all(task["title"] != "Алисина задача" for task in switched["view"]["tasks"])
    back = apply_gigabuddy_action(tmp_path, "select_employee", {"employee_id": "alice-demo"})
    assert any(task["title"] == "Алисина задача" for task in back["view"]["tasks"])


def test_gigabuddy_actions_stage_rollback_and_events_are_bounded(tmp_path):
    approved = apply_gigabuddy_action(tmp_path, "approve_stage", {"stage": "assistant", "reason": "готова"})
    assert approved["view"]["stage"]["id"] == "assistant"
    fast = apply_gigabuddy_action(tmp_path, "demo_accelerate", {"stage": "partner", "reason": "Быстрый виток"})
    assert fast["view"]["stage"]["id"] == "partner"
    rolled = apply_gigabuddy_action(tmp_path, "rollback", {"version_id": "v1"})
    assert rolled["view"]["stage"]["id"] == "advisor"
    for i in range(100):
        apply_gigabuddy_action(tmp_path, "reject_stage", {"reason": f"reason {i}", "task_title": f"task {i}"})
    state = load_gigabuddy_state(tmp_path)
    assert len(state["events"]) <= 80
    assert len(state["employees"]["alice-demo"]["tasks"]) <= 24
    assert len(state["employees"]["alice-demo"]["mentor_notes"]) <= 12


def test_gigabuddy_view_hides_internal_diagnostics_and_mentor_private_text(tmp_path):
    state = default_gigabuddy_state()
    state["employees"]["alice-demo"]["internal_signals"] = {"confidence_risk": "high anxiety marker"}
    state["employees"]["alice-demo"]["mentor_notes"] = ["private mentor note"]
    state["events"] = [{"op": "demo_accelerate", "employee_id": "alice-demo", "detail": "Быстрый виток демо"}]
    view = build_gigabuddy_view(state)
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "mentorNotes" not in dumped
    assert "private mentor note" not in dumped
    assert "Быстрый виток" not in dumped
    assert "anxiety" not in dumped
    assert "тревож" not in dumped.lower()


def test_gigabuddy_rejects_unknown_ops_and_payload_fields(tmp_path):
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "unknown", {})
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "add_task", {"title": "ok", "OUROBOROS_PRODUCT_MODE": ""})


def test_gigabuddy_malformed_state_normalizes_to_defaults(tmp_path):
    path = tmp_path / STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json", encoding="utf-8")
    state = load_gigabuddy_state(tmp_path)
    assert state["schema_version"] == 1
    assert state["active_employee_id"] == "alice-demo"
