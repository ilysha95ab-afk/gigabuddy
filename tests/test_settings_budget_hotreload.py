"""Settings save budget hot-reload regression tests."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient


def _settings_client(monkeypatch, tmp_path, current: dict, raw_current: dict | None = None):
    import server as srv
    import ouroboros.gateway.settings as gateway_settings

    raw_state = raw_current if raw_current is not None else current
    monkeypatch.setattr(srv, "load_settings", lambda: dict(current))
    monkeypatch.setattr(gateway_settings, "load_settings", lambda: dict(current))
    monkeypatch.setattr(gateway_settings, "_owner_read_settings_raw", lambda: dict(raw_state))

    def fake_save_settings(settings, *args, **kwargs):
        current.clear()
        current.update(settings)
        if raw_current is not None:
            raw_current.clear()
            raw_current.update(settings)

    monkeypatch.setattr(srv, "save_settings", fake_save_settings)
    monkeypatch.setattr(gateway_settings, "save_settings", fake_save_settings)
    monkeypatch.setattr(gateway_settings, "_owner_write_settings", fake_save_settings)
    monkeypatch.setattr(srv, "_apply_settings_to_env", lambda *_a, **_k: None)
    monkeypatch.setattr(gateway_settings, "_apply_settings_to_env", lambda *_a, **_k: None)
    monkeypatch.setattr(srv, "_start_supervisor_if_needed", lambda *_a, **_k: False)
    monkeypatch.setattr(srv, "apply_runtime_provider_defaults", lambda s: (dict(s), False, []))
    monkeypatch.setattr(gateway_settings, "apply_runtime_provider_defaults", lambda s: (dict(s), False, []))
    monkeypatch.setattr(srv, "_mcp_reconfigure_startup", lambda *_a, **_k: None, raising=False)

    app = Starlette(routes=[Route("/api/settings", endpoint=srv.api_settings_post, methods=["POST"])])
    app.state.drive_root = tmp_path / "drive"
    app.state.repo_dir = tmp_path / "repo"
    return TestClient(app)


def test_settings_post_updates_budget_limits_and_per_task_threshold(monkeypatch, tmp_path):
    import supervisor.message_bus as bus_mod
    import supervisor.state as state_mod

    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    current = dict(_defaults)
    current["TOTAL_BUDGET"] = 10.0
    monkeypatch.setattr(state_mod, "TOTAL_BUDGET_LIMIT", 10.0)
    monkeypatch.setattr(bus_mod, "TOTAL_BUDGET_LIMIT", 10.0)

    client = _settings_client(monkeypatch, tmp_path, current)

    resp = client.post("/api/settings", json={"TOTAL_BUDGET": 25.0})

    assert resp.status_code == 200, resp.text
    assert resp.json().get("immediate_changed") is True
    assert state_mod.TOTAL_BUDGET_LIMIT == 25.0
    assert bus_mod.TOTAL_BUDGET_LIMIT == 25.0

    resp = client.post("/api/settings", json={"OUROBOROS_PER_TASK_COST_USD": "7.5"})

    assert resp.status_code == 200, resp.text
    assert resp.json().get("immediate_changed") is not True
    assert resp.json().get("next_task_changed") is True
    assert current["OUROBOROS_PER_TASK_COST_USD"] == 7.5

    invalid_cases = [
        ({"TOTAL_BUDGET": 0}, "greater than zero"),
        ({"TOTAL_BUDGET": 0.005}, "at least 0.01"),
        (["TOTAL_BUDGET", 25], "JSON body must be an object."),
        ({"OUROBOROS_PER_TASK_COST_USD": "nan"}, "must be a number"),
        ({"OUROBOROS_PER_TASK_COST_USD": "0.005"}, "at least 0.01"),
        ({"TOTAL_BUDGET": True}, "must be a number"),
    ]
    clean_budget_state = dict(current)
    clean_budget_state["TOTAL_BUDGET"] = 10.0
    clean_budget_state["OUROBOROS_PER_TASK_COST_USD"] = 20.0
    for payload, error in invalid_cases:
        current.clear()
        current.update(clean_budget_state)
        resp = client.post("/api/settings", json=payload)

        assert resp.status_code == 400
        assert error in resp.json()["error"]
        assert current["TOTAL_BUDGET"] == 10.0
        assert current["OUROBOROS_PER_TASK_COST_USD"] == 20.0


def test_settings_post_rejects_malformed_evolution_cadence(monkeypatch, tmp_path):
    """A direct API client must not be able to persist a malformed post-task evolution
    cadence (e.g. every_n:0) — backend half of the strict every_n validation contract."""

    key = "OUROBOROS_POST_TASK_EVOLUTION_CADENCE"
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    current = dict(_defaults)
    current[key] = "llm"
    client = _settings_client(monkeypatch, tmp_path, current)

    for good in ("off", "llm", "every_n:1", "every_n:25"):
        resp = client.post("/api/settings", json={key: good})
        assert resp.status_code == 200, (good, resp.text)
        assert current[key] == good

    current[key] = "llm"
    for bad in ("every_n:0", "every_n:-1", "every_n:", "every_nonsense", "daily"):
        resp = client.post("/api/settings", json={key: bad})
        assert resp.status_code == 400, (bad, resp.text)
        assert "every_n:<positive int>" in resp.json()["error"]
        assert current[key] == "llm", bad  # not persisted


def test_settings_post_auto_downgrades_max_on_sub1m_route_change(monkeypatch, tmp_path):
    """v6.33.0 WS11 (owner decision): changing the model while Max is on stays
    FRICTION-FREE — the model change SUCCEEDS and, if the new route can't be
    confirmed ≥1M, context mode AUTO-DOWNGRADES to Low with a plain notice (not a
    409 that blocks the save)."""
    import ouroboros.capability_evidence as ce
    import ouroboros.config as cfg
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults

    current = dict(_defaults)
    current["OUROBOROS_CONTEXT_MODE"] = "max"
    current["OUROBOROS_MODEL"] = "openai/gpt-5.5"
    monkeypatch.setenv("OUROBOROS_CONTEXT_MODE", "max")
    # Isolate the capability-evidence store so a cached confirmed/acked window from
    # another test cannot leak in (the probe reads config.DATA_DIR, not tmp_path).
    (tmp_path / "evidence-store").mkdir()
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "evidence-store")
    # New route carries no >=1M evidence (unprobeable) and is REACHABLE — mock both the
    # metadata window AND the generative probe (v6.46.0) so no real network call is made;
    # a reachable-but-unprobeable route must auto-downgrade (a transport FAILURE is the
    # sibling 503 test, kept distinct).
    monkeypatch.setattr(ce, "_provider_metadata_window", lambda *a, **k: 0)
    monkeypatch.setattr(ce, "_generative_probe_window", lambda *a, **k: (0, ce.STATUS_UNPROBEABLE, "reachable-no-evidence"))

    client = _settings_client(monkeypatch, tmp_path, current)
    resp = client.post("/api/settings", json={"OUROBOROS_MODEL": "anthropic/claude-opus-4-8"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body.get("context_mode_downgraded") is True
    assert body.get("context_mode") == "low"
    assert body.get("notice")  # plain-language explanation
    # The model change SUCCEEDED; context mode dropped to Low.
    assert current["OUROBOROS_MODEL"] == "anthropic/claude-opus-4-8"
    assert current["OUROBOROS_CONTEXT_MODE"] == "low"


def test_settings_post_errors_on_max_route_change_when_provider_unreachable(monkeypatch, tmp_path):
    """v6.33.0 WS11 P4 (owner decision): a genuine NO-CONNECTION during the
    max-mode probe is an ERROR (503), NOT a silent downgrade — and the model is
    NOT saved (distinct from a sub-1M/unprobeable route, which auto-downgrades)."""
    import ouroboros.capability_evidence as ce
    import ouroboros.config as cfg
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults

    current = dict(_defaults)
    current["OUROBOROS_CONTEXT_MODE"] = "max"
    current["OUROBOROS_MODEL"] = "openrouter/gpt-5.5"
    monkeypatch.setenv("OUROBOROS_CONTEXT_MODE", "max")
    (tmp_path / "evidence-store").mkdir()
    monkeypatch.setattr(cfg, "DATA_DIR", tmp_path / "evidence-store")
    # Provider unreachable: no metadata window AND a transport failure.
    monkeypatch.setattr(ce, "_provider_metadata_window", lambda *a, **k: 0)
    monkeypatch.setattr(ce, "_metadata_fetch_transport_failed", lambda *a, **k: True)

    client = _settings_client(monkeypatch, tmp_path, current)
    resp = client.post("/api/settings", json={"OUROBOROS_MODEL": "openrouter/other-model"})

    assert resp.status_code == 503, resp.text
    assert "connection" in resp.json().get("error", "").lower()
    # The model was NOT saved — the error path returns before persistence.
    assert current["OUROBOROS_MODEL"] == "openrouter/gpt-5.5"
    assert current["OUROBOROS_CONTEXT_MODE"] == "max"


def test_gigabuddy_return_pin_action_clears_product_mode(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    import ouroboros.gateway.settings as gateway_settings

    current = dict(_defaults)
    current["OUROBOROS_PRODUCT_MODE"] = "gigabuddy"
    current["GIGABUDDY_ADMIN_PIN"] = "1234"
    gateway_settings._GIGABUDDY_RETURN_FAILURES.clear()
    client = _settings_client(monkeypatch, tmp_path, current)

    bad = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "0000"})
    assert bad.status_code == 403
    assert "0000" not in bad.text
    assert current["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"

    malformed = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "12ab"})
    assert malformed.status_code == 403
    assert "12ab" not in malformed.text
    assert current["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"

    current["GIGABUDDY_ADMIN_PIN"] = ""
    unset = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "1234"})
    assert unset.status_code == 403
    assert "1234" not in unset.text
    assert current["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"
    current["GIGABUDDY_ADMIN_PIN"] = "1234"

    good = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "1234"})
    assert good.status_code == 200, good.text
    assert good.json().get("ok") is True
    assert good.json().get("product_mode") == ""
    assert "1234" not in good.text
    assert current["OUROBOROS_PRODUCT_MODE"] == ""


def test_gigabuddy_generic_settings_cannot_bypass_active_pin_gate(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    import ouroboros.gateway.settings as gateway_settings

    current = dict(_defaults)
    current["OUROBOROS_PRODUCT_MODE"] = "gigabuddy"
    current["GIGABUDDY_ADMIN_PIN"] = "1234"
    gateway_settings._GIGABUDDY_RETURN_FAILURES.clear()
    client = _settings_client(monkeypatch, tmp_path, current)

    exit_resp = client.post("/api/settings", json={"OUROBOROS_PRODUCT_MODE": ""})
    assert exit_resp.status_code == 403
    assert current["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"

    overwrite_resp = client.post("/api/settings", json={"GIGABUDDY_ADMIN_PIN": "9999"})
    assert overwrite_resp.status_code == 403
    assert current["GIGABUDDY_ADMIN_PIN"] == "1234"

    masked_resp = client.post("/api/settings", json={"GIGABUDDY_ADMIN_PIN": "***set***"})
    assert masked_resp.status_code == 200, masked_resp.text
    assert current["GIGABUDDY_ADMIN_PIN"] == "1234"


def test_gigabuddy_return_pin_cooldown(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    import ouroboros.gateway.settings as gateway_settings

    current = dict(_defaults)
    current["OUROBOROS_PRODUCT_MODE"] = "gigabuddy"
    current["GIGABUDDY_ADMIN_PIN"] = "1234"
    gateway_settings._GIGABUDDY_RETURN_FAILURES.clear()
    client = _settings_client(monkeypatch, tmp_path, current)

    for _ in range(gateway_settings._GIGABUDDY_RETURN_MAX_FAILURES):
        resp = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "0000"})
        assert resp.status_code == 403
    cooled = client.post("/api/settings", json={"_action": "gigabuddy_return", "pin": "1234"})
    assert cooled.status_code == 429
    assert current["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"


def test_gigabuddy_generic_guard_uses_effective_mode_when_raw_differs(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    import ouroboros.gateway.settings as gateway_settings

    effective = dict(_defaults)
    effective["OUROBOROS_PRODUCT_MODE"] = "gigabuddy"
    effective["GIGABUDDY_ADMIN_PIN"] = "1234"
    raw = dict(effective)
    raw["OUROBOROS_PRODUCT_MODE"] = ""
    gateway_settings._GIGABUDDY_RETURN_FAILURES.clear()
    client = _settings_client(monkeypatch, tmp_path, effective, raw_current=raw)

    resp = client.post("/api/settings", json={"OUROBOROS_PRODUCT_MODE": ""})

    assert resp.status_code == 403
    assert effective["OUROBOROS_PRODUCT_MODE"] == "gigabuddy"
    assert raw["OUROBOROS_PRODUCT_MODE"] == ""


def test_masked_gigabuddy_pin_placeholder_does_not_create_secret(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    import ouroboros.gateway.settings as gateway_settings

    current = dict(_defaults)
    current["OUROBOROS_PRODUCT_MODE"] = ""
    current.pop("GIGABUDDY_ADMIN_PIN", None)
    gateway_settings._GIGABUDDY_RETURN_FAILURES.clear()
    client = _settings_client(monkeypatch, tmp_path, current)

    resp = client.post("/api/settings", json={"GIGABUDDY_ADMIN_PIN": "***set***"})

    assert resp.status_code == 200, resp.text
    assert "GIGABUDDY_ADMIN_PIN" not in current


def test_gigabuddy_state_action_writes_runtime_state_not_settings(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults
    from ouroboros.gigabuddy_state import STATE_RELATIVE_PATH

    current = dict(_defaults)
    current["OUROBOROS_PRODUCT_MODE"] = "gigabuddy"
    current["GIGABUDDY_ADMIN_PIN"] = "1234"
    before = dict(current)
    client = _settings_client(monkeypatch, tmp_path, current)

    resp = client.post("/api/settings", json={
        "_action": "gigabuddy",
        "op": "add_task",
        "payload": {"title": "Секретный текст задачи не должен попадать в audit", "note": "mentor private note"},
    })

    assert resp.status_code == 200, resp.text
    assert resp.json().get("ok") is True
    assert current == before
    assert (tmp_path / "drive" / STATE_RELATIVE_PATH).is_file()
    events = (tmp_path / "drive" / "logs" / "events.jsonl").read_text(encoding="utf-8")
    assert "add_task" in events
    assert "alice-demo" in events
    assert "Секретный текст" not in events
    assert "mentor private note" not in events
    assert "1234" not in events


def test_gigabuddy_state_action_rejects_unknown_op_and_settings_fields(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults

    current = dict(_defaults)
    client = _settings_client(monkeypatch, tmp_path, current)

    unknown = client.post("/api/settings", json={"_action": "gigabuddy", "op": "bogus", "payload": {}})
    assert unknown.status_code == 400

    settings_like = client.post("/api/settings", json={
        "_action": "gigabuddy",
        "op": "add_task",
        "payload": {"title": "ok", "OUROBOROS_PRODUCT_MODE": ""},
    })
    assert settings_like.status_code == 400


def test_unknown_settings_action_is_not_persisted(monkeypatch, tmp_path):
    from ouroboros.config import SETTINGS_DEFAULTS as _defaults

    current = dict(_defaults)
    client = _settings_client(monkeypatch, tmp_path, current)

    resp = client.post("/api/settings", json={"_action": "unknown_demo_action"})

    assert resp.status_code == 400
    assert "_action" not in current



def test_owner_audit_filters_pin_password_credential_and_token(monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace
    import ouroboros.gateway.settings as gateway_settings

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(drive_root=tmp_path)),
        client=SimpleNamespace(host="127.0.0.1"),
    )

    gateway_settings._owner_audit(
        request,
        "test_secret_filter",
        {
            "submitted_pin": "1234",
            "admin_password": "pw",
            "credential_hint": "cred",
            "session_token": "tok",
            "public_result": "ok",
        },
    )

    event_lines = (tmp_path / "logs" / "events.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(event_lines[-1])
    assert row["public_result"] == "ok"
    assert "submitted_pin" not in row
    assert "admin_password" not in row
    assert "credential_hint" not in row
    assert "session_token" not in row
    assert "1234" not in json.dumps(row)
