"""GigaBuddy department knowledge base — simplified keyword retrieval.

Folder-confined, fail-soft, bounded knowledge-base retrieval for per-employee
department documentation. Pure stdlib, no BM25, no LLM, no persistence —
keyword-matching with weighted scoring over structural markdown chunks.

Design:
- Chunks are structural markdown sections (heading + body).
- Search is weighted keyword matching (heading=6, tags=4, body=1).
- Connections are shared significant tokens between chunks.
- No embeddings, no vector DB, no LLM, no .wiki_index/ persistence.
- Build on demand with a process-local memory cache.
- Fail-soft: never raises on missing/unparseable data.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple



log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------

_MAX_FILE_BYTES = 256_000          # 256 KiB per file
_MAX_FILES = 48                    # max source files per employee
_MAX_CHUNKS = 320                  # max chunks per employee
_MAX_CHUNK_CHARS = 3200            # max chars per chunk body
_MAX_QUERY_TOKENS = 24            # max tokens extracted from a query
_MAX_EXCERPT_CHARS = 700           # max chars in a format_excerpt output
_TOP_N_DEFAULT = 4                 # default top-N results
_MAX_NEIGHBOURS_DEFAULT = 3       # default graph-neighbour expansion
_MIN_TOKEN_LEN = 3                 # minimum significant token length
_MAX_NEIGHBOUR_LINKS = 4          # max neighbours per chunk in search

_DOCX_EXTS = (".docx",)
_TEXT_EXTS = (".txt", ".md", ".markdown")

# Weight multipliers for keyword matching
_WEIGHT_HEADING = 6.0
_WEIGHT_TAGS = 4.0
_WEIGHT_BODY = 1.0


# ---------------------------------------------------------------------------
# Docx support (fail-soft import)
# ---------------------------------------------------------------------------

def docx_supported() -> bool:
    """Return True if docx2txt is available."""
    try:
        import docx2txt  # noqa: F401
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Chunk dataclass
# ---------------------------------------------------------------------------

@dataclass
class Chunk:
    """A structural section of a knowledge-base file."""
    heading: str = ""
    body: str = ""
    source_path: str = ""
    source_file: str = ""
    tags: List[str] = field(default_factory=list)
    links: List[str] = field(default_factory=list)
    breadcrumbs: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "heading": self.heading,
            "body": self.body,
            "source_path": self.source_path,
            "source_file": self.source_file,
            "tags": list(self.tags),
            "links": list(self.links),
            "breadcrumbs": list(self.breadcrumbs),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Chunk":
        return cls(
            heading=str(d.get("heading", "")),
            body=str(d.get("body", "")),
            source_path=str(d.get("source_path", "")),
            source_file=str(d.get("source_file", "")),
            tags=list(d.get("tags", [])),
            links=list(d.get("links", [])),
            breadcrumbs=list(d.get("breadcrumbs", [])),
        )


@dataclass
class KnowledgeIndex:
    """A built knowledge-base index for one employee."""
    employee_id: str
    chunks: List[Chunk] = field(default_factory=list)
    signature: str = ""
    llm_built: bool = False  # always False in simplified implementation

    def is_empty(self) -> bool:
        return len(self.chunks) == 0


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def _extract_text(path: Path) -> Optional[str]:
    """Extract text from .txt/.md/.docx. Fail-soft: returns None on error."""
    try:
        suffix = path.suffix.lower()
        if suffix in _DOCX_EXTS:
            if not docx_supported():
                log.debug("GigaBuddy knowledge .docx extraction skipped (docx2txt unavailable): %s", path)
                return None
            import docx2txt
            text = docx2txt.process(str(path))
            if text:
                text = text[:_MAX_FILE_BYTES]
            return text or None
        if suffix in _TEXT_EXTS:
            raw = path.read_text(encoding="utf-8", errors="replace")
            if len(raw) > _MAX_FILE_BYTES:
                raw = raw[:_MAX_FILE_BYTES]
            return raw or None
        return None
    except Exception as exc:
        log.debug("GigaBuddy knowledge text extraction failed (%s): %s", path, exc)
        return None


# ---------------------------------------------------------------------------
# Tokenization
# ---------------------------------------------------------------------------

_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    """Split text into lowercase significant tokens."""
    raw = _TOKEN_SPLIT_RE.split(text.lower())
    return [t for t in raw if len(t) >= _MIN_TOKEN_LEN]


def _token_counts(text: str) -> Dict[str, int]:
    """Return {token: count} for a text block."""
    counts: Dict[str, int] = {}
    for tok in _tokenize(text):
        counts[tok] = counts.get(tok, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Structural markdown chunking
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"^---\s*$", re.MULTILINE)
_TAG_LINE_RE = re.compile(r"^(?:tags|теги)\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _chunk_markdown(text: str, source_path: str, source_file: str) -> List[Chunk]:
    """Split markdown into structural chunks by heading level."""
    # Strip frontmatter
    fm_match = _FRONTMATTER_RE.match(text)
    frontmatter_tags: List[str] = []
    body_start = 0
    if fm_match:
        end_match = _FRONTMATTER_RE.search(text, fm_match.end())
        if end_match:
            fm_text = text[fm_match.end():end_match.start()]
            for line in fm_text.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    if key.strip().lower() in ("tags", "теги"):
                        # Accept both "tags: a, b" and "tags: [a, b]" spellings.
                        val = val.strip()
                        if val.startswith("[") and val.endswith("]"):
                            val = val[1:-1]
                        frontmatter_tags = [t.strip() for t in val.split(",") if t.strip()]
            body_start = end_match.end()

    body = text[body_start:]
    if not body.strip():
        return []

    # Split by headings
    heading_positions: List[Tuple[int, int, str, int]] = []
    for m in _HEADING_RE.finditer(body):
        heading_positions.append((m.start(), m.end(), m.group(2).strip(), len(m.group(1))))

    chunks: List[Chunk] = []
    breadcrumb_stack: List[Tuple[str, int]] = []  # (heading_text, level)

    if not heading_positions:
        # No headings — treat whole body as one chunk
        chunks.append(_make_chunk(
            heading=source_file,
            body=body.strip()[:_MAX_CHUNK_CHARS],
            source_path=source_path,
            source_file=source_file,
            frontmatter_tags=frontmatter_tags,
        ))
        return chunks

    # Pre-heading content
    if heading_positions[0][0] > 0:
        pre_body = body[:heading_positions[0][0]].strip()
        if pre_body:
            chunks.append(_make_chunk(
                heading=source_file,
                body=pre_body[:_MAX_CHUNK_CHARS],
                source_path=source_path,
                source_file=source_file,
                frontmatter_tags=frontmatter_tags,
            ))

    for i, (start, end, heading_text, level) in enumerate(heading_positions):
        # Update breadcrumb stack
        while breadcrumb_stack and breadcrumb_stack[-1][1] >= level:
            breadcrumb_stack.pop()
        breadcrumb_stack.append((heading_text, level))
        breadcrumbs = [h for h, _ in breadcrumb_stack]

        # Body until next heading or end
        body_start_i = end
        body_end_i = heading_positions[i + 1][0] if i + 1 < len(heading_positions) else len(body)
        chunk_body = body[body_start_i:body_end_i].strip()

        chunks.append(_make_chunk(
            heading=heading_text,
            body=chunk_body[:_MAX_CHUNK_CHARS],
            source_path=source_path,
            source_file=source_file,
            breadcrumbs=breadcrumbs,
            frontmatter_tags=frontmatter_tags,
        ))

        if len(chunks) >= _MAX_CHUNKS:
            break

    return chunks


def _make_chunk(
    *,
    heading: str,
    body: str,
    source_path: str,
    source_file: str,
    breadcrumbs: Optional[List[str]] = None,
    frontmatter_tags: Optional[List[str]] = None,
) -> Chunk:
    """Build a Chunk, extracting inline tags and wiki-links."""
    # Extract inline tags (tags: a, b, c)
    tags = list(frontmatter_tags) if frontmatter_tags else []
    tag_match = _TAG_LINE_RE.search(body)
    if tag_match:
        inline_tags = [t.strip() for t in tag_match.group(1).split(",") if t.strip()]
        tags.extend(inline_tags)

    # Extract wiki-links [[target]]
    links = [m.group(1).strip() for m in _LINK_RE.finditer(body)]

    # Remove tag lines and wiki-link markup from body
    clean_body = _TAG_LINE_RE.sub("", body)
    clean_body = _LINK_RE.sub(r"\1", clean_body)
    clean_body = clean_body.strip()

    return Chunk(
        heading=heading,
        body=clean_body,
        source_path=source_path,
        source_file=source_file,
        tags=tags,
        links=links,
        breadcrumbs=breadcrumbs or [heading],
    )


# ---------------------------------------------------------------------------
# File enumeration and index building
# ---------------------------------------------------------------------------

def _is_confined(path: Path, base: Path) -> bool:
    """Check that path stays within base directory."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except (ValueError, OSError):
        return False


def _knowledge_dir(employee_id: str) -> Path:
    """Return the knowledge directory for an employee."""
    from ouroboros.gigabuddy_profile import employees_root, employee_dir
    return employee_dir(employee_id) / "knowledge"


def _iter_knowledge_files(kb_dir: Path) -> List[Path]:
    """Iterate over knowledge source files in a directory."""
    if not kb_dir.is_dir():
        return []
    results: List[Path] = []
    try:
        for entry in sorted(kb_dir.rglob("*")):
            if not entry.is_file():
                continue
            if entry.suffix.lower() not in _TEXT_EXTS and entry.suffix.lower() not in _DOCX_EXTS:
                continue
            if not _is_confined(entry, kb_dir):
                continue
            # Skip service directories
            if ".wiki_index" in entry.parts:
                continue
            results.append(entry)
            if len(results) >= _MAX_FILES:
                break
    except Exception as exc:
        log.debug("GigaBuddy knowledge file enumeration failed: %s", exc)
    return results


def _folder_signature(kb_dir: Path, files: List[Path]) -> str:
    """Compute a simple signature for cache invalidation."""
    import hashlib
    h = hashlib.sha1()
    for f in files:
        try:
            st = f.stat()
            h.update(f"{f.name}:{st.st_size}:{int(st.st_mtime)}:".encode())
        except Exception:
            pass
    return h.hexdigest()


def _live_signature(employee_id: str) -> str:
    """Compute the live folder signature for an employee's KB."""
    kb_dir = _knowledge_dir(employee_id)
    files = _iter_knowledge_files(kb_dir)
    return _folder_signature(kb_dir, files)


def build_index(employee_id: str, *, use_llm: bool = False) -> KnowledgeIndex:
    """Build a knowledge index from source files.

    Args:
        employee_id: Employee identifier.
        use_llm: Ignored (kept for API compatibility). Always structural.

    Returns:
        KnowledgeIndex with chunks from all source files.
    """
    kb_dir = _knowledge_dir(employee_id)
    if not kb_dir.is_dir():
        return KnowledgeIndex(employee_id=employee_id, signature="", llm_built=False)

    files = _iter_knowledge_files(kb_dir)
    if not files:
        return KnowledgeIndex(employee_id=employee_id, signature="", llm_built=False)

    sig = _folder_signature(kb_dir, files)
    chunks: List[Chunk] = []

    for f in files:
        text = _extract_text(f)
        if not text:
            continue
        file_chunks = _chunk_markdown(text, str(f), f.name)
        chunks.extend(file_chunks)
        if len(chunks) >= _MAX_CHUNKS:
            chunks = chunks[:_MAX_CHUNKS]
            break

    idx = KnowledgeIndex(
        employee_id=employee_id,
        chunks=chunks,
        signature=sig,
        llm_built=False,
    )

    # Update memory cache
    _INDEX_CACHE[employee_id] = (sig, idx)
    return idx


def rebuild_knowledge(employee_id: str, *, use_llm: bool = False) -> KnowledgeIndex:
    """Rebuild knowledge index. Alias for build_index (API compatibility)."""
    _INDEX_CACHE.pop(employee_id, None)
    return build_index(employee_id, use_llm=use_llm)


# ---------------------------------------------------------------------------
# Memory cache
# ---------------------------------------------------------------------------

_INDEX_CACHE: Dict[str, Tuple[str, KnowledgeIndex]] = {}


def get_index(employee_id: str) -> KnowledgeIndex:
    """Get the index for an employee, building on demand if needed."""
    live_sig = _live_signature(employee_id)
    cached = _INDEX_CACHE.get(employee_id)
    if cached and cached[0] == live_sig:
        return cached[1]
    return build_index(employee_id)


def clear_cache() -> None:
    """Clear the process-local index cache."""
    _INDEX_CACHE.clear()


# ---------------------------------------------------------------------------
# Knowledge status
# ---------------------------------------------------------------------------

def knowledge_status(employee_id: str) -> Dict[str, Any]:
    """Return status info for an employee's knowledge base.

    Returns:
        Dict with keys: status (empty/ready), docCount, chunkCount, llmBuilt.
    """
    try:
        kb_dir = _knowledge_dir(employee_id)
        files = _iter_knowledge_files(kb_dir)
        doc_count = len(files)
        if doc_count == 0:
            return {"status": "empty", "docCount": 0, "chunkCount": 0, "llmBuilt": False}
        idx = get_index(employee_id)
        return {
            "status": "ready" if not idx.is_empty() else "empty",
            "docCount": doc_count,
            "chunkCount": len(idx.chunks),
            "llmBuilt": False,
        }
    except Exception as exc:
        log.debug("GigaBuddy knowledge_status failed for %s: %s", employee_id, exc)
        return {"status": "empty", "docCount": 0, "chunkCount": 0, "llmBuilt": False}


# ---------------------------------------------------------------------------
# Search — keyword matching with weighted scoring
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    """A single search result."""
    chunk: Chunk
    score: float
    is_neighbour: bool = False


def _chunk_token_index(chunk: Chunk) -> Dict[str, int]:
    """Build a token-count map for a chunk's heading + tags + body."""
    combined = " ".join([
        chunk.heading,
        " ".join(chunk.tags),
        chunk.body,
    ])
    return _token_counts(combined)


def _chunk_heading_tags_tokens(chunk: Chunk) -> set:
    """Return the set of significant tokens from heading + tags."""
    combined = " ".join([chunk.heading] + chunk.tags)
    return set(_tokenize(combined))


def _score_chunk(chunk: Chunk, query_tokens: List[str]) -> float:
    """Score a chunk against query tokens using weighted keyword matching."""
    if not query_tokens:
        return 0.0

    heading_counts = _token_counts(chunk.heading)
    tags_text = " ".join(chunk.tags)
    tags_counts = _token_counts(tags_text)
    body_counts = _token_counts(chunk.body)

    score = 0.0
    for token in query_tokens:
        score += _WEIGHT_HEADING * heading_counts.get(token, 0)
        score += _WEIGHT_TAGS * tags_counts.get(token, 0)
        score += _WEIGHT_BODY * body_counts.get(token, 0)

    return score


def _build_connection_graph(chunks: List[Chunk]) -> Dict[int, List[int]]:
    """Build a simple connection graph: chunks are connected if they share
    >=2 significant tokens in heading/tags."""
    graph: Dict[int, List[int]] = {i: [] for i in range(len(chunks))}
    token_sets = [_chunk_heading_tags_tokens(c) for c in chunks]

    for i in range(len(chunks)):
        for j in range(i + 1, len(chunks)):
            shared = token_sets[i] & token_sets[j]
            if len(shared) >= 2:
                graph[i].append(j)
                graph[j].append(i)

    return graph


def search(
    query: str,
    idx: KnowledgeIndex,
    *,
    top_n: int = _TOP_N_DEFAULT,
    with_neighbours: bool = True,
    max_neighbours: int = _MAX_NEIGHBOURS_DEFAULT,
) -> List[SearchResult]:
    """Search the index for chunks matching the query.

    Uses weighted keyword matching: heading=6, tags=4, body=1.
    Optionally expands results with graph-connected neighbours.
    """
    if idx.is_empty() or not query.strip():
        return []

    query_tokens = _tokenize(query)[:_MAX_QUERY_TOKENS]
    if not query_tokens:
        return []

    # Score all chunks
    scored: List[Tuple[int, float]] = []
    for i, chunk in enumerate(idx.chunks):
        score = _score_chunk(chunk, query_tokens)
        if score > 0:
            scored.append((i, score))

    if not scored:
        return []

    # Sort by score descending
    scored.sort(key=lambda x: -x[1])  # sort by score

    # Take top-N
    top_indices = [i for i, _ in scored[:top_n]]
    top_set = set(top_indices)

    results: List[SearchResult] = []
    for i in top_indices:
        score = next(s for idx_i, s in scored if idx_i == i)
        results.append(SearchResult(
            chunk=idx.chunks[i],
            score=score,
            is_neighbour=False,
        ))

    # Expand with neighbours
    if with_neighbours and len(results) > 0:
        graph = _build_connection_graph(idx.chunks)
        neighbour_added = 0
        for i in top_indices:
            for neighbour_i in graph.get(i, []):
                if neighbour_i not in top_set and neighbour_added < max_neighbours:
                    results.append(SearchResult(
                        chunk=idx.chunks[neighbour_i],
                        score=0.0,
                        is_neighbour=True,
                    ))
                    top_set.add(neighbour_i)
                    neighbour_added += 1
                    if neighbour_added >= max_neighbours:
                        break
            if neighbour_added >= max_neighbours:
                break

    return results


# ---------------------------------------------------------------------------
# Structural digest and excerpt formatting
# ---------------------------------------------------------------------------

def structural_digest(idx: KnowledgeIndex) -> Dict[str, Any]:
    """Build a compact structural map of the knowledge base.

    Returns a dict with topics, tags, file/chunk counts for grounding.
    """
    if idx.is_empty():
        return {"topics": [], "tags": [], "files": 0, "chunks": 0}

    topics: List[str] = []
    all_tags: List[str] = []
    files_seen: set = set()

    for chunk in idx.chunks:
        if chunk.heading:
            topics.append(chunk.heading)
        all_tags.extend(chunk.tags)
        files_seen.add(chunk.source_file)

    # Deduplicate while preserving order
    seen_topics: set = set()
    unique_topics: List[str] = []
    for t in topics:
        if t not in seen_topics:
            seen_topics.add(t)
            unique_topics.append(t)

    seen_tags: set = set()
    unique_tags: List[str] = []
    for t in all_tags:
        if t not in seen_tags:
            seen_tags.add(t)
            unique_tags.append(t)

    return {
        "topics": unique_topics[:48],
        "tags": unique_tags[:32],
        "files": len(files_seen),
        "chunks": len(idx.chunks),
    }


def format_excerpt(chunk: Chunk, max_chars: int = _MAX_EXCERPT_CHARS) -> str:
    """Format a chunk as a labelled excerpt for injection into persona prompt."""
    parts: List[str] = []

    if chunk.breadcrumbs:
        parts.append(" › ".join(chunk.breadcrumbs))
    elif chunk.heading:
        parts.append(chunk.heading)

    if chunk.source_file:
        parts.append(f"[{chunk.source_file}]")

    if chunk.tags:
        parts.append(f"tags: {', '.join(chunk.tags[:6])}")

    header = " ".join(parts)
    body = chunk.body[:max_chars]
    if len(chunk.body) > max_chars:
        body += "…"

    if header:
        return f"**{header}**\n\n{body}"
    return body


# ---------------------------------------------------------------------------
# Knowledge context block (for persona prompt injection)
# ---------------------------------------------------------------------------

def knowledge_context_block(
    employee_id: str,
    query: str = "",
    *,
    top_n: int = _TOP_N_DEFAULT,
    max_excerpt_chars: int = _MAX_EXCERPT_CHARS,
) -> str:
    """Build a knowledge context block for persona prompt injection.

    Searches the knowledge base and returns formatted excerpts of top results.
    Fail-soft: returns empty string on any error.
    """
    try:
        idx = get_index(employee_id)
        if idx.is_empty():
            return ""

        results = search(query, idx, top_n=top_n, with_neighbours=True, max_neighbours=2)
        if not results:
            return ""

        excerpts: List[str] = []
        for result in results:
            excerpt = format_excerpt(result.chunk, max_chars=max_excerpt_chars)
            if result.is_neighbour:
                excerpt = f"(связано) {excerpt}"
            excerpts.append(excerpt)

        header = "## Выдержки из базы знаний отдела\n\n"
        return header + "\n\n---\n\n".join(excerpts)
    except Exception as exc:
        log.debug("GigaBuddy knowledge_context_block failed for %s: %s", employee_id, exc)
        return ""
