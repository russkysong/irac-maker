import html
from datetime import datetime, timezone

import streamlit as st
import styles
import components as C
import outlines
import history
import preferences
from irac_engine import (
    compare_irac, grade_issue_spot, grade_essay, generate_mbe_question,
    generate_hypo,
    socratic_next_question, check_model_ready, AREAS_OF_LAW,
)
from export import export_to_pdf

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="IRAC Maker", page_icon="⚖️", layout="wide")
styles.inject()

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="irac-header">
    <div class="irac-logo">⚖️ IRAC<span class="irac-logo-accent"> Maker</span></div>
    <div class="irac-tagline">AI-powered legal writing practice for law school students</div>
</div>
""", unsafe_allow_html=True)

def _safe_area(value, default: str = "Contracts") -> str:
    """Normalize an area-of-law string to a known value.

    Defends against stale/corrupted session_state values that could end up
    in the LLM prompt. Only the dialog picker writes these keys today, but
    a forgotten test value or an old saved session could otherwise leak
    through to generation.
    """
    return value if value in AREAS_OF_LAW else default


@st.cache_resource(show_spinner="Warming up the model…")
def _model_ready_cached() -> bool:
    """Check that the model exists AND force it into VRAM with a tiny call.

    Without warm-up, the user's first real request pays the 10-30s model-load
    cost with no UI feedback. With it, that cost is paid once during the
    Streamlit "Loading…" spinner before the page even renders, and every
    subsequent interaction (within keep_alive=30m) is instant.

    Cached via @st.cache_resource so this runs ONCE per session even though
    Streamlit reruns the whole script on every interaction.
    """
    if not check_model_ready():
        return False
    try:
        import ollama
        from irac_engine import MODEL_NAME
        ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": "ready"}],
            options={"num_predict": 4},
            keep_alive="30m",
            think=False,
        )
    except Exception:
        # Even if warm-up fails (network blip, transient ollama issue), the
        # existence check passed — let the user proceed; their first real
        # request will trigger the load with the regular spinner.
        pass
    return True

if not _model_ready_cached():
    st.error("**Model not found.** Run setup first:\n\n```bash\nbash setup.sh\n```", icon="🔴")
    st.stop()

# ── Session state ──────────────────────────────────────────────────────────────
DEFAULTS = {
    "last_irac": None, "last_facts": "",
    # Single source of truth for area-of-law across all 11 tabs. Pick once
    # via the chip in any tab — every other tab reads the same value.
    "current_area": "Contracts",
    # First-run gate — flips to True once the user explicitly picks an area
    # via pick_area_dialog. Returning users with `current_area` in the prefs
    # file get area_confirmed=True at startup so they skip the welcome card.
    "area_confirmed": False,
    # Rule-outline source for IRAC generation (My Outlines tab pill).
    # "mine" = uploaded files, "default" = built-in AI-generated outlines,
    # "none" = no context, LLM uses its own training knowledge.
    "outline_source": "default",
    # Current topic within current_area for hypo generation. Empty string
    # means "(any)" — the LLM picks a topic. Auto-resets when current_area
    # changes (see the validity guard right after the prefs hydrate block).
    "current_topic": "",
    "socratic_history": [], "socratic_facts": "", "socratic_area": "Contracts",
    "socratic_started": False,
    # MBE Practice state
    "mbe_question": None, "mbe_user_answer": None, "mbe_submitted": False,
    "mbe_correct_count": 0, "mbe_total_count": 0,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Persistent UI preferences ──────────────────────────────────────────────────
# Load saved prefs and seed session_state for keys that aren't already set.
# Saving happens via _persist_prefs() at the bottom of every script run.
_PERSISTED_KEYS = ("current_area", "cmp_mode", "outline_source")
_saved_prefs = preferences.load()
for _k in _PERSISTED_KEYS:
    if _k in _saved_prefs and _k not in st.session_state:
        st.session_state[_k] = _saved_prefs[_k]

# Returning user — they already picked an area in a past session, so skip
# the welcome gate. We use `setdefault` so reruns within a session don't
# clobber a freshly-flipped flag.
if "current_area" in _saved_prefs:
    st.session_state["area_confirmed"] = True


def _persist_prefs() -> None:
    """Write current values of persisted keys to disk if they've changed.

    Called once at the end of each script run. We compare against the snapshot
    we loaded so we only hit disk when something actually moved.
    """
    snapshot = {k: st.session_state.get(k) for k in _PERSISTED_KEYS
                if k in st.session_state}
    if snapshot != _saved_prefs:
        preferences.save(snapshot)

# ── First-run welcome gate ────────────────────────────────────────────────────
# Generation-tab inputs are disabled (`_locked`) until the user explicitly
# confirms an area-of-law pick. The welcome card below appears only on first
# run — once `area_confirmed` flips True (via pick_area_dialog), the card
# stops rendering and `_locked` becomes False. Library tabs are unaffected.
_locked = not st.session_state.get("area_confirmed", False)

if _locked:
    st.markdown("""
<div class="irac-card irac-card-accent"
     style="margin-bottom:1.25rem;padding:22px 26px;text-align:center;">
    <div style="font-size:1.6rem;margin-bottom:0.4rem;">👋</div>
    <div style="font-family:Poppins,sans-serif;font-size:17px;font-weight:600;
                color:#faf9f5;margin-bottom:0.5rem;">
        Welcome — pick your Area of Law to start
    </div>
    <div style="font-family:Lora,serif;font-size:13.5px;color:#b0aea5;
                line-height:1.6;">
        Every IRAC, brief, and drill needs to know which area of doctrine
        to use. Pick once below — your choice is saved and you can change
        it any time from the chip in any tab.
    </div>
</div>
""", unsafe_allow_html=True)
    _gate_col_l, _gate_col_pick, _gate_col_r = st.columns([1, 2, 1])
    with _gate_col_pick:
        _gate_area = _safe_area(st.session_state.get("current_area"))
        if st.button(
            f"⚖️ Pick Area of Law — currently {_gate_area}",
            key="gate_area_btn",
            use_container_width=True,
            type="primary",
        ):
            C.pick_area_dialog("current_area")
    st.divider()

# ── Topic validity guard ──────────────────────────────────────────────────────
# If the user picks a new area, their previously-set topic may no longer be
# valid (e.g. "Agency" is a Business Associations topic but not a Torts topic).
# Reset current_topic in that case so the topic chip falls back to "(any)".
from irac_engine import AREA_TOPICS as _AREA_TOPICS
_active_area_topics = _AREA_TOPICS.get(st.session_state.get("current_area", ""), [])
if st.session_state.get("current_topic") and st.session_state["current_topic"] not in _active_area_topics:
    st.session_state["current_topic"] = ""

# ── Tabs ───────────────────────────────────────────────────────────────────────
# Two-level structure: 3 category tabs at the top, sub-tabs inside each.
# We keep the original tab_xxx variable names (declared inside the appropriate
# `with top_*:` block) so every existing `with tab_xxx:` block elsewhere in the
# file still works without renaming. The DeltaGenerator each variable points to
# is now a sub-tab that lives inside its parent category — Streamlit handles
# rendering to the right place even when `with tab_xxx:` is used outside the
# parent's `with` block.
top_gen, top_practice, top_library = st.tabs(["Generate", "Practice", "Library"])

with top_gen:
    tab_gen, tab_brief, tab_both = st.tabs([
        "IRAC", "Case Brief", "Both Sides",
    ])

with top_practice:
    tab_spot, tab_mbe, tab_cmp, tab_essay, tab_soc = st.tabs([
        "Issue Spotting", "MBE Practice", "Compare & Feedback",
        "Long Essay", "Socratic Mode",
    ])

with top_library:
    tab_outlines, tab_history, tab_about = st.tabs([
        "My Outlines", "History", "About",
    ])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ════════════════════════════════════════════════════════════════════════════════
with tab_gen:
    # ── Setup (full width, single column) ─────────────────────────────────────
    _area = _safe_area(st.session_state.get("current_area"))
    if st.button(f"⚖️ Area of Law: {_area}", key="btn_area_gen"):
        C.pick_area_dialog("current_area")
    area_gen = _area
    facts_gen = st.text_area(
        "Facts", height=260, key="facts_gen",
        disabled=_locked,
        placeholder=(
            "Paste or type your fact pattern here...\n\n"
            "e.g. Alice offered to sell her 2020 Honda Civic for $12,000. "
            "Bob replied '$11,500.' Alice said 'Deal at $11,800.' "
            "Bob showed up three days later — Alice had already sold to Carol."
        ),
    )
    col_a, col_b = st.columns([3, 2])
    with col_a:
        gen_btn = st.button("Generate IRAC", type="primary", use_container_width=True, disabled=_locked)
    with col_b:
        zoom_btn = st.button("Issue Map First", use_container_width=True, disabled=_locked, help="See all issues before full analysis")

    st.divider()

    # ── Analysis (full width, single column) ──────────────────────────────────
    st.markdown('<div class="section-label">Analysis</div>', unsafe_allow_html=True)

    if zoom_btn:
        if not facts_gen.strip():
            st.warning("Paste your facts first.")
        else:
            try:
                issue_map_text = C.stream_issue_map_with_progress(facts_gen, area_gen)
                st.markdown(
                    f'<div class="irac-card irac-card-blue" style="animation:slideInRight 0.4s ease;">'
                    f'{issue_map_text}</div>',
                    unsafe_allow_html=True,
                )
                st.info("Click **Generate IRAC** to analyze a specific issue in depth.")
            except Exception as e:
                st.error(f"Issue map failed: {e}")

    elif gen_btn:
        if not facts_gen.strip():
            st.warning("Paste your facts first.")
        else:
            try:
                result = C.stream_with_progress(facts_gen, area_gen)
                st.session_state.last_irac = result
                st.session_state.last_facts = facts_gen
                st.session_state.current_area = area_gen
                # Auto-save to ~/.iracmaker/history/. Failures here shouldn't
                # block showing the IRAC, so swallow exceptions silently.
                try:
                    history.save_irac(facts_gen, area_gen, result.model_dump())
                except Exception:
                    pass
                C.show_irreac(result)
                st.divider()
                pdf_bytes = export_to_pdf(result, facts_gen, area_gen)
                st.download_button(
                    "Download as PDF", data=pdf_bytes,
                    file_name="irac_analysis.pdf", mime="application/pdf",
                    use_container_width=True,
                )
                st.success("Switch to **Compare & Feedback** to grade your own draft against this.")
            except Exception as e:
                st.error(f"Generation failed: {e}")
    else:
        st.markdown("""
<div class="irac-card" style="text-align:center;padding:3rem 2rem;border-style:dashed;">
    <div style="font-size:2rem;margin-bottom:1rem;">⚖️</div>
    <div style="font-family:Poppins,sans-serif;font-size:14px;color:#b0aea5;">
        Paste your hypo and click <strong style="color:#d97757;">Generate IRAC</strong><br>
        or use <strong style="color:#6a9bcc;">Issue Map First</strong> to see all issues before diving in.
    </div>
</div>
""", unsafe_allow_html=True)

    # ── "How IRAC Works" — full-width, below ──────────────────────────────────
    st.divider()
    st.markdown('<div class="section-label">How IRAC Works</div>', unsafe_allow_html=True)
    st.markdown("""
<p style="font-family:Lora,serif;font-size:12.5px;color:#b0aea5;line-height:1.55;margin-bottom:0.4rem;">
<strong style="color:#e8e6dc;">IRAC</strong> is the standard legal reasoning framework used in American law schools and on the bar exam.
</p>

<table class="how-irac-table">
    <colgroup>
        <col style="width: 170px;">
        <col>
    </colgroup>
    <thead>
        <tr><th>Step</th><th>What it covers</th></tr>
    </thead>
    <tbody>
        <tr><td><strong>I — Issue</strong></td><td>The precise legal question the court must answer</td></tr>
        <tr><td><strong>R — Rule</strong></td><td>The applicable rule with citation — statute, restatement section, or landmark case</td></tr>
        <tr><td><strong>A — Application</strong></td><td>Each rule element applied to the specific facts — <strong style="color:#faf9f5;">this is where exam points are won or lost</strong></td></tr>
        <tr><td><strong>C — Conclusion</strong></td><td>A direct answer to the Issue, with a confidence level</td></tr>
    </tbody>
</table>

<p style="font-family:Lora,serif;font-size:12px;color:#6e6c65;font-style:italic;line-height:1.55;margin-top:0.5rem;">
<strong style="color:#b0aea5;font-style:normal;">Note:</strong> The AI breaks the Rule into two parts — what the rule says, and how courts have interpreted it. Richer than a basic IRAC outline.
</p>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — CASE BRIEF
# ════════════════════════════════════════════════════════════════════════════════
with tab_brief:
    st.markdown("""
<div class="irac-card irac-card-blue" style="margin-bottom:1.5rem;">
    <div class="section-label" style="color:#6a9bcc;">Case Brief</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        Paste a case opinion and get a structured brief — Facts, Procedural Posture,
        Issue, Holding, Reasoning, Dissent, and exam notes. Built for the cold-call
        moments and the night-before-exam review.
    </p>
</div>
""", unsafe_allow_html=True)

    case_text = st.text_area(
        "Case opinion",
        height=320,
        key="case_text",
        disabled=_locked,
        placeholder=(
            "Paste the full opinion (or a long excerpt) here.\n\n"
            "Tip: include the case caption (Plaintiff v. Defendant, Cite, Year) "
            "if you have it — the brief will use the proper citation."
        ),
    )
    brief_btn = st.button(
        "Generate Brief",
        type="primary",
        use_container_width=True,
        disabled=_locked,
        key="brief_btn",
    )

    if brief_btn:
        if not case_text.strip():
            st.warning("Paste a case opinion first.")
        elif len(case_text.strip()) < 200:
            st.warning("This looks too short to be a case opinion. Paste more text.")
        else:
            try:
                brief = C.stream_brief_with_progress(case_text)
                st.session_state.last_brief = brief
                try:
                    history.save_brief(case_text, brief.model_dump())
                except Exception:
                    pass
                C.show_case_brief(brief)
            except Exception as e:
                st.error(f"Brief failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — BOTH SIDES
# ════════════════════════════════════════════════════════════════════════════════
with tab_both:
    st.markdown("""
<div class="irac-card irac-card-accent" style="margin-bottom:1.5rem;">
    <div class="section-label">Design It Twice — Both Sides</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        Generates the <strong style="color:#d97757;">plaintiff's strongest IRAC</strong> and the
        <strong style="color:#6a9bcc;">defendant's strongest IRAC</strong> side by side.
        Seeing competing analyses sharpens your own reasoning.
    </p>
</div>
""", unsafe_allow_html=True)

    _area_bs = _safe_area(st.session_state.get("current_area"))
    if st.button(f"⚖️ Area of Law: {_area_bs}", key="btn_area_bs"):
        C.pick_area_dialog("current_area")
    area_bs = _area_bs
    facts_bs = st.text_area("Facts", height=180, key="facts_bs",
                            disabled=_locked,
                            placeholder="Paste the fact pattern here...")
    both_btn = st.button("Generate Both Sides", type="primary",
                         use_container_width=True, disabled=_locked)

    if both_btn:
        if not facts_bs.strip():
            st.warning("Paste facts first.")
        else:
            try:
                # Sequential streaming — Ollama can't truly parallelize on this
                # hardware (proven slower in benchmarks), so we get the same
                # total time AND real progress feedback per side.
                p_result = C.stream_with_progress(
                    facts_bs, area_bs, start_pct=0, end_pct=50,
                    phase="Building plaintiff's argument",
                )
                d_result = C.stream_with_progress(
                    facts_bs, area_bs, start_pct=50, end_pct=100,
                    phase="Building defendant's argument",
                )
                # Default to plaintiff for cross-tab handoff to Compare/PDF.
                st.session_state.last_irac = p_result
                st.session_state.last_facts = facts_bs
                st.session_state.current_area = area_bs
                st.divider()
                # Stacked vertical layout — plaintiff first, then defendant.
                st.markdown('<div class="section-label" style="color:#d97757;">Plaintiff\'s Best Argument</div>', unsafe_allow_html=True)
                C.show_irreac(p_result)
                st.divider()
                st.markdown('<div class="section-label" style="color:#6a9bcc;">Defendant\'s Best Argument</div>', unsafe_allow_html=True)
                C.show_irreac(d_result)
            except Exception as e:
                st.error(f"Generation failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 4 — ISSUE SPOTTING
# ════════════════════════════════════════════════════════════════════════════════
with tab_spot:
    st.markdown("""
<div class="irac-card irac-card-accent" style="margin-bottom:1.5rem;">
    <div class="section-label">Issue Spotting Drill</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        A fast-feedback exercise — paste a hypo, list every legal issue you can spot
        (one per line), and get scored on coverage. The grader returns what you caught,
        what you missed, and any false alarms. No full IRAC required.
    </p>
</div>
""", unsafe_allow_html=True)

    _area_spot = _safe_area(st.session_state.get("current_area"))
    _topic_spot = st.session_state.get("current_topic") or ""
    _topic_label_spot = _topic_spot if _topic_spot else "(any)"
    _has_topics_spot = bool(_AREA_TOPICS.get(_area_spot))
    col_area_spot, col_topic_spot, col_hypo_spot = st.columns([2, 2, 1])
    with col_area_spot:
        if st.button(f"⚖️ Area: {_area_spot}", key="btn_area_spot",
                     use_container_width=True):
            C.pick_area_dialog("current_area")
    with col_topic_spot:
        if st.button(
            f"🏷 Topic: {_topic_label_spot}",
            key="btn_topic_spot",
            use_container_width=True,
            disabled=_locked or not _has_topics_spot,
            help="Pick a sub-topic to anchor the hypo (optional)." if _has_topics_spot else "No sub-topics defined for this area.",
        ):
            C.pick_topic_dialog(_area_spot, "current_topic")
    area_spot = _area_spot
    with col_hypo_spot:
        if st.button("⚡ Generate hypo", key="hypo_spot",
                     use_container_width=True,
                     disabled=_locked,
                     help="Have the AI write a fresh fact pattern in this area."):
            try:
                with st.spinner("Drafting a fresh hypo..."):
                    # Issue Spotting: no call-of-question (would hint at issues).
                    st.session_state["facts_spot"] = generate_hypo(
                        area_spot, "Multi-issue",
                        topic=_topic_spot, include_call=False,
                    )
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't draft hypo: {e}")

    facts_spot = st.text_area(
        "Facts",
        height=200,
        key="facts_spot",
        disabled=_locked,
        placeholder="Paste the fact pattern here, or click ⚡ Generate hypo.",
    )
    issues_spot = st.text_area(
        "Issues you spotted (one per line)",
        height=180,
        key="issues_spot",
        disabled=_locked,
        placeholder=(
            "List each issue you see. One per line. Loose phrasing is fine.\n\n"
            "e.g.\n"
            "- Mirror image rule / counter-offer\n"
            "- Statute of frauds (sale of goods over $500)\n"
            "- Promissory estoppel"
        ),
    )

    spot_btn = st.button(
        "Grade my spotting",
        type="primary",
        use_container_width=True,
        disabled=_locked,
        key="spot_btn",
    )

    if spot_btn:
        if not facts_spot.strip():
            st.warning("Paste facts first.")
        elif not issues_spot.strip():
            st.warning("List at least one issue you think you spotted.")
        else:
            try:
                spot_result = C.run_with_time_progress(
                    grade_issue_spot,
                    phase="Grading your spotting",
                    est_seconds=35,
                    sublabels=[
                        (0,  "Reading the facts..."),
                        (30, "Identifying every real issue..."),
                        (65, "Matching against your list..."),
                        (88, "Scoring coverage and writing feedback..."),
                    ],
                    facts=facts_spot, area=area_spot,
                    student_issues=issues_spot,
                )
                # Auto-save to history (non-blocking).
                try:
                    history.save_spot(facts_spot, area_spot, issues_spot,
                                      spot_result.model_dump())
                except Exception:
                    pass
                st.divider()
                C.show_issue_spotting(spot_result)
            except Exception as e:
                st.error(f"Grading failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 5 — MBE PRACTICE
# ════════════════════════════════════════════════════════════════════════════════
with tab_mbe:
    st.markdown("""
<div class="irac-card irac-card-blue" style="margin-bottom:1.5rem;">
    <div class="section-label" style="color:#6a9bcc;">MBE Practice</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        Generate one MBE-style multiple choice question on demand. Pick an
        answer, get a full explanation for every choice, and see your
        running score this session.
    </p>
</div>
""", unsafe_allow_html=True)

    # ── Settings row + score badge ────────────────────────────────────────────
    col_area, col_diff, col_score = st.columns([2, 2, 1])
    with col_area:
        _area_mbe = _safe_area(st.session_state.get("current_area"))
        if st.button(f"⚖️ Area of Law: {_area_mbe}", key="btn_area_mbe"):
            C.pick_area_dialog("current_area")
        area_mbe = _area_mbe
    with col_diff:
        difficulty_mbe = st.pills(
            "Difficulty", ["Easy", "Medium", "Hard"],
            default=st.session_state.get("mbe_difficulty", "Medium"),
            key="mbe_difficulty",
            label_visibility="collapsed",
            disabled=_locked,
        ) or "Medium"
    with col_score:
        total = st.session_state.get("mbe_total_count", 0)
        correct = st.session_state.get("mbe_correct_count", 0)
        score_color = "#788c5d" if total and correct/total >= 0.7 else (
            "#d97757" if total and correct/total >= 0.5 else "#b0aea5")
        st.markdown(
            f'<div style="text-align:right;padding:6px 0;">'
            f'<div style="font-family:Poppins,sans-serif;font-size:10px;font-weight:700;'
            f'letter-spacing:0.12em;text-transform:uppercase;color:#b0aea5;">Score</div>'
            f'<div style="font-family:Poppins,sans-serif;font-size:22px;font-weight:700;'
            f'color:{score_color};">{correct}/{total}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Action buttons ─────────────────────────────────────────────────────────
    col_new, col_reset = st.columns([3, 1])
    with col_new:
        new_q_btn = st.button(
            "Generate new question" if st.session_state.get("mbe_question") else "Generate first question",
            type="primary", use_container_width=True, key="mbe_new_btn",
            disabled=_locked,
        )
    with col_reset:
        if st.button("Reset score", use_container_width=True, key="mbe_reset_btn"):
            st.session_state.mbe_correct_count = 0
            st.session_state.mbe_total_count = 0
            st.session_state.mbe_question = None
            st.session_state.mbe_user_answer = None
            st.session_state.mbe_submitted = False
            st.rerun()

    if new_q_btn:
        try:
            q = C.run_with_time_progress(
                generate_mbe_question,
                phase="Drafting an MBE question",
                est_seconds=30,
                sublabels=[
                    (0,  "Picking a doctrine to test..."),
                    (35, "Writing a fact pattern..."),
                    (65, "Crafting four plausible choices..."),
                    (88, "Writing per-choice explanations..."),
                ],
                area=area_mbe, difficulty=difficulty_mbe,
            )
            st.session_state.mbe_question = q.model_dump()
            st.session_state.mbe_user_answer = None
            st.session_state.mbe_submitted = False
            st.rerun()
        except Exception as e:
            st.error(f"Question generation failed: {e}")

    # ── Display current question ───────────────────────────────────────────────
    q_dict = st.session_state.get("mbe_question")
    if q_dict:
        from models import MBEQuestion as _MBEQuestion
        question = _MBEQuestion(**q_dict)
        st.divider()
        C.show_mbe_question_card(question)

        # Defensive guard: if the model returned a malformed question with no
        # choices, the radio would render empty and the Submit button would be
        # permanently disabled — silent broken UI. Show a clear retry message.
        if not question.choices:
            st.error(
                "Question generation returned no choices. Click "
                "**Generate new question** above to try again."
            )
        elif not st.session_state.get("mbe_submitted"):
            # Pre-submit: radio + Submit
            choice_letters = [c.letter for c in question.choices]
            choice_labels = {c.letter: f"**{c.letter}.** {c.text}" for c in question.choices}
            picked = st.radio(
                "Your answer",
                choice_letters,
                format_func=lambda l: choice_labels.get(l, l),
                key="mbe_user_answer",
                label_visibility="collapsed",
                index=None,
            )
            submit = st.button(
                "Submit answer",
                type="primary",
                use_container_width=True,
                disabled=picked is None,
                key="mbe_submit_btn",
            )
            if submit:
                st.session_state.mbe_submitted = True
                st.session_state.mbe_total_count = (
                    st.session_state.get("mbe_total_count", 0) + 1
                )
                if (picked or "").strip().upper() == question.correct_letter.strip().upper():
                    st.session_state.mbe_correct_count = (
                        st.session_state.get("mbe_correct_count", 0) + 1
                    )
                st.rerun()
        else:
            # Post-submit: full explanations + Next button
            user_answer = st.session_state.get("mbe_user_answer") or ""
            C.show_mbe_result(question, user_answer)


# ════════════════════════════════════════════════════════════════════════════════
# TAB 6 — COMPARE & FEEDBACK
# ════════════════════════════════════════════════════════════════════════════════
with tab_cmp:
    st.markdown("""
<div class="irac-card irac-card-accent" style="margin-bottom:1.5rem;">
    <div class="section-label">Compare & Feedback</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        Write your own IRAC — Issue, Rule, Application, Conclusion — then get it graded
        section by section. Application carries the most weight (~50%).
    </p>
</div>
""", unsafe_allow_html=True)

    # ── Mode selector ──────────────────────────────────────────────────────────
    cmp_mode = st.radio(
        "How would you like to enter your IRAC?",
        [
            "Section by section (I, R, A, C)",
            "Paste my whole IRAC as one block",
        ],
        horizontal=True,
        key="cmp_mode",
        disabled=_locked,
        help=(
            "Section by section: write each I/R/A/C field individually with tips and word counts. "
            "Paste whole: drop in an IRAC you wrote elsewhere as one block of text. "
            "Either way, the AI drafts a model answer from the facts and grades you against it."
        ),
    )
    is_paste = cmp_mode == "Paste my whole IRAC as one block"

    _area_cmp = _safe_area(st.session_state.get("current_area"))
    _topic_cmp = st.session_state.get("current_topic") or ""
    _topic_label_cmp = _topic_cmp if _topic_cmp else "(any)"
    _has_topics_cmp = bool(_AREA_TOPICS.get(_area_cmp))
    col_area_cmp, col_topic_cmp, col_hypo_cmp = st.columns([2, 2, 1])
    with col_area_cmp:
        if st.button(f"⚖️ Area: {_area_cmp}", key="btn_area_cmp",
                     use_container_width=True):
            C.pick_area_dialog("current_area")
    with col_topic_cmp:
        if st.button(
            f"🏷 Topic: {_topic_label_cmp}",
            key="btn_topic_cmp",
            use_container_width=True,
            disabled=_locked or not _has_topics_cmp,
            help="Pick a sub-topic to anchor the hypo (optional)." if _has_topics_cmp else "No sub-topics defined for this area.",
        ):
            C.pick_topic_dialog(_area_cmp, "current_topic")
    area_cmp = _area_cmp
    with col_hypo_cmp:
        if st.button("⚡ Generate hypo", key="hypo_cmp",
                     use_container_width=True,
                     disabled=_locked,
                     help="Have the AI write a fresh single-issue hypo in this area."):
            try:
                with st.spinner("Drafting a fresh hypo..."):
                    # Compare: include MEE-style **Question:** call.
                    st.session_state["facts_cmp"] = generate_hypo(
                        area_cmp, "Single issue",
                        topic=_topic_cmp, include_call=True,
                    )
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't draft hypo: {e}")

    # First-render-only seed from cross-tab handoff. After that, Streamlit owns
    # session_state["facts_cmp"] — both via user typing and via the hypo button.
    if "facts_cmp" not in st.session_state:
        st.session_state["facts_cmp"] = st.session_state.last_facts

    facts_cmp = st.text_area(
        "Facts", height=110, key="facts_cmp",
        disabled=_locked,
        placeholder="Paste the hypo facts here, or click ⚡ Generate hypo.",
    )

    # Defaults so the variables exist regardless of branch taken.
    student_issue = student_rule = student_app = student_conc = ""
    student_full_text = ""

    if not is_paste:
        # ── Section-by-section input (default) ─────────────────────────────────
        st.markdown('<div class="section-label" style="margin-top:1rem;">Your IRAC Draft</div>', unsafe_allow_html=True)
        st.caption("Write each section separately. Even a rough draft earns better feedback than a blank page.")

        # Streamlit anti-pattern note: setting `value=` on a widget with a `key=`
        # only works on the first render. After session_state[key] exists, `value`
        # is silently ignored. To inject template text we must write the widget's
        # session_state key directly, BEFORE the widget is constructed, then rerun.
        col_i, col_r = st.columns(2)
        with col_i:
            col_i_hdr, col_i_btn = st.columns([3, 1])
            with col_i_hdr:
                st.markdown("**I — Issue**")
            with col_i_btn:
                if st.button("Template", key="tpl_i", use_container_width=True, disabled=_locked):
                    st.session_state["s_issue"] = C.starter_template("issue")
                    st.rerun()
            student_issue = st.text_area(
                "Issue", height=110, label_visibility="collapsed", key="s_issue",
                disabled=_locked,
                placeholder="Whether ... given ...",
            )
            C.word_count_bar(student_issue, "issue")

        with col_r:
            col_r_hdr, col_r_btn = st.columns([3, 1])
            with col_r_hdr:
                st.markdown("**R — Rule**")
            with col_r_btn:
                if st.button("Template", key="tpl_r", use_container_width=True, disabled=_locked):
                    st.session_state["s_rule"] = C.starter_template("rule")
                    st.rerun()
            student_rule = st.text_area(
                "Rule", height=110, label_visibility="collapsed", key="s_rule",
                disabled=_locked,
                placeholder="Under [statute/case], the rule requires...",
            )
            C.word_count_bar(student_rule, "rule")

        col_a, col_c = st.columns(2)
        with col_a:
            col_a_hdr, col_a_btn = st.columns([3, 1])
            with col_a_hdr:
                st.markdown("**A — Application**")
            with col_a_btn:
                if st.button("Template", key="tpl_a", use_container_width=True, disabled=_locked):
                    st.session_state["s_app"] = C.starter_template("application")
                    st.rerun()
            student_app = st.text_area(
                "Application", height=200, label_visibility="collapsed", key="s_app",
                disabled=_locked,
                placeholder="Element 1: ...\nElement 2: ...",
            )
            C.word_count_bar(student_app, "application")

        with col_c:
            col_c_hdr, col_c_btn = st.columns([3, 1])
            with col_c_hdr:
                st.markdown("**C — Conclusion**")
            with col_c_btn:
                if st.button("Template", key="tpl_c", use_container_width=True, disabled=_locked):
                    st.session_state["s_conc"] = C.starter_template("conclusion")
                    st.rerun()
            student_conc = st.text_area(
                "Conclusion", height=200, label_visibility="collapsed", key="s_conc",
                disabled=_locked,
                placeholder="Therefore, ...",
            )
            C.word_count_bar(student_conc, "conclusion")
    else:
        # ── Whole-paste input ──────────────────────────────────────────────────
        st.markdown('<div class="section-label" style="margin-top:1rem;">Your IRAC</div>', unsafe_allow_html=True)
        st.caption(
            "Paste the whole IRAC you wrote elsewhere as one block of text. Section labels "
            "(Issue:, Rule:, Application:, Conclusion: or I:, R:, A:, C:) help the grader, but aren't required."
        )
        student_full_text = st.text_area(
            "Your IRAC",
            height=320,
            label_visibility="collapsed",
            key="s_full",
            disabled=_locked,
            placeholder=(
                "Issue: ...\n"
                "Rule: ...\n"
                "Application: ...\n"
                "Conclusion: ..."
            ),
        )

    cmp_btn = st.button(
        "Generate AI IRAC + Get Feedback",
        type="primary", use_container_width=True,
        disabled=_locked,
    )

    if cmp_btn:
        if not facts_cmp.strip():
            st.warning("Paste facts first.")
        elif is_paste and not student_full_text.strip():
            st.warning("Paste your IRAC before comparing.")
        elif (not is_paste) and not any(
            [student_issue.strip(), student_rule.strip(), student_app.strip(), student_conc.strip()]
        ):
            st.warning("Write at least one section of your draft before comparing.")
        else:
            try:
                model_irac = C.stream_with_progress(
                    facts_cmp, area_cmp, start_pct=0, end_pct=70,
                    phase="Generating model IRAC",
                )
                st.session_state.last_irac = model_irac
                st.session_state.last_facts = facts_cmp
                st.session_state.current_area = area_cmp

                # In paste mode, the whole text fills all four student fields —
                # compare_irac dedupes them and sends one combined block to the grader.
                cmp_kwargs = dict(
                    facts=facts_cmp, area=area_cmp,
                    student_issue=student_issue,
                    student_rule=student_rule,
                    student_application=student_app,
                    student_conclusion=student_conc,
                    model_irac=model_irac,
                )
                if is_paste:
                    cmp_kwargs["student_full_text"] = student_full_text

                feedback = C.run_with_time_progress(
                    compare_irac,
                    phase="Grading your draft",
                    est_seconds=80,
                    sublabels=[
                        (0,  "Reading your draft..."),
                        (20, "Comparing Issue and Rule sections..."),
                        (45, "Evaluating Application — element by element..."),
                        (75, "Weighing Conclusion and overall coherence..."),
                        (90, "Assigning grade and feedback..."),
                    ],
                    **cmp_kwargs,
                )
                st.divider()
                st.markdown('<div class="section-label">Side-by-Side Comparison</div>', unsafe_allow_html=True)
                col_s, col_ai = st.columns(2, gap="large")
                with col_s:
                    st.markdown('<div class="section-label" style="color:#6a9bcc;">Your Draft</div>', unsafe_allow_html=True)
                    if is_paste:
                        with st.expander("**Your IRAC (full text)**", expanded=True):
                            st.markdown(student_full_text.strip() or "*Not provided*")
                    else:
                        for label, text in [
                            ("I — Issue", student_issue), ("R — Rule", student_rule),
                            ("A — Application", student_app), ("C — Conclusion", student_conc),
                        ]:
                            with st.expander(f"**{label}**", expanded=True):
                                st.markdown(text or "*Not provided*")
                with col_ai:
                    st.markdown('<div class="section-label" style="color:#d97757;">AI IRAC</div>', unsafe_allow_html=True)
                    C.show_irreac(model_irac)

                st.divider()
                st.markdown('<div class="section-label">Professor\'s Feedback</div>', unsafe_allow_html=True)
                C.grade_badge(feedback.overall_grade)
                st.markdown(
                    f'<div class="irac-card" style="font-family:Lora,serif;font-style:italic;color:#e8e6dc;">'
                    f'"{feedback.overall_feedback}"</div>',
                    unsafe_allow_html=True,
                )
                C.insight_box(feedback.key_insight)

                st.markdown('<div class="section-label" style="margin-top:1rem;">Section Breakdown</div>', unsafe_allow_html=True)
                for label, sec in [
                    ("I — Issue", feedback.issue), ("R — Rule", feedback.rule),
                    ("A — Application", feedback.application), ("C — Conclusion", feedback.conclusion),
                ]:
                    pill_html = C.score_pill(sec.score)
                    with st.expander(f"**{label}**", expanded=True):
                        st.markdown(
                            f'<div style="margin-bottom:12px;">{pill_html}</div>',
                            unsafe_allow_html=True,
                        )
                        col_got, col_gap = st.columns(2)
                        with col_got:
                            st.markdown('<div class="feedback-col-header">What you got right</div>', unsafe_allow_html=True)
                            st.markdown(f'<div style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">{sec.strengths or "—"}</div>', unsafe_allow_html=True)
                        with col_gap:
                            st.markdown('<div class="feedback-col-header">What to improve</div>', unsafe_allow_html=True)
                            st.markdown(f'<div style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">{sec.gaps or "—"}</div>', unsafe_allow_html=True)

                st.divider()
                pdf_bytes = export_to_pdf(model_irac, facts_cmp, area_cmp)
                st.download_button(
                    "Download AI IRAC as PDF",
                    data=pdf_bytes,
                    file_name="irac_feedback.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

            except Exception as e:
                st.error(f"Something went wrong: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — LONG ESSAY
# ════════════════════════════════════════════════════════════════════════════════
with tab_essay:
    st.markdown("""
<div class="irac-card irac-card-green" style="margin-bottom:1.5rem;">
    <div class="section-label" style="color:#788c5d;">Long Essay Grader</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        For multi-issue, bar-exam-style essays. Paste the facts and your full
        essay — the AI identifies every real issue, locates how you addressed
        each one, scores each separately, and gives an overall grade with
        coverage notes.
    </p>
</div>
""", unsafe_allow_html=True)

    _area_essay = _safe_area(st.session_state.get("current_area"))
    _topic_essay = st.session_state.get("current_topic") or ""
    _topic_label_essay = _topic_essay if _topic_essay else "(any)"
    _has_topics_essay = bool(_AREA_TOPICS.get(_area_essay))
    col_area_essay, col_topic_essay, col_hypo_essay = st.columns([2, 2, 1])
    with col_area_essay:
        if st.button(f"⚖️ Area: {_area_essay}", key="btn_area_essay",
                     use_container_width=True):
            C.pick_area_dialog("current_area")
    with col_topic_essay:
        if st.button(
            f"🏷 Topic: {_topic_label_essay}",
            key="btn_topic_essay",
            use_container_width=True,
            disabled=_locked or not _has_topics_essay,
            help="Pick a sub-topic to anchor the hypo (optional)." if _has_topics_essay else "No sub-topics defined for this area.",
        ):
            C.pick_topic_dialog(_area_essay, "current_topic")
    area_essay = _area_essay
    with col_hypo_essay:
        if st.button("⚡ Generate hypo", key="hypo_essay",
                     use_container_width=True,
                     disabled=_locked,
                     help="Have the AI write a fresh bar-exam-length hypo in this area."):
            try:
                with st.spinner("Drafting a comprehensive hypo..."):
                    # Long Essay: include MEE-style **Question:** call.
                    st.session_state["facts_essay"] = generate_hypo(
                        area_essay, "Comprehensive",
                        topic=_topic_essay, include_call=True,
                    )
                st.rerun()
            except Exception as e:
                st.error(f"Couldn't draft hypo: {e}")

    facts_essay = st.text_area(
        "Facts",
        height=180,
        key="facts_essay",
        disabled=_locked,
        placeholder="Paste the multi-issue fact pattern here, or click ⚡ Generate hypo.",
    )
    essay_text = st.text_area(
        "Your essay",
        height=380,
        key="essay_text",
        disabled=_locked,
        placeholder=(
            "Paste your full essay. Address each issue you spot with full IRAC "
            "(Issue, Rule, Application, Conclusion). Section labels help but aren't required."
        ),
    )

    essay_btn = st.button(
        "Grade my essay", type="primary", use_container_width=True,
        key="essay_btn", disabled=_locked,
    )

    if essay_btn:
        if not facts_essay.strip():
            st.warning("Paste facts first.")
        elif not essay_text.strip():
            st.warning("Paste your essay before grading.")
        elif len(essay_text.strip()) < 200:
            st.warning("This looks too short for a multi-issue essay. Use **Compare & Feedback** for short single-issue drafts.")
        else:
            try:
                feedback = C.run_with_time_progress(
                    grade_essay,
                    phase="Grading your essay",
                    est_seconds=120,
                    sublabels=[
                        (0,  "Reading the facts..."),
                        (15, "Identifying every real issue..."),
                        (40, "Locating how you addressed each issue..."),
                        (65, "Scoring issue by issue..."),
                        (85, "Aggregating to overall grade and coverage..."),
                        (95, "Writing key insight..."),
                    ],
                    facts=facts_essay, area=area_essay, essay=essay_text,
                )
                try:
                    history.save_essay(facts_essay, area_essay, essay_text, feedback.model_dump())
                except Exception:
                    pass
                st.divider()
                C.show_essay_feedback(feedback)
            except Exception as e:
                st.error(f"Grading failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 8 — SOCRATIC MODE
# ════════════════════════════════════════════════════════════════════════════════
with tab_soc:
    st.markdown("""
<div class="irac-card irac-card-blue" style="margin-bottom:1.5rem;">
    <div class="section-label">Socratic Mode</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;">
        The professor asks <strong style="color:#6a9bcc;">one question at a time</strong> to help you
        identify the legal issues yourself. No answers given until you find them.
        Based on the <em>grill-me</em> skill pattern.
    </p>
</div>
""", unsafe_allow_html=True)

    if not st.session_state.socratic_started:
        _area_soc = _safe_area(st.session_state.get("current_area"))
        if st.button(f"⚖️ Area of Law: {_area_soc}", key="btn_area_soc"):
            C.pick_area_dialog("current_area")
        soc_area = _area_soc
        col_soc_f, col_soc_btn = st.columns([3, 1])
        with col_soc_f:
            soc_facts = st.text_area("Facts", height=160, key="soc_facts_input",
                                      disabled=_locked,
                                      placeholder="Paste the hypo facts here...")
        with col_soc_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            start_btn = st.button("Start Session", type="primary",
                                  use_container_width=True, disabled=_locked)

        if start_btn:
            if not soc_facts.strip():
                st.warning("Paste facts first.")
            else:
                st.session_state.socratic_facts = soc_facts
                st.session_state.socratic_area = soc_area
                st.session_state.socratic_history = []
                st.session_state.socratic_started = True
                opening = C.run_with_time_progress(
                    socratic_next_question,
                    phase="Professor is reading the hypo",
                    est_seconds=12,
                    sublabels=[
                        (0,  "Reviewing the fact pattern..."),
                        (40, "Spotting where to begin..."),
                        (75, "Drafting the opening question..."),
                    ],
                    facts=soc_facts, area=soc_area,
                    history=[{"role": "user", "content": "(session just started — ask your first question)"}],
                )
                st.session_state.socratic_history.append({"role": "assistant", "content": opening})
                st.rerun()
    else:
        col_meta, col_reset = st.columns([4, 1])
        with col_meta:
            st.markdown(
                f'<div style="font-family:Poppins,sans-serif;font-size:13px;color:#b0aea5;">'
                f'Area: <strong style="color:#faf9f5;">{st.session_state.socratic_area}</strong> · '
                f'Answer the professor\'s questions to identify all issues.</div>',
                unsafe_allow_html=True,
            )
        with col_reset:
            if st.button("Start Over", use_container_width=True):
                st.session_state.socratic_started = False
                st.session_state.socratic_history = []
                st.rerun()

        with st.expander("View Hypo", expanded=False):
            st.markdown(
                f'<div style="font-family:Lora,serif;font-style:italic;color:#b0aea5;">'
                f'{html.escape(st.session_state.socratic_facts)}</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        for msg in st.session_state.socratic_history:
            with st.chat_message("assistant" if msg["role"] == "assistant" else "user"):
                st.markdown(msg["content"])

        # Match only the protocol marker — "COMPLETE:" at the start of an
        # assistant turn — not casual mentions of the word elsewhere.
        complete = any(
            m["content"].lstrip().startswith("COMPLETE:")
            for m in st.session_state.socratic_history
            if m["role"] == "assistant"
        )

        if complete:
            st.success("You've identified all the key issues. Ready for the full analysis?")
            if st.button("Generate Full IRAC", type="primary", use_container_width=True):
                try:
                    result = C.stream_with_progress(
                        st.session_state.socratic_facts,
                        st.session_state.socratic_area,
                    )
                    st.session_state.last_irac = result
                    st.session_state.last_facts = st.session_state.socratic_facts
                    st.session_state.current_area = st.session_state.socratic_area
                    C.show_irreac(result)
                    pdf_bytes = export_to_pdf(
                        result, st.session_state.socratic_facts,
                        st.session_state.socratic_area,
                    )
                    st.download_button(
                        "Download as PDF", data=pdf_bytes,
                        file_name="socratic_irac.pdf", mime="application/pdf",
                        use_container_width=True,
                    )
                except Exception as e:
                    st.error(f"Generation failed: {e}")
        else:
            if user_input := st.chat_input("Your answer..."):
                st.session_state.socratic_history.append({"role": "user", "content": user_input})
                next_q = C.run_with_time_progress(
                    socratic_next_question,
                    phase="Professor thinking",
                    est_seconds=10,
                    sublabels=[
                        (0,  "Considering your answer..."),
                        (45, "Choosing what to probe next..."),
                        (80, "Phrasing the next question..."),
                    ],
                    facts=st.session_state.socratic_facts,
                    area=st.session_state.socratic_area,
                    history=st.session_state.socratic_history,
                )
                st.session_state.socratic_history.append({"role": "assistant", "content": next_q})
                st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 9 — MY OUTLINES
# ════════════════════════════════════════════════════════════════════════════════
def _humanize_age(iso_ts: str) -> str:
    """Render '2 days ago' / 'just now' from an ISO timestamp."""
    try:
        ts = datetime.fromisoformat(iso_ts.rstrip("Z")).replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - ts
    except Exception:
        return iso_ts
    secs = int(delta.total_seconds())
    if secs < 60: return "just now"
    if secs < 3600: return f"{secs // 60} min ago"
    if secs < 86400: return f"{secs // 3600} hr ago"
    days = secs // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"


with tab_outlines:
    # ── Privacy notice ─────────────────────────────────────────────────────────
    st.markdown("""
<div class="irac-card irac-card-blue" style="margin-bottom:1.5rem;">
    <div class="section-label" style="color:#6a9bcc;">Local-only · Private</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;line-height:1.7;">
        Files stay on this computer. They are <strong>never</strong> uploaded,
        sent to a server, or committed to git. You are responsible for
        ensuring you have rights to any outline you upload — typically a
        commercial study guide you've purchased is fine for personal use.
    </p>
</div>
""", unsafe_allow_html=True)

    # ── Upload form ────────────────────────────────────────────────────────────
    st.markdown('<div class="section-label">Upload an Outline</div>', unsafe_allow_html=True)
    upload_area = st.pills(
        "Area of Law", AREAS_OF_LAW,
        default="Contracts", key="outline_upload_area",
    ) or "Contracts"
    uploaded_file = st.file_uploader(
        "Outline file",
        type=["pdf", "docx", "txt", "md"],
        key="outline_upload_file",
        help="PDF, DOCX, TXT, or Markdown. Scanned PDFs without an OCR text layer won't work.",
    )
    if st.button("Add to my outlines", type="primary",
                 use_container_width=True, disabled=uploaded_file is None):
        try:
            meta = outlines.add_outline(
                filename=uploaded_file.name,
                area=upload_area,
                content=uploaded_file.getvalue(),
            )
            st.success(f"Saved **{meta['filename']}** ({meta['char_count']:,} chars).")
            st.rerun()
        except ImportError:
            st.error(
                "PDF and DOCX support requires extra packages. Run:\n\n"
                "```bash\nbash setup.sh\n```\n\nor\n\n"
                "```bash\npip install pypdf python-docx\n```"
            )
        except ValueError as e:
            st.warning(str(e))
        except Exception as e:
            st.error(f"Upload failed: {e}")

    st.divider()

    # ── Outline source — 3-way picker ─────────────────────────────────────────
    st.markdown('<div class="section-label">Rule Outline Source</div>', unsafe_allow_html=True)
    st.caption(
        "Which rule reference should the AI use when generating an IRAC for you? "
        "The choice persists across restarts."
    )
    st.pills(
        "Outline source",
        ["mine", "default", "none"],
        default=st.session_state.get("outline_source", "default"),
        key="outline_source",
        format_func=lambda x: {
            "mine":    "📚 My uploaded outlines",
            "default": "🤖 Built-in (AI-generated, cached)",
            "none":    "🚫 None — LLM general knowledge only",
        }[x],
        label_visibility="collapsed",
    )

    st.divider()

    # ── Built-in outlines (AI-generated, cached forever) ──────────────────────
    import default_outlines
    st.markdown('<div class="section-label">Built-in Outlines</div>', unsafe_allow_html=True)
    st.caption(
        "Per-area rule references generated by the local LLM and cached to "
        "`~/.iracmaker/default_outlines/`. First request per area takes ~30–60s; "
        "after that, instant. Used when **Outline source = Built-in** above."
    )
    _bo_status = default_outlines.status_all(AREAS_OF_LAW)
    for _bo in _bo_status:
        _area_name = _bo["area"]
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            if _bo["exists"]:
                _gen_at = _bo.get("generated_at", "") or ""
                badge_color = "#788c5d"
                status_text = (
                    f"<span style=\"color:{badge_color};font-weight:600;\">✓ Ready</span> · "
                    f"{_bo['char_count']:,} chars · generated {_humanize_age(_gen_at + 'Z') if _gen_at else 'recently'}"
                )
            else:
                status_text = (
                    "<span style=\"color:#6e6c65;font-style:italic;\">Not yet generated</span>"
                )
            st.markdown(
                f'<div class="irac-card" style="padding:10px 14px;margin-bottom:6px;">'
                f'<div style="font-family:Poppins,sans-serif;font-size:14px;font-weight:600;color:#faf9f5;">'
                f'{html.escape(_area_name)}'
                f'</div>'
                f'<div style="font-family:Lora,serif;font-size:12px;color:#b0aea5;margin-top:3px;">'
                f'{status_text}'
                f'</div></div>',
                unsafe_allow_html=True,
            )
        with col_btn:
            label = "Regenerate" if _bo["exists"] else "Generate"
            if st.button(label, key=f"bo_btn_{_area_name}",
                         use_container_width=True):
                try:
                    with st.spinner(f"Drafting {_area_name} outline (~30–60s)..."):
                        if _bo["exists"]:
                            default_outlines.regenerate(_area_name)
                        else:
                            default_outlines.get_or_generate(_area_name)
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't generate: {e}")

    # Optional: view + edit current outline for the active area
    _active_outline_path = default_outlines.find_path(_safe_area(st.session_state.get("current_area")))
    if _active_outline_path:
        with st.expander(
            f"📖 View outline for **{_safe_area(st.session_state.get('current_area'))}**",
            expanded=False,
        ):
            st.markdown(default_outlines.load(_safe_area(st.session_state.get("current_area"))))

    st.divider()

    # ── Existing outlines list ─────────────────────────────────────────────────
    st.markdown('<div class="section-label">My Outlines</div>', unsafe_allow_html=True)
    items = outlines.load_index()

    if not items:
        st.markdown("""
<div class="irac-card" style="text-align:center;padding:2.5rem 1.5rem;border-style:dashed;">
    <div style="font-size:1.6rem;margin-bottom:0.6rem;">📚</div>
    <div style="font-family:Poppins,sans-serif;font-size:13px;color:#b0aea5;">
        No outlines yet. Upload one above to get started.
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        for item in items:
            col_info, col_del = st.columns([5, 1])
            with col_info:
                age = _humanize_age(item.get("uploaded_at", ""))
                area_chip = (
                    f'<span style="display:inline-block;background:rgba(217,119,87,0.12);'
                    f'border:1px solid rgba(217,119,87,0.3);color:#d97757;'
                    f'font-family:Poppins,sans-serif;font-size:10px;font-weight:600;'
                    f'letter-spacing:0.06em;text-transform:uppercase;'
                    f'padding:2px 9px;border-radius:999px;margin-left:8px;">{html.escape(item.get("area",""))}</span>'
                )
                st.markdown(
                    f'<div class="irac-card" style="padding:12px 16px;margin-bottom:6px;">'
                    f'<div style="font-family:Poppins,sans-serif;font-size:14px;font-weight:600;color:#faf9f5;">'
                    f'{html.escape(item.get("filename","(unnamed)"))}{area_chip}'
                    f'</div>'
                    f'<div style="font-family:Lora,serif;font-size:12px;color:#b0aea5;margin-top:4px;">'
                    f'{item.get("char_count", 0):,} chars · uploaded {age}'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("Delete", key=f"del_{item['id']}", use_container_width=True):
                    outlines.delete_outline(item["id"])
                    st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 10 — HISTORY
# ════════════════════════════════════════════════════════════════════════════════
from models import (
    IRRACOutput as _IRRACOutput,
    CaseBrief as _CaseBrief,
    IssueSpottingResult as _IssueSpottingResult,
    EssayFeedback as _EssayFeedback,
)

with tab_history:
    st.markdown("""
<div class="irac-card irac-card-accent" style="margin-bottom:1.5rem;">
    <div class="section-label">History</div>
    <p style="margin:0;font-size:14px;color:#b0aea5;line-height:1.7;">
        Every IRAC and Case Brief you generate is auto-saved to this computer.
        Search, reopen, or delete any past entry. Stored locally under
        <code style="background:#0d0d0c;padding:1px 6px;border-radius:3px;">~/.iracmaker/history/</code>.
    </p>
</div>
""", unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────────────────
    col_q, col_t, col_clear = st.columns([3, 2, 1])
    with col_q:
        history_query = st.text_input(
            "Search", placeholder="Search by issue, case name, or content...",
            key="history_query", label_visibility="collapsed",
        )
    with col_t:
        history_type = st.pills(
            "Type",
            ["all", "irac", "brief", "spot", "essay"],
            default="all",
            key="history_type",
            format_func=lambda x: {
                "all": "All", "irac": "IRACs", "brief": "Briefs",
                "spot": "Spot Drills", "essay": "Long Essays",
            }[x],
            label_visibility="collapsed",
        ) or "all"
    with col_clear:
        st.write("")  # spacer for vertical alignment
        cleared = st.button("Clear", use_container_width=True, key="history_clear_filters")
        if cleared:
            for k in ("history_query", "history_type"):
                if k in st.session_state:
                    del st.session_state[k]
            st.rerun()

    entries = history.filter_history(query=history_query, entry_type=history_type)

    if not entries:
        st.markdown("""
<div class="irac-card" style="text-align:center;padding:2.5rem 1.5rem;border-style:dashed;">
    <div style="font-size:1.6rem;margin-bottom:0.6rem;">📓</div>
    <div style="font-family:Poppins,sans-serif;font-size:13px;color:#b0aea5;">
        Nothing saved yet. Generate an IRAC or Case Brief — it'll show up here automatically.
    </div>
</div>
""", unsafe_allow_html=True)
    else:
        st.caption(f"{len(entries)} entr{'y' if len(entries)==1 else 'ies'} found.")
        for entry in entries:
            entry_id = entry.get("id", "")
            entry_type_v = entry.get("type", "irac")
            type_color = {
                "irac":  "#d97757",
                "brief": "#6a9bcc",
                "spot":  "#788c5d",
                "essay": "#788c5d",
            }.get(entry_type_v, "#b0aea5")
            type_label = {
                "irac":  "IRAC",
                "brief": "Brief",
                "spot":  "Spot Drill",
                "essay": "Long Essay",
            }.get(entry_type_v, entry_type_v.upper())
            area = entry.get("area")
            saved_iso = entry.get("saved_at", "")
            age = _humanize_age(saved_iso)
            title = html.escape(entry.get("title", "(untitled)"))

            type_badge = (
                f'<span style="display:inline-block;background:{type_color}22;'
                f'border:1px solid {type_color}55;color:{type_color};'
                f'font-family:Poppins,sans-serif;font-size:10px;font-weight:700;'
                f'letter-spacing:0.08em;text-transform:uppercase;'
                f'padding:2px 9px;border-radius:999px;margin-right:8px;">{type_label}</span>'
            )
            area_badge = ""
            if area:
                area_badge = (
                    f'<span style="display:inline-block;background:rgba(176,174,165,0.08);'
                    f'border:1px solid rgba(176,174,165,0.2);color:#b0aea5;'
                    f'font-family:Poppins,sans-serif;font-size:10px;font-weight:600;'
                    f'letter-spacing:0.06em;text-transform:uppercase;'
                    f'padding:2px 9px;border-radius:999px;margin-left:8px;">{html.escape(area)}</span>'
                )

            with st.expander(
                f"**{entry.get('title', '(untitled)')}**  ·  {type_label}  ·  {age}",
                expanded=False,
            ):
                st.markdown(
                    f'<div style="margin-bottom:14px;">{type_badge}'
                    f'<span style="font-family:Lora,serif;font-size:13px;color:#b0aea5;">'
                    f'Saved {age}{" · " + html.escape(area) if area else ""}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                result = entry.get("result", {})
                try:
                    if entry_type_v == "irac":
                        if entry.get("facts"):
                            with st.expander("Original facts", expanded=False):
                                st.markdown(html.escape(entry["facts"]))
                        C.show_irreac(_IRRACOutput(**result))
                    elif entry_type_v == "spot":
                        if entry.get("facts"):
                            with st.expander("Original facts", expanded=False):
                                st.markdown(html.escape(entry["facts"]))
                        if entry.get("student_issues"):
                            with st.expander("Your spotted issues", expanded=False):
                                st.markdown(html.escape(entry["student_issues"]))
                        C.show_issue_spotting(_IssueSpottingResult(**result))
                    elif entry_type_v == "essay":
                        if entry.get("facts"):
                            with st.expander("Original facts", expanded=False):
                                st.markdown(html.escape(entry["facts"]))
                        if entry.get("essay"):
                            with st.expander("Your essay", expanded=False):
                                st.markdown(html.escape(entry["essay"]))
                        C.show_essay_feedback(_EssayFeedback(**result))
                    else:  # brief
                        if entry.get("case_text"):
                            with st.expander("Original case text", expanded=False):
                                st.markdown(html.escape(entry["case_text"][:5000]) +
                                            ("…" if len(entry.get("case_text", "")) > 5000 else ""))
                        C.show_case_brief(_CaseBrief(**result))
                except Exception as e:
                    st.error(f"Couldn't render this entry: {e}")
                    st.json(result)

                col_open, col_del = st.columns([4, 1])
                with col_open:
                    # Note: clicking this only seeds last_facts / current_area so
                    # the Compare tab pre-fills the facts box and area chip.
                    # The Compare tab still regenerates a fresh AI model on
                    # grade — it doesn't reuse the saved IRAC. Keep the label
                    # honest about that.
                    if entry_type_v == "irac" and st.button(
                        "Load these facts into Compare & Feedback",
                        key=f"reopen_{entry_id}",
                        use_container_width=True,
                    ):
                        st.session_state.last_irac = _IRRACOutput(**result)
                        st.session_state.last_facts = entry.get("facts", "")
                        st.session_state.current_area = _safe_area(area)
                        # facts_cmp may already exist from a prior visit —
                        # overwrite it so the freshly-loaded facts actually appear.
                        st.session_state["facts_cmp"] = entry.get("facts", "")
                        st.toast(
                            "Facts loaded. Switch to Practice → Compare & Feedback "
                            "and write your draft.",
                            icon="↗️",
                        )
                with col_del:
                    if st.button("Delete", key=f"hist_del_{entry_id}",
                                 use_container_width=True):
                        history.delete_entry(entry_id)
                        st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 11 — ABOUT
# ════════════════════════════════════════════════════════════════════════════════
with tab_about:
    # ── Modes (single-column stack) ────────────────────────────────────────────
    st.markdown('<div class="section-label">Modes</div>', unsafe_allow_html=True)
    st.markdown("""
<div style="display:flex; flex-direction:column; gap:10px; margin-bottom:1.5rem;">
    <div class="irac-card" style="padding:16px 18px;">
        <div class="section-label">Generate IRAC</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Paste a fact pattern — AI drafts a full structured IRAC analysis with citations and element-by-element application.
        </div>
    </div>
    <div class="irac-card irac-card-blue" style="padding:16px 18px;">
        <div class="section-label" style="color:#6a9bcc;">Case Brief</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Paste a court opinion — get a structured brief with Facts, Procedural Posture, Issue, Holding, Reasoning, Dissent, and exam notes.
        </div>
    </div>
    <div class="irac-card irac-card-blue" style="padding:16px 18px;">
        <div class="section-label" style="color:#6a9bcc;">Both Sides</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Generates the plaintiff's strongest argument and the defendant's strongest argument side by side.
        </div>
    </div>
    <div class="irac-card irac-card-green" style="padding:16px 18px;">
        <div class="section-label" style="color:#788c5d;">Issue Spotting</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Drill-style: paste a hypo, list every issue you can spot, get scored on coverage. Faster feedback than writing a full IRAC.
        </div>
    </div>
    <div class="irac-card" style="padding:16px 18px;border-left:3px solid #d97757;">
        <div class="section-label">⚡ Generate hypo</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            A button on Issue Spotting, Long Essay, and Compare & Feedback that has the AI write a fresh fact pattern for the area you've picked. Fills the facts box for you so you can drill against new hypos without finding your own.
        </div>
    </div>
    <div class="irac-card irac-card-blue" style="padding:16px 18px;">
        <div class="section-label" style="color:#6a9bcc;">MBE Practice</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Generates one MBE-style multiple-choice question on demand with full per-choice explanations. Tracks running score this session.
        </div>
    </div>
    <div class="irac-card irac-card-green" style="padding:16px 18px;">
        <div class="section-label" style="color:#788c5d;">Compare & Feedback</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Write your own IRAC first, then get it graded section-by-section against the AI's model answer.
        </div>
    </div>
    <div class="irac-card irac-card-green" style="padding:16px 18px;">
        <div class="section-label" style="color:#788c5d;">Long Essay</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Bar-exam-style: paste a multi-issue fact pattern and your full essay. AI identifies every real issue, locates how you addressed each, scores them separately, and gives an overall grade with coverage notes.
        </div>
    </div>
    <div class="irac-card" style="padding:16px 18px;border-left:3px solid #b0aea5;">
        <div class="section-label" style="color:#b0aea5;">Socratic Mode</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            A professor asks you one question at a time to help you spot the legal issues yourself — no answers given upfront.
        </div>
    </div>
    <div class="irac-card irac-card-accent" style="padding:16px 18px;">
        <div class="section-label">My Outlines</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Upload your own legally-purchased outlines (PDF, DOCX, TXT). They stay on this computer and get used as context when generating IRACs in matching areas of law — so the AI's analysis sounds like your outline, not a generic restatement.
        </div>
    </div>
    <div class="irac-card" style="padding:16px 18px;border-left:3px solid #b0aea5;">
        <div class="section-label" style="color:#b0aea5;">History</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Every IRAC and Case Brief you generate is auto-saved locally. Search, reopen, or delete past entries — nothing is ever sent off this computer.
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # ── Writing Tips (single-column stack, in I-R-A-C order) ───────────────────
    st.markdown('<div class="section-label" style="margin-top:1rem;">Writing Tips</div>', unsafe_allow_html=True)
    st.caption("Quick reminders for each section of the IRAC, used when grading your draft in Compare & Feedback.")

    st.markdown("**I — Issue**")
    C.section_tip("issue")
    st.markdown("**R — Rule**")
    C.section_tip("rule")
    st.markdown("**A — Application**")
    C.section_tip("application")
    st.markdown("**C — Conclusion**")
    C.section_tip("conclusion")


# ── Persist user preferences (last thing each run) ────────────────────────────
_persist_prefs()
