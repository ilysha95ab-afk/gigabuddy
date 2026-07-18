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


def test_gigabuddy_view_exposes_profile_interface_and_track(tmp_path):
    result = apply_gigabuddy_action(tmp_path, "get_state", {})
    view = result["view"]
    # Structured employee profile.
    assert view["profile"]["name"] == "Алиса"
    assert view["profile"]["department"] == "Люди и культура"
    assert "котики" in view["profile"]["interests"]
    # Interface personalization attributes (safe presentation, not diagnostics).
    iface = view["interface"]
    assert iface["theme"] == "soft-cat"
    assert iface["accentColor"] == "#e8799f"
    assert iface["tone"] == "playful"
    assert iface["mascot"] == "🐾"
    assert "hero" in iface["layout"]
    # Adaptation track keyed to the current stage.
    stages = {item["id"]: item["status"] for item in view["track"]}
    assert stages == {"advisor": "active", "assistant": "planned", "partner": "planned"}


def test_gigabuddy_invalid_interface_falls_back_to_design_system(tmp_path):
    state = default_gigabuddy_state()
    state["employees"]["alice-demo"]["interface"] = {
        "theme": "rainbow-explosion",
        "accent_color": "red; background:url(evil)",
        "tone": "aggressive",
        "mascot": "x" * 40,
        "layout": ["hero", "unknown_section", "hero"],
    }
    view = build_gigabuddy_view(state)
    iface = view["interface"]
    assert iface["theme"] == "neutral"
    assert iface["accentColor"] == "#c93545"
    assert iface["tone"] == "friendly"
    assert len(iface["mascot"]) <= 8
    # Unknown section dropped; every known section still present.
    assert "unknown_section" not in iface["layout"]
    assert "questionnaire" in iface["layout"]


def test_gigabuddy_track_progress_advances_with_stage(tmp_path):
    start = apply_gigabuddy_action(tmp_path, "get_state", {})
    # advisor active (0.5), others planned => 0.5/3 ~= 17%
    assert start["view"]["progressPct"] == 17
    advanced = apply_gigabuddy_action(tmp_path, "approve_stage", {"stage": "assistant", "reason": "готова"})
    # advisor done (1) + assistant active (0.5) => 1.5/3 = 50%
    assert advanced["view"]["progressPct"] == 50
    assert advanced["view"]["profile"]["name"] == "Алиса"


def test_gigabuddy_view_still_hides_diagnostics_with_new_fields(tmp_path):
    state = default_gigabuddy_state()
    state["employees"]["alice-demo"]["internal_signals"] = {"confidence_risk": "high anxiety marker"}
    state["employees"]["alice-demo"]["mentor_notes"] = ["private mentor note"]
    state["employees"]["alice-demo"]["rollback_history"] = [{"version_id": "v1", "reason": "secret rollback reason"}]
    view = build_gigabuddy_view(state)
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "mentorNotes" not in dumped
    assert "rollback_history" not in dumped
    assert "private mentor note" not in dumped
    assert "anxiety" not in dumped


def test_gigabuddy_rollback_records_history_internally(tmp_path):
    apply_gigabuddy_action(tmp_path, "approve_stage", {"stage": "assistant", "reason": "ok"})
    apply_gigabuddy_action(tmp_path, "rollback", {"version_id": "v1"})
    state = load_gigabuddy_state(tmp_path)
    history = state["employees"]["alice-demo"]["rollback_history"]
    assert len(history) >= 1
    assert history[-1]["version_id"] == "v1"
    assert len(history) <= 16


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
