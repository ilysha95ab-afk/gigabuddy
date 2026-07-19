"""GigaBuddy department knowledge base — the "Karpathy wiki" (C #4).

A lexical/structural retrieval engine over the newcomer's department knowledge
base (``~/Ouroboros/gigabuddy/employees/<id>/knowledge/``). It is deliberately
NOT RAG: no embeddings, no vector DB, no heavy dependencies — pure stdlib. The
"fullness" comes from structure (markdown-aware chunking, frontmatter + inline
tags, ``[[wiki-link]]`` graph with backlinks) and BM25-style lexical scoring,
not infrastructure weight.

Discipline mirrors ``gigabuddy_profile`` exactly: strictly folder-confined
(``_is_confined`` on the dir AND every file; a ``..``/symlink escape is
refused), fail-soft (a missing/empty/broken folder yields an empty index and
never raises), and bounded (caps on file count, file size, total size, chunk
count). The built index is cached per employee, keyed on the folder's file
composition + mtimes, so repeated questions do not re-read the tree.

Retrieval returns top-N relevant chunks PLUS their graph neighbours (chunks
linked via ``[[wiki-link]]`` in either direction), so an answer can pull in a
directly-related section even when the query only matched a sibling. The persona
answers strictly from these excerpts and, when nothing scores, says so honestly
rather than fabricating a fact.
"""

from __future__ import annotations

import logging
import math
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# --- Bounds (mirror gigabuddy_profile's conservative posture) ----------------
_MAX_FILE_BYTES = 256 * 1024
_MAX_FILES = 200
_MAX_TOTAL_BYTES = 8 * 1024 * 1024
_MAX_CHUNKS = 2000
_MAX_CHUNK_BODY_CHARS = 4000
# Plain-text formats read directly; .docx is extracted via optional docx2txt.
_TEXT_EXTS = (".md", ".markdown", ".txt")
_DOCX_EXTS = (".docx",)
_KNOWLEDGE_EXTS = _TEXT_EXTS + _DOCX_EXTS

# The served built wiki lives in a SERVICE subdir beside the mentor's sources, so
# the mentor's own files stay clean and untouched. Derived data only; safe to
# delete (rebuilds from sources). Skipped during ingest so it never re-indexes
# itself.
_WIKI_INDEX_DIRNAME = ".wiki_index"
_WIKI_INDEX_FILE = "index.json"
_WIKI_INDEX_SCHEMA = 1

# LLM wiki-building bounds. The build is a ONE-TIME setup process (persisted to
# .wiki_index/), never per-query, so a per-file LLM call is affordable; still
# bound the input so a huge doc can't blow the prompt.
_LLM_MAX_INPUT_CHARS = 12000
_LLM_MAX_CHUNKS_PER_FILE = 40

# The Karpathy-wiki build prompt: the LLM segments RAW mentor text (no manual
# markup) into semantic chunks and GENERATES the tags + cross-topic links itself.
# Output is strict JSON so parsing is deterministic; on any failure the caller
# falls back to structural markdown chunking (honest degrade, never fabricates).
_WIKI_BUILD_PROMPT = (
    "Ты строишь структурированную вики-базу знаний из сырого текста документа "
    "отдела. Раздели текст на осмысленные СЕМАНТИЧЕСКИЕ куски (по темам, не по "
    "строкам). Для КАЖДОГО куска придумай короткий заголовок, 1-5 тегов и список "
    "связанных тем (topic-заголовков других кусков этого же документа), чтобы "
    "получился граф связей между темами. НЕ выдумывай факты — используй только то, "
    "что есть в тексте. Верни СТРОГО JSON-объект вида:\n"
    '{"chunks":[{"heading":"...","body":"...","tags":["..."],"links":["..."]}]}\n'
    "Не добавляй пояснений вне JSON. Тело каждого куска — дословный/сжатый текст из "
    "документа, теги и links — на языке документа.\n\n"
    # NOTE: the JSON example above contains literal { } braces, so this template
    # MUST NOT be filled with str.format() (it would treat them as fields and
    # raise KeyError). The caller substitutes via _build_wiki_prompt() below.
    "Файл: __GK_SOURCE__\n---\n__GK_TEXT__\n---"
)


def _build_wiki_prompt(source: str, text: str) -> str:
    """Fill the wiki-build prompt WITHOUT str.format() — the prompt embeds a
    literal JSON example whose { } braces are not format fields."""
    return _WIKI_BUILD_PROMPT.replace("__GK_SOURCE__", source).replace(
        "__GK_TEXT__", text
    )


def _knowledge_llm_model() -> str:
    """The LIGHT slot, resolved to a credentialed provider (empty light -> main).

    Chunking/tagging is not reasoning-heavy, so the light lane is appropriate
    (mirrors ``project_naming._light_naming_model``)."""
    from ouroboros.config import get_light_model
    from ouroboros.provider_models import resolve_credentialed_model

    return resolve_credentialed_model(get_light_model())


def _knowledge_use_local() -> bool:
    return str(os.environ.get("USE_LOCAL_LIGHT", "") or "").lower() in ("true", "1")


def _llm_build_chunks(rel_path: str, text: str) -> Optional[List[Chunk]]:
    """Ask the LIGHT LLM to segment raw text into semantic chunks with generated
    tags + cross-topic links (the Karpathy-wiki methodology). Returns ``None`` on
    ANY failure (no creds / provider error / bad JSON) so the caller falls back to
    deterministic structural chunking. Never raises. The physical send is bound to
    a ``gigabuddy_knowledge`` usage scope (the monetary authority)."""
    body_text = (text or "").strip()
    if not body_text:
        return None
    prompt_text = body_text if len(body_text) <= _LLM_MAX_INPUT_CHARS else (
        body_text[:_LLM_MAX_INPUT_CHARS] + " …[документ обрезан для построения вики]"
    )
    try:
        import json

        from ouroboros import model_concurrency
        from ouroboros.llm import LLMClient
        from ouroboros.usage_accounting import UsageScope, current_usage_scope, usage_scope

        model = _knowledge_llm_model()
        use_local = _knowledge_use_local()
        client = LLMClient()
        scope = current_usage_scope()
        if scope is not None:
            from dataclasses import replace as _replace

            scope = _replace(scope, category="gigabuddy_knowledge", source="gigabuddy_knowledge")
        else:
            scope = UsageScope(
                drive_root=None,
                task_id="gigabuddy_knowledge",
                root_task_id="gigabuddy_knowledge",
                parent_task_id="",
                category="gigabuddy_knowledge",
                source="gigabuddy_knowledge",
            )
        chat_kwargs = dict(
            messages=[{
                "role": "user",
                "content": _build_wiki_prompt(rel_path, prompt_text),
            }],
            model=model,
            tools=None,
            reasoning_effort="low",
            max_tokens=8192,
            use_local=use_local,
            response_format={"type": "json_object"},
        )
        with model_concurrency.model_call_slot(model, use_local):
            with usage_scope(scope):
                msg, _usage = client.chat(**chat_kwargs)
        content = str((msg or {}).get("content") or "").strip()
        if not content:
            return None
        parsed = _parse_llm_chunks_json(content)
        if parsed is None:
            return None
        return _chunks_from_llm(rel_path, parsed)
    except Exception:
        log.debug("GigaBuddy LLM wiki build failed for %s; using fallback", rel_path, exc_info=True)
        return None


def _parse_llm_chunks_json(content: str) -> Optional[List[Dict[str, Any]]]:
    """Parse the model's JSON output, tolerating a ```json fenced block. Returns
    the list under ``chunks`` or ``None`` when the shape is wrong."""
    import json

    raw = content.strip()
    if raw.startswith("```"):
        # strip a fenced ```json ... ``` wrapper
        raw = re.sub(r"^```[a-zA-Z0-9]*\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw).strip()
    try:
        data = json.loads(raw)
    except Exception:
        # last resort: extract the first {...} object
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    if not isinstance(data, dict):
        return None
    chunks = data.get("chunks")
    if not isinstance(chunks, list):
        return None
    return [c for c in chunks if isinstance(c, dict)]


def _chunks_from_llm(rel_path: str, raw_chunks: List[Dict[str, Any]]) -> Optional[List[Chunk]]:
    """Turn parsed LLM chunk dicts into ``Chunk`` objects (bounded, fail-soft).
    Returns ``None`` if nothing usable was produced (caller then falls back)."""
    out: List[Chunk] = []
    for i, rc in enumerate(raw_chunks):
        if len(out) >= _LLM_MAX_CHUNKS_PER_FILE:
            break
        heading = str(rc.get("heading") or "").strip()
        body = str(rc.get("body") or "").strip()
        if not body and not heading:
            continue
        tags = sorted({_normalize_tag(t) for t in (rc.get("tags") or []) if _normalize_tag(t)})
        links = sorted({_normalize_topic(l) for l in (rc.get("links") or []) if _normalize_topic(l)})
        if not heading:
            heading = pathlib.Path(rel_path).stem.replace("-", " ").replace("_", " ").strip()
        out.append(Chunk(
            chunk_id=f"{rel_path}#{i}",
            source=rel_path,
            heading=heading,
            heading_path=[],
            body=body[:_MAX_CHUNK_BODY_CHARS],
            tags=tags,
            links=links,
            topic_key=_normalize_topic(heading),
        ))
    return out or None

# --- BM25 parameters (Robertson/Okapi standard defaults) ---------------------
_BM25_K1 = 1.5
_BM25_B = 0.75
# Field boosts: a query term matching a heading/tag is worth much more than body.
# Headings and tags are the human-curated topic labels of a chunk, so an exact
# topic-word hit there is a far stronger relevance signal than the same word
# scattered through prose; the weights make a heading hit decisively outrank a
# chunk that only matched common query words (e.g. "как", "оформить") in its body.
_HEADING_WEIGHT = 6.0
_TAG_WEIGHT = 4.0
_BODY_WEIGHT = 1.0

_SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789_-")

# Token: unicode word runs (letters/digits/_), min length 2, keeps Cyrillic.
_TOKEN_RE = re.compile(r"[^\W\d_]+|\d+", re.UNICODE)
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")
_INLINE_TAG_RE = re.compile(r"(?:^|\s)#([A-Za-zА-Яа-я][\w./-]*)")
_FRONTMATTER_TAGS_RE = re.compile(
    r"^tags\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE
)


def _slug(value: Any, default: str = "unknown") -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch in _SLUG_KEEP else "-" for ch in raw)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or default)[:64]


def employees_root() -> pathlib.Path:
    """Root of the employee folder tree (shares the profile module's override)."""
    override = os.environ.get("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", "").strip()
    if override:
        return pathlib.Path(os.path.expanduser(override))
    home = pathlib.Path(os.path.expanduser("~"))
    return home / "Ouroboros" / "gigabuddy" / "employees"


def knowledge_dir(employee_id: str) -> pathlib.Path:
    return employees_root() / _slug(employee_id) / "knowledge"


def _is_confined(path: pathlib.Path, root: pathlib.Path) -> bool:
    """True only if the RESOLVED path stays inside the RESOLVED root."""
    try:
        resolved = path.resolve()
        base = root.resolve()
    except OSError:
        return False
    return resolved == base or base in resolved.parents


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    return [t.lower() for t in _TOKEN_RE.findall(text) if len(t) >= 2]


def _normalize_tag(tag: str) -> str:
    return str(tag or "").strip().lstrip("#").lower()[:64]


def _normalize_topic(topic: str) -> str:
    """Canonical form of a wiki-link target / heading used as a graph node key."""
    return " ".join(str(topic or "").strip().lower().split())[:120]


# --- Chunk model -------------------------------------------------------------


@dataclass
class Chunk:
    chunk_id: str          # stable: "<relpath>#<n>"
    source: str            # relative file path
    heading: str           # section heading (or file title / "")
    heading_path: List[str]  # breadcrumb of ancestor headings
    body: str
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)      # outgoing wiki-links (normalized topics)
    topic_key: str = ""    # this chunk's own heading as a normalized topic
    # populated at index-build time:
    _len: int = 0
    _tf_heading: Dict[str, int] = field(default_factory=dict)
    _tf_tags: Dict[str, int] = field(default_factory=dict)
    _tf_body: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializable form for the persisted ``.wiki_index/`` (derived fields
        are recomputed on load, so only the semantic content is stored)."""
        return {
            "chunk_id": self.chunk_id,
            "source": self.source,
            "heading": self.heading,
            "heading_path": list(self.heading_path),
            "body": self.body,
            "tags": list(self.tags),
            "links": list(self.links),
            "topic_key": self.topic_key,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Chunk":
        return Chunk(
            chunk_id=str(data.get("chunk_id") or ""),
            source=str(data.get("source") or ""),
            heading=str(data.get("heading") or ""),
            heading_path=[str(h) for h in (data.get("heading_path") or []) if str(h).strip()],
            body=str(data.get("body") or "")[:_MAX_CHUNK_BODY_CHARS],
            tags=[_normalize_tag(t) for t in (data.get("tags") or []) if _normalize_tag(t)],
            links=[_normalize_topic(l) for l in (data.get("links") or []) if _normalize_topic(l)],
            topic_key=_normalize_topic(str(data.get("topic_key") or data.get("heading") or "")),
        )


def _extract_text(path: pathlib.Path) -> Optional[str]:
    """Extract plain text from a source file (fail-soft).

    ``.txt``/``.md``/``.markdown`` are read directly (utf-8, replace errors).
    ``.docx`` is extracted via the OPTIONAL ``docx2txt`` dependency — if it is not
    installed, ``.docx`` is skipped honestly (returns ``None``) rather than
    pretending to support it. Never raises."""
    try:
        suffix = path.suffix.lower()
        if suffix in _TEXT_EXTS:
            return _read_text_capped(path)
        if suffix in _DOCX_EXTS:
            try:
                import docx2txt  # optional; absent → .docx unsupported (honest skip)
            except Exception:
                log.info("GigaBuddy: docx2txt not installed; .docx skipped: %s", path.name)
                return None
            try:
                if path.stat().st_size > _MAX_FILE_BYTES:
                    return None
            except OSError:
                return None
            text = docx2txt.process(str(path))
            return text if isinstance(text, str) else None
    except Exception:
        log.debug("GigaBuddy text extraction failed for %s", path, exc_info=True)
        return None
    return None


def docx_supported() -> bool:
    """Whether native ``.docx`` extraction is available in this runtime."""
    try:
        import docx2txt  # noqa: F401
        return True
    except Exception:
        return False


def _parse_frontmatter_tags(text: str) -> Tuple[List[str], str]:
    """Return (tags, body_without_frontmatter). Only reads a leading YAML-ish
    ``---`` fenced block for a flat ``tags:`` line (list or comma/space form).
    Not a YAML parser (stdlib-only, dependency-free)."""
    lines = text.splitlines()
    if not (lines and lines[0].strip() == "---"):
        return [], text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return [], text
    fm = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1:])
    tags: List[str] = []
    m = _FRONTMATTER_TAGS_RE.search(fm)
    if m:
        raw = m.group(1).strip()
        # forms: [a, b, c]  |  a, b, c  |  a b c
        raw = raw.strip("[]")
        parts = re.split(r"[,\s]+", raw)
        tags = [_normalize_tag(p) for p in parts if _normalize_tag(p)]
    return tags, body


def _extract_inline(text: str) -> Tuple[List[str], List[str]]:
    """Return (inline_tags, wiki_link_topics) found anywhere in the text."""
    tags = [_normalize_tag(t) for t in _INLINE_TAG_RE.findall(text)]
    tags = [t for t in tags if t]
    links = [_normalize_topic(t) for t in _WIKILINK_RE.findall(text)]
    links = [l for l in links if l]
    return tags, links


def _chunk_markdown(rel_path: str, text: str) -> List[Chunk]:
    """Markdown-aware chunking by heading (H1-H6), not by line.

    Each heading opens a new chunk; content until the next heading is its body.
    Ancestor headings form a breadcrumb (``heading_path``). Frontmatter tags apply
    to every chunk in the file; inline ``#tags`` and ``[[links]]`` attach to the
    chunk they appear in. A file with no headings becomes one chunk titled by its
    filename. Fail-soft on any malformed content."""
    fm_tags, body_text = _parse_frontmatter_tags(text)
    file_title = pathlib.Path(rel_path).stem.replace("-", " ").replace("_", " ").strip()

    lines = body_text.splitlines()
    chunks: List[Chunk] = []
    # section stack: list of (level, heading)
    stack: List[Tuple[int, str]] = []
    cur_heading = ""
    cur_level = 0
    cur_body: List[str] = []
    seq = 0

    def flush() -> None:
        nonlocal seq, cur_body, cur_heading, cur_level
        body = "\n".join(cur_body).strip()
        heading = cur_heading or file_title
        if not body and not (cur_heading or cur_body):
            return
        # Skip a fully empty leading pseudo-section.
        if not body and not cur_heading:
            return
        inline_tags, links = _extract_inline((heading + "\n" + body))
        tags = sorted(set(fm_tags) | set(inline_tags))
        breadcrumb = [h for (_lvl, h) in stack if h]
        chunk = Chunk(
            chunk_id=f"{rel_path}#{seq}",
            source=rel_path,
            heading=heading,
            heading_path=breadcrumb[:],
            body=body[:_MAX_CHUNK_BODY_CHARS],
            tags=tags,
            links=sorted(set(links)),
            topic_key=_normalize_topic(heading),
        )
        chunks.append(chunk)
        seq += 1

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            # close the current section before opening a new one
            flush()
            level = len(m.group(1))
            heading = m.group(2).strip()
            # maintain ancestor stack
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, heading))
            cur_heading = heading
            cur_level = level
            cur_body = []
        else:
            cur_body.append(line)
    flush()

    # File with no headings and no content parsed → single title chunk of body.
    if not chunks:
        body = body_text.strip()
        if body:
            inline_tags, links = _extract_inline(body)
            chunks.append(
                Chunk(
                    chunk_id=f"{rel_path}#0",
                    source=rel_path,
                    heading=file_title,
                    heading_path=[],
                    body=body[:_MAX_CHUNK_BODY_CHARS],
                    tags=sorted(set(fm_tags) | set(t for t in inline_tags if t)),
                    links=sorted(set(links)),
                    topic_key=_normalize_topic(file_title),
                )
            )
    return chunks


# --- Index -------------------------------------------------------------------


@dataclass
class KnowledgeIndex:
    employee_id: str
    chunks: List[Chunk] = field(default_factory=list)
    # graph: topic_key -> set of chunk_ids that declare that topic (as heading)
    _topic_to_chunk: Dict[str, List[str]] = field(default_factory=dict)
    _chunk_by_id: Dict[str, Chunk] = field(default_factory=dict)
    # BM25 corpus stats
    _df: Dict[str, int] = field(default_factory=dict)      # document frequency
    _avg_len: float = 0.0
    _n: int = 0
    # backlink graph: chunk_id -> set of neighbour chunk_ids
    _neighbours: Dict[str, set] = field(default_factory=dict)
    signature: str = ""
    # True only when every ingested file was segmented by the LLM (Karpathy
    # methodology); False when at least one file fell back to structural chunking
    # or the build ran without the LLM (hot-path/status build).
    llm_built: bool = False

    def is_empty(self) -> bool:
        return not self.chunks


def _under_service_dir(path: pathlib.Path) -> bool:
    """True when ``path`` lives inside the ``.wiki_index`` service subdir, so the
    derived index never re-indexes itself or perturbs the source signature."""
    return _WIKI_INDEX_DIRNAME in path.parts


def _folder_signature(kdir: pathlib.Path, root: pathlib.Path) -> str:
    """A cheap composition+mtime signature for cache invalidation."""
    parts: List[str] = []
    try:
        for path in sorted(kdir.rglob("*")):
            if not path.is_file():
                continue
            if _under_service_dir(path):
                continue
            if path.suffix.lower() not in _KNOWLEDGE_EXTS:
                continue
            if not _is_confined(path, root):
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            parts.append(f"{path.relative_to(kdir)}:{int(st.st_mtime)}:{st.st_size}")
    except OSError:
        return ""
    return "|".join(parts)


def _iter_knowledge_files(kdir: pathlib.Path, root: pathlib.Path) -> List[pathlib.Path]:
    files: List[pathlib.Path] = []
    total = 0
    try:
        candidates = sorted(
            p for p in kdir.rglob("*")
            if p.is_file()
            and not _under_service_dir(p)
            and p.suffix.lower() in _KNOWLEDGE_EXTS
        )
    except OSError:
        return []
    for path in candidates:
        if len(files) >= _MAX_FILES:
            break
        if not _is_confined(path, root):
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size > _MAX_FILE_BYTES:
            log.warning("GigaBuddy knowledge file too large, skipping: %s", path.name)
            continue
        if total + size > _MAX_TOTAL_BYTES:
            break
        total += size
        files.append(path)
    return files


def _read_text_capped(path: pathlib.Path) -> Optional[str]:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > _MAX_FILE_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def build_index(employee_id: str, *, use_llm: bool = False) -> KnowledgeIndex:
    """Ingest ``employees/<id>/knowledge/`` into a searchable index (fail-soft).

    Recursively walks the folder (bounded), EXTRACTS text from each source
    (.txt/.md read directly, .docx via optional ``docx2txt``), segments it into
    chunks, builds the backlink graph, and precomputes BM25 corpus statistics.

    When ``use_llm`` is True (the ONE-TIME setup build), each file's raw text is
    segmented by the LIGHT LLM which GENERATES the tags + cross-topic links
    (Karpathy methodology). On any LLM failure it degrades to deterministic
    ``_chunk_markdown`` (structural chunking) — honest, never fabricated. When
    ``use_llm`` is False (the hot per-turn / status path) only the deterministic
    chunker runs, so a persona turn never triggers an LLM call. A missing / empty
    / unreadable folder yields an empty index; it never raises."""
    idx = KnowledgeIndex(employee_id=_slug(employee_id))
    root = employees_root()
    kdir = knowledge_dir(employee_id)
    if not _is_confined(kdir, root):
        log.warning("GigaBuddy knowledge path escapes employees root; refused")
        return idx
    try:
        if not kdir.is_dir():
            return idx
    except OSError:
        return idx

    idx.signature = _folder_signature(kdir, root)
    idx.llm_built = bool(use_llm)
    files = _iter_knowledge_files(kdir, root)
    for path in files:
        if len(idx.chunks) >= _MAX_CHUNKS:
            break
        text = _extract_text(path)
        if text is None:
            continue
        try:
            rel = str(path.relative_to(kdir))
        except ValueError:
            continue
        file_chunks: Optional[List[Chunk]] = None
        if use_llm:
            file_chunks = _llm_build_chunks(rel, text)
            if file_chunks is None:
                idx.llm_built = False  # at least one file fell back → not fully LLM-built
        if file_chunks is None:
            file_chunks = _chunk_markdown(rel, text)
        for chunk in file_chunks:
            if len(idx.chunks) >= _MAX_CHUNKS:
                break
            idx.chunks.append(chunk)

    _finalize_index(idx)
    return idx


def _finalize_index(idx: KnowledgeIndex) -> None:
    """Precompute per-chunk term frequencies, doc frequencies, avg length,
    the topic→chunk map, and the (bidirectional) wiki-link neighbour graph."""
    total_len = 0
    df: Dict[str, int] = {}
    for chunk in idx.chunks:
        idx._chunk_by_id[chunk.chunk_id] = chunk
        if chunk.topic_key:
            idx._topic_to_chunk.setdefault(chunk.topic_key, []).append(chunk.chunk_id)

        heading_tokens = _tokenize(chunk.heading + " " + " ".join(chunk.heading_path))
        tag_tokens = _tokenize(" ".join(chunk.tags))
        body_tokens = _tokenize(chunk.body)

        chunk._tf_heading = _count(heading_tokens)
        chunk._tf_tags = _count(tag_tokens)
        chunk._tf_body = _count(body_tokens)
        # weighted length for BM25 length-normalization
        chunk._len = (
            len(heading_tokens) + len(tag_tokens) + len(body_tokens)
        ) or 1
        total_len += chunk._len

        seen_terms = set(chunk._tf_heading) | set(chunk._tf_tags) | set(chunk._tf_body)
        for term in seen_terms:
            df[term] = df.get(term, 0) + 1

    idx._df = df
    idx._n = len(idx.chunks)
    idx._avg_len = (total_len / idx._n) if idx._n else 0.0

    # Backlink graph: an edge exists both directions when chunk A links topic T
    # and chunk B declares heading topic T.
    neighbours: Dict[str, set] = {c.chunk_id: set() for c in idx.chunks}
    for chunk in idx.chunks:
        for topic in chunk.links:
            for target_id in idx._topic_to_chunk.get(topic, []):
                if target_id == chunk.chunk_id:
                    continue
                neighbours[chunk.chunk_id].add(target_id)
                neighbours.setdefault(target_id, set()).add(chunk.chunk_id)
    idx._neighbours = neighbours


def _count(tokens: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in tokens:
        out[t] = out.get(t, 0) + 1
    return out


def _idf(idx: KnowledgeIndex, term: str) -> float:
    n = idx._n
    df = idx._df.get(term, 0)
    if n <= 0 or df <= 0:
        return 0.0
    # Robertson-Sparck-Jones IDF with +0.5 smoothing, floored at 0.
    return max(0.0, math.log((n - df + 0.5) / (df + 0.5) + 1.0))


def _bm25_score(idx: KnowledgeIndex, chunk: Chunk, query_terms: List[str]) -> float:
    """Field-weighted BM25 over heading/tags/body.

    Standard Okapi BM25 saturation + length normalization, applied to a weighted
    term-frequency that boosts heading and tag matches over body matches."""
    if not query_terms or chunk._len <= 0:
        return 0.0
    avg = idx._avg_len or 1.0
    norm = _BM25_K1 * (1.0 - _BM25_B + _BM25_B * (chunk._len / avg))
    score = 0.0
    for term in query_terms:
        idf = _idf(idx, term)
        if idf <= 0.0:
            continue
        tf = (
            _HEADING_WEIGHT * chunk._tf_heading.get(term, 0)
            + _TAG_WEIGHT * chunk._tf_tags.get(term, 0)
            + _BODY_WEIGHT * chunk._tf_body.get(term, 0)
        )
        if tf <= 0.0:
            continue
        score += idf * (tf * (_BM25_K1 + 1.0)) / (tf + norm)
    return score


def search(
    idx: KnowledgeIndex,
    query: str,
    *,
    top_n: int = 3,
    with_neighbours: bool = True,
    max_neighbours: int = 2,
) -> List[Chunk]:
    """Return the top-N BM25 chunks for the query, plus graph neighbours.

    Neighbours are chunks linked via ``[[wiki-link]]`` to/from a matched chunk;
    they are appended after the scored hits (de-duplicated, bounded) so a related
    section rides along even when the query only matched a sibling. An empty query
    or a zero-score result returns ``[]`` (the honest "not in the base" path)."""
    if idx.is_empty():
        return []
    query_terms = _tokenize(query)
    if not query_terms:
        return []
    scored: List[Tuple[float, Chunk]] = []
    for chunk in idx.chunks:
        s = _bm25_score(idx, chunk, query_terms)
        if s > 0.0:
            scored.append((s, chunk))
    if not scored:
        return []
    scored.sort(key=lambda pair: (-pair[0], pair[1].chunk_id))
    top = [c for _s, c in scored[:top_n]]

    if not with_neighbours:
        return top

    picked_ids = {c.chunk_id for c in top}
    result: List[Chunk] = list(top)
    added = 0
    for chunk in top:
        if added >= max_neighbours:
            break
        for nb_id in sorted(idx._neighbours.get(chunk.chunk_id, ())):
            if nb_id in picked_ids:
                continue
            nb = idx._chunk_by_id.get(nb_id)
            if nb is None:
                continue
            result.append(nb)
            picked_ids.add(nb_id)
            added += 1
            if added >= max_neighbours:
                break
    return result


def structural_digest(idx: KnowledgeIndex, *, max_topics: int = 24, max_tags: int = 24) -> Dict[str, Any]:
    """A compact map of the knowledge base: topics (headings), tags, file count.

    Used to ground the persona even without a query — so it knows what the base
    actually covers and can answer "we have X" / "we don't have Y" honestly."""
    if idx.is_empty():
        return {"topics": [], "tags": [], "files": 0, "chunks": 0}
    topics: List[str] = []
    seen_topics = set()
    for chunk in idx.chunks:
        h = chunk.heading.strip()
        key = h.lower()
        if h and key not in seen_topics:
            seen_topics.add(key)
            topics.append(h)
        if len(topics) >= max_topics:
            break
    tag_counts: Dict[str, int] = {}
    for chunk in idx.chunks:
        for t in chunk.tags:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    tags = [t for t, _c in sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:max_tags]]
    files = len({c.source for c in idx.chunks})
    return {"topics": topics, "tags": tags, "files": files, "chunks": len(idx.chunks)}


# --- Persona-facing rendering ------------------------------------------------


def format_excerpt(chunk: Chunk, *, max_chars: int = 700) -> str:
    """Render one chunk as a labelled excerpt for injection into the persona."""
    where = chunk.source
    if chunk.heading_path:
        crumb = " › ".join(chunk.heading_path)
        where = f"{chunk.source} › {crumb}"
    body = chunk.body.strip()
    if len(body) > max_chars:
        body = body[:max_chars].rstrip() + " …"
    tag_line = f" [теги: {', '.join(chunk.tags)}]" if chunk.tags else ""
    return f"— «{chunk.heading}» ({where}){tag_line}\n{body}"


# --- Persistence (.wiki_index/) ----------------------------------------------
#
# The built wiki is persisted beside the mentor's sources in a SERVICE subdir so
# the (possibly LLM-built) index survives process restarts and is not rebuilt on
# every persona turn. The stored ``signature`` is the source-folder composition/
# mtime fingerprint: when it still matches, the persisted index is reused; when
# it drifts (mentor added/removed/edited a file), a rebuild is needed.


def _wiki_index_dir(employee_id: str) -> Optional[pathlib.Path]:
    root = employees_root()
    kdir = knowledge_dir(employee_id)
    if not _is_confined(kdir, root):
        return None
    return kdir / _WIKI_INDEX_DIRNAME


def _wiki_index_path(employee_id: str) -> Optional[pathlib.Path]:
    d = _wiki_index_dir(employee_id)
    return (d / _WIKI_INDEX_FILE) if d is not None else None


def _index_to_payload(idx: KnowledgeIndex) -> Dict[str, Any]:
    return {
        "schema": _WIKI_INDEX_SCHEMA,
        "employee_id": idx.employee_id,
        "signature": idx.signature,
        "llm_built": bool(idx.llm_built),
        "chunks": [c.to_dict() for c in idx.chunks],
    }


def save_index(idx: KnowledgeIndex) -> bool:
    """Persist the built index to ``.wiki_index/index.json`` (fail-soft)."""
    path = _wiki_index_path(idx.employee_id)
    if path is None:
        return False
    try:
        from ouroboros.utils import atomic_write_json

        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path, _index_to_payload(idx))
        return True
    except Exception:
        log.debug("GigaBuddy: failed to persist wiki index", exc_info=True)
        return False


def load_persisted_index(employee_id: str) -> Optional[KnowledgeIndex]:
    """Load a persisted index if present and schema-current (fail-soft).

    Returns ``None`` when there is no persisted index, it is corrupt, or its
    schema differs. The stored ``signature`` is NOT validated here — the caller
    compares it against the live source signature to decide staleness."""
    path = _wiki_index_path(employee_id)
    if path is None:
        return None
    try:
        from ouroboros.utils import read_json_dict

        data = read_json_dict(path)
    except Exception:
        return None
    if not isinstance(data, dict) or int(data.get("schema") or 0) != _WIKI_INDEX_SCHEMA:
        return None
    raw_chunks = data.get("chunks")
    if not isinstance(raw_chunks, list):
        return None
    idx = KnowledgeIndex(employee_id=_slug(str(data.get("employee_id") or employee_id)))
    idx.signature = str(data.get("signature") or "")
    idx.llm_built = bool(data.get("llm_built"))
    for rc in raw_chunks:
        if isinstance(rc, dict):
            try:
                idx.chunks.append(Chunk.from_dict(rc))
            except Exception:
                continue
    _finalize_index(idx)
    return idx


def _live_signature(employee_id: str) -> str:
    root = employees_root()
    kdir = knowledge_dir(employee_id)
    try:
        return _folder_signature(kdir, root) if _is_confined(kdir, root) else ""
    except Exception:
        return ""


def rebuild_knowledge(employee_id: str, *, use_llm: bool = True) -> KnowledgeIndex:
    """The ONE-TIME setup build: (re)build the wiki with the LLM, persist it, and
    refresh the process cache. Safe to call repeatedly (idempotent per signature —
    the caller decides when a rebuild is needed). Fully fail-soft."""
    idx = build_index(employee_id, use_llm=use_llm)
    save_index(idx)
    try:
        _INDEX_CACHE[_slug(employee_id)] = (idx.signature or _live_signature(employee_id), idx)
    except Exception:
        pass
    return idx


def knowledge_status(employee_id: str) -> Dict[str, Any]:
    """Report the knowledge base's build status WITHOUT triggering an LLM build.

    Returns ``{status, docCount, chunkCount, llmBuilt}`` where status is one of:
      * ``empty``    — no source files in ``knowledge/``
      * ``building`` — sources exist but no fresh persisted index yet (a rebuild
                       is needed: either never built, or the folder changed)
      * ``ready``    — a persisted index matches the current source signature
    Never raises. This is the hot/status path — no LLM call here."""
    try:
        sig = _live_signature(employee_id)
        if not sig:
            return {"status": "empty", "docCount": 0, "chunkCount": 0, "llmBuilt": False}
        persisted = load_persisted_index(employee_id)
        if persisted is not None and persisted.signature == sig and not persisted.is_empty():
            files = len({c.source for c in persisted.chunks})
            return {
                "status": "ready",
                "docCount": files,
                "chunkCount": len(persisted.chunks),
                "llmBuilt": bool(persisted.llm_built),
            }
        # sources present but no matching fresh persisted index → needs (re)build
        return {"status": "building", "docCount": 0, "chunkCount": 0, "llmBuilt": False}
    except Exception:
        log.debug("GigaBuddy knowledge_status failed", exc_info=True)
        return {"status": "error", "docCount": 0, "chunkCount": 0, "llmBuilt": False}


# --- Cache -------------------------------------------------------------------

# Process-local cache: employee_slug -> (signature, KnowledgeIndex). Rebuilt when
# the folder's file composition/mtimes change. Fail-soft: cache errors just
# rebuild. This keeps repeated novice questions from re-reading the tree.
_INDEX_CACHE: Dict[str, Tuple[str, KnowledgeIndex]] = {}


def get_index(employee_id: str, *, use_cache: bool = True) -> KnowledgeIndex:
    """Return the retrieval index for the employee (hot path — never runs the LLM).

    Resolution order, all keyed on the live source signature:
      1. process cache (matching signature) → return it;
      2. persisted ``.wiki_index/`` (matching signature) → load + cache it;
      3. otherwise a deterministic structural build (``use_llm=False``) so a
         persona turn is never blocked on an LLM call. The richer LLM-built wiki
         is produced out-of-band by ``rebuild_knowledge`` (setup), persisted, and
         then picked up here via step 2."""
    slug = _slug(employee_id)
    sig = _live_signature(employee_id)
    if use_cache:
        cached = _INDEX_CACHE.get(slug)
        if cached and cached[0] == sig:
            return cached[1]
    persisted = load_persisted_index(employee_id)
    if persisted is not None and persisted.signature == sig and not persisted.is_empty():
        if use_cache:
            _INDEX_CACHE[slug] = (sig, persisted)
        return persisted
    idx = build_index(employee_id, use_llm=False)
    if use_cache:
        _INDEX_CACHE[slug] = (idx.signature or sig, idx)
    return idx


def clear_cache() -> None:
    _INDEX_CACHE.clear()


def knowledge_context_block(
    employee_id: str,
    query: str = "",
    *,
    top_n: int = 3,
    max_excerpt_chars: int = 700,
) -> str:
    """Build the persona's knowledge-base grounding block (or "").

    Always includes a structural digest (topics + tags) so the mentor knows what
    the base covers. When a query is available (the newcomer's latest message),
    also injects the top-N BM25 excerpts + graph neighbours. Returns "" when the
    base is empty (the persona then falls back to naming the folder + honesty).
    Fully fail-soft: any error yields "" so the novice thread never breaks."""
    try:
        idx = get_index(employee_id)
    except Exception:
        log.debug("GigaBuddy knowledge index unavailable", exc_info=True)
        return ""
    if idx.is_empty():
        return ""

    digest = structural_digest(idx)
    lines: List[str] = []
    lines.append(
        "### База знаний отдела (вики) — отвечай ТОЛЬКО по ней\n"
        "Ниже — реальная база знаний отдела сотрудника. Отвечай на вопросы новичка, "
        "опираясь СТРОГО на эти материалы. Если ответа в базе нет — честно скажи, что "
        "этого в базе знаний отдела нет и ты уточнишь у наставника; НЕ выдумывай факты."
    )
    if digest["topics"]:
        lines.append("Темы в базе: " + ", ".join(digest["topics"]))
    if digest["tags"]:
        lines.append("Теги: " + ", ".join("#" + t for t in digest["tags"]))

    if query and query.strip():
        hits = search(idx, query, top_n=top_n, with_neighbours=True)
        if hits:
            lines.append("\nНаиболее релевантные выдержки под текущий вопрос:")
            for chunk in hits:
                lines.append(format_excerpt(chunk, max_chars=max_excerpt_chars))
        else:
            lines.append(
                "\nПод текущий вопрос в базе знаний отдела релевантных материалов НЕ "
                "нашлось — честно скажи это новичку и предложи уточнить у наставника."
            )
    return "\n".join(lines)
