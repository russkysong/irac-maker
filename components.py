import time
import streamlit as st
import streamlit.components.v1 as components
from models import IRRACOutput


# ── Area-of-Law modal picker ──────────────────────────────────────────────────
@st.dialog("Pick Area of Law")
def pick_area_dialog(state_key: str, default: str = "Contracts"):
    """Modal picker that auto-closes the moment a pill is selected.

    The dialog widget needs its own widget key (separate from `state_key`)
    because Streamlit doesn't allow modifying a widget's session_state value
    during the same run that the widget is created. We mirror the pick into
    `state_key` and call st.rerun() — that closes the dialog AND lets the
    parent page read the new value from session_state on the next render.
    """
    from irac_engine import AREAS_OF_LAW
    current = st.session_state.get(state_key) or default
    selected = st.pills(
        "Area of Law", AREAS_OF_LAW,
        default=current,
        key=f"_dialog_pills_{state_key}",
        label_visibility="collapsed",
    )
    if selected and selected != current:
        st.session_state[state_key] = selected
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


def render_timer(minutes: int = 90):
    """Renders an interactive countdown timer using JavaScript."""
    components.html(f"""
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;600;700&display=swap" rel="stylesheet">
<div style="background:#1e1d1b; border:1px solid #2a2925; border-radius:12px; padding:20px 16px; text-align:center; font-family:'Poppins',sans-serif;">
    <div style="font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:0.12em; color:#b0aea5; margin-bottom:10px;">Bar Exam Timer</div>
    <div id="td" style="font-size:52px; font-weight:700; color:#faf9f5; letter-spacing:0.04em; line-height:1; font-variant-numeric:tabular-nums;">{minutes:02d}:00</div>
    <div id="tlabel" style="font-size:11px; color:#b0aea5; margin-top:6px; height:16px;"></div>
    <div style="margin-top:16px; display:flex; gap:8px; justify-content:center;">
        <button id="startBtn" onclick="toggle()" style="background:#d97757; color:#141413; border:none; border-radius:7px; padding:7px 20px; font-family:'Poppins',sans-serif; font-size:13px; font-weight:600; cursor:pointer; transition:all 0.2s;">Start</button>
        <button onclick="reset()" style="background:#2a2925; color:#faf9f5; border:1px solid #3a3830; border-radius:7px; padding:7px 16px; font-family:'Poppins',sans-serif; font-size:13px; cursor:pointer; transition:all 0.2s;">Reset</button>
    </div>
</div>
<script>
const TOTAL = {minutes * 60};
let rem = TOTAL, iv = null, running = false;

function fmt(s) {{
    return String(Math.floor(s/60)).padStart(2,'0') + ':' + String(s%60).padStart(2,'0');
}}
function update() {{
    const d = document.getElementById('td');
    const l = document.getElementById('tlabel');
    d.textContent = rem > 0 ? fmt(rem) : 'TIME UP';
    if (rem <= 0) {{
        d.style.color='#ef4444'; d.style.animation='pulse 1s ease infinite';
        l.textContent='Time is up';
    }} else if (rem <= 300) {{
        d.style.color='#ef4444'; d.style.animation='pulse 1s ease infinite';
        l.textContent='Under 5 minutes!';
    }} else if (rem <= 600) {{
        d.style.color='#d97757'; d.style.animation='none';
        l.textContent='10 minutes remaining';
    }} else {{
        d.style.color='#faf9f5'; d.style.animation='none';
        l.textContent='';
    }}
}}
function toggle() {{
    const btn = document.getElementById('startBtn');
    if (!running) {{
        running=true; btn.textContent='Pause'; btn.style.background='#3a3830'; btn.style.color='#faf9f5';
        iv = setInterval(()=>{{ if(rem>0){{rem--;update();}} else {{clearInterval(iv);running=false;}} }}, 1000);
    }} else {{
        running=false; clearInterval(iv); btn.textContent='Resume'; btn.style.background='#d97757'; btn.style.color='#141413';
    }}
}}
function reset() {{
    clearInterval(iv); running=false; rem=TOTAL; update();
    const btn=document.getElementById('startBtn'); btn.textContent='Start'; btn.style.background='#d97757'; btn.style.color='#141413';
}}
</script>
<style>
@keyframes pulse {{ 0%,100%{{opacity:1}} 50%{{opacity:0.45}} }}
</style>
""", height=175)


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

    for event, data in stream_irreac(facts, area):
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
