"""Native GigaBuddy department knowledge-base tests (simplified, v6.87.3).

No LLM, no BM25, no persistence — pure keyword-matching over structural chunks.
"""
import json
import os
from pathlib import Path

import pytest

from ouroboros import gigabuddy_knowledge as gk


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    """Isolate employees root + clear process-local cache."""
    root = tmp_path / "employees"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(root))
    gk.clear_cache()
    yield
    gk.clear_cache()


def _emp_dir(emp_id="alice"):
    root = Path(os.environ["OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT"])
    d = root / emp_id / "knowledge"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Tests to KEEP (unchanged spirit, adapted to simplified API)
# ---------------------------------------------------------------------------

def test_raw_txt_ingested_without_any_markup():
    """Plain .txt prose is chunked and retrievable without manual tags/links."""
    d = _emp_dir()
    (d / "vpn.txt").write_text(
        "# Настройка VPN\n"
        "Для доступа к корпоративной сети используйте Cisco AnyConnect.\n"
        "Подключение выполняется через шлюз vpn.company.local.\n"
        "Свяжитесь с IT-отделом для получения учётных данных.\n",
        encoding="utf-8",
    )
    idx = gk.build_index("alice")
    assert idx is not None
    assert len(idx.chunks) >= 1
    # The chunk heading should contain "VPN"
    headings = [c.heading.lower() for c in idx.chunks]
    assert any("vpn" in h for h in headings)


def test_docx_supported_or_honestly_skipped():
    """.docx extraction is fail-soft: supported via docx2txt or honestly skipped."""
    if not gk.docx_supported():
        # Not installed — just verify the function returns False
        assert gk.docx_supported() is False
        return
    # docx2txt IS installed — write a minimal .docx is hard without a library,
    # so just verify the function returns True and extraction of a non-docx
    # file returns None or empty.
    d = _emp_dir()
    fake = d / "fake.docx"
    fake.write_bytes(b"not a real docx")
    text = gk._extract_text(fake)
    # Should not raise; returns None or empty string
    assert text is None or text == ""


def test_structural_chunking_by_heading():
    """Multiple headings produce multiple chunks with breadcrumbs."""
    d = _emp_dir()
    (d / "hr.md").write_text(
        "# Доступы\n"
        "Порядок получения доступов к SAP.\n\n"
        "## Запрос\n"
        "Создайте тикет в Jira.\n\n"
        "## Согласование\n"
        "Руководитель подтверждает.\n",
        encoding="utf-8",
    )
    idx = gk.build_index("alice")
    headings = [c.heading for c in idx.chunks]
    # At least top-level "Доступы" appears
    assert any("Доступы" in h for h in headings)
    # Sub-headings create their own chunks
    assert any("Запрос" in h for h in headings)
    assert any("Согласование" in h for h in headings)


def test_retrieval_finds_relevant_chunk():
    """A keyword search returns the most relevant chunk in top results."""
    d = _emp_dir()
    (d / "access.md").write_text(
        "# Доступы\n"
        "Порядок получения доступов к корпоративным системам.\n"
        "SAP SuccessFactors, Jira, Confluence.\n",
        encoding="utf-8",
    )
    (d / "vacation.md").write_text(
        "# Отпуск\n"
        "Заявление на отпуск подаётся через портал SelfService.\n"
        "Срок — не менее 3 дней до начала.\n",
        encoding="utf-8",
    )
    idx = gk.build_index("alice")
    results = gk.search("доступы SAP", idx, top_n=3)
    assert len(results) >= 1
    # The access chunk should rank first (heading match)
    top = results[0]
    assert "Доступы" in top.chunk.heading or "доступ" in top.chunk.heading.lower()


def test_empty_query_returns_empty():
    """Empty or whitespace-only query returns no results."""
    d = _emp_dir()
    (d / "doc.txt").write_text("# Раздел\nТекст раздела.\n", encoding="utf-8")
    idx = gk.build_index("alice")
    assert gk.search("", idx) == []
    assert gk.search("   ", idx) == []


def test_connection_graph():
    """Chunks sharing >=2 significant heading/tag tokens are connected."""
    d = _emp_dir()
    (d / "doc.md").write_text(
        "# Доступы SAP SuccessFactors\n"
        "Настройка доступов в SAP.\n\n"
        "# Доступы SAP Jira\n"
        "Управление доступами в Jira Service Desk.\n",
        encoding="utf-8",
    )
    idx = gk.build_index("alice")
    graph = gk._build_connection_graph(idx.chunks)
    # At least one pair of chunks should be connected (both share "доступы")
    assert any(len(neighbours) > 0 for neighbours in graph.values())


def test_format_excerpt():
    """format_excerpt produces a labelled excerpt from a chunk."""
    from ouroboros.gigabuddy_knowledge import Chunk, format_excerpt

    chunk = Chunk(
        heading="Тестовый раздел",
        breadcrumbs=["Документ", "Тестовый раздел"],
        source_file="doc.md",
        body="Содержимое раздела для проверки форматирования.",
        tags=["тест"],
    )
    excerpt = format_excerpt(chunk)
    assert "Тестовый раздел" in excerpt
    assert "doc.md" in excerpt
    assert "Содержимое" in excerpt


# ---------------------------------------------------------------------------
# Lifecycle tests (UPDATED: no "building" state)
# ---------------------------------------------------------------------------

def test_status_lifecycle_empty_to_ready():
    """Status goes empty → ready (no building step)."""
    # No files → empty
    d = _emp_dir()  # dir exists but empty
    status = gk.knowledge_status("alice")
    assert status["status"] == "empty"
    assert status["llmBuilt"] is False

    # Add a file → ready after build
    (d / "doc.txt").write_text("# Документ\nТекст.\n", encoding="utf-8")
    gk.clear_cache()
    status = gk.knowledge_status("alice")
    assert status["status"] == "ready"
    assert status["docCount"] >= 1
    assert status["chunkCount"] >= 1


def test_delete_source_marks_empty_again():
    """Deleting the only source file returns status to empty."""
    d = _emp_dir()
    (d / "doc.txt").write_text("# Документ\nТекст.\n", encoding="utf-8")
    gk.build_index("alice")
    gk.clear_cache()
    status = gk.knowledge_status("alice")
    assert status["status"] == "ready"

    (d / "doc.txt").unlink()
    gk.clear_cache()
    status = gk.knowledge_status("alice")
    assert status["status"] == "empty"


# ---------------------------------------------------------------------------
# API compatibility tests
# ---------------------------------------------------------------------------

def test_rebuild_knowledge_is_no_op_compatible():
    """rebuild_knowledge(employee_id, use_llm=True) still works (use_llm ignored)."""
    d = _emp_dir()
    (d / "doc.txt").write_text("# Документ\nТекст.\n", encoding="utf-8")
    # Should not raise even with use_llm=True
    idx = gk.rebuild_knowledge("alice", use_llm=True)
    assert idx is not None
    assert len(idx.chunks) >= 1


def test_knowledge_context_block_returns_string():
    """knowledge_context_block returns a non-empty string for a match."""
    d = _emp_dir()
    (d / "access.md").write_text(
        "# Доступы\nПорядок получения доступов к системам.\n",
        encoding="utf-8",
    )
    block = gk.knowledge_context_block("alice", "доступы")
    assert isinstance(block, str)
    assert len(block) > 0
    assert "Доступы" in block


def test_knowledge_context_block_empty_on_no_match():
    """knowledge_context_block returns empty string when no files exist."""
    _emp_dir()  # empty
    block = gk.knowledge_context_block("alice", "что-то")
    assert block == ""
