"""Local-only outline storage + retrieval for the My Outlines feature.

Files live under ~/.iracmaker/outlines/ and never leave the user's machine.
Each outline is a pair: an entry in index.json (metadata) plus a sibling
<id>.txt file holding the extracted plain text. Storing text separately
keeps index.json tiny so it loads on every Streamlit rerun.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import List

OUTLINES_DIR = Path.home() / ".iracmaker" / "outlines"
INDEX_FILE = OUTLINES_DIR / "index.json"


# ── Filesystem helpers ─────────────────────────────────────────────────────────

def _ensure_dir() -> None:
    OUTLINES_DIR.mkdir(parents=True, exist_ok=True)


def load_index() -> List[dict]:
    """Returns the manifest of all uploaded outlines (newest first)."""
    _ensure_dir()
    if not INDEX_FILE.exists():
        return []
    try:
        items = json.loads(INDEX_FILE.read_text())
        return list(items) if isinstance(items, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_index(items: List[dict]) -> None:
    _ensure_dir()
    INDEX_FILE.write_text(json.dumps(items, indent=2))


# ── Text extraction ────────────────────────────────────────────────────────────

def extract_text(filename: str, content: bytes) -> str:
    """Pull plain text out of a PDF / DOCX / TXT / MD byte blob.

    Raises ImportError if the user hasn't installed pypdf or python-docx
    (caller surfaces this as a "reinstall deps" message).
    """
    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        from pypdf import PdfReader  # noqa: import-positioned-here-for-graceful-degrade
        reader = PdfReader(BytesIO(content))
        pages = []
        for p in reader.pages:
            try:
                pages.append(p.extract_text() or "")
            except Exception:
                # A single corrupt page shouldn't take down the whole upload.
                continue
        return "\n\n".join(pages)

    if suffix == ".docx":
        from docx import Document  # noqa: same — defer import for clean error
        doc = Document(BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text)

    # .txt / .md / anything else — best-effort utf-8 decode.
    return content.decode("utf-8", errors="replace")


# ── CRUD ───────────────────────────────────────────────────────────────────────

def add_outline(filename: str, area: str, content: bytes) -> dict:
    """Save a new outline. Returns its metadata entry.

    Raises ValueError if no usable text could be extracted (e.g., scanned
    PDF with no embedded text layer).
    """
    _ensure_dir()
    text = extract_text(filename, content)
    if not text.strip():
        raise ValueError(
            "Could not extract any text from this file. If it's a scanned "
            "PDF, you'll need to OCR it first."
        )

    item_id = uuid.uuid4().hex[:8]
    text_path = OUTLINES_DIR / f"{item_id}.txt"
    text_path.write_text(text)

    meta = {
        "id": item_id,
        "filename": filename,
        "area": area,
        "char_count": len(text),
        "uploaded_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
    items = load_index()
    items.insert(0, meta)  # newest first
    save_index(items)
    return meta


def delete_outline(item_id: str) -> None:
    items = [i for i in load_index() if i.get("id") != item_id]
    save_index(items)
    text_path = OUTLINES_DIR / f"{item_id}.txt"
    if text_path.exists():
        try:
            text_path.unlink()
        except OSError:
            pass  # leave the orphan file rather than crash the UI


def get_outline_text(item_id: str) -> str:
    text_path = OUTLINES_DIR / f"{item_id}.txt"
    return text_path.read_text() if text_path.exists() else ""


# ── Retrieval (poor man's RAG) ─────────────────────────────────────────────────

# Tiny stop-word list — kept inline so we don't pull in nltk for nothing.
_STOPWORDS = {
    "the", "and", "for", "that", "this", "with", "from", "have", "been",
    "were", "their", "they", "them", "would", "could", "should", "shall",
    "will", "into", "when", "what", "where", "which", "while", "after",
    "before", "between", "because", "about", "above", "below", "under",
    "over", "during", "such", "than", "then", "more", "most",
    "some", "other", "another", "each", "every", "both", "either",
    "neither", "also", "only", "very", "just", "even", "still", "again",
    "thus", "hence", "however", "moreover", "therefore",
}


def _keywords(facts: str, n: int = 15) -> List[str]:
    """Pull up to N candidate keywords (≥4 chars, non-stop-word) from facts.

    Order matters (we iterate keywords in fact-pattern order looking for hits
    in outlines), but membership-check needs O(1) — so we keep both an ordered
    list and a set for dedup.
    """
    words = re.findall(r"\b[A-Za-z][A-Za-z'-]{3,}\b", facts.lower())
    seen_set: set = set()
    seen_list: List[str] = []
    for w in words:
        if w in _STOPWORDS or w in seen_set:
            continue
        seen_set.add(w)
        seen_list.append(w)
        if len(seen_list) >= n:
            break
    return seen_list


def relevant_excerpts(facts: str, area: str, max_chars: int = 4000) -> str:
    """Concatenate keyword-matched windows from outlines tagged `area`.

    Returns "" when no outlines exist for the area or no keyword hits.
    Excerpts are 600 chars centered on the first hit, prefixed with a
    `--- From <filename> ---` header so the LLM can attribute paraphrases.
    """
    items = [i for i in load_index() if i.get("area") == area]
    if not items:
        return ""

    keywords = _keywords(facts)
    if not keywords:
        return ""

    excerpts: List[str] = []
    chars_used = 0

    for item in items:
        if chars_used >= max_chars:
            break
        text = get_outline_text(item.get("id", ""))
        if not text:
            continue
        text_lower = text.lower()

        for kw in keywords:
            idx = text_lower.find(kw)
            if idx < 0:
                continue
            start = max(0, idx - 200)
            end = min(len(text), idx + 400)
            window = text[start:end].strip()
            if not window:
                continue
            block = f"--- From {item.get('filename', 'outline')} ---\n{window}"
            excerpts.append(block)
            chars_used += len(block)
            break  # one excerpt per outline is enough — keep variety

    return "\n\n".join(excerpts)
