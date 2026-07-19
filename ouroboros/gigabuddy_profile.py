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
_PROFILE_EXTS = (".json", ".md", ".markdown", ".txt", ".docx")
_DOCX_EXTS = (".docx",)
# Max characters of free-form profile text fed to the LLM extractor (a profile
# is short; this is a generous cap that keeps the light-lane call cheap).
_LLM_PROFILE_MAX_CHARS = 8000
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
    """Read a profile file to text (fail-soft, size-capped).

    ``.json``/``.md``/``.markdown``/``.txt`` are read directly. ``.docx`` is
    extracted via the OPTIONAL ``docx2txt`` dependency — absent, ``.docx`` is
    skipped honestly (returns ``None``) rather than pretending to support it."""
    try:
        if not path.is_file():
            return None
        if path.stat().st_size > _MAX_PROFILE_BYTES:
            log.warning("GigaBuddy profile file too large, skipping: %s", path.name)
            return None
        if path.suffix.lower() in _DOCX_EXTS:
            try:
                import docx2txt  # optional; absent → .docx unsupported (honest skip)
            except Exception:
                log.info("GigaBuddy: docx2txt not installed; profile .docx skipped: %s", path.name)
                return None
            try:
                text = docx2txt.process(str(path))
            except Exception:
                log.debug("GigaBuddy profile .docx extraction failed: %s", path.name, exc_info=True)
                return None
            return text if isinstance(text, str) else None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def docx_supported() -> bool:
    """Whether native ``.docx`` profile extraction is available in this runtime."""
    try:
        import docx2txt  # noqa: F401
        return True
    except Exception:
        return False


def _coerce_interests(value: Any) -> List[str]:
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(value, str):
        items = [part.strip() for part in re.split(r"[,;\n]", value) if part.strip()]
    else:
        items = []
    return items[:16]


def _scan_profile_text(text: str) -> Dict[str, Any]:
    """Scan ALL lines of a free-form profile for ``key: value`` pairs.

    Unlike a frontmatter parser, this does not stop at the first non-kv line —
    it scans every line for ``[-*]? key: value`` so bullet-list profiles
    (``- Имя: Алиса Смирнова``) work without YAML-style frontmatter. Continuation
    lines (no colon) after a kv-line are appended to the previous value. The full
    text is also captured as ``experience`` if not already set."""
    lines = text.splitlines()
    data: Dict[str, Any] = {}
    last_key: Optional[str] = None
    for line in lines:
        stripped = line.strip()
        # Separator fences (---, ***, ===) and markdown headings (# ...) are
        # structural, not content: they must not continue a previous kv value.
        if stripped and (
            set(stripped) <= {"-", "*", "=", "_"}
            or stripped.startswith("#")
        ):
            continue
        m = re.match(r"^\s*[-*]?\s*(.+?)\s*:\s*(.*)$", line)
        if m:
            key = m.group(1).strip().lower().replace(" ", "_")
            data[key] = m.group(2).strip()
            last_key = key
        elif last_key and line.strip():
            data[last_key] = (str(data.get(last_key, "")) + " " + line.strip()).strip()
    if text.strip() and not data.get("experience"):
        data["experience"] = text.strip()
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


_PROFILE_LLM_PROMPT = (
    "Ты извлекаешь структурированный профиль сотрудника из произвольного текста, "
    "написанного наставником в любой форме (свободный текст, «Имя: Алиса», "
    "«имя - Алиса», абзацы). Верни СТРОГО JSON-объект с полями: name, role, "
    "department, experience, interests (массив строк). Бери ТОЛЬКО то, что реально "
    "есть в тексте — не выдумывай. Отсутствующее поле опусти или оставь пустым. "
    "Никакого текста кроме JSON.\n\nТЕКСТ:\n__GB_PROFILE_TEXT__"
)


def _llm_extract_profile(text: str) -> Optional[Dict[str, Any]]:
    """Ask the LIGHT LLM to pull profile fields from FREE-FORM text.

    Returns a loosely-keyed dict (name/role/department/experience/interests) or
    ``None`` on ANY failure (no creds / provider error / bad JSON) so the caller
    falls back to the deterministic frontmatter/JSON parser. Never raises. The
    physical send is bound to a ``gigabuddy_profile`` usage scope (the monetary
    authority). Extraction is grounded in the file text only — no fabrication."""
    body = (text or "").strip()
    if not body:
        return None
    prompt_text = body if len(body) <= _LLM_PROFILE_MAX_CHARS else (
        body[:_LLM_PROFILE_MAX_CHARS] + " …[профиль обрезан для извлечения]"
    )
    try:
        from dataclasses import replace as _replace

        from ouroboros import model_concurrency
        from ouroboros.config import get_light_model
        from ouroboros.llm import LLMClient
        from ouroboros.provider_models import resolve_credentialed_model
        from ouroboros.usage_accounting import (
            UsageScope,
            current_usage_scope,
            usage_scope,
        )

        model = resolve_credentialed_model(get_light_model())
        use_local = str(os.environ.get("USE_LOCAL_LIGHT", "") or "").lower() in ("true", "1")
        client = LLMClient()
        scope = current_usage_scope()
        if scope is not None:
            scope = _replace(scope, category="gigabuddy_profile", source="gigabuddy_profile")
        else:
            scope = UsageScope(
                drive_root=None,
                task_id="gigabuddy_profile",
                root_task_id="gigabuddy_profile",
                parent_task_id="",
                category="gigabuddy_profile",
                source="gigabuddy_profile",
            )
        chat_kwargs = dict(
            messages=[{
                "role": "user",
                "content": _PROFILE_LLM_PROMPT.replace("__GB_PROFILE_TEXT__", prompt_text),
            }],
            model=model,
            tools=None,
            reasoning_effort="low",
            max_tokens=2048,
            use_local=use_local,
            response_format={"type": "json_object"},
        )
        with model_concurrency.model_call_slot(model, use_local):
            with usage_scope(scope):
                msg, _usage = client.chat(**chat_kwargs)
        content = str((msg or {}).get("content") or "").strip()
        if not content:
            return None
        raw = content
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z0-9]*\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if not m:
                return None
            try:
                data = json.loads(m.group(0))
            except (ValueError, TypeError):
                return None
        if not isinstance(data, dict):
            return None
        # Keep only recognized, non-empty scalar/list fields (defence in depth).
        cleaned: Dict[str, Any] = {}
        for key in ("name", "role", "department", "experience"):
            val = data.get(key)
            if isinstance(val, (str, int, float)) and str(val).strip():
                cleaned[key] = str(val).strip()
        interests = data.get("interests")
        if interests:
            cleaned["interests"] = interests
        return cleaned or None
    except Exception:
        log.debug("GigaBuddy LLM profile extraction failed; using deterministic fallback", exc_info=True)
        return None


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
        raw = _scan_profile_text(text)
    if not isinstance(raw, dict) or not raw:
        return {}
    return _normalize_raw_profile(raw)


def extract_profile_flexible(text: str, *, is_json: bool) -> Dict[str, Any]:
    """Extract a profile fragment from ANY-FORM text (deterministic only).

    JSON is parsed as JSON. Non-JSON text is scanned for ``key: value`` pairs
    across all lines (bullet-list friendly). Fully fail-soft: any failure
    degrades to an empty fragment (neutral start). Never fabricates fields the
    source did not contain."""
    if not text or not text.strip():
        return {}
    return parse_profile_text(text, is_json=is_json)


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
        # Flexible extraction: JSON/frontmatter parse deterministically; free-form
        # text (no frontmatter name) falls to the LLM extractor, then fails soft.
        fragment = extract_profile_flexible(text, is_json=path.suffix.lower() == ".json")
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


# --- Profile summary (short UI card) -----------------------------------------

_SUMMARY_FILENAME = "profile_summary.json"
_SUMMARY_MAX_TAGS = 4
_SUMMARY_TAG_MAX_CHARS = 24

_SUMMARY_PROMPT = """Сожми профиль новичка в короткую карточку для UI наставника.

Верни ТОЛЬКО JSON одним объектом, без пояснений и markdown:
{"headline": "...", "tags": ["...", "..."]}

Правила:
- headline: имя, подразделение и 1-2 короткие фразы о роли и сильных сторонах.
  Образец: «Алиса Смирнова. Блок Люди и Культура. Первая роль в найме; сильна в
  коммуникации, осваивает внутренние регламенты».
- tags: 2-4 коротких хэштега (1-3 слова каждый) из интересных фактов анкеты —
  интересы, ритуалы, особенности. Образец: «командные ритуалы», «котики».
- Только факты из текста профиля, ничего не выдумывай.

Текст профиля:
__GB_PROFILE_TEXT__"""


def _summary_sidecar_path(employee_id: str) -> pathlib.Path:
    return employee_dir(employee_id) / _SUMMARY_FILENAME


def _fallback_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic summary when the LLM is unavailable: name + department,
    no tags. Never raises, never fabricates."""
    profile = profile if isinstance(profile, dict) else {}
    name = str(profile.get("name") or "").strip()
    department = str(profile.get("department") or "").strip()
    parts = [part for part in (name, department) if part]
    return {"headline": ". ".join(parts), "tags": []}


def _clean_llm_summary(data: Any, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(data, dict):
        return None
    headline = str(data.get("headline") or "").strip()
    if not headline:
        return None
    tags_raw = data.get("tags")
    tags: List[str] = []
    if isinstance(tags_raw, list):
        for item in tags_raw:
            tag = str(item or "").strip()[:_SUMMARY_TAG_MAX_CHARS]
            if tag and tag not in tags:
                tags.append(tag)
            if len(tags) >= _SUMMARY_MAX_TAGS:
                break
    return {"headline": headline[:400], "tags": tags}


def generate_profile_summary(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Build the short UI summary for one employee profile.

    ONE plain-text LIGHT call — NO ``response_format`` (cloud.ru rejects
    ``json_object``; known provider-strictness class). The JSON object is pulled
    out of the reply text with a ``{...}`` regex instead. ANY failure falls back
    to the deterministic name+department summary. Never raises.
    """
    profile = profile if isinstance(profile, dict) else {}
    text_bits = [
        str(profile.get(key) or "").strip()
        for key in ("name", "role", "department", "experience")
    ]
    interests = profile.get("interests")
    if isinstance(interests, list):
        text_bits.append("Интересы: " + ", ".join(str(i) for i in interests))
    body = "\n".join(bit for bit in text_bits if bit)
    if not body:
        return {"headline": "", "tags": []}
    prompt_text = body if len(body) <= _LLM_PROFILE_MAX_CHARS else body[:_LLM_PROFILE_MAX_CHARS]
    try:
        from dataclasses import replace as _replace

        from ouroboros import model_concurrency
        from ouroboros.config import get_light_model
        from ouroboros.llm import LLMClient
        from ouroboros.provider_models import resolve_credentialed_model
        from ouroboros.usage_accounting import (
            UsageScope,
            current_usage_scope,
            usage_scope,
        )

        model = resolve_credentialed_model(get_light_model())
        use_local = str(os.environ.get("USE_LOCAL_LIGHT", "") or "").lower() in ("true", "1")
        client = LLMClient()
        scope = current_usage_scope()
        if scope is not None:
            scope = _replace(scope, category="gigabuddy_profile", source="gigabuddy_profile")
        else:
            scope = UsageScope(
                drive_root=None,
                task_id="gigabuddy_profile",
                root_task_id="gigabuddy_profile",
                parent_task_id="",
                category="gigabuddy_profile",
                source="gigabuddy_profile",
            )
        chat_kwargs = dict(
            messages=[{
                "role": "user",
                "content": _SUMMARY_PROMPT.replace("__GB_PROFILE_TEXT__", prompt_text),
            }],
            model=model,
            tools=None,
            reasoning_effort="low",
            max_tokens=1024,
            use_local=use_local,
        )
        with model_concurrency.model_call_slot(model, use_local):
            with usage_scope(scope):
                msg, _usage = client.chat(**chat_kwargs)
        content = str((msg or {}).get("content") or "").strip()
        if not content:
            return _fallback_summary(profile)
        raw = content
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-zA-Z0-9]*\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return _fallback_summary(profile)
        try:
            data = json.loads(match.group(0))
        except (ValueError, TypeError):
            return _fallback_summary(profile)
        cleaned = _clean_llm_summary(data, profile)
        return cleaned if cleaned else _fallback_summary(profile)
    except Exception:
        log.debug("GigaBuddy profile summary LLM failed; deterministic fallback", exc_info=True)
        return _fallback_summary(profile)


def ensure_profile_summary(employee_id: str, profile: Dict[str, Any]) -> Dict[str, Any]:
    """Return the cached summary for the employee, generating it ONCE on first
    use. The cache is a per-employee sidecar (``profile_summary.json`` in the
    employee folder) so polls never regenerate and restarts keep the summary.
    Fail-soft: a read/write problem still yields a valid summary shape.
    """
    path = _summary_sidecar_path(employee_id)
    try:
        if path.is_file():
            cached = json.loads(path.read_text(encoding="utf-8"))
            cleaned = _clean_llm_summary(cached, profile) or _fallback_summary(profile)
            if cleaned.get("headline"):
                return cleaned
    except Exception:
        log.debug("GigaBuddy profile summary cache unreadable; regenerating", exc_info=True)
    summary = generate_profile_summary(profile)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        log.debug("GigaBuddy profile summary cache write failed", exc_info=True)
    return summary
