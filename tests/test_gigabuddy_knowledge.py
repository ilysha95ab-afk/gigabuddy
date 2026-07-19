"""C #4 — GigaBuddy "Karpathy wiki" department knowledge retrieval (v6.81.0).

Form (Б): a pure-stdlib lexical/structural retrieval engine over
``employees/<id>/knowledge/`` — markdown-aware chunking, frontmatter + inline
tags, ``[[wiki-link]]`` graph, BM25-style scoring. NOT RAG. Strictly
folder-confined, fail-soft, bounded, cached. Persona injects excerpts and is
honest when nothing scores; the double-gate and novice-safety must not regress.
"""

import pytest

from ouroboros import gigabuddy_knowledge as gk
from ouroboros import gigabuddy_state
from ouroboros.gigabuddy_state import (
    NOVICE_PROJECT_ID,
    apply_gigabuddy_action,
    build_gigabuddy_persona,
    gigabuddy_persona_section,
)


@pytest.fixture(autouse=True)
def _isolate_employees_root(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", str(tmp_path / "employees")
    )
    gk.clear_cache()
    yield
    gk.clear_cache()


def _kdir(tmp_path, employee_id="alice-demo"):
    d = tmp_path / "employees" / employee_id / "knowledge"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write(kdir, name, text):
    (kdir / name).write_text(text, encoding="utf-8")


# --- ingest: fail-soft + confinement + bounded -------------------------------


def test_missing_folder_yields_empty_index_no_raise(tmp_path):
    idx = gk.build_index("nobody")
    assert idx.is_empty()
    assert idx.chunks == []


def test_empty_folder_yields_empty_index(tmp_path):
    _kdir(tmp_path)  # exists but empty
    idx = gk.build_index("alice-demo")
    assert idx.is_empty()


def test_broken_binary_file_does_not_crash(tmp_path):
    kdir = _kdir(tmp_path)
    (kdir / "bad.md").write_bytes(b"\xff\xfe\x00\x01 broken \x80\x81")
    idx = gk.build_index("alice-demo")  # errors='replace' → no raise
    assert isinstance(idx.chunks, list)


def test_symlink_escape_is_refused(tmp_path):
    kdir = _kdir(tmp_path)
    secret = tmp_path / "outside_secret.md"
    secret.write_text("# Secret\nTOP SECRET should never be indexed", encoding="utf-8")
    link = kdir / "sneak.md"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unsupported on this platform")
    idx = gk.build_index("alice-demo")
    bodies = " ".join(c.body for c in idx.chunks)
    assert "TOP SECRET" not in bodies


def test_oversize_file_skipped(tmp_path, monkeypatch):
    kdir = _kdir(tmp_path)
    monkeypatch.setattr(gk, "_MAX_FILE_BYTES", 64)
    _write(kdir, "big.md", "# Big\n" + ("x " * 500))
    idx = gk.build_index("alice-demo")
    assert idx.is_empty()


# --- markdown chunking -------------------------------------------------------


def test_chunking_by_heading_not_line(tmp_path):
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "onboarding.md",
        "# Онбординг\nВводный текст.\n\n"
        "## Доступы\nКак получить доступы к системам.\n\n"
        "## Процессы\nОписание рабочих процессов.\n",
    )
    idx = gk.build_index("alice-demo")
    headings = sorted(c.heading for c in idx.chunks)
    assert "Доступы" in headings
    assert "Процессы" in headings
    # each section is one chunk, not one-per-line
    assert len(idx.chunks) == 3


def test_heading_breadcrumb(tmp_path):
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "doc.md",
        "# Топ\n\n## Средний\n\n### Лист\ntext body\n",
    )
    leaf = next(c for c in idx_chunks(tmp_path) if c.heading == "Лист")
    assert leaf.heading_path[:2] == ["Топ", "Средний"]


def idx_chunks(tmp_path):
    return gk.build_index("alice-demo").chunks


def test_no_heading_file_becomes_single_titled_chunk(tmp_path):
    kdir = _kdir(tmp_path)
    _write(kdir, "readme.txt", "Just some plain text with no headings at all.")
    idx = gk.build_index("alice-demo")
    assert len(idx.chunks) == 1
    assert idx.chunks[0].heading  # titled by filename stem
    assert "plain text" in idx.chunks[0].body


# --- tags + wiki-link graph --------------------------------------------------


def test_frontmatter_and_inline_tags_extracted(tmp_path):
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "policy.md",
        "---\ntags: [security, access]\n---\n"
        "# Политика\nВажно про #compliance и доступы.\n",
    )
    idx = gk.build_index("alice-demo")
    chunk = idx.chunks[0]
    assert "security" in chunk.tags
    assert "access" in chunk.tags
    assert "compliance" in chunk.tags


def test_wikilink_graph_neighbours(tmp_path):
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "a.md",
        "# Доступы\nЧтобы начать, см. [[VPN]].\n",
    )
    _write(
        kdir,
        "b.md",
        "# VPN\nНастройка VPN-клиента для удалённой работы.\n",
    )
    idx = gk.build_index("alice-demo")
    # search for "доступы" should pull the VPN neighbour via the [[VPN]] link
    hits = gk.search(idx, "доступы", top_n=1, with_neighbours=True)
    headings = [c.heading for c in hits]
    assert "Доступы" in headings
    assert "VPN" in headings  # graph neighbour rode along


# --- BM25 retrieval + honesty ------------------------------------------------


def test_bm25_returns_relevant_top_n(tmp_path):
    kdir = _kdir(tmp_path)
    _write(kdir, "vac.md", "# Отпуск\nКак оформить отпуск и сколько дней положено.\n")
    _write(kdir, "eq.md", "# Оборудование\nВыдача ноутбука и периферии.\n")
    idx = gk.build_index("alice-demo")
    hits = gk.search(idx, "как оформить отпуск", top_n=1, with_neighbours=False)
    assert hits
    assert hits[0].heading == "Отпуск"


def test_heading_and_tag_weighted_over_body(tmp_path):
    kdir = _kdir(tmp_path)
    # "безопасность" appears once in a heading of one chunk, and buried in body of
    # another; the heading match should win.
    _write(kdir, "sec.md", "# Безопасность\nОбщие правила работы в офисе.\n")
    _write(
        kdir,
        "misc.md",
        "# Разное\nТут случайно упомянута безопасность где-то в тексте абзаца.\n",
    )
    idx = gk.build_index("alice-demo")
    hits = gk.search(idx, "безопасность", top_n=2, with_neighbours=False)
    assert hits[0].heading == "Безопасность"


def test_irrelevant_query_returns_empty(tmp_path):
    kdir = _kdir(tmp_path)
    _write(kdir, "vac.md", "# Отпуск\nКак оформить отпуск.\n")
    idx = gk.build_index("alice-demo")
    hits = gk.search(idx, "квантовая хромодинамика реактор", top_n=3)
    assert hits == []


def test_empty_query_returns_empty(tmp_path):
    kdir = _kdir(tmp_path)
    _write(kdir, "vac.md", "# Отпуск\nтекст.\n")
    idx = gk.build_index("alice-demo")
    assert gk.search(idx, "", top_n=3) == []
    assert gk.search(idx, "   ", top_n=3) == []


# --- structural digest -------------------------------------------------------


def test_structural_digest_lists_topics_and_tags(tmp_path):
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "d.md",
        "---\ntags: [onboarding]\n---\n# Доступы\ntext\n\n## VPN\nmore\n",
    )
    idx = gk.build_index("alice-demo")
    digest = gk.structural_digest(idx)
    assert "Доступы" in digest["topics"]
    assert "VPN" in digest["topics"]
    assert "onboarding" in digest["tags"]
    assert digest["files"] == 1


# --- cache -------------------------------------------------------------------


def test_index_cache_rebuilds_on_change(tmp_path):
    kdir = _kdir(tmp_path)
    _write(kdir, "a.md", "# Один\ntext\n")
    idx1 = gk.get_index("alice-demo")
    assert len(idx1.chunks) == 1
    # same call returns cached object
    idx2 = gk.get_index("alice-demo")
    assert idx2 is idx1
    # add a file → signature changes → rebuild
    _write(kdir, "b.md", "# Два\ntext\n")
    idx3 = gk.get_index("alice-demo")
    assert idx3 is not idx1
    assert len(idx3.chunks) == 2


# --- persona integration -----------------------------------------------------


def _novice_task(objective=""):
    return {
        "id": "t1",
        "type": "task",
        "project_id": NOVICE_PROJECT_ID,
        "objective": objective,
        "_is_direct_chat": True,
    }


def test_persona_injects_knowledge_excerpts(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    kdir = _kdir(tmp_path)
    _write(
        kdir,
        "vac.md",
        "# Отпуск\nКак оформить отпуск: подать заявление за две недели.\n",
    )
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    persona = gigabuddy_persona_section(
        _novice_task(objective="как оформить отпуск?"), tmp_path
    )
    assert "База знаний отдела" in persona
    assert "Отпуск" in persona
    assert "подать заявление" in persona


def test_persona_honest_when_base_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    _kdir(tmp_path)  # empty knowledge folder
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    persona = gigabuddy_persona_section(_novice_task(objective="что-нибудь?"), tmp_path)
    # empty base → honest fallback naming the folder, never fabricated facts
    assert "База знаний отдела" in persona
    assert "НЕ выдумывай" in persona


def test_persona_honest_when_no_relevant_match(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    kdir = _kdir(tmp_path)
    _write(kdir, "vac.md", "# Отпуск\nКак оформить отпуск.\n")
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    persona = gigabuddy_persona_section(
        _novice_task(objective="квантовая хромодинамика реактор"), tmp_path
    )
    assert "релевантных материалов НЕ" in persona


def test_persona_does_not_leak_novice_sensitive_with_knowledge(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    kdir = _kdir(tmp_path)
    _write(kdir, "d.md", "# Доступы\nПравила доступа.\n")
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    persona = gigabuddy_persona_section(_novice_task(objective="доступы"), tmp_path)
    # sensitive internal signals / mentor notes / rollback history must NOT appear
    assert "internal_signals" not in persona
    assert "rollback" not in persona.lower()
    assert "mentor_notes" not in persona


def test_double_gate_preserved_with_knowledge(tmp_path, monkeypatch):
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "gigabuddy")
    kdir = _kdir(tmp_path)
    _write(kdir, "d.md", "# Доступы\ntext\n")
    apply_gigabuddy_action(tmp_path, "load_profile", {"employee_id": "alice-demo"})
    # non-novice project → no persona regardless of knowledge base
    dev_task = {"id": "t2", "type": "task", "_is_direct_chat": True}
    assert gigabuddy_persona_section(dev_task, tmp_path) == ""
    # product mode off → no persona
    monkeypatch.setenv("OUROBOROS_PRODUCT_MODE", "")
    assert gigabuddy_persona_section(_novice_task(objective="доступы"), tmp_path) == ""
