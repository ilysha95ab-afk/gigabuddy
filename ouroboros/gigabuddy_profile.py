"""GigaBuddy employee-folder profile parsing (B3).

A mentor drops a newcomer's first-source files into
``~/Ouroboros/gigabuddy/employees/<employee_id>/`` BEFORE the demo:

    profile/       — the newcomer profile (JSON and/or markdown with frontmatter)
    questionnaire/ — the base questionnaire from HR/management (optional)
    knowledge/     — the department knowledge base (retrieval skill is B3/C)

This module reads that folder and builds an employee-state fragment the reducer
can merge. It is deliberately small and dependency-free (no YAML/RAG): it parses
JSON directly and a simple ``key: value`` markdown frontmatter block. Everything
is FAIL-SOFT: a missing/empty/broken folder yields ``None`` (stay neutral,
nameless — never fabricate a candidate) and never raises. File access is confined
to the employee folder under the home GigaBuddy tree; arbitrary FS traversal is
refused.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

_MAX_PROFILE_BYTES = 256 * 1024
_PROFILE_EXTS = (".json", ".md", ".markdown", ".txt")
# A conservative slug identical in spirit to gigabuddy_state._slug so paths stay
# confined and predictable. Kept local to avoid a circular import.
_SLUG_KEEP = set("abcdefghijklmnopqrstuvwxyz0123456789_-")


def _slug(value: Any, default: str = "unknown") -> str:
    raw = str(value or "").strip().lower()
    cleaned = "".join(ch if ch in _SLUG_KEEP else "-" for ch in raw)
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or default)[:64]


def employees_root() -> pathlib.Path:
    """Absolute root of the owner-facing employee folder tree.

    Defaults to ``~/Ouroboros/gigabuddy/employees``. An explicit
    ``OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT`` override relocates it (used by tests
    for hermetic isolation and by non-default deployments); confinement is always
    enforced against whatever this returns."""
    override = os.environ.get("OUROBOROS_GIGABUDDY_EMPLOYEES_ROOT", "").strip()
    if override:
        return pathlib.Path(os.path.expanduser(override))
    home = pathlib.Path(os.path.expanduser("~"))
    return home / "Ouroboros" / "gigabuddy" / "employees"


def employee_dir(employee_id: str) -> pathlib.Path:
    return employees_root() / _slug(employee_id)


def _is_confined(path: pathlib.Path, root: pathlib.Path) -> bool:
    """True only if the RESOLVED path stays inside the RESOLVED root."""
    try:
        resolved = path.resolve()
        base = root.resolve()
    except OSError:
        return False
    return resolved == base or base in resolved.parents


def _read_text_capped(path: pathlib.Path) -> Optional[str]:
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > _MAX_PROFILE_BYTES:
            log.warning("GigaBuddy profile file too large, skipping: %s", path.name)
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _coerce_interests(value: Any) -> List[str]:
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        items = [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    else:
        items = []
    return items[:16]


def _parse_markdown_frontmatter(text: str) -> Dict[str, Any]:
    """Parse a simple ``key: value`` frontmatter (optionally fenced by ``---``).

    Not YAML: only flat ``key: value`` lines are read, plus an ``interests`` value
    that may be a comma/newline-separated list. Everything after the frontmatter
    (or the whole body when unfenced) is captured as ``experience`` if not already
    set — so a mentor can write a couple of lines of prose."""
    lines = text.splitlines()
    data: Dict[str, Any] = {}
    body_start = 0
    if lines and lines[0].strip() == "---":
        end = None
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end = i
                break
        if end is not None:
            fm_lines = lines[1:end]
            body_start = end + 1
        else:
            fm_lines = lines[1:]
            body_start = len(lines)
    else:
        # No fence: read leading key:value lines until a blank/non-kv line.
        fm_lines = []
        for i, line in enumerate(lines):
            if not line.strip():
                body_start = i + 1
                break
            if re.match(r"^[A-Za-zА-Яа-я_][\w \-А-Яа-я]*:\s", line):
                fm_lines.append(line)
                body_start = i + 1
            else:
                body_start = i
                break
    for line in fm_lines:
        m = re.match(r"^\s*([\w \-А-Яа-я]+?)\s*:\s*(.*)$", line)
        if not m:
            continue
        key = m.group(1).strip().lower().replace(" ", "_")
        data[key] = m.group(2).strip()
    body = "\n".join(lines[body_start:]).strip()
    if body and not data.get("experience"):
        data["experience"] = body
    return data


def _normalize_raw_profile(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Map a loosely-keyed parsed dict onto the reducer's profile/interface shape.

    Accepts Russian and English key aliases so a mentor can write either. Returns
    a fragment; the reducer clips/validates every field (allow-lists, hex accent,
    length caps), so this only needs to route values to the right keys."""
    def pick(*keys: str) -> Any:
        for k in keys:
            if k in raw and str(raw[k]).strip():
                return raw[k]
        return None

    profile: Dict[str, Any] = {}
    name = pick("name", "имя", "fullname", "full_name", "фио")
    role = pick("role", "роль", "position", "должность")
    department = pick("department", "отдел", "team", "команда", "подразделение")
    experience = pick("experience", "опыт", "bio", "about", "описание")
    interests = raw.get("interests") or raw.get("интересы") or raw.get("hobbies") or raw.get("увлечения")
    if name:
        profile["name"] = str(name).strip()
    if role:
        profile["role"] = str(role).strip()
    if department:
        profile["department"] = str(department).strip()
    if experience:
        profile["experience"] = str(experience).strip()
    interest_list = _coerce_interests(interests)
    if interest_list:
        profile["interests"] = interest_list

    fragment: Dict[str, Any] = {}
    if profile:
        fragment["profile"] = profile
        if profile.get("name"):
            fragment["name"] = profile["name"]
        if profile.get("role"):
            fragment["role"] = profile["role"]

    # Optional interface personalization block (already validated by the reducer).
    iface_raw = raw.get("interface") if isinstance(raw.get("interface"), dict) else {}
    iface: Dict[str, Any] = {}
    theme = iface_raw.get("theme") or raw.get("theme") or raw.get("тема")
    accent = iface_raw.get("accent_color") or raw.get("accent_color") or raw.get("accent") or raw.get("акцент")
    mascot = iface_raw.get("mascot") or raw.get("mascot") or raw.get("avatar") or raw.get("маскот")
    tone = iface_raw.get("tone") or raw.get("tone") or raw.get("тон")
    if theme:
        iface["theme"] = str(theme).strip()
    if accent:
        iface["accent_color"] = str(accent).strip()
    if mascot:
        iface["mascot"] = str(mascot).strip()
    if tone:
        iface["tone"] = str(tone).strip()
    if iface:
        fragment["interface"] = iface
    return fragment


def parse_profile_text(text: str, *, is_json: bool) -> Dict[str, Any]:
    """Parse one profile document into a reducer-mergeable fragment.

    ``is_json`` selects JSON vs the simple markdown/frontmatter parser. Returns an
    empty dict on unparseable content (fail-soft)."""
    if not text or not text.strip():
        return {}
    raw: Dict[str, Any]
    if is_json:
        try:
            loaded = json.loads(text)
        except (ValueError, TypeError):
            return {}
        raw = loaded if isinstance(loaded, dict) else {}
    else:
        raw = _parse_markdown_frontmatter(text)
    if not isinstance(raw, dict) or not raw:
        return {}
    return _normalize_raw_profile(raw)


def load_employee_profile(employee_id: str) -> Optional[Dict[str, Any]]:
    """Read ``employees/<id>/profile/`` and return a reducer-mergeable fragment.

    Returns ``None`` when there is no usable profile (missing folder, empty, or
    every file unparseable) so the caller stays in the neutral nameless state.
    JSON files take precedence over markdown; the first file that yields a name is
    used. Fully fail-soft and path-confined."""
    root = employees_root()
    emp_dir = employee_dir(employee_id)
    profile_dir = emp_dir / "profile"
    if not _is_confined(profile_dir, root):
        log.warning("GigaBuddy profile path escapes employees root; refused")
        return None
    try:
        if not profile_dir.is_dir():
            return None
        candidates = sorted(
            (p for p in profile_dir.iterdir()
             if p.is_file() and p.suffix.lower() in _PROFILE_EXTS),
            key=lambda p: (p.suffix.lower() != ".json", p.name.lower()),
        )
    except OSError:
        return None
    best: Optional[Dict[str, Any]] = None
    for path in candidates:
        if not _is_confined(path, root):
            continue
        text = _read_text_capped(path)
        if text is None:
            continue
        fragment = parse_profile_text(text, is_json=path.suffix.lower() == ".json")
        if not fragment:
            continue
        if fragment.get("name"):
            return fragment
        if best is None:
            best = fragment
    return best


def has_questionnaire(employee_id: str) -> bool:
    """Whether the employee folder carries a base questionnaire (integration point
    for the #5 methodology skill; the chat questionnaire may lean on it)."""
    root = employees_root()
    qdir = employee_dir(employee_id) / "questionnaire"
    if not _is_confined(qdir, root):
        return False
    try:
        return qdir.is_dir() and any(p.is_file() for p in qdir.iterdir())
    except OSError:
        return False


_MAX_QUESTIONNAIRE_HINTS = 8


def _extract_question_lines(text: str) -> List[str]:
    """Pull human-facing question/prompt lines from a base-questionnaire file.

    Deliberately format-tolerant (JSON list/dict, markdown bullets, or plain
    lines): a mentor may write the base questionnaire however they like. We only
    surface a handful of grounding prompts, so this is a lossy digest, not a
    parser. Returns [] on anything unusable (fail-soft)."""
    if not text or not text.strip():
        return []
    hints: List[str] = []
    stripped = text.strip()
    if stripped[:1] in ("{", "["):
        try:
            loaded = json.loads(stripped)
        except (ValueError, TypeError):
            loaded = None
        candidates: List[Any] = []
        if isinstance(loaded, list):
            candidates = loaded
        elif isinstance(loaded, dict):
            qs = loaded.get("questions") or loaded.get("вопросы") or loaded.get("prompts")
            if isinstance(qs, list):
                candidates = qs
            else:
                candidates = [v for v in loaded.values() if isinstance(v, str)]
        for item in candidates:
            if isinstance(item, str) and item.strip():
                hints.append(item.strip())
            elif isinstance(item, dict):
                q = item.get("question") or item.get("text") or item.get("prompt") or item.get("вопрос")
                if isinstance(q, str) and q.strip():
                    hints.append(q.strip())
    if not hints:
        for line in stripped.splitlines():
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            # A prompt line: ends with '?' or is a reasonably long directive.
            if cleaned and (cleaned.endswith("?") or len(cleaned) >= 12):
                hints.append(cleaned)
    # De-duplicate preserving order, clip length, bound count.
    seen: set[str] = set()
    result: List[str] = []
    for hint in hints:
        clipped = hint[:280]
        if clipped in seen:
            continue
        seen.add(clipped)
        result.append(clipped)
        if len(result) >= _MAX_QUESTIONNAIRE_HINTS:
            break
    return result


def read_questionnaire_hints(employee_id: str) -> List[str]:
    """Return a small list of the mentor's base-questionnaire prompts (or []).

    Integration point for the #5 methodology (form Б): when HR/management dropped
    a base questionnaire into ``employees/<id>/questionnaire/``, the persona leans
    on these real questions as the acquaintance's starting point instead of
    improvising. Fully fail-soft and path-confined; never raises, never fabricates
    (a missing/empty/unparseable folder yields [])."""
    root = employees_root()
    qdir = employee_dir(employee_id) / "questionnaire"
    if not _is_confined(qdir, root):
        return []
    try:
        if not qdir.is_dir():
            return []
        files = sorted(
            (p for p in qdir.iterdir()
             if p.is_file() and p.suffix.lower() in _PROFILE_EXTS),
            key=lambda p: (p.suffix.lower() != ".json", p.name.lower()),
        )
    except OSError:
        return []
    hints: List[str] = []
    for path in files:
        if not _is_confined(path, root):
            continue
        text = _read_text_capped(path)
        if text is None:
            continue
        hints.extend(_extract_question_lines(text))
        if len(hints) >= _MAX_QUESTIONNAIRE_HINTS:
            break
    # Final de-dupe + bound across files.
    seen: set[str] = set()
    result: List[str] = []
    for hint in hints:
        if hint in seen:
            continue
        seen.add(hint)
        result.append(hint)
        if len(result) >= _MAX_QUESTIONNAIRE_HINTS:
            break
    return result


def knowledge_dir_exists(employee_id: str) -> bool:
    """Whether the employee's department knowledge base folder exists (integration
    point for the #4 Karpathy-wiki retrieval skill)."""
    root = employees_root()
    kdir = employee_dir(employee_id) / "knowledge"
    if not _is_confined(kdir, root):
        return False
    try:
        return kdir.is_dir()
    except OSError:
        return False
