"""Mentor-side GigaBuddy evolution-approval wiring (task c8f90ea7).

Covers the transport-neutral approval loop the Telegram bridge carries:
- the mentor context section surfaces pending proposals in a NON-novice thread,
- it never fires inside the novice thread or with product mode off,
- the ``gigabuddy_action`` tool closes propose→approve→revert end-to-end.
"""

import pathlib
import tempfile

import pytest

from ouroboros.gigabuddy_state import (
    NOVICE_PROJECT_ID,
    apply_gigabuddy_action,
)
from ouroboros.gigabuddy_mentor import (
    build_gigabuddy_mentor_section,
    gigabuddy_mentor_section,
    pending_evolution_proposals,
)


@pytest.fixture(autouse=True)
def _isolate_employees_root(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(tmp_path / "employees"))


def _load_alice(tmp_path):
    return apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})


def _stage_interface_proposal(tmp_path) -> str:
    _load_alice(tmp_path)
    res = apply_gigabuddy_action(
        tmp_path,
        "propose_evolution",
        {"depth": "interface", "theme": "cat", "mascot": "котёнок", "source": "novice_request"},
    )
    return res["audit"]["proposal_id"]


# ── pending proposals + mentor section ───────────────────────────────

def test_pending_lists_only_proposed(tmp_path):
    pid = _stage_interface_proposal(tmp_path)
    pending = pending_evolution_proposals(tmp_path)
    assert [p["id"] for p in pending] == [pid]
    assert pending[0]["status"] == "proposed"


def test_mentor_section_surfaces_pending(tmp_path):
    pid = _stage_interface_proposal(tmp_path)
    section = build_gigabuddy_mentor_section(tmp_path)
    assert pid in section
    assert "approve_evolution" in section
    assert "gigabuddy_action" in section
    # Depth + a soft-layer field must be described for the mentor.
    assert "интерфейс" in section


def test_mentor_section_empty_without_pending(tmp_path):
    _load_alice(tmp_path)  # loaded, but no proposal staged
    assert build_gigabuddy_mentor_section(tmp_path) == ""


def test_mentor_section_empty_after_approval(tmp_path):
    pid = _stage_interface_proposal(tmp_path)
    apply_gigabuddy_action(tmp_path, "approve_evolution", {"proposal_id": pid})
    # No longer "proposed" → nothing pending → no section.
    assert pending_evolution_proposals(tmp_path) == []
    assert build_gigabuddy_mentor_section(tmp_path) == ""


# ── gating: product mode + novice-thread ─────────────────────────────

def test_gate_off_when_product_mode_off(tmp_path, monkeypatch):
    _stage_interface_proposal(tmp_path)
    monkeypatch.delenv("OUROBOROS_PRODUCT_MODE", raising=False)
    task = {"objective": "hi", "project_id": ""}
    assert gigabuddy_mentor_section(task, tmp_path) == ""


def test_gate_off_inside_novice_thread(tmp_path, monkeypatch):
    _stage_interface_proposal(tmp_path)
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    novice_task = {"objective": "hi", "project_id": NOVICE_PROJECT_ID}
    # The novice thread must NEVER see evolution chrome (gets the persona instead).
    assert gigabuddy_mentor_section(novice_task, tmp_path) == ""


def test_gate_on_in_mentor_thread(tmp_path, monkeypatch):
    pid = _stage_interface_proposal(tmp_path)
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    mentor_task = {"objective": "одобряю", "project_id": ""}
    section = gigabuddy_mentor_section(mentor_task, tmp_path)
    assert pid in section


# ── gigabuddy_action tool: end-to-end approval loop ──────────────────

class _Ctx:
    def __init__(self, drive_root):
        self.drive_root = drive_root


def _tool():
    from ouroboros.tools.gigabuddy import get_tools

    entries = {e.name: e for e in get_tools()}
    return entries["gigabuddy_action"]


def test_tool_requires_product_mode(tmp_path, monkeypatch):
    monkeypatch.delenv("OUROBOROS_PRODUCT_MODE", raising=False)
    out = _tool().handler(_Ctx(tmp_path), op="get_state")
    assert "GIGABUDDY_PRODUCT_MODE_OFF" in out


def test_tool_rejects_unknown_op(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    out = _tool().handler(_Ctx(tmp_path), op="approve_stage", payload={})
    assert "TOOL_ARG_ERROR" in out


def test_tool_closes_propose_approve_loop(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    _load_alice(tmp_path)
    tool = _tool()
    ctx = _Ctx(tmp_path)
    # Capture Alice's ORIGINAL theme so the apply/revert delta is observable.
    # (arbitrary theme strings are bounded to ALLOWED_THEMES — that is the safety
    # point; pick a valid theme that DIFFERS from Alice's default so the change
    # and its revert are both visible.)
    original_theme = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]["interface"].get("theme")
    target_theme = "ocean-calm" if original_theme != "ocean-calm" else "warm-sunrise"
    # propose via the tool (agent-driven, the way the mentor loop stages it)
    propose = tool.handler(
        ctx, op="propose_evolution",
        payload={"depth": "interface", "theme": target_theme, "mascot": "котёнок"},
    )
    assert propose.startswith("OK:")
    pid = [p for p in pending_evolution_proposals(tmp_path)][0]["id"]
    # approve via the tool → interface applied
    approved = tool.handler(ctx, op="approve_evolution", payload={"proposal_id": pid})
    assert approved.startswith("OK:")
    view = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert view["interface"].get("theme") == target_theme
    assert view["interface"].get("mascot") == "котёнок"
    # revert via the tool → interface restored to Alice's original theme
    reverted = tool.handler(ctx, op="revert_evolution", payload={"proposal_id": pid})
    assert reverted.startswith("OK:")
    view2 = apply_gigabuddy_action(tmp_path, "get_state", {})["view"]
    assert view2["interface"].get("theme") == original_theme
    assert view2["interface"].get("theme") != target_theme


def test_tool_bad_proposal_id_is_clean_error(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    _load_alice(tmp_path)
    out = _tool().handler(_Ctx(tmp_path), op="approve_evolution", payload={"proposal_id": "nope"})
    assert "GIGABUDDY_ACTION_FAILED" in out
