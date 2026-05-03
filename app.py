import html
from datetime import datetime, timezone

import streamlit as st
import styles
import components as C
import outlines
import history
from irac_engine import (
    compare_irac,
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

@st.cache_resource(show_spinner=False)
def _model_ready_cached() -> bool:
    return check_model_ready()

if not _model_ready_cached():
    st.error("**Model not found.** Run setup first:\n\n```bash\nbash setup.sh\n```", icon="🔴")
    st.stop()

# ── Session state ──────────────────────────────────────────────────────────────
DEFAULTS = {
    "last_irac": None, "last_facts": "", "last_area": "Contracts",
    "socratic_history": [], "socratic_facts": "", "socratic_area": "Contracts",
    "socratic_started": False,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Tabs ───────────────────────────────────────────────────────────────────────
tab_gen, tab_brief, tab_both, tab_cmp, tab_soc, tab_outlines, tab_history, tab_about = st.tabs([
    "Generate IRAC", "Case Brief", "Both Sides", "Compare & Feedback",
    "Socratic Mode", "My Outlines", "History", "About",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ════════════════════════════════════════════════════════════════════════════════
with tab_gen:
    # ── Setup (full width, single column) ─────────────────────────────────────
    _area = st.session_state.get("area_gen_value") or "Contracts"
    if st.button(f"⚖️ Area of Law: {_area}", key="btn_area_gen"):
        C.pick_area_dialog("area_gen_value")
    area_gen = _area
    facts_gen = st.text_area(
        "Facts", height=260, key="facts_gen",
        placeholder=(
            "Paste or type your fact pattern here...\n\n"
            "e.g. Alice offered to sell her 2020 Honda Civic for $12,000. "
            "Bob replied '$11,500.' Alice said 'Deal at $11,800.' "
            "Bob showed up three days later — Alice had already sold to Carol."
        ),
    )
    col_a, col_b = st.columns([3, 2])
    with col_a:
        gen_btn = st.button("Generate IRAC", type="primary", use_container_width=True)
    with col_b:
        zoom_btn = st.button("Issue Map First", use_container_width=True, help="See all issues before full analysis")

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
                st.session_state.last_area = area_gen
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
<p style="font-family:Lora,serif;font-size:15px;color:#e8e6dc;line-height:1.7;">
<strong>IRAC</strong> is the standard legal reasoning framework used in American law schools and on the bar exam.
</p>

<table class="how-irac-table">
    <colgroup>
        <col style="width: 220px;">
        <col>
    </colgroup>
    <thead>
        <tr><th>Step</th><th>What it covers</th></tr>
    </thead>
    <tbody>
        <tr><td><strong>I — Issue</strong></td><td>The precise legal question the court must answer</td></tr>
        <tr><td><strong>R — Rule</strong></td><td>The applicable rule with citation — statute, restatement section, or landmark case</td></tr>
        <tr><td><strong>A — Application</strong></td><td>Each rule element applied to the specific facts — <strong>this is where exam points are won or lost</strong></td></tr>
        <tr><td><strong>C — Conclusion</strong></td><td>A direct answer to the Issue, with a confidence level</td></tr>
    </tbody>
</table>

<p style="font-family:Lora,serif;font-size:15px;color:#e8e6dc;line-height:1.7;margin-top:1rem;">
<strong>Note:</strong> The AI breaks the Rule into two parts — what the rule says, and how courts have interpreted it. This gives you richer Rule analysis than a basic IRAC outline.
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

    _area_bs = st.session_state.get("area_bs_value") or "Contracts"
    if st.button(f"⚖️ Area of Law: {_area_bs}", key="btn_area_bs"):
        C.pick_area_dialog("area_bs_value")
    area_bs = _area_bs
    facts_bs = st.text_area("Facts", height=180, key="facts_bs",
                            placeholder="Paste the fact pattern here...")
    both_btn = st.button("Generate Both Sides", type="primary", use_container_width=True)

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
                st.session_state.last_area = area_bs
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
# TAB 4 — COMPARE & FEEDBACK
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
        help=(
            "Section by section: write each I/R/A/C field individually with tips and word counts. "
            "Paste whole: drop in an IRAC you wrote elsewhere as one block of text. "
            "Either way, the AI drafts a model answer from the facts and grades you against it."
        ),
    )
    is_paste = cmp_mode == "Paste my whole IRAC as one block"

    _area_cmp = st.session_state.get("area_cmp_value") or st.session_state.last_area
    if st.button(f"⚖️ Area of Law: {_area_cmp}", key="btn_area_cmp"):
        C.pick_area_dialog("area_cmp_value")
    area_cmp = _area_cmp
    facts_cmp = st.text_area(
        "Facts", height=110, key="facts_cmp",
        value=st.session_state.last_facts,
        placeholder="Paste the hypo facts here...",
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
                if st.button("Template", key="tpl_i", use_container_width=True):
                    st.session_state["s_issue"] = C.starter_template("issue")
                    st.rerun()
            student_issue = st.text_area(
                "Issue", height=110, label_visibility="collapsed", key="s_issue",
                placeholder="Whether ... given ...",
            )
            C.word_count_bar(student_issue, "issue")

        with col_r:
            col_r_hdr, col_r_btn = st.columns([3, 1])
            with col_r_hdr:
                st.markdown("**R — Rule**")
            with col_r_btn:
                if st.button("Template", key="tpl_r", use_container_width=True):
                    st.session_state["s_rule"] = C.starter_template("rule")
                    st.rerun()
            student_rule = st.text_area(
                "Rule", height=110, label_visibility="collapsed", key="s_rule",
                placeholder="Under [statute/case], the rule requires...",
            )
            C.word_count_bar(student_rule, "rule")

        col_a, col_c = st.columns(2)
        with col_a:
            col_a_hdr, col_a_btn = st.columns([3, 1])
            with col_a_hdr:
                st.markdown("**A — Application**")
            with col_a_btn:
                if st.button("Template", key="tpl_a", use_container_width=True):
                    st.session_state["s_app"] = C.starter_template("application")
                    st.rerun()
            student_app = st.text_area(
                "Application", height=200, label_visibility="collapsed", key="s_app",
                placeholder="Element 1: ...\nElement 2: ...",
            )
            C.word_count_bar(student_app, "application")

        with col_c:
            col_c_hdr, col_c_btn = st.columns([3, 1])
            with col_c_hdr:
                st.markdown("**C — Conclusion**")
            with col_c_btn:
                if st.button("Template", key="tpl_c", use_container_width=True):
                    st.session_state["s_conc"] = C.starter_template("conclusion")
                    st.rerun()
            student_conc = st.text_area(
                "Conclusion", height=200, label_visibility="collapsed", key="s_conc",
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
                st.session_state.last_area = area_cmp

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
# TAB 5 — SOCRATIC MODE
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
        _area_soc = st.session_state.get("soc_area_value") or "Contracts"
        if st.button(f"⚖️ Area of Law: {_area_soc}", key="btn_area_soc"):
            C.pick_area_dialog("soc_area_value")
        soc_area = _area_soc
        col_soc_f, col_soc_btn = st.columns([3, 1])
        with col_soc_f:
            soc_facts = st.text_area("Facts", height=160, key="soc_facts_input",
                                      placeholder="Paste the hypo facts here...")
        with col_soc_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            start_btn = st.button("Start Session", type="primary", use_container_width=True)

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
                    st.session_state.last_area = st.session_state.socratic_area
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
# TAB 6 — MY OUTLINES
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

    # ── Auto-inject toggle ─────────────────────────────────────────────────────
    st.toggle(
        "Use my outlines when generating IRACs",
        value=st.session_state.get("inject_outlines", True),
        key="inject_outlines",
        help=(
            "When on, the IRAC generator looks for outlines tagged with the "
            "current area of law and adds short matching excerpts as context."
        ),
    )

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
# TAB 7 — HISTORY
# ════════════════════════════════════════════════════════════════════════════════
from models import IRRACOutput as _IRRACOutput, CaseBrief as _CaseBrief

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
            ["all", "irac", "brief"],
            default="all",
            key="history_type",
            format_func=lambda x: {"all": "All", "irac": "IRACs", "brief": "Briefs"}[x],
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
            type_color = "#d97757" if entry_type_v == "irac" else "#6a9bcc"
            type_label = "IRAC" if entry_type_v == "irac" else "Brief"
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
                    if entry_type_v == "irac" and st.button(
                        "Reopen in Compare & Feedback",
                        key=f"reopen_{entry_id}",
                        use_container_width=True,
                    ):
                        st.session_state.last_irac = _IRRACOutput(**result)
                        st.session_state.last_facts = entry.get("facts", "")
                        st.session_state.last_area = area or "Contracts"
                        st.toast("Loaded into Compare & Feedback tab.", icon="↗️")
                with col_del:
                    if st.button("Delete", key=f"hist_del_{entry_id}",
                                 use_container_width=True):
                        history.delete_entry(entry_id)
                        st.rerun()


# ════════════════════════════════════════════════════════════════════════════════
# TAB 8 — ABOUT
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
        <div class="section-label" style="color:#788c5d;">Compare & Feedback</div>
        <div style="font-family:Lora,serif;font-size:14px;color:#b0aea5;line-height:1.6;">
            Write your own IRAC first, then get it graded section-by-section against the AI's model answer.
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
