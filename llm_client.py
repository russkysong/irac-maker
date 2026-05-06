"""Provider abstraction for LLM chat calls.

Default: the local Ollama model (irac-maker).
Optional BYOK: xAI Grok via OpenAI-compatible endpoint.

The public `chat()` function mirrors `ollama.chat()`'s signature and
return shape so it's a drop-in replacement at every call site in
`irac_engine.py`. The active provider is read from Streamlit
session_state (set by the Settings tab UI) so users can switch
providers between runs without restarting the app.

Privacy contract:
- Default stays local — BYOK requires explicit user action in Settings.
- Reading session_state, not preferences directly, means a paused
  Streamlit run can't accidentally route traffic to a stale endpoint.
"""

from __future__ import annotations

from typing import Any, Iterator, Optional


# ── Settings access ───────────────────────────────────────────────────────────

_DEFAULTS = {
    "provider": "local",        # "local" | "xai"
    "api_key": "",
    "base_url": "https://api.x.ai/v1",
    "model": "grok-4-fast-non-reasoning",
}


def get_byok() -> dict:
    """Return current BYOK settings, reading from session_state with defaults.

    Falls back to all-local when invoked outside a Streamlit context (e.g.,
    unit tests, scripts), so importing this module never crashes.
    """
    try:
        import streamlit as st
        return {
            "provider": st.session_state.get("byok_provider") or _DEFAULTS["provider"],
            "api_key": st.session_state.get("byok_api_key") or _DEFAULTS["api_key"],
            "base_url": st.session_state.get("byok_base_url") or _DEFAULTS["base_url"],
            "model": st.session_state.get("byok_model") or _DEFAULTS["model"],
        }
    except Exception:
        return dict(_DEFAULTS)


def is_byok_active() -> bool:
    """True if the user has opted into BYOK *and* provided an API key."""
    s = get_byok()
    return s["provider"] != "local" and bool(s["api_key"].strip())


# ── Public API: drop-in replacement for ollama.chat() ────────────────────────

def chat(
    model: str,
    messages: list,
    stream: bool = False,
    format: Optional[str] = None,
    options: Optional[dict] = None,
    keep_alive: str = "30m",
    think: bool = False,
) -> Any:
    """Drop-in replacement for `ollama.chat()`.

    Returns the same shape ollama produces:
      • stream=False → ``{"message": {"content": "..."}}``
      • stream=True  → iterator of those dicts (one per token chunk)

    Provider-specific kwargs (`keep_alive`, `think`) are silently dropped on
    the xAI path. The xAI SDK reads `max_tokens` instead of `num_predict`.
    """
    if is_byok_active():
        return _chat_xai(messages, stream, format, options)
    return _chat_ollama(model, messages, stream, format, options,
                        keep_alive, think)


# ── Local (Ollama) path ──────────────────────────────────────────────────────

def _chat_ollama(model, messages, stream, format, options, keep_alive, think):
    import ollama
    kwargs = {"model": model, "messages": messages,
              "keep_alive": keep_alive, "think": think}
    if options is not None:
        kwargs["options"] = options
    if format:
        kwargs["format"] = format
    if stream:
        kwargs["stream"] = True
    return ollama.chat(**kwargs)


# ── xAI (Grok) path ──────────────────────────────────────────────────────────

def _chat_xai(messages, stream, format, options):
    """Route the call to xAI's OpenAI-compatible endpoint.

    Lazy import so users without the openai package can still run the app
    in local-only mode.
    """
    try:
        from openai import OpenAI
    except ImportError as e:
        raise RuntimeError(
            "BYOK requires the `openai` package. Install with: "
            "pip install openai>=1.0.0"
        ) from e

    s = get_byok()
    client = OpenAI(api_key=s["api_key"], base_url=s["base_url"])

    kwargs = {"model": s["model"], "messages": messages, "stream": stream}
    if options and "num_predict" in options:
        kwargs["max_tokens"] = options["num_predict"]
    if format == "json":
        # OpenAI-compatible APIs use this discriminated union.
        kwargs["response_format"] = {"type": "json_object"}

    resp = client.chat.completions.create(**kwargs)

    if stream:
        return _adapt_openai_stream(resp)
    content = ""
    try:
        content = resp.choices[0].message.content or ""
    except (AttributeError, IndexError):
        content = ""
    return {"message": {"content": content}}


def _adapt_openai_stream(stream) -> Iterator[dict]:
    """Translate OpenAI streaming chunks into Ollama's response shape.

    Each yielded dict matches what `ollama.chat(stream=True)` yields, so
    callers in irac_engine.py work unchanged.
    """
    for chunk in stream:
        try:
            delta = chunk.choices[0].delta.content or ""
        except (AttributeError, IndexError):
            delta = ""
        if delta:
            yield {"message": {"content": delta}}


# ── Connectivity test (used by the Settings UI's "Test connection" button) ──

def test_connection() -> tuple[bool, str]:
    """Make a 4-token call against the active provider. Returns (ok, msg).

    Does NOT consume the user's API budget meaningfully — max_tokens=4.
    """
    try:
        resp = chat(
            model="irac-maker",  # ignored on xai path
            messages=[{"role": "user", "content": "Reply with 'ok'."}],
            options={"num_predict": 4},
        )
        content = resp.get("message", {}).get("content", "").strip()
        if not content:
            return False, "Empty response from provider."
        return True, f"Connected. Reply: {content!r}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"
