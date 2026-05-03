import html
import streamlit as st
import styles
import components as C
from irac_engine import (
    compare_irac,
    socratic_next_question, check_model_ready, AREAS_OF_LAW,
)
from models import IRRACOutput
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

<div style="display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:1.5rem;">
    <div class="irac-card" style="padding:14px 16px;">
        <div class="section-label">Generate IRAC</div>
        <div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;line-height:1.5;">
            Paste a fact pattern — AI drafts a full structured IRAC analysis with citations and element-by-element application.
        </div>
    </div>
    <div class="irac-card irac-card-blue" style="padding:14px 16px;">
        <div class="section-label" style="color:#6a9bcc;">Both Sides</div>
        <div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;line-height:1.5;">
            Generates the plaintiff's strongest argument and the defendant's strongest argument side by side.
        </div>
    </div>
    <div class="irac-card irac-card-green" style="padding:14px 16px;">
        <div class="section-label" style="color:#788c5d;">Compare & Feedback</div>
        <div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;line-height:1.5;">
            Write your own IRAC first, then get it graded section-by-section against the AI's model answer.
        </div>
    </div>
    <div class="irac-card" style="padding:14px 16px;border-left:3px solid #b0aea5;">
        <div class="section-label" style="color:#b0aea5;">Socratic Mode</div>
        <div style="font-family:Lora,serif;font-size:13px;color:#b0aea5;line-height:1.5;">
            A professor asks you one question at a time to help you spot the legal issues yourself — no answers given upfront.
        </div>
    </div>
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
tab_gen, tab_both, tab_cmp, tab_soc = st.tabs([
    "Generate IRAC", "Both Sides", "Compare & Feedback", "Socratic Mode",
])


# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — GENERATE
# ════════════════════════════════════════════════════════════════════════════════
with tab_gen:
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown('<div class="section-label">Hypo Setup</div>', unsafe_allow_html=True)
        area_gen = st.pills(
            "Area of Law", AREAS_OF_LAW,
            default="Contracts", key="area_gen",
        ) or "Contracts"
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
        st.markdown('<div class="section-label">Options</div>', unsafe_allow_html=True)
        show_timer = st.toggle("Bar Exam Timer", value=False)
        if show_timer:
            timer_min = st.slider("Minutes", 30, 180, 90, 5)
            C.render_timer(timer_min)

        st.markdown('<div class="section-label" style="margin-top:1rem;">How IRAC Works</div>', unsafe_allow_html=True)
        st.markdown("""
**IRAC** is the standard legal reasoning framework used in American law schools and on the bar exam.

| Step | What it covers |
|---|---|
| **I — Issue** | The precise legal question the court must answer |
| **R — Rule** | The applicable rule with citation — statute, restatement section, or landmark case |
| **A — Application** | Each rule element applied to the specific facts — **this is where exam points are won or lost** |
| **C — Conclusion** | A direct answer to the Issue, with a confidence level |

**Note:** The AI breaks the Rule into two parts — what the rule says, and how courts have interpreted it. This gives you richer Rule analysis than a basic IRAC outline.
""")

    with col_right:
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


# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — BOTH SIDES
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

    area_bs = st.pills(
        "Area of Law", AREAS_OF_LAW,
        default="Contracts", key="area_bs",
    ) or "Contracts"
    col_bs, col_empty = st.columns([1, 2])
    with col_bs:
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
                col_p, col_d = st.columns(2, gap="large")
                with col_p:
                    st.markdown('<div class="section-label" style="color:#d97757;">Plaintiff\'s Best Argument</div>', unsafe_allow_html=True)
                    C.show_irreac(p_result)
                with col_d:
                    st.markdown('<div class="section-label" style="color:#6a9bcc;">Defendant\'s Best Argument</div>', unsafe_allow_html=True)
                    C.show_irreac(d_result)
            except Exception as e:
                st.error(f"Generation failed: {e}")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — COMPARE & FEEDBACK
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
        "Reference IRAC source",
        [
            "Compare against AI-drafted answer",
            "Compare against my own reference IRAC",
        ],
        horizontal=True,
        key="cmp_mode",
        help=(
            "AI-drafted: the model generates the reference IRAC from the facts. "
            "Own reference: paste an IRAC you want to grade against (e.g., a textbook model answer)."
        ),
    )
    is_manual = cmp_mode == "Compare against my own reference IRAC"

    area_cmp = st.pills(
        "Area of Law", AREAS_OF_LAW,
        default=st.session_state.last_area, key="area_cmp",
    ) or st.session_state.last_area
    facts_cmp = st.text_area(
        "Facts", height=110, key="facts_cmp",
        value=st.session_state.last_facts,
        placeholder="Paste the hypo facts here...",
    )

    st.markdown('<div class="section-label" style="margin-top:1rem;">Your IRAC Draft</div>', unsafe_allow_html=True)
    st.caption("Write each section separately. Even a rough draft earns better feedback than a blank page.")

    # Issue + Rule row
    # Streamlit anti-pattern note: setting `value=` on a widget with a `key=`
    # only works on the first render. After session_state[key] exists, `value`
    # is silently ignored. To inject template text we must write the widget's
    # session_state key directly, BEFORE the widget is constructed, then rerun.
    col_i, col_r = st.columns(2)
    with col_i:
        C.section_tip("issue")
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
        C.section_tip("rule")
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

    # Application + Conclusion row
    col_a, col_c = st.columns(2)
    with col_a:
        C.section_tip("application")
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
        C.section_tip("conclusion")
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

    # ── Reference IRAC input (only when manual mode) ──────────────────────────
    ref_full_text = ""
    if is_manual:
        st.divider()
        st.markdown('<div class="section-label">Reference IRAC (whole)</div>', unsafe_allow_html=True)
        st.caption(
            "Paste the whole IRAC you want to compare against — one block of text. "
            "Section labels (Issue:, Rule:, Application:, Conclusion: or I:, R:, A:, C:) help, "
            "but aren't required."
        )
        ref_full_text = st.text_area(
            "Reference IRAC",
            height=320,
            label_visibility="collapsed",
            key="r_full",
            placeholder=(
                "Paste a textbook model answer, your professor's answer key, or any "
                "complete IRAC here as one block.\n\n"
                "Issue: ...\n"
                "Rule: ...\n"
                "Application: ...\n"
                "Conclusion: ..."
            ),
        )

    btn_label = (
        "Compare with My Reference + Get Feedback"
        if is_manual
        else "Generate AI IRAC + Get Feedback"
    )
    cmp_btn = st.button(btn_label, type="primary", use_container_width=True)

    if cmp_btn:
        if not facts_cmp.strip():
            st.warning("Paste facts first.")
        elif not any([student_issue.strip(), student_rule.strip(), student_app.strip(), student_conc.strip()]):
            st.warning("Write at least one section of your draft before comparing.")
        elif is_manual and not ref_full_text.strip():
            st.warning("Paste your reference IRAC before comparing.")
        else:
            try:
                if is_manual:
                    # Whole-text reference: stash the full paste in `application` so
                    # the existing IRRACOutput model can carry it. compare_irac
                    # detects an empty rule_statement+issue+conclusion and switches
                    # to whole-text grading mode.
                    model_irac = IRRACOutput(
                        issue="",
                        rule_statement="",
                        rule_exploration="",
                        application=ref_full_text.strip(),
                        conclusion="",
                        tips=[],
                    )
                else:
                    model_irac = C.stream_with_progress(
                        facts_cmp, area_cmp, start_pct=0, end_pct=70,
                        phase="Generating model IRAC",
                    )
                st.session_state.last_irac = model_irac
                st.session_state.last_facts = facts_cmp
                st.session_state.last_area = area_cmp

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
                    facts=facts_cmp, area=area_cmp,
                    student_issue=student_issue, student_rule=student_rule,
                    student_application=student_app, student_conclusion=student_conc,
                    model_irac=model_irac,
                )
                st.divider()
                st.markdown('<div class="section-label">Side-by-Side Comparison</div>', unsafe_allow_html=True)
                col_s, col_ai = st.columns(2, gap="large")
                with col_s:
                    st.markdown('<div class="section-label" style="color:#6a9bcc;">Your Draft</div>', unsafe_allow_html=True)
                    for label, text in [
                        ("I — Issue", student_issue), ("R — Rule", student_rule),
                        ("A — Application", student_app), ("C — Conclusion", student_conc),
                    ]:
                        with st.expander(f"**{label}**", expanded=True):
                            st.markdown(text or "*Not provided*")
                with col_ai:
                    ref_label = "Your Reference IRAC" if is_manual else "AI IRAC"
                    st.markdown(f'<div class="section-label" style="color:#d97757;">{ref_label}</div>', unsafe_allow_html=True)
                    if is_manual:
                        with st.expander("**Reference (full text)**", expanded=True):
                            st.markdown(ref_full_text.strip() or "*Not provided*")
                    else:
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

                # PDF download is only meaningful for the AI-drafted reference
                # (it expects a structured IRREAC). Skip it in whole-text mode.
                if not is_manual:
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
# TAB 4 — SOCRATIC MODE
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
        soc_area = st.pills(
            "Area of Law", AREAS_OF_LAW,
            default="Contracts", key="soc_area_input",
        ) or "Contracts"
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
