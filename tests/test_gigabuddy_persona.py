"""B1 role-contract / persona (v6.77.0).

The product-mode ГигаБадди persona must be injected into the system context ONLY
for the novice thread AND only when product mode is gigabuddy. Ordinary Ouroboros
(product off) and the developer's own chat/threads must be unchanged.
"""

import json

import pytest

from ouroboros import gigabuddy_state
from ouroboros.gigabuddy_state import (
    BLANK_EMPLOYEE_ID,
    NOVICE_PROJECT_ID,
    apply_gigabuddy_action,
    build_gigabuddy_persona,
    default_gigabuddy_state,
    gigabuddy_persona_section,
    novice_knowledge_dir,
)


@pytest.fixture(autouse=True)
def _isolate_employees_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(tmp_path / "employees"))


def _novice_task():
    return {"id": "t1", "type": "task", "project_id": NOVICE_PROJECT_ID, "_is_direct_chat": True}


def _dev_task():
    return {"id": "t2", "type": "task", "_is_direct_chat": True}


def test_persona_injected_for_novice_thread_in_product_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    apply_gigabuddy_action(tmp_path, "get_state", {})  # materialize default state
    persona = gigabuddy_persona_section(_novice_task(), tmp_path)
    assert persona
    assert "ГигаБадди" in persona
    # B3 neutral default: NO fabricated name; the persona runs the acquaintance
    # (questionnaire) scenario instead of greeting a hardcoded Alice.
    assert "Алиса" not in persona
    assert "знаком" in persona.lower()  # acquaintance/questionnaire scenario


def test_persona_personalizes_from_loaded_profile(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    # After a profile is loaded, the persona addresses the newcomer by name.
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    persona = gigabuddy_persona_section(_novice_task(), tmp_path)
    assert persona
    assert "Алиса" in persona


def test_persona_hard_boundary_content_present(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    persona = build_gigabuddy_persona(tmp_path)
    assert persona
    # Hard role boundary: never leak Ouroboros internals to the novice.
    assert "Ouroboros" in persona
    assert "НИКОГДА" in persona
    # Stage / adaptation track awareness.
    assert "стадия" in persona.lower()
    assert "трек" in persona.lower()
    # Knowledge-folder integration point (retrieval itself is B3/C).
    assert "knowledge" in persona
    assert "gigabuddy/employees" in persona


def test_persona_is_not_injected_without_product_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("OUROBOROS_PRODUCT_MODE", raising=False)
    assert gigabuddy_persona_section(_novice_task(), tmp_path) == ""
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "")
    assert gigabuddy_persona_section(_novice_task(), tmp_path) == ""


def test_persona_is_not_injected_for_non_novice_thread(tmp_path, monkeypatch):
    # Product mode ON, but a developer / non-novice thread gets NO persona.
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    assert gigabuddy_persona_section(_dev_task(), tmp_path) == ""
    assert gigabuddy_persona_section({"id": "x", "project_id": "some-other"}, tmp_path) == ""


def test_persona_never_leaks_sensitive_state(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    # Seed sensitive internal fields, then confirm the persona never surfaces them.
    state = default_gigabuddy_state()
    emp = state["employees"][BLANK_EMPLOYEE_ID]
    emp["name"] = "Тест"  # named so the persona renders the profile block
    emp["profile"] = dict(emp.get("profile") or {}, name="Тест")
    emp["internal_signals"] = {"confidence_risk": "high anxiety marker"}
    emp["mentor_notes"] = ["private mentor note"]
    emp["rollback_history"] = [{"version_id": "v1", "reason": "secret rollback reason"}]
    apply_gigabuddy_action(tmp_path, "get_state", {})
    # Persist the seeded sensitive state through the reducer path.
    path = tmp_path / gigabuddy_state.STATE_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    persona = build_gigabuddy_persona(tmp_path)
    assert persona
    assert "private mentor note" not in persona
    assert "secret rollback reason" not in persona
    assert "anxiety" not in persona
    assert "confidence_risk" not in persona
    assert "internal_signals" not in persona


def test_persona_fail_soft_on_error(tmp_path, monkeypatch):
    # Any failure in the persona builder must yield "" (never break the thread).
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")

    def _boom(_root):
        raise RuntimeError("state read failed")

    monkeypatch.setattr(gigabuddy_state, "load_gigabuddy_state", _boom)
    assert build_gigabuddy_persona(tmp_path) == ""
    assert gigabuddy_persona_section(_novice_task(), tmp_path) == ""


def test_novice_knowledge_dir_is_employee_scoped():
    path = novice_knowledge_dir("alice-demo")
    assert path.name == "knowledge"
    assert "gigabuddy" in str(path)
    assert "employees" in str(path)
    assert "alice-demo" in str(path)
