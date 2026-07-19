"""GigaBuddy built-in demo profiles (pure data).

Alice/Leonid are LOADABLE demo configs the owner swaps in by hand for the demo
(via the ``load_profile`` action). They are deliberately NOT the hardcoded
default state (the default is the neutral, nameless newcomer — see
``gigabuddy_state.default_gigabuddy_state``).

Extracted from ``gigabuddy_state`` to keep that reducer module under the
``review.MAX_MODULE_LINES`` gate (P7 module-size discipline). This module is
pure data + one read-only helper; it imports nothing from the reducer, so there
is no import cycle.
"""

from __future__ import annotations

from typing import Any, Dict, List

# Loadable built-in demo profiles. Each spec is a reducer-mergeable fragment
# (name/role/profile/interface) applied via ``_apply_profile_fragment``; the
# subsequent normalize pass validates every field (allow-lists, hex accent, caps).
DEMO_PROFILES: Dict[str, Dict[str, Any]] = {
    "alice-demo": {
        "name": "Алиса",
        "role": "HR · Люди и культура",
        "profile": {
            "name": "Алиса",
            "role": "HR · Люди и культура",
            "department": "Люди и культура",
            "experience": "Первая роль в найме; сильна в коммуникации, осваивает внутренние регламенты.",
            "interests": ["котики", "иллюстрация", "командные ритуалы"],
        },
        "interface": {"theme": "soft-cat", "accent_color": "#e8799f", "mascot": "🐾", "tone": "playful"},
    },
    "leonid-demo": {
        "name": "Леонид",
        "role": "Разработчик · внутренний переход",
        "profile": {
            "name": "Леонид",
            "role": "Разработчик · внутренний переход",
            "department": "Инженерия платформы",
            "experience": "Опытный разработчик; переходит между командами, нужен быстрый деловой тон.",
            "interests": ["распределённые системы", "надёжность", "code review"],
        },
        "interface": {"theme": "strict-terminal", "accent_color": "#5ad1c9", "mascot": "⌘", "tone": "formal"},
    },
}


def list_demo_profiles() -> List[Dict[str, str]]:
    """Loadable built-in demo profiles (id + display name) for the owner switcher."""
    return [
        {"id": pid, "name": str(spec.get("name") or pid)}
        for pid, spec in DEMO_PROFILES.items()
    ]
