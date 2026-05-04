"""Tiny disk-persistent user preferences.

Stores `current_area`, `cmp_mode`, and any other small UI prefs we want to
survive an app restart. Lives at ~/.iracmaker/preferences.json (same root
as outlines/ and history/, so a single rm -rf wipes everything).

Failures are silent: if the file can't be read or written, the app keeps
working on session-state defaults. Prefs are an enhancement, not critical.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

PREFS_FILE = Path.home() / ".iracmaker" / "preferences.json"


def load() -> Dict[str, Any]:
    if not PREFS_FILE.exists():
        return {}
    try:
        data = json.loads(PREFS_FILE.read_text())
        return dict(data) if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save(prefs: Dict[str, Any]) -> None:
    try:
        PREFS_FILE.parent.mkdir(parents=True, exist_ok=True)
        PREFS_FILE.write_text(json.dumps(prefs, indent=2))
    except OSError:
        # Disk full, perms denied, etc — silently drop. Worst case the user's
        # prefs reset on next launch, which is harmless.
        pass
