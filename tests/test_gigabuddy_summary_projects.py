"""Focused tests for v6.87.4: short profile summary (LLM, no response_format,
cached sidecar) + per-employee novice projects + small UI text fixes."""

import json

import pytest


@pytest.fixture(autouse=True)
def _isolate_employees_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(tmp_path / "employees"))


# --- Profile summary ----------------------------------------------------------


def test_summary_deterministic_fallback_on_llm_failure(monkeypatch):
    from ouroboros import gigabuddy_profile
    from ouroboros.llm import LLMClient

    def _boom(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(LLMClient, "chat", _boom)
    out = gigabuddy_profile.generate_profile_summary(
        {"name": "Алиса Смирнова", "department": "Блок Люди и Культура", "experience": "первая роль"}
    )
    assert out["headline"] == "Алиса Смирнова. Блок Люди и Культура"
    assert out["tags"] == []


def test_summary_llm_plain_text_without_response_format(monkeypatch):
    from ouroboros import gigabuddy_profile
    from ouroboros.llm import LLMClient
    from ouroboros import provider_models

    monkeypatch.setattr(provider_models, "resolve_credentialed_model", lambda m: "test-model")
    captured = {}

    def _fake_chat(self, **kwargs):
        captured.update(kwargs)
        return (
            {"content": 'конечно! {"headline": "Алиса Смирнова. HR. Первая роль в найме", '
                        '"tags": ["котики", "командные ритуалы"]} спасибо'},
            {},
        )

    monkeypatch.setattr(LLMClient, "chat", _fake_chat)
    out = gigabuddy_profile.generate_profile_summary({"name": "Алиса Смирнова", "department": "HR"})
    # cloud.ru rejects response_format={"type": "json_object"} — the summary call
    # must be plain text and pull the JSON object out of the reply instead.
    assert "response_format" not in captured
    assert out["headline"] == "Алиса Смирнова. HR. Первая роль в найме"
    assert out["tags"] == ["котики", "командные ритуалы"]


def test_summary_cached_sidecar_no_regeneration(tmp_path, monkeypatch):
    from ouroboros import gigabuddy_profile

    calls = {"n": 0}

    def _fake_generate(profile):
        calls["n"] += 1
        return {"headline": "Нова. HR.", "tags": ["котики"]}

    monkeypatch.setattr(gigabuddy_profile, "generate_profile_summary", _fake_generate)
    profile = {"name": "Нова", "department": "HR"}
    first = gigabuddy_profile.ensure_profile_summary("nova-001", profile)
    assert first == {"headline": "Нова. HR.", "tags": ["котики"]}
    sidecar = gigabuddy_profile.employee_dir("nova-001") / "profile_summary.json"
    assert sidecar.is_file()

    def _boom(profile):
        raise AssertionError("must NOT regenerate on a later poll")

    monkeypatch.setattr(gigabuddy_profile, "generate_profile_summary", _boom)
    second = gigabuddy_profile.ensure_profile_summary("nova-001", profile)
    assert second == first
    assert calls["n"] == 1


def test_summary_empty_profile_is_empty():
    from ouroboros import gigabuddy_profile

    assert gigabuddy_profile.generate_profile_summary({}) == {"headline": "", "tags": []}


# --- Per-employee novice projects ---------------------------------------------


def test_ensure_employee_project_deterministic_id_and_idempotent(tmp_path):
    from ouroboros import gigabuddy_projects, projects_registry

    first = gigabuddy_projects.ensure_employee_project(tmp_path, "alisa_20260714", "Алиса Смирнова")
    assert first["project_id"] == "gigabuddy-novice-alisa_20260714"
    assert first["chat_id"] != 0
    second = gigabuddy_projects.ensure_employee_project(tmp_path, "alisa_20260714", "Алиса Смирнова")
    assert second == first
    # Two employees → two separate projects (dialogue stored per employee).
    other = gigabuddy_projects.ensure_employee_project(tmp_path, "leonid_20260714", "Леонид")
    assert other["project_id"] == "gigabuddy-novice-leonid_20260714"
    assert other["chat_id"] != first["chat_id"]


def test_is_novice_project_id_accepts_employee_slugs():
    from ouroboros.gigabuddy_state import is_novice_project_id

    assert is_novice_project_id("gigabuddy-novice")
    assert is_novice_project_id("gigabuddy-novice-2")
    assert is_novice_project_id("gigabuddy-novice-alisa_20260714")
    assert not is_novice_project_id("")
    assert not is_novice_project_id("other-project")
    assert not is_novice_project_id("gigabuddy-novice-")


# --- Small fixes ---------------------------------------------------------------


def test_default_employee_role_is_not_demo():
    from ouroboros.gigabuddy_state import normalize_gigabuddy_state

    state = normalize_gigabuddy_state({"employees": {"x-1": {"id": "x-1"}}})
    assert state["employees"]["x-1"]["role"] == ""


def test_gigabuddy_js_ui_text():
    import pathlib

    js = (pathlib.Path(__file__).resolve().parent.parent / "web" / "modules" / "gigabuddy.js").read_text(encoding="utf-8")
    assert "Telegram позже" not in js
    assert "События / Telegram" in js
    assert "profileSummary" in js
    assert "summaryChips" in js
