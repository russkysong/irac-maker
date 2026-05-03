"""Local-only persistence for past IRACs and Case Briefs.

Files live under ~/.iracmaker/history/ — one JSON per entry, newest first
when listed. The data never leaves the user's machine and the repo never
sees it.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

HISTORY_DIR = Path.home() / ".iracmaker" / "history"


# ── Filesystem helpers ─────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _truncate(s: str, n: int = 90) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s if len(s) <= n else s[: n - 1] + "…"


def _entry_path(entry_id: str) -> Path:
    return HISTORY_DIR / f"{entry_id}.json"


# ── Save / Delete / Load ───────────────────────────────────────────────────────

def save_irac(facts: str, area: str, result_dict: dict) -> dict:
    """Persist an IRAC generation. Returns the saved entry metadata."""
    _ensure_dir()
    entry = {
        "id": _new_id(),
        "type": "irac",
        "title": _truncate(result_dict.get("issue", "(untitled)"), 90),
        "area": area,
        "facts": facts.strip(),
        "result": result_dict,
        "saved_at": _now(),
    }
    _entry_path(entry["id"]).write_text(json.dumps(entry, indent=2))
    return entry


def save_brief(case_text: str, result_dict: dict) -> dict:
    """Persist a Case Brief generation. Returns the saved entry metadata."""
    _ensure_dir()
    title = result_dict.get("case_name") or _truncate(result_dict.get("issue", "(untitled brief)"), 90)
    entry = {
        "id": _new_id(),
        "type": "brief",
        "title": _truncate(title, 90),
        "area": None,
        "case_text": case_text.strip(),
        "result": result_dict,
        "saved_at": _now(),
    }
    _entry_path(entry["id"]).write_text(json.dumps(entry, indent=2))
    return entry


def save_essay(facts: str, area: str, essay: str, result_dict: dict) -> dict:
    """Persist a Long-form Essay grading. Returns the saved entry metadata.

    Title combines the overall grade with the first line of facts so the
    History list shows at-a-glance which essay it was.
    """
    _ensure_dir()
    grade = result_dict.get("overall_grade", "—")
    first_line = _truncate((facts.strip().split("\n", 1)[0] or "(untitled essay)"), 60)
    entry = {
        "id": _new_id(),
        "type": "essay",
        "title": _truncate(f"Essay {grade} — {first_line}", 90),
        "area": area,
        "facts": facts.strip(),
        "essay": essay.strip(),
        "result": result_dict,
        "saved_at": _now(),
    }
    _entry_path(entry["id"]).write_text(json.dumps(entry, indent=2))
    return entry


def save_spot(facts: str, area: str, student_issues: str, result_dict: dict) -> dict:
    """Persist an Issue Spotting drill. Returns the saved entry metadata.

    Title is the coverage score + first line of facts so the History list
    shows at-a-glance which drill it was.
    """
    _ensure_dir()
    score = result_dict.get("coverage_score", "—")
    first_line = _truncate((facts.strip().split("\n", 1)[0] or "(untitled drill)"), 60)
    entry = {
        "id": _new_id(),
        "type": "spot",
        "title": _truncate(f"Spot {score} — {first_line}", 90),
        "area": area,
        "facts": facts.strip(),
        "student_issues": student_issues.strip(),
        "result": result_dict,
        "saved_at": _now(),
    }
    _entry_path(entry["id"]).write_text(json.dumps(entry, indent=2))
    return entry


def delete_entry(entry_id: str) -> None:
    p = _entry_path(entry_id)
    if p.exists():
        try:
            p.unlink()
        except OSError:
            pass


def load_history() -> List[dict]:
    """Returns all saved entries, newest first. Skips unparseable files."""
    _ensure_dir()
    entries: List[dict] = []
    for p in HISTORY_DIR.glob("*.json"):
        try:
            entries.append(json.loads(p.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    entries.sort(key=lambda e: e.get("saved_at", ""), reverse=True)
    return entries


def get_entry(entry_id: str) -> Optional[dict]:
    p = _entry_path(entry_id)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


# ── Search ────────────────────────────────────────────────────────────────────

def filter_history(query: str = "", entry_type: str = "all",
                   area: str = "all") -> List[dict]:
    """Lightweight client-side filter for the History tab list view."""
    entries = load_history()
    if entry_type != "all":
        entries = [e for e in entries if e.get("type") == entry_type]
    if area != "all":
        entries = [e for e in entries if e.get("area") == area]
    if query.strip():
        pat = re.compile(re.escape(query.strip()), re.IGNORECASE)
        entries = [
            e for e in entries
            if pat.search(e.get("title", "")) or pat.search(json.dumps(e.get("result", {})))
        ]
    return entries
