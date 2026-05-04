import time
import streamlit as st
from models import IRRACOutput


# ── Area-of-Law modal picker ──────────────────────────────────────────────────
@st.dialog("Pick Area of Law")
def pick_area_dialog(state_key: str, default: str = "Contracts"):
    """Modal picker. Auto-closes when the user picks a *different* pill.

    The auto-close-on-change branch keeps the snappy UX from before. The
    explicit "Use this area" button below handles the edge case where the
    user is happy with the currently-selected pill (important for the
    first-run welcome gate: a user who likes the Contracts default needs
    *some* way to confirm and unlock the app).

    Earlier we had `if selected:` which fired on first render — st.pills
    returns its default value immediately, so the dialog rerun()'d itself
    closed before the user could see anything.
    """
    from irac_engine import AREAS_OF_LAW
    current = st.session_state.get(state_key) or default
    selected = st.pills(
        "Area of Law", AREAS_OF_LAW,
        default=current,
        key=f"_dialog_pills_{state_key}",
        label_visibility="collapsed",
    )

    # Snappy path: user clicked a different pill. Auto-confirm and close.
    if selected and selected != current:
        st.session_state[state_key] = selected
        st.session_state["area_confirmed"] = True
        st.rerun()

    # Fallback: explicit confirm for "I'm fine with this one already". Mostly
    # matters on first run when the welcome gate needs area_confirmed=True
    # and the user doesn't want to change away from the default.
    if st.button(f"Use {selected or current}", type="primary",
                 use_container_width=True, key=f"_dialog_confirm_{state_key}"):
        st.session_state[state_key] = selected or current
        st.session_state["area_confirmed"] = True
        st.rerun()

# ── Word count targets per IRAC section ───────────────────────────────────────
WORD_TARGETS = {
    "issue":       (30,  80,  "1–2 sentences"),
    "rule":        (120, 300, "2–4 paragraphs"),
    "application": (200, 500, "bulk of analysis"),
    "conclusion":  (25,  60,  "1–2 sentences"),
}

SECTION_TIPS = {
    "issue": (
        "Issue tip",
        "Frame as 'Whether [legal question] given [key facts].' "
        "One sentence per issue. State the legal question — not the factual background."
    ),
    "rule": (
        "Rule tip",
        "Cover two parts: (1) <strong>Rule Statement</strong> — the rule with a specific citation "
        "(Restatement § #, UCC § #, or landmark case + year). "
        "(2) <strong>Rule Exploration</strong> — how courts have interpreted it: key cases, "
        "majority vs minority views, circuit splits. 'The law requires...' earns no citation credit."
    ),
    "application": (
        "Application tip",
        "This section is worth ~50% of your exam score. Each rule element gets its own paragraph. "
        "Address the strongest counter-argument for every disputed element."
    ),
    "conclusion": (
        "Conclusion tip",
        "Answer the Issue directly. Add confidence level: High / Moderate / Low "
        "with a one-sentence reason. Never introduce new analysis here."
    ),
}


def word_count_bar(text: str, section: str):
    """Renders a word count progress bar under a text area."""
    count = len(text.split()) if text.strip() else 0
    min_w, max_w, label = WORD_TARGETS[section]

    if count == 0:
        color = "#3a3830"
        pct = 0.0
    elif count < min_w:
        color = "#d97757"
        pct = count / min_w * 0.5
    elif count <= max_w:
        color = "#788c5d"
        pct = 0.5 + (count - min_w) / (max_w - min_w) * 0.5
    else:
        color = "#6a9bcc"
        pct = 1.0

    count_color = "#faf9f5" if count > 0 else "#b0aea5"

    st.markdown(f"""
<div class="word-count-row">
    <span class="word-count-num" style="color:{count_color};">{count} words</span>
    <span class="word-count-target">Target: {min_w}–{max_w} ({label})</span>
</div>
<div class="word-count-bar-bg">
    <div class="word-count-bar-fill" style="width:{pct*100:.1f}%; background:{color};"></div>
</div>
""", unsafe_allow_html=True)


def section_tip(section: str):
    """Renders a styled writing tip for the given IRAC section."""
    label, tip = SECTION_TIPS[section]
    st.markdown(f"""
<div class="tip-box">
    <div class="tip-box-label">{label}</div>
    {tip}
</div>
""", unsafe_allow_html=True)


def score_pill(score: str) -> str:
    """Returns HTML for a styled score pill."""
    css = {
        "Excellent": "pill-excellent",
        "Good": "pill-good",
        "Needs Work": "pill-needs-work",
        "Missing": "pill-missing",
    }.get(score, "pill-needs-work")
    return f'<span class="score-pill {css}">{score}</span>'


def grade_badge(grade: str):
    """Renders a styled circular grade badge."""
    css = "grade-a" if grade.startswith("A") else \
          "grade-b" if grade.startswith("B") else \
          "grade-c" if grade.startswith("C") else "grade-df"
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:16px;margin-bottom:1rem;">'
        f'<div class="grade-circle {css}">{grade}</div>'
        f'<div style="font-family:Poppins,sans-serif;font-size:13px;color:#b0aea5;">'
        f'Overall Grade</div></div>',
        unsafe_allow_html=True,
    )


def insight_box(text: str):
    """Renders the key insight box."""
    st.markdown(f"""
<div class="insight-box">
    <div class="insight-label">Key Insight</div>
    {text}
</div>
""", unsafe_allow_html=True)


def show_irreac(result: IRRACOutput, expanded: bool = True):
    """Renders a full IRREAC result in styled expanders.

    When `rule_exploration` is empty (e.g., a user-pasted reference IRAC that
    doesn't split R1/R2), R1 and R2 are collapsed into a single "R — Rule".
    """
    sections = [("I — Issue", result.issue, "irac-card-accent")]
    if result.rule_exploration.strip():
        sections.append(("R1 — Rule Statement", result.rule_statement, "irac-card-blue"))
        sections.append(("R2 — Rule Exploration", result.rule_exploration, "irac-card-blue"))
    else:
        sections.append(("R — Rule", result.rule_statement, "irac-card-blue"))
    sections.append(("A — Application", result.application, "irac-card-accent"))
    sections.append(("C — Conclusion", result.conclusion, "irac-card-green"))

    for label, content, _ in sections:
        with st.expander(f"**{label}**", expanded=expanded):
            st.markdown(content or "*Not provided*")

    if result.tips:
        st.markdown("""
<div style="margin-top:1rem;">
    <div class="section-label">Common Mistakes to Avoid</div>
</div>
""", unsafe_allow_html=True)
        for tip in result.tips:
            st.markdown(
                f'<div class="irac-card" style="margin-bottom:6px;padding:10px 14px;">'
                f'<span style="color:#d97757;font-weight:700;margin-right:8px;">—</span>'
                f'<span style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">{tip}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── MBE renderers ─────────────────────────────────────────────────────────────

def show_mbe_question_card(question):
    """Renders the fact pattern + call-of-question (without revealing the answer)."""
    st.markdown(
        f'<div class="irac-card irac-card-blue" style="padding:18px 22px;margin-bottom:1rem;">'
        f'<div class="section-label" style="color:#6a9bcc;">Fact Pattern</div>'
        f'<div style="font-family:Lora,serif;font-size:15px;line-height:1.7;color:#e8e6dc;">'
        f'{question.facts}'
        f'</div>'
        f'<div style="margin-top:16px;font-family:Poppins,sans-serif;font-size:14px;'
        f'font-weight:600;color:#faf9f5;border-top:1px solid #2a2925;padding-top:14px;">'
        f'{question.call_of_question}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def show_mbe_result(question, user_answer: str):
    """After-submit view: highlights correct + user's pick, shows all 4 explanations."""
    correct = question.correct_letter.strip().upper()
    user = (user_answer or "").strip().upper()
    is_correct = (user == correct)

    badge_color = "#788c5d" if is_correct else "#ef4444"
    badge_label = "✓ Correct" if is_correct else "✗ Incorrect"

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:1rem;">'
        f'<div style="background:{badge_color}22;border:1px solid {badge_color}55;'
        f'color:{badge_color};font-family:Poppins,sans-serif;font-size:13px;font-weight:700;'
        f'letter-spacing:0.06em;text-transform:uppercase;padding:6px 14px;border-radius:999px;">'
        f'{badge_label}'
        f'</div>'
        f'<div style="font-family:Poppins,sans-serif;font-size:14px;color:#b0aea5;">'
        f'You picked <strong style="color:#faf9f5;">{user or "—"}</strong>. '
        f'Correct answer: <strong style="color:#788c5d;">{correct}</strong>.'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for choice in question.choices:
        letter = choice.letter.strip().upper()
        is_right = (letter == correct)
        is_user = (letter == user)

        # Border color: green for correct answer, red for user's wrong pick, gray otherwise.
        if is_right:
            border_color = "#788c5d"
        elif is_user and not is_correct:
            border_color = "#ef4444"
        else:
            border_color = "#2a2925"

        # Marker emoji to make scanning fast.
        if is_right:
            marker = "✓"
        elif is_user and not is_correct:
            marker = "✗"
        else:
            marker = "·"

        explanation = question.explanations.get(letter, "")
        st.markdown(
            f'<div class="irac-card" style="padding:12px 16px;margin-bottom:8px;'
            f'border:1px solid {border_color};border-left:3px solid {border_color};">'
            f'<div style="font-family:Poppins,sans-serif;font-size:14px;font-weight:600;'
            f'color:#faf9f5;margin-bottom:6px;">'
            f'<span style="color:{border_color};margin-right:8px;">{marker}</span>'
            f'<strong>{letter}.</strong> {choice.text}'
            f'</div>'
            f'<div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;line-height:1.6;'
            f'padding-left:24px;">'
            f'{explanation or "—"}'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Long-form Essay renderer ──────────────────────────────────────────────────

def show_essay_feedback(feedback):
    """Renders an EssayFeedback: grade badge, coverage, per-issue breakdown."""
    if feedback.overall_grade:
        grade_badge(feedback.overall_grade)

    if feedback.coverage_note:
        st.markdown(
            f'<div class="irac-card irac-card-blue" style="padding:12px 16px;margin-bottom:12px;'
            f'font-family:Poppins,sans-serif;font-size:13px;color:#faf9f5;">'
            f'<span style="color:#6a9bcc;font-weight:700;text-transform:uppercase;'
            f'letter-spacing:0.1em;font-size:11px;margin-right:8px;">Coverage</span>'
            f'{feedback.coverage_note}'
            f'</div>',
            unsafe_allow_html=True,
        )

    if feedback.overall_feedback:
        st.markdown(
            f'<div class="irac-card" style="font-family:Lora,serif;font-style:italic;'
            f'color:#e8e6dc;margin-bottom:1rem;">"{feedback.overall_feedback}"</div>',
            unsafe_allow_html=True,
        )

    if feedback.key_insight:
        insight_box(feedback.key_insight)

    if feedback.issues:
        st.markdown(
            '<div class="section-label" style="margin-top:1rem;">Issue-by-Issue Breakdown</div>',
            unsafe_allow_html=True,
        )
        for it in feedback.issues:
            pill_html = score_pill(it.score)
            with st.expander(f"**{it.issue_name or '(unnamed issue)'}**", expanded=True):
                st.markdown(
                    f'<div style="margin-bottom:12px;">{pill_html}</div>',
                    unsafe_allow_html=True,
                )
                if it.student_treatment:
                    st.markdown(
                        f'<div style="font-family:Lora,serif;font-size:13px;'
                        f'color:#b0aea5;font-style:italic;margin-bottom:10px;">'
                        f'Your treatment: {it.student_treatment}</div>',
                        unsafe_allow_html=True,
                    )
                col_got, col_gap = st.columns(2)
                with col_got:
                    st.markdown('<div class="feedback-col-header">What you got right</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">'
                        f'{it.strengths or "—"}</div>',
                        unsafe_allow_html=True,
                    )
                with col_gap:
                    st.markdown('<div class="feedback-col-header">What to improve</div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">'
                        f'{it.gaps or "—"}</div>',
                        unsafe_allow_html=True,
                    )


# ── Issue Spotting renderer ───────────────────────────────────────────────────

def show_issue_spotting(result):
    """Renders an IssueSpottingResult: coverage score badge + 3 lists.

    The three buckets get color-coded so the student can scan in seconds:
      green = caught, orange = missed, gray-red = false alarm.
    """
    # Coverage score header — parse "4/6" into a percentage for the bar.
    score = result.coverage_score or ""
    pct = 0
    try:
        if "/" in score:
            num, denom = score.split("/", 1)
            num_i, denom_i = int(num.strip()), int(denom.strip())
            pct = int(num_i / denom_i * 100) if denom_i else 0
    except (ValueError, ZeroDivisionError):
        pct = 0

    bar_color = "#788c5d" if pct >= 80 else ("#d97757" if pct >= 50 else "#ef4444")
    st.markdown(f"""
<div class="irac-card" style="margin-bottom:1.25rem;padding:18px 22px;">
    <div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:14px;">
        <div>
            <div class="section-label">Coverage</div>
            <div style="font-family:Poppins,sans-serif;font-size:14px;color:#b0aea5;">
                Caught {len(result.student_caught)} of {len(result.student_caught) + len(result.student_missed)} real issues
            </div>
        </div>
        <div style="font-family:Poppins,sans-serif;font-size:34px;font-weight:700;color:{bar_color};line-height:1;">
            {score or '—'}
        </div>
    </div>
    <div style="background:#2a2925;border-radius:6px;height:8px;overflow:hidden;">
        <div style="width:{pct}%;height:100%;background:{bar_color};transition:width 0.4s ease;"></div>
    </div>
</div>
""", unsafe_allow_html=True)

    if result.overall_feedback.strip():
        st.markdown(
            f'<div class="irac-card" style="font-family:Lora,serif;font-style:italic;'
            f'color:#e8e6dc;margin-bottom:1.25rem;">'
            f'"{result.overall_feedback}"</div>',
            unsafe_allow_html=True,
        )

    def _bucket(label: str, color: str, items, empty_msg: str, name_key: str = "name", rationale_key: str = "rationale"):
        st.markdown(
            f'<div class="section-label" style="color:{color};margin-top:8px;">{label}</div>',
            unsafe_allow_html=True,
        )
        if not items:
            st.markdown(
                f'<div class="irac-card" style="padding:10px 14px;font-family:Lora,serif;'
                f'font-style:italic;color:#6e6c65;">{empty_msg}</div>',
                unsafe_allow_html=True,
            )
            return
        for it in items:
            if hasattr(it, name_key):
                name = getattr(it, name_key)
                rationale = getattr(it, rationale_key, "")
            else:
                name, rationale = str(it), ""
            st.markdown(
                f'<div class="irac-card" style="padding:10px 14px;margin-bottom:5px;'
                f'border-left:3px solid {color};">'
                f'<div style="font-family:Poppins,sans-serif;font-weight:600;font-size:14px;color:#faf9f5;">{name}</div>'
                + (f'<div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;margin-top:4px;">{rationale}</div>' if rationale else '')
                + '</div>',
                unsafe_allow_html=True,
            )

    _bucket("✓ Caught", "#788c5d", result.student_caught,
            "You didn't catch any of the real issues this round.")
    _bucket("✗ Missed", "#d97757", result.student_missed,
            "Nothing missed — full coverage.")
    if result.student_extra:
        _bucket("? False alarm", "#b0aea5", result.student_extra,
                "", name_key="(no_attr)", rationale_key="(no_attr)")


# ── Case Brief renderer ───────────────────────────────────────────────────────

def show_case_brief(brief, expanded: bool = True):
    """Renders a CaseBrief in styled expanders.

    Mirrors show_irreac's visual rhythm so the two outputs feel like one app.
    The Dissent expander only renders if there's actually a dissent.
    """
    # Case name as a header card before the expanders.
    st.markdown(
        f'<div class="irac-card irac-card-accent" style="margin-bottom:1rem;padding:14px 18px;">'
        f'<div class="section-label">Case Name</div>'
        f'<div style="font-family:Lora,serif;font-size:15px;color:#faf9f5;font-weight:600;">'
        f'{brief.case_name or "(not identified)"}'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    sections = [
        ("Facts", brief.facts, "irac-card-blue"),
        ("Procedural Posture", brief.procedural_posture, "irac-card-blue"),
        ("Issue", brief.issue, "irac-card-accent"),
        ("Holding", brief.holding, "irac-card-green"),
        ("Reasoning", brief.reasoning, "irac-card-accent"),
    ]
    for label, content, _ in sections:
        with st.expander(f"**{label}**", expanded=expanded):
            st.markdown(content or "*Not provided*")

    if brief.dissent.strip():
        with st.expander("**Dissent**", expanded=expanded):
            st.markdown(brief.dissent)

    if brief.notes:
        st.markdown(
            '<div style="margin-top:1rem;">'
            '<div class="section-label">Exam Notes</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        for note in brief.notes:
            st.markdown(
                f'<div class="irac-card" style="margin-bottom:6px;padding:10px 14px;">'
                f'<span style="color:#d97757;font-weight:700;margin-right:8px;">—</span>'
                f'<span style="font-family:Lora,serif;font-size:14px;color:#e8e6dc;">{note}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )



# ── Progress bar ──────────────────────────────────────────────────────────────

# Maps stream status labels → (percentage, sublabel)
_PROGRESS_STEPS = {
    "Identifying the legal issue...":             (18, "Reading the facts and spotting the legal question"),
    "Retrieving applicable rules...":             (35, "Finding statutes, restatements, and case law"),
    "Exploring case law and interpretations...":  (52, "Reviewing how courts have applied this rule"),
    "Applying rules to the facts...":             (72, "Analyzing each element against the specific facts"),
    "Drafting conclusion...":                     (88, "Writing the final answer with confidence level"),
    "Preparing study tips...":                    (95, "Identifying common mistakes on this issue type"),
}

# Same shape, different labels — used by the Case Brief streaming pipeline.
_BRIEF_PROGRESS_STEPS = {
    "Identifying the case...":                  (8,  "Reading citation and party names"),
    "Extracting the facts...":                  (22, "Distilling what happened, in plain English"),
    "Tracing the procedural history...":        (35, "How the case got to this court"),
    "Framing the legal question...":            (48, "Pinning down the precise issue"),
    "Distilling the holding...":                (62, "What the court decided and the rule it announced"),
    "Summarizing the court's reasoning...":     (80, "Why the court ruled this way"),
    "Capturing the dissent...":                 (90, "Recording any dissenting opinion"),
    "Compiling exam takeaways...":              (96, "Why this case matters for your exam"),
}


def _render_progress(slot, pct: int, label: str, sublabel: str = "", done: bool = False):
    bar_color = "#788c5d" if done else "#d97757"
    glow = f"box-shadow: 0 0 12px rgba(217,119,87,0.4);" if not done else ""
    slot.markdown(f"""
<div style="background:#1e1d1b; border:1px solid #2a2925; border-radius:14px;
            padding:28px 28px 22px 28px; margin:12px 0;">
    <div style="display:flex; justify-content:space-between; align-items:baseline; margin-bottom:16px;">
        <div>
            <div style="font-family:'Poppins',sans-serif; font-size:11px; font-weight:700;
                        text-transform:uppercase; letter-spacing:0.12em; color:#b0aea5; margin-bottom:4px;">
                {'✓ Complete' if done else 'Generating'}
            </div>
            <div style="font-family:'Poppins',sans-serif; font-size:15px; font-weight:600; color:#faf9f5;">
                {label}
            </div>
        </div>
        <div style="font-family:'Poppins',sans-serif; font-size:32px; font-weight:700;
                    color:{'#788c5d' if done else '#d97757'}; line-height:1;">
            {pct}%
        </div>
    </div>
    <div style="background:#2a2925; border-radius:8px; height:10px; overflow:hidden; margin-bottom:12px;">
        <div style="width:{pct}%; height:100%;
                    background:linear-gradient(90deg, {bar_color}, {'#a0c070' if done else '#e8956a'});
                    border-radius:8px; {glow}
                    transition: width 0.4s ease;"></div>
    </div>
    <div style="font-family:'Lora',serif; font-size:13px; color:#b0aea5; min-height:18px;">
        {sublabel}
    </div>
</div>
""", unsafe_allow_html=True)


def stream_with_progress(facts: str, area: str,
                         start_pct: int = 0, end_pct: int = 100,
                         phase: str = "Generating IRAC analysis") -> IRRACOutput:
    """
    Runs stream_irreac with a live animated progress bar.
    start_pct / end_pct let you chain multiple phases (e.g. 0→50, 50→100).
    Returns the parsed IRRACOutput.
    """
    from irac_engine import stream_irreac

    slot = st.empty()
    _render_progress(slot, start_pct, phase, "Starting...")

    result = None
    current_pct = start_pct
    current_label = phase
    current_sublabel = "Reading the facts..."
    last_section_pct = start_pct  # tracks last pct set by a section marker

    source = st.session_state.get("outline_source", "default")
    if source not in ("mine", "default", "none"):
        source = "default"
    for event, data in stream_irreac(facts, area, outline_source=source):
        if event == "status":
            step_pct, sublabel = _PROGRESS_STEPS.get(data, (start_pct + 10, ""))
            new_pct = start_pct + int((step_pct / 100) * (end_pct - start_pct))
            # Floor: never let the bar move backwards. With non-zero start_pct
            # (e.g. Compare tab uses start_pct=0..70 then 70..100), token-based
            # ticks can outpace the first section marker's mapped percentage.
            current_pct = max(current_pct, new_pct)
            last_section_pct = current_pct
            current_label = data
            current_sublabel = sublabel
            _render_progress(slot, current_pct, current_label, current_sublabel)
        elif event == "tick":
            # Show gentle progress between section markers so the bar isn't frozen.
            # Map first ~800 tokens to the first 15% of the bar's allocated range
            # (start_pct → end_pct), not an absolute +15 — otherwise a non-zero
            # start_pct (e.g. Compare tab uses 0..70) over-shoots and the first
            # section marker would have to pull the bar backwards.
            token_count = data
            range_size = end_pct - start_pct
            tick_max = int(0.15 * range_size)
            tick_pct = start_pct + min(int(token_count / 800 * tick_max), tick_max)
            if tick_pct > current_pct and last_section_pct == start_pct:
                current_pct = tick_pct
                _render_progress(slot, current_pct, current_label, current_sublabel)
        elif event == "done":
            result = data

    _render_progress(slot, end_pct, "Complete", "", done=True)
    time.sleep(0.6)
    slot.empty()
    return result


def stream_brief_with_progress(text: str, phase: str = "Briefing the case"):
    """Same animated progress bar as stream_with_progress, but for case briefs.

    Reuses _BRIEF_PROGRESS_STEPS (case-brief-specific labels) and the engine's
    stream_case_brief generator. Returns the parsed CaseBrief.
    """
    from irac_engine import stream_case_brief

    slot = st.empty()
    _render_progress(slot, 0, phase, "Reading the case opinion...")

    result = None
    current_pct = 0
    current_label = phase
    current_sublabel = "Reading the case opinion..."
    last_section_pct = 0

    for event, data in stream_case_brief(text):
        if event == "status":
            step_pct, sublabel = _BRIEF_PROGRESS_STEPS.get(data, (current_pct + 5, ""))
            current_pct = max(current_pct, step_pct)
            last_section_pct = current_pct
            current_label = data
            current_sublabel = sublabel
            _render_progress(slot, current_pct, current_label, current_sublabel)
        elif event == "tick":
            token_count = data
            tick_pct = min(int(token_count / 800 * 15), 15)
            if tick_pct > current_pct and last_section_pct == 0:
                current_pct = tick_pct
                _render_progress(slot, current_pct, current_label, current_sublabel)
        elif event == "done":
            result = data

    _render_progress(slot, 100, "Complete", "", done=True)
    time.sleep(0.6)
    slot.empty()
    return result


def run_with_time_progress(func, *args, phase: str, sublabels: list,
                           est_seconds: float = 60.0, **kwargs):
    """
    Run a non-streaming function while showing the animated progress card.
    Used for calls that don't expose token-level events (e.g. parallel dual
    generation, JSON-format grading). Progress is estimated from elapsed time.

    sublabels: list of (pct_threshold, label) tuples — label shown once that
    pct is reached. First entry is the initial sublabel.
    """
    from concurrent.futures import ThreadPoolExecutor

    progress_slot = st.empty()
    initial_sublabel = sublabels[0][1] if sublabels else ""
    _render_progress(progress_slot, 0, phase, initial_sublabel)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func, *args, **kwargs)
        start = time.time()
        last_pct = 0
        while not future.done():
            elapsed = time.time() - start
            if elapsed < est_seconds:
                # Linear ramp 0 → 90 over the estimated duration.
                pct = int(elapsed / est_seconds * 90)
            else:
                # Asymptotic crawl: each additional est_seconds halves the gap
                # to 99. Bar keeps moving — never the dead 95% pause.
                overage = elapsed - est_seconds
                crawl = 9 * (1 - 0.5 ** (overage / est_seconds))
                pct = min(int(90 + crawl), 99)
            sublabel = initial_sublabel
            for threshold, label in sublabels:
                if pct >= threshold:
                    sublabel = label
            if pct != last_pct:
                _render_progress(progress_slot, pct, phase, sublabel)
                last_pct = pct
            time.sleep(0.4)
        result = future.result()

    _render_progress(progress_slot, 100, "Complete", "", done=True)
    time.sleep(0.4)
    progress_slot.empty()
    return result


def stream_issue_map_with_progress(facts: str, area: str) -> str:
    """
    Renders a live progress bar + incremental issue-map text as the model streams.
    Returns the full text once generation completes.
    """
    from irac_engine import stream_zoom_out

    progress_slot = st.empty()
    text_slot = st.empty()

    _render_progress(progress_slot, 0, "Mapping issues", "Reading the facts...")

    # Issue maps are short — typically 150–300 tokens.
    EST_TOKENS = 250
    accumulated = ""
    last_pct = 0
    last_text_render = 0

    sublabel_steps = [
        (10,  "Spotting threshold issues..."),
        (35,  "Identifying substantive issues..."),
        (65,  "Weighing strength of each issue..."),
        (85,  "Recommending analysis order..."),
    ]

    for token, accumulated, count in stream_zoom_out(facts, area):
        pct = min(int(count / EST_TOKENS * 95), 95)

        sublabel = "Reading the facts..."
        for threshold, label in sublabel_steps:
            if pct >= threshold:
                sublabel = label

        if pct - last_pct >= 4:
            _render_progress(progress_slot, pct, "Mapping issues", sublabel)
            last_pct = pct

        # Stream the text into the page every ~15 tokens so the user
        # sees content appearing — far more reassuring than a static bar.
        if count - last_text_render >= 15:
            text_slot.markdown(
                f'<div class="irac-card irac-card-blue" style="opacity:0.85;">{accumulated}</div>',
                unsafe_allow_html=True,
            )
            last_text_render = count

    _render_progress(progress_slot, 100, "Complete", "", done=True)
    time.sleep(0.4)
    progress_slot.empty()
    text_slot.empty()
    return accumulated.strip()


def starter_template(section: str) -> str:
    """Returns a starter sentence template for each IRAC section."""
    templates = {
        "issue": "Whether [party A] can [claim/defense] against [party B] for [legal theory] given [key fact].",
        "rule": "Under [Restatement (Second) of Contracts § __] / [UCC § __] / [[Case Name], [Year]], [state the rule]. The elements are: (1) [element 1]; (2) [element 2]; (3) [element 3].\n\nCourts have interpreted this rule to [majority view]. A minority of jurisdictions [minority view]. In [Key Case, Year], the court held [relevant interpretation].",
        "application": "Element 1: [Element Name]\n[Apply the rule to the specific facts. Quote or paraphrase key facts. Counter-argument: [opposing party] may argue [X], however [refutation].]\n\nElement 2: [Element Name]\n[Continue analysis...]",
        "conclusion": "Therefore, [party] will likely [prevail/not prevail] on a claim for [theory]. Confidence: [High/Moderate/Low] — [one-sentence reason].",
    }
    return templates.get(section, "")
