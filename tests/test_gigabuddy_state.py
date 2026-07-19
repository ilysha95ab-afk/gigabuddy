import json

import pytest

from ouroboros import gigabuddy_state, projects_registry
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


def test_ensure_novice_project_recovers_from_tombstoned_canonical_id(tmp_path):
    # If the owner deletes the novice thread, the canonical id is permanently
    # reserved (tombstoned) and create_project raises for it. The helper must NOT
    # strand the newcomer chat on an empty descriptor — it walks a deterministic
    # fallback suffix and returns the first usable id (gigabuddy-novice-2).
    projects_registry.create_project(tmp_path, NOVICE_PROJECT_ID, name="Новичок")
    projects_registry.begin_project_deletion(tmp_path, NOVICE_PROJECT_ID)
    desc = ensure_novice_project(tmp_path)
    assert desc["project_id"] == f"{NOVICE_PROJECT_ID}-2"
    assert desc["chat_id"] > 1
    # The recovered id must be a REGISTERED (routable) project chat id.
    assert desc["chat_id"] in projects_registry.reserved_project_chat_ids(tmp_path)


def test_ensure_novice_project_recovery_is_stable_across_calls(tmp_path):
    # A single owner-delete advances the suffix by exactly one and the recovered
    # id is stable across restarts (idempotent create_project for the ACTIVE id).
    projects_registry.create_project(tmp_path, NOVICE_PROJECT_ID, name="Новичок")
    projects_registry.begin_project_deletion(tmp_path, NOVICE_PROJECT_ID)
    first = ensure_novice_project(tmp_path)
    second = ensure_novice_project(tmp_path)
    assert first == second
    assert first["project_id"] == f"{NOVICE_PROJECT_ID}-2"


def test_ensure_novice_project_fail_soft_when_all_generations_exhausted(tmp_path):
    # Pathological case: every candidate id tombstoned -> honest zero descriptor
    # (the placeholder is correct here). Reserve+delete the whole window.
    for candidate in gigabuddy_state._novice_project_id_candidates():
        projects_registry.create_project(tmp_path, candidate, name="Новичок")
        projects_registry.begin_project_deletion(tmp_path, candidate)
    desc = ensure_novice_project(tmp_path)
    assert desc == {"chat_id": 0, "project_id": ""}


def test_is_novice_project_id_matches_canonical_and_generations():
    assert gigabuddy_state.is_novice_project_id(NOVICE_PROJECT_ID)
    assert gigabuddy_state.is_novice_project_id(f"{NOVICE_PROJECT_ID}-2")
    assert gigabuddy_state.is_novice_project_id(f"{NOVICE_PROJECT_ID}-17")
    # v6.87.4: per-employee ids (gigabuddy-novice-<employee_slug>) are novice ids too.
    assert gigabuddy_state.is_novice_project_id(f"{NOVICE_PROJECT_ID}-x")
    assert gigabuddy_state.is_novice_project_id(f"{NOVICE_PROJECT_ID}-alisa_20260714")
    assert not gigabuddy_state.is_novice_project_id("gigabuddy")
    assert not gigabuddy_state.is_novice_project_id(f"{NOVICE_PROJECT_ID}-")
    assert not gigabuddy_state.is_novice_project_id("")


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


# --- Flexible profile extraction (v6.86.0) ---------------------------------


def test_flexible_profile_frontmatter_name_no_llm(tmp_path, monkeypatch):
    """A frontmatter «Имя: Алиса, роль HR» parses deterministically — the LLM is
    never even called (deterministic name found first)."""
    from ouroboros import gigabuddy_profile

    calls = {"n": 0}
    def _boom(_text):
        calls["n"] += 1
        raise AssertionError("LLM must not be called when frontmatter has a name")
    monkeypatch.setattr(gigabuddy_profile, "_llm_extract_profile", _boom)

    frag = gigabuddy_profile.extract_profile_flexible(
        "---\nИмя: Алиса\nроль: HR\n---\n", is_json=False)
    assert frag["name"] == "Алиса"
    assert frag["role"] == "HR"
    assert calls["n"] == 0


def test_flexible_profile_freeform_deterministic(tmp_path, monkeypatch):
    """A bullet-list profile («- Имя: Алиса») under a colon-less heading is
    extracted DETERMINISTICALLY (no LLM anywhere in the path — the LLM extractor
    was removed in v6.87.3 after the cloud.ru response_format rejection)."""
    from ouroboros import gigabuddy_profile

    monkeypatch.setattr(
        gigabuddy_profile, "_llm_extract_profile",
        lambda _t: (_ for _ in ()).throw(AssertionError("LLM must never run")))
    frag = gigabuddy_profile.extract_profile_flexible(
        "Портрет новичка\n\n"
        "- Имя: Алиса\n"
        "- Роль: HR\n"
        "- Подразделение: Люди и культура\n",
        is_json=False)
    # _normalize_raw_profile lifts name/role to the top and keeps the full
    # profile block nested (department lives there).
    assert frag["name"] == "Алиса"
    assert frag["role"] == "HR"
    assert frag["profile"]["department"] == "Люди и культура"


def test_flexible_profile_pure_prose_yields_no_name(tmp_path, monkeypatch):
    """Pure prose with NO key: value lines honestly yields no name (neutral
    start) — deterministic extraction never fabricates fields."""
    from ouroboros import gigabuddy_profile

    frag = gigabuddy_profile.extract_profile_flexible(
        "Знакомьтесь, у нас новый сотрудник, работает в HR.", is_json=False)
    assert not frag.get("name")


class _FakeLLMClient:
    """Fake LLMClient injected at the REAL client seam (`ouroboros.llm.LLMClient`)
    so `_llm_extract_profile` runs its actual body — usage-scope rebind,
    `model_call_slot`, `usage_scope`, and JSON-strictness parsing — instead of
    being stubbed wholesale. Records the exact chat kwargs for assertions."""

    last_kwargs = None

    def __init__(self, *_a, **_kw):
        pass

    def chat(self, **kwargs):
        _FakeLLMClient.last_kwargs = kwargs
        return {"role": "assistant", "content": _FakeLLMClient._content}, {}


def _inject_fake_llm(monkeypatch, content):
    """Patch the LLMClient CLASS the extractor imports, and capture the usage
    scope active during the send so we can assert the accounting wiring."""
    import ouroboros.llm as _llm
    import ouroboros.usage_accounting as _ua

    captured = {"scope": None}
    _FakeLLMClient._content = content

    real_usage_scope = _ua.usage_scope

    def _spy_usage_scope(scope):
        captured["scope"] = scope
        return real_usage_scope(scope)

    monkeypatch.setattr(_llm, "LLMClient", _FakeLLMClient)
    monkeypatch.setattr(_ua, "usage_scope", _spy_usage_scope)
    return captured


def test_llm_extract_profile_real_seam_success(tmp_path, monkeypatch):
    """Inject a fake LLMClient at the real seam: the extractor's genuine body
    parses strict JSON AND binds the send to a `gigabuddy_profile` usage scope
    (the monetary-accounting path, same as the knowledge module)."""
    from ouroboros import gigabuddy_profile

    captured = _inject_fake_llm(
        monkeypatch,
        json.dumps({"name": "Алиса", "role": "HR", "department": "Люди и культура"}))

    out = gigabuddy_profile._llm_extract_profile("имя - Алиса, HR, Люди и культура")
    assert out is not None
    assert out["name"] == "Алиса"
    assert out["role"] == "HR"
    # Accounting wiring actually exercised: the send ran under a rebound scope
    # tagged for gigabuddy_profile (the monetary authority), and json_object
    # response_format was requested through the real chat kwargs.
    assert captured["scope"] is not None
    assert captured["scope"].category == "gigabuddy_profile"
    assert captured["scope"].source == "gigabuddy_profile"
    assert _FakeLLMClient.last_kwargs["response_format"] == {"type": "json_object"}


def test_llm_extract_profile_real_seam_code_fence(tmp_path, monkeypatch):
    """A ```json fenced reply is de-fenced and parsed by the real extractor body."""
    from ouroboros import gigabuddy_profile

    _inject_fake_llm(monkeypatch, "```json\n{\"name\": \"Нова\"}\n```")
    out = gigabuddy_profile._llm_extract_profile("свободный текст про Нову")
    assert out is not None and out["name"] == "Нова"


def test_llm_extract_profile_real_seam_empty_returns_none(tmp_path, monkeypatch):
    """Empty model content → None (clean fall-through to deterministic parser)."""
    from ouroboros import gigabuddy_profile

    _inject_fake_llm(monkeypatch, "")
    assert gigabuddy_profile._llm_extract_profile("любой текст") is None


def test_llm_extract_profile_real_seam_bad_json_returns_none(tmp_path, monkeypatch):
    """Non-JSON garbage with no {...} → None; never raises, never fabricates."""
    from ouroboros import gigabuddy_profile

    _inject_fake_llm(monkeypatch, "извините, не понял запрос")
    assert gigabuddy_profile._llm_extract_profile("любой текст") is None


def test_llm_extract_profile_freeform_dash_name_alisa(tmp_path, monkeypatch):
    """Distinct, independently-reviewable receipt for the «имя - Алиса» free-form
    case: driving the REAL extractor seam yields name == 'Алиса'."""
    from ouroboros import gigabuddy_profile

    _inject_fake_llm(monkeypatch, json.dumps({"name": "Алиса"}))
    out = gigabuddy_profile._llm_extract_profile("имя - Алиса")
    assert out is not None and out["name"] == "Алиса"


def test_flexible_profile_llm_failure_degrades_cleanly(tmp_path, monkeypatch):
    """LLM unavailable/None → fall back to the deterministic result (here empty),
    never raises, never fabricates."""
    from ouroboros import gigabuddy_profile

    monkeypatch.setattr(gigabuddy_profile, "_llm_extract_profile", lambda _text: None)
    # Unstructured prose the deterministic parser can't turn into a name.
    frag = gigabuddy_profile.extract_profile_flexible(
        "какой-то свободный текст без явных полей", is_json=False)
    assert "name" not in frag  # no fabrication


def test_flexible_profile_empty_is_neutral(tmp_path):
    from ouroboros import gigabuddy_profile

    assert gigabuddy_profile.extract_profile_flexible("", is_json=False) == {}
    assert gigabuddy_profile.extract_profile_flexible("   ", is_json=False) == {}


def test_flexible_profile_json_never_calls_llm(tmp_path, monkeypatch):
    """JSON is already structured → deterministic parse, LLM never invoked."""
    from ouroboros import gigabuddy_profile

    monkeypatch.setattr(
        gigabuddy_profile, "_llm_extract_profile",
        lambda _t: (_ for _ in ()).throw(AssertionError("LLM must not run for JSON")))
    frag = gigabuddy_profile.extract_profile_flexible(
        json.dumps({"name": "Нова", "role": "Аналитик"}), is_json=True)
    assert frag["name"] == "Нова"


def test_flexible_profile_load_bullet_file_deterministic(tmp_path, monkeypatch):
    """End-to-end: a real bullet-list .txt profile (heading without a colon,
    then «- Имя: …» lines — the owner's actual file format) loads the name
    deterministically, with no LLM anywhere in the path."""
    from ouroboros import gigabuddy_profile

    monkeypatch.setattr(
        gigabuddy_profile, "_llm_extract_profile",
        lambda _t: (_ for _ in ()).throw(AssertionError("LLM must never run")))
    emp_dir = gigabuddy_profile.employee_dir("freeform-emp") / "profile"
    emp_dir.mkdir(parents=True, exist_ok=True)
    (emp_dir / "about.txt").write_text(
        "Портрет новичка\n\n"
        "- Имя: Алиса\n"
        "- Роль: HR-специалист\n",
        encoding="utf-8")
    result = apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "freeform-emp"})
    assert result["audit"]["loaded"] is True
    assert result["view"]["profile"]["name"] == "Алиса"


# --- Reset employee onboarding (v6.86.0) -----------------------------------


def test_reset_onboarding_clears_track_keeps_profile(tmp_path):
    """After a built track, reset_onboarding empties track/stage/progress but
    preserves the loaded profile identity + interface."""
    # Load a profile and build a track (as the questionnaire would).
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"label": "Первые дни", "title": "Знакомство", "steps": ["1:1"]},
        {"label": "Первый месяц", "title": "Задача"},
    ]})
    built = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert len(built["track"]) == 2
    assert built["profile"]["name"] == "Алиса"

    reset = apply_gigabuddy_action(tmp_path, "reset_onboarding", {})
    view = reset["view"]
    # Track/stage/progress cleared to neutral.
    assert view["track"] == []
    assert view["progressPct"] == 0
    assert view["stage"]["id"] == "advisor"
    # Profile identity + interface preserved (mentor re-runs the questionnaire).
    assert view["profile"]["name"] == "Алиса"
    assert view["interface"]["mascot"] == "🐾"

    # Durable: a fresh load from disk still shows the cleared track.
    reloaded = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert reloaded["track"] == []
    assert reloaded["profile"]["name"] == "Алиса"


def test_reset_onboarding_then_new_track(tmp_path):
    """reset → the mentor supplies new data → a new track builds cleanly."""
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"label": "Старый", "title": "Старый трек"}]})
    apply_gigabuddy_action(tmp_path, "reset_onboarding", {})
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [
        {"label": "Новый", "title": "Новый трек"},
        {"label": "Ещё", "title": "Второй этап"}]})
    view = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert [s["title"] for s in view["track"]] == ["Новый трек", "Второй этап"]


def test_reset_onboarding_rejects_unknown_payload(tmp_path):
    with pytest.raises(GigaBuddyStateError):
        apply_gigabuddy_action(tmp_path, "reset_onboarding", {"employee_id": "x"})


def test_reset_onboarding_view_hides_no_diagnostics(tmp_path):
    """The reset op's view stays novice-safe (no internal_signals/proposals leak)."""
    apply_gigabuddy_action(tmp_path, "set_track", {"stages": [{"label": "X", "title": "Y"}]})
    view = apply_gigabuddy_action(tmp_path, "reset_onboarding", {})["view"]
    dumped = json.dumps(view, ensure_ascii=False)
    assert "internal_signals" not in dumped
    assert "evolution_proposals" not in dumped
    assert "mentor_notes" not in dumped


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
