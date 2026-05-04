"""Built-in (AI-generated, lazy-cached) rule-reference outlines.

One file per area-of-law under ~/.iracmaker/default_outlines/. Each file is
plain markdown with the area's rules, elements, exceptions, and defenses —
written by the local LLM the first time the area is requested, then reused.

The user can regenerate any outline (force fresh) or delete one (next request
will regenerate it).

This is distinct from outlines.py, which handles the user's own *uploaded*
study materials. Both feed the IRAC generator's prompt-context pipeline,
but only one source is active per generation (see app.py's outline_source
pill).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import List, Optional

OUTLINE_DIR = Path.home() / ".iracmaker" / "default_outlines"


# ── Filesystem helpers ─────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    OUTLINE_DIR.mkdir(parents=True, exist_ok=True)


def _slug(area: str) -> str:
    """Filesystem-safe filename from an area-of-law string."""
    return area.replace(" ", "_").replace("/", "_")


def _path(area: str) -> Path:
    return OUTLINE_DIR / f"{_slug(area)}.txt"


# ── Public API ────────────────────────────────────────────────────────────────

def exists(area: str) -> bool:
    return _path(area).exists()


def load(area: str) -> str:
    p = _path(area)
    if not p.exists():
        return ""
    try:
        return p.read_text()
    except OSError:
        return ""


def save(area: str, text: str) -> None:
    _ensure_dir()
    _path(area).write_text(text)


def delete(area: str) -> None:
    p = _path(area)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def get_or_generate(area: str) -> str:
    """Return the cached outline for `area`, generating + caching it on first use.

    Importing `irac_engine` lazily so this module stays unit-testable without
    Ollama installed.
    """
    if exists(area):
        return load(area)
    try:
        from irac_engine import generate_default_outline
        text = generate_default_outline(area)
        if text.strip():
            save(area, text)
        return text
    except Exception:
        # If generation fails, return empty — caller falls back to no-context.
        return ""


def regenerate(area: str) -> str:
    """Force a fresh generation, overwriting the cached file."""
    delete(area)
    return get_or_generate(area)


def status(area: str) -> dict:
    """Metadata snapshot for the My Outlines UI list."""
    p = _path(area)
    if not p.exists():
        return {
            "area": area,
            "exists": False,
            "char_count": 0,
            "generated_at": None,
        }
    try:
        s = p.stat()
        return {
            "area": area,
            "exists": True,
            "char_count": s.st_size,
            "generated_at": datetime.fromtimestamp(s.st_mtime).isoformat(timespec="seconds"),
        }
    except OSError:
        return {
            "area": area,
            "exists": False,
            "char_count": 0,
            "generated_at": None,
        }


def status_all(areas: List[str]) -> List[dict]:
    return [status(a) for a in areas]


def find_path(area: str) -> Optional[Path]:
    """Return the on-disk path for the area's outline if it exists, else None."""
    p = _path(area)
    return p if p.exists() else None
