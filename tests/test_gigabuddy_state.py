import json

import pytest

from ouroboros import projects_registry
from ouroboros.gigabuddy_state import (
    BLANK_EMPLOYEE_ID,
    GigaBuddyStateError,
    NOVICE_PROJECT_ID,
    STATE_RELATIVE_PATH,
    apply_gigabuddy_action,
    build_gigabuddy_view,
    default_gigabuddy_state,
    ensure_novice_project,
    list_demo_profiles,
    load_gigabuddy_state,
)


@pytest.fixture(autouse=True)
def _isolate_employees_root(tmp_path, monkeypatch):
    """Confine employee-folder profile reads to a per-test tmp dir so no test
    touches the real ~/Ouroboros/gigabuddy tree."""
    monkeypatch.setenv("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(tmp_path / "employees"))


def _load_alice(tmp_path):
    """Alice is now a LOADABLE demo profile, not the hardcoded default. Tests that
    need the populated Alice fixture load it explicitly (mirrors the owner's
    hand-swap for a demo)."""
    return apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})


def test_gigabuddy_state_first_write_creates_parent_and_returns_view(tmp_path):
    result = apply_gigabuddy_action(tmp_path, "add_task", {"title": "Сделать пробную задачу"})
    assert result["ok"] is True
    assert (tmp_path / STATE_RELATIVE_PATH).is_file()
    # B3: a fresh install is the neutral, nameless novice — NOT synthetic Alice.
    assert result["view"]["employee"]["id"] == BLANK_EMPLOYEE_ID
    assert result["view"]["employee"]["name"] == ""
    assert result["view"]["profile"]["name"] == ""
    assert any(task["title"] == "Сделать пробную задачу" for task in result["view"]["tasks"])


def test_gigabuddy_employee_switch_preserves_per_employee_state(tmp_path):
    # load_profile is the demo-switch mechanism (owner hand-swaps configs). Each
    # loaded employee keeps its own per-employee state.
    _load_alice(tmp_path)
    apply_gigabuddy_action(tmp_path, "add_task", {"title": "Алисина задача"})
    loaded = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "leonid-demo"})
    assert loaded["view"]["employee"]["name"] == "Леонид"
    assert all(task["title"] != "Алисина задача" for task in loaded["view"]["tasks"])
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
    assert len(state["employees"][BLANK_EMPLOYEE_ID]["tasks"]) <= 24
    assert len(state["employees"][BLANK_EMPLOYEE_ID]["mentor_notes"]) <= 12


def test_gigabuddy_view_hides_internal_diagnostics_and_mentor_private_text(tmp_path):
    state = default_gigabuddy_state()
    state["employees"][BLANK_EMPLOYEE_ID]["internal_signals"] = {"confidence_risk": "high anxiety marker"}
    state["employees"][BLANK_EMPLOYEE_ID]["mentor_notes"] = ["private mentor note"]
    state["events"] = [{"op": "demo_accelerate", "employee_id": BLANK_EMPLOYEE_ID, "detail": "Быстрый виток демо"}]
    view = build_gigabuddy_view(state)
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "mentorNotes" not in dumped
    assert "private mentor note" not in dumped
    assert "Быстрый виток" not in dumped
    assert "anxiety" not in dumped
    assert "тревож" not in dumped.lower()


def test_gigabuddy_view_exposes_profile_interface_and_track(tmp_path):
    # Alice's populated profile/interface/track is a LOADABLE demo now.
    result = _load_alice(tmp_path)
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
    # Build the personal track (as the chat questionnaire would) and confirm the
    # durable write renders exactly those stages/steps.
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"label": "Знакомство", "title": "Первая неделя", "steps": ["Познакомиться с командой"]},
        {"label": "Погружение", "title": "Первый месяц"},
    ]})
    built = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]["track"]
    assert len(built) == 2
    assert built[0]["status"] == "active"
    assert built[0]["steps"] == ["Познакомиться с командой"]
    for item in built:
        assert isinstance(item["steps"], list)


def test_gigabuddy_view_track_projects_bounded_steps(tmp_path):
    # B2: when a stage carries onboarding steps, the view projects them (bounded,
    # view-pure). This is the LEFT adaptation-track detail the newcomer expands.
    state = default_gigabuddy_state()
    steps = [f"Шаг {i}" for i in range(30)]  # exceeds MAX_TRACK_STEPS on purpose
    state["employees"][BLANK_EMPLOYEE_ID]["track"] = [
        {"id": "advisor", "label": "Знакомство", "title": "Старт", "status": "active", "steps": steps},
    ]
    view = build_gigabuddy_view(state)
    projected = view["track"][0]["steps"]
    assert projected[:3] == ["Шаг 0", "Шаг 1", "Шаг 2"]
    assert 0 < len(projected) <= 12  # MAX_TRACK_STEPS
    # Steps stay out of any sensitive projection; view is still novice-safe.
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "mentorNotes" not in dumped


def test_gigabuddy_invalid_interface_falls_back_to_design_system(tmp_path):
    state = default_gigabuddy_state()
    state["employees"][BLANK_EMPLOYEE_ID]["interface"] = {
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
    # B3: the neutral novice starts with an EMPTY track → 0% progress (no
    # fabricated stages). Load Alice (a demo) then build a track to exercise
    # progress advancement.
    start = apply_gigabuddy_action(tmp_path, "get_state", {})
    assert start["view"]["progressPct"] == 0
    assert start["view"]["track"] == []
    _load_alice(tmp_path)
    advanced = apply_gigabuddy_action(tmp_path, "approve_stage", {"stage": "assistant", "reason": "готова"})
    # approve_stage seeds+syncs a track: advisor done (1) + assistant active (0.5)
    # + partner planned => 1.5/3 = 50%
    assert advanced["view"]["progressPct"] == 50
    assert advanced["view"]["profile"]["name"] == "Алиса"


def test_gigabuddy_view_still_hides_diagnostics_with_new_fields(tmp_path):
    state = default_gigabuddy_state()
    state["employees"][BLANK_EMPLOYEE_ID]["internal_signals"] = {"confidence_risk": "high anxiety marker"}
    state["employees"][BLANK_EMPLOYEE_ID]["mentor_notes"] = ["private mentor note"]
    state["employees"][BLANK_EMPLOYEE_ID]["rollback_history"] = [{"version_id": "v1", "reason": "secret rollback reason"}]
    # A stored evolution proposal must NEVER reach the novice-safe view. The
    # view is an allow-list by omission today; the sentinel pins that so a
    # future spread refactor cannot silently leak proposals to the novice.
    state["employees"][BLANK_EMPLOYEE_ID]["evolution_proposals"] = [
        {"id": "evo-x", "depth": "interface", "payload": {"theme": "soft-cat"},
         "status": "applied", "pre_image": {"stage": "advisor"},
         "git_tag_hint": "GIGA_EVO_SENTINEL_TAG"}
    ]
    view = build_gigabuddy_view(state)
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "mentorNotes" not in dumped
    assert "rollback_history" not in dumped
    assert "private mentor note" not in dumped
    assert "anxiety" not in dumped
    assert "evolution_proposals" not in dumped
    assert "GIGA_EVO_SENTINEL_TAG" not in dumped
    assert "pre_image" not in dumped


def test_gigabuddy_rollback_records_history_internally(tmp_path):
    apply_gigabuddy_action(tmp_path, "approve_stage", {"stage": "assistant", "reason": "ok"})
    apply_gigabuddy_action(tmp_path, "rollback", {"version_id": "v1"})
    state = load_gigabuddy_state(tmp_path)
    history = state["employees"][BLANK_EMPLOYEE_ID]["rollback_history"]
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
    # B3: malformed state normalizes to the NEUTRAL novice default, not Alice.
    assert state["active_employee_id"] == BLANK_EMPLOYEE_ID


# --- B1: novice-thread partitioning via a registered project (v6.76.0) --------

def test_ensure_novice_project_registers_and_is_reserved(tmp_path):
    desc = ensure_novice_project(tmp_path)
    assert desc["project_id"] == NOVICE_PROJECT_ID
    assert desc["chat_id"] > 1
    # The chat_id must be a REGISTERED project chat id WITHOUT any prior get_state:
    # that registration is exactly what makes the novice thread partition in the
    # UI/history layer (reserved_project_chat_ids is the routing SSOT).
    assert desc["chat_id"] in projects_registry.reserved_project_chat_ids(tmp_path)


def test_ensure_novice_project_is_idempotent(tmp_path):
    first = ensure_novice_project(tmp_path)
    second = ensure_novice_project(tmp_path)
    assert first == second
    entries = [p for p in projects_registry.list_reserved_projects(tmp_path)
               if p.get("id") == NOVICE_PROJECT_ID]
    assert len(entries) == 1


def test_ensure_novice_project_fail_soft_on_non_active_reservation(tmp_path):
    # A tombstoned/deleting reservation makes create_project raise; the helper
    # must fail soft to a zero descriptor rather than surface a stale live id.
    projects_registry.create_project(tmp_path, NOVICE_PROJECT_ID, name="Новичок")
    projects_registry.begin_project_deletion(tmp_path, NOVICE_PROJECT_ID)
    desc = ensure_novice_project(tmp_path)
    assert desc == {"chat_id": 0, "project_id": ""}


def test_ensure_novice_project_is_not_a_reducer_mutation(tmp_path):
    # Calling the registry bridge must not create GigaBuddy reducer state.
    ensure_novice_project(tmp_path)
    assert not (tmp_path / STATE_RELATIVE_PATH).exists()


# --- B3: neutral start, profile-file parsing, chat-questionnaire track ---------

def test_b3_default_state_is_neutral_and_nameless(tmp_path):
    # A fresh install must NOT be synthetic Alice: no name, no department, empty
    # track, neutral theme. This is the "never fabricate a candidate" discipline.
    view = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert view["employee"]["id"] == BLANK_EMPLOYEE_ID
    assert view["profile"]["name"] == ""
    assert view["profile"].get("department", "") == ""
    assert view["track"] == []
    assert view["interface"]["theme"] == "neutral"
    assert view["progressPct"] == 0


def test_b3_demo_profiles_are_loadable_not_default(tmp_path):
    ids = {p["id"] for p in list_demo_profiles()}
    assert {"alice-demo", "leonid-demo"} <= ids
    # They are NOT the default; loading one is an explicit action.
    loaded = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "leonid-demo"})
    assert loaded["view"]["profile"]["name"] == "Леонид"
    assert loaded["audit"]["loaded"] is True
    assert loaded["audit"]["source"] == "demo"


def test_b3_load_profile_from_valid_file(tmp_path):
    from ouroboros import gigabuddy_profile

    emp_dir = gigabuddy_profile.employee_dir("nova-001") / "profile"
    emp_dir.mkdir(parents=True, exist_ok=True)
    (emp_dir / "profile.json").write_text(json.dumps({
        "name": "Нова",
        "role": "Аналитик",
        "department": "Данные",
        "experience": "Junior, любит SQL",
        "interests": ["графики", "музыка"],
        "interface": {"tone": "friendly", "accent_color": "#5ad1c9"},
    }, ensure_ascii=False), encoding="utf-8")
    result = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "nova-001"})
    view = result["view"]
    assert result["audit"]["source"] == "file"
    assert view["profile"]["name"] == "Нова"
    assert view["profile"]["department"] == "Данные"
    assert "графики" in view["profile"]["interests"]
    assert view["interface"]["tone"] == "friendly"
    # A freshly loaded profile still has an empty track (questionnaire fills it).
    assert view["track"] == []


def test_b3_load_profile_from_markdown_frontmatter(tmp_path):
    from ouroboros import gigabuddy_profile

    emp_dir = gigabuddy_profile.employee_dir("md-emp") / "profile"
    emp_dir.mkdir(parents=True, exist_ok=True)
    (emp_dir / "profile.md").write_text(
        "---\nname: Марк\nrole: Дизайнер\ndepartment: Продукт\ninterests: типографика, цвет\n---\n"
        "Пришёл из смежной команды, быстро учится.",
        encoding="utf-8",
    )
    view = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "md-emp"})["view"]
    assert view["profile"]["name"] == "Марк"
    assert view["profile"]["role"] == "Дизайнер"
    assert "типографика" in view["profile"]["interests"]
    assert "смежной команды" in view["profile"]["experience"]


def test_b3_load_profile_missing_or_broken_stays_neutral(tmp_path):
    from ouroboros import gigabuddy_profile

    # Missing folder → fail-soft, stays nameless.
    missing = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "ghost"})
    assert missing["audit"]["loaded"] is False
    assert missing["view"]["profile"]["name"] == ""
    # Broken JSON → fail-soft, no fabrication.
    emp_dir = gigabuddy_profile.employee_dir("broken") / "profile"
    emp_dir.mkdir(parents=True, exist_ok=True)
    (emp_dir / "profile.json").write_text("{ not valid json", encoding="utf-8")
    broken = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "broken"})
    assert broken["audit"]["loaded"] is False
    assert broken["view"]["profile"]["name"] == ""


def test_b3_chat_questionnaire_fills_track_and_persists(tmp_path):
    # The chat questionnaire's outcome is a durable set_track write; the left
    # track (B2) renders exactly this.
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"label": "Первые дни", "title": "Знакомство с командой", "steps": ["Встреча 1:1", "Доступы"]},
        {"label": "Первый месяц", "title": "Первая реальная задача", "steps": ["Взять тикет"]},
        {"label": "Автономность", "title": "Самостоятельная работа"},
    ]})
    # Durable: a fresh load from disk still carries the track.
    reloaded = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert len(reloaded["track"]) == 3
    assert reloaded["track"][0]["status"] == "active"
    assert reloaded["track"][0]["steps"][:2] == ["Встреча 1:1", "Доступы"]


def test_b3_record_progress_is_durable(tmp_path):
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"id": "advisor", "label": "Старт", "title": "A"},
        {"id": "assistant", "label": "Рост", "title": "B"},
    ]})
    apply_gigabuddy_action(tmp_path, "record_progress", {"stage_id": "advisor", "status": "done"})
    # Persisted to disk, not only in dialogue.
    state = load_gigabuddy_state(tmp_path)
    emp = state["employees"][state["active_employee_id"]]
    statuses = {i["id"]: i["status"] for i in emp["track"]}
    assert statuses["advisor"] == "done"
    assert emp["progress_pct"] > 0


def test_b3_set_track_rejects_empty(tmp_path):
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "set_track", {"stages": []})


def test_b3_profile_file_access_is_confined(tmp_path):
    # A traversal-style id must never escape the employees root.
    from ouroboros import gigabuddy_profile

    assert gigabuddy_profile.load_employee_profile("../../etc") is None


# --- Reversible self-evolution (v6.83.0) -----------------------------------


def _propose_evo(tmp_path, **payload):
    r = apply_gigabuddy_action(tmp_path, "propose_evolution", payload)
    return r["audit"]["proposal_id"], r


def _evo_emp(state):
    return state["employees"][state["active_employee_id"]]


def test_evolution_propose_applies_nothing(tmp_path):
    _load_alice(tmp_path)
    before = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]["interface"]["theme"]
    target = "ocean-calm" if before != "ocean-calm" else "warm-sunrise"
    pid, r = _propose_evo(tmp_path, depth="interface", theme=target, source="novice_request")
    emp = _evo_emp(r["state"])
    assert emp["interface"]["theme"] == before  # unchanged
    assert emp["evolution_proposals"][-1]["status"] == "proposed"
    assert emp["evolution_proposals"][-1]["id"] == pid


def test_evolution_approve_interface_applies_only_validated_fields(tmp_path):
    _load_alice(tmp_path)
    base = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]["interface"]
    target = "ocean-calm" if base["theme"] != "ocean-calm" else "warm-sunrise"
    pid, _ = _propose_evo(tmp_path, depth="interface", theme=target, mascot="🐬", tone="playful")
    r = apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    emp = _evo_emp(r["state"])
    assert emp["interface"]["theme"] == target
    assert emp["interface"]["mascot"] == "🐬"
    assert emp["interface"]["tone"] == "playful"
    prop = emp["evolution_proposals"][-1]
    assert prop["status"] == "applied"
    assert "pre_image" in prop
    assert prop["git_tag_hint"].startswith("giga-evo-")


def test_evolution_approve_interface_rejects_arbitrary_accent(tmp_path):
    # A bad accent falls back to the design-system default; a proposal can never
    # inject arbitrary CSS.
    _load_alice(tmp_path)
    pid, _ = _propose_evo(tmp_path, depth="interface", accent_color="url(evil)")
    r = apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    emp = _evo_emp(r["state"])
    from ouroboros.gigabuddy_state import DEFAULT_ACCENT, _HEX_ACCENT_RE
    assert _HEX_ACCENT_RE.fullmatch(emp["interface"]["accent_color"])
    assert emp["interface"]["accent_color"] == DEFAULT_ACCENT


def test_evolution_revert_interface_restores_all_fields(tmp_path):
    _load_alice(tmp_path)
    base = dict(apply_gigabuddy_action(tmp_path, "get_state", {})["view"]["interface"])
    target = "ocean-calm" if base["theme"] != "ocean-calm" else "warm-sunrise"
    pid, _ = _propose_evo(tmp_path, depth="interface", theme=target, mascot="🐬", tone="playful")
    apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    r = apply_gigabuddy_action(tmp_path, "revert_evolution", {"proposal_id": pid})
    iface = _evo_emp(r["state"])["interface"]
    assert iface["theme"] == base["theme"]
    assert iface["mascot"] == base["mascot"]
    assert iface["tone"] == base["tone"]
    assert iface["layout"] == base["layout"]
    # base is the VIEW projection (accentColor); state uses accent_color.
    assert iface["accent_color"] == base["accentColor"]
    assert _evo_emp(r["state"])["evolution_proposals"][-1]["status"] == "reverted"


def test_evolution_role_tempo_approve_and_revert_restore_effective_state(tmp_path):
    _load_alice(tmp_path)
    pre = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    pre_stage = pre["stage"]["id"]
    pre_pct = pre["progressPct"]
    pre_ver = _evo_emp(load_gigabuddy_state(tmp_path))["active_behavior_version_id"]
    pid, _ = _propose_evo(tmp_path, depth="role_tempo")
    r = apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    adv = build_gigabuddy_view(r["state"])
    assert adv["stage"]["id"] != pre_stage  # advanced
    # Revert restores stage AND behavior version AND derived progress — NOT v1.
    r = apply_gigabuddy_action(tmp_path, "revert_evolution", {"proposal_id": pid})
    emp = _evo_emp(r["state"])
    assert emp["stage"] == pre_stage
    assert emp["active_behavior_version_id"] == pre_ver
    assert build_gigabuddy_view(r["state"])["progressPct"] == pre_pct


def test_evolution_ui_is_proposal_only(tmp_path):
    _load_alice(tmp_path)
    pid, r = _propose_evo(tmp_path, depth="ui", label="иконка котиков")
    before = json.dumps(build_gigabuddy_view(r["state"]), ensure_ascii=False)
    r = apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    prop = _evo_emp(r["state"])["evolution_proposals"][-1]
    assert prop["status"] == "approved"
    assert "pre_image" not in prop
    assert r["audit"]["applied"] is False
    assert prop["git_tag_hint"].startswith("giga-evo-")
    assert json.dumps(build_gigabuddy_view(r["state"]), ensure_ascii=False) == before
    # A ui proposal is never "applied", so it cannot be reverted.
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "revert_evolution", {"proposal_id": pid})


def test_evolution_unknown_depth_rejected(tmp_path):
    _load_alice(tmp_path)
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "propose_evolution", {"depth": "core"})


def test_evolution_double_approve_and_revert_before_apply_raise(tmp_path):
    _load_alice(tmp_path)
    pid, _ = _propose_evo(tmp_path, depth="interface", theme="ocean-calm")
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "revert_evolution", {"proposal_id": pid})
    apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})


def test_evolution_proposals_are_active_employee_scoped(tmp_path):
    _load_alice(tmp_path)
    pid, _ = _propose_evo(tmp_path, depth="interface", theme="ocean-calm")
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "leonid-demo"})
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})


def test_evolution_proposals_survive_normalize_round_trip(tmp_path):
    _load_alice(tmp_path)
    pid, _ = _propose_evo(tmp_path, depth="interface", theme="ocean-calm")
    apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    reloaded = load_gigabuddy_state(tmp_path)
    props = _evo_emp(reloaded)["evolution_proposals"]
    assert any(p["id"] == pid and p["status"] == "applied" for p in props)
    assert len(props) <= 24


def test_evolution_ops_round_trip_through_apply_without_raising(tmp_path):
    # Each new op must be present in ALL THREE registries (ALLOWED_OPS, _OPS,
    # _ALLOWED_PAYLOAD_KEYS) — a missing entry hard-raises.
    _load_alice(tmp_path)
    r = apply_gigabuddy_action(tmp_path, "propose_evolution", {"depth": "interface", "theme": "ocean-calm"})
    pid = r["audit"]["proposal_id"]
    apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    apply_gigabuddy_action(tmp_path, "revert_evolution", {"proposal_id": pid})
