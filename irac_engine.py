import json
import ollama
from models import (
    IRRACOutput, DualIRAC, IRACFeedback, CaseBrief,
    IssueSpottingResult, EssayFeedback, MBEQuestion,
)

MODEL_NAME = "irac-maker"

# Shared Ollama config:
#   num_predict=1536  → cap output so the model can't ramble past the JSON close brace
#   keep_alive="30m"  → prevents the 6.6GB model from being unloaded from VRAM between
#                       requests; otherwise every call after 5min idle pays a 10–30s reload.
#   think=False       → CRITICAL: disables Qwen3.5's hidden chain-of-thought. This is a
#                       top-level kwarg on ollama.chat — putting it inside `options` is
#                       silently ignored, and the model burns thousands of tokens thinking
#                       before emitting any visible content.
_OLLAMA_OPTIONS = {"num_predict": 1536}
_KEEP_ALIVE = "30m"

AREAS_OF_LAW = [
    "Contracts",
    "Torts",
    "Constitutional Law",
    "Criminal Law",
    "Criminal Procedure",
    "Property",
    "Civil Procedure",
    "Evidence",
    "Administrative Law",
    "Business Associations",
    "Family Law",
    "Professional Responsibility",
]

# Frequently-tested sub-topics within each area (MEE/MBE focus). Used by the
# Hypo Generator and (later) MBE Practice to scope the fact pattern. Keeping
# the lists short — a topic should be specific enough to anchor a single
# essay/question but broad enough that the LLM has room to write a real hypo.
AREA_TOPICS = {
    "Business Associations": [
        "Agency",
        "General Partnership",
        "Limited Partnership / LLP",
        "Corporation: Formation & Promoters",
        "Corporation: Director & Officer Duties",
        "Corporation: Shareholder Rights & Derivative Suits",
        "Corporation: Piercing the Corporate Veil",
        "Corporation: Mergers & Dissolution",
        "Limited Liability Company (LLC)",
    ],
    "Contracts": [
        "Offer & Acceptance",
        "Consideration & Promissory Estoppel",
        "Defenses to Formation",
        "Statute of Frauds",
        "Performance & Breach",
        "Remedies & Damages",
        "UCC Article 2 (Sales)",
        "Third-Party Rights & Assignment",
    ],
    "Torts": [
        "Intentional Torts",
        "Negligence",
        "Strict Liability",
        "Products Liability",
        "Defamation",
        "Privacy Torts",
        "Vicarious Liability",
        "Damages & Defenses",
    ],
    "Constitutional Law": [
        "Justiciability (Standing, Ripeness, Mootness)",
        "Federalism & Commerce Clause",
        "Separation of Powers",
        "Procedural Due Process",
        "Substantive Due Process",
        "Equal Protection",
        "First Amendment: Speech",
        "First Amendment: Religion",
        "Takings",
    ],
    "Criminal Law": [
        "Actus Reus & Mens Rea",
        "Homicide",
        "Inchoate Crimes (Attempt, Solicitation, Conspiracy)",
        "Accomplice Liability",
        "Property Crimes",
        "Defenses (Self-Defense, Insanity, Duress, etc.)",
    ],
    "Criminal Procedure": [
        "Fourth Amendment: Search & Seizure",
        "Fourth Amendment: Warrants & Exceptions",
        "Fifth Amendment: Self-Incrimination & Miranda",
        "Sixth Amendment: Right to Counsel",
        "Identification Procedures",
        "Exclusionary Rule",
    ],
    "Property": [
        "Estates in Land",
        "Future Interests",
        "Concurrent Estates (JT, TIC, TBE)",
        "Landlord-Tenant",
        "Real Property Sales (Contract & Deed)",
        "Easements, Covenants, Equitable Servitudes",
        "Adverse Possession",
        "Mortgages",
        "Recording & Title",
    ],
    "Civil Procedure": [
        "Subject Matter Jurisdiction",
        "Personal Jurisdiction",
        "Venue & Removal",
        "Erie Doctrine & Choice of Law",
        "Pleadings & Motions",
        "Discovery",
        "Summary Judgment & Trial",
        "Joinder & Class Actions",
        "Preclusion (Res Judicata, Collateral Estoppel)",
    ],
    "Evidence": [
        "Relevance (FRE 401-403)",
        "Hearsay & Exceptions",
        "Character Evidence",
        "Impeachment",
        "Privileges",
        "Authentication & Best Evidence",
        "Expert & Lay Opinion",
    ],
    "Administrative Law": [
        "Rulemaking Procedures",
        "Adjudication & Due Process",
        "Judicial Review (Standing, Ripeness)",
        "Chevron / Skidmore Deference",
        "Delegation Doctrine",
    ],
    "Family Law": [
        "Marriage & Premarital Agreements",
        "Divorce Grounds",
        "Property Distribution",
        "Spousal Support / Alimony",
        "Child Custody",
        "Child Support",
        "Adoption & Termination of Parental Rights",
    ],
    "Professional Responsibility": [
        "Conflicts of Interest",
        "Confidentiality",
        "Client Funds & Trust Accounts",
        "Fees & Fee-Splitting",
        "Candor Toward the Tribunal",
        "Solicitation & Advertising",
        "Reporting Misconduct",
    ],
}

# ── prompts ────────────────────────────────────────────────────────────────────

GENERATE_PROMPT = """Analyze this American law school hypo using IRREAC.
Respond ONLY with valid JSON. No text before or after the JSON.

Area of Law: {area}

Facts:
{facts}

JSON response:"""

# Variant used when the user has uploaded outlines and the auto-inject toggle
# is on — see outlines.relevant_excerpts(). Excerpts are paraphrase-source,
# never to be quoted verbatim.
GENERATE_PROMPT_WITH_OUTLINE = """Analyze this American law school hypo using IRREAC.
Respond ONLY with valid JSON. No text before or after the JSON.

The following excerpts are from the student's own legally-owned outline.
Use them to inform the rule citations, terminology, and analysis emphasis.
Do NOT copy verbatim — paraphrase. Treat this as background context.

--- STUDENT'S OUTLINE EXCERPTS ---
{excerpts}
---

Area of Law: {area}

Facts:
{facts}

JSON response:"""

PLAINTIFF_PROMPT = """You are arguing the PLAINTIFF'S strongest possible IRREAC.
Build the most favorable interpretation of the facts for the plaintiff.
Respond ONLY with valid JSON.

Area of Law: {area}

Facts:
{facts}

JSON response (plaintiff's strongest argument):"""

DEFENDANT_PROMPT = """You are arguing the DEFENDANT'S strongest possible IRREAC.
Build the most favorable interpretation of the facts for the defendant.
Emphasize counter-arguments, missing elements, and defenses.
Respond ONLY with valid JSON.

Area of Law: {area}

Facts:
{facts}

JSON response (defendant's strongest argument):"""

FEEDBACK_SYSTEM = """You are a tough but fair American law school professor grading a student's IRAC answer.

You will receive: the facts, a model IRREAC (the correct answer), and the student's IRAC draft.

Grading rules:
- Be specific — quote or paraphrase exact parts of the student's answer
- Be honest — do not inflate scores; law school grading is rigorous
- Be constructive — say how to improve, not just what is wrong
- Score each section: "Excellent" / "Good" / "Needs Work" / "Missing"
- Overall grade uses a realistic law school curve (most get B or B+; A is exceptional)
- Application is worth the most — it is where exam points are won or lost
- If the student stated the conclusion before completing the Application, call it out explicitly

Respond ONLY with valid JSON:
{
  "issue": {"score": "Excellent|Good|Needs Work|Missing", "strengths": "...", "gaps": "..."},
  "rule": {"score": "Excellent|Good|Needs Work|Missing", "strengths": "...", "gaps": "..."},
  "application": {"score": "Excellent|Good|Needs Work|Missing", "strengths": "...", "gaps": "..."},
  "conclusion": {"score": "Excellent|Good|Needs Work|Missing", "strengths": "...", "gaps": "..."},
  "overall_grade": "A|A-|B+|B|B-|C+|C|C-|D|F",
  "key_insight": "The single most important thing the student should fix or add",
  "overall_feedback": "2-3 sentence holistic assessment"
}"""

FEEDBACK_PROMPT = """Area of Law: {area}

Facts:
{facts}

--- MODEL IRREAC ---
Issue: {model_issue}
Rule Statement: {model_rule_statement}
Rule Exploration: {model_rule_exploration}
Application: {model_application}
Conclusion: {model_conclusion}

--- STUDENT IRAC ---
Issue: {student_issue}
Rule: {student_rule}
Application: {student_application}
Conclusion: {student_conclusion}

Grade the student's IRAC. Respond ONLY with valid JSON."""

WHOLE_STUDENT_FEEDBACK_PROMPT = """Area of Law: {area}

Facts:
{facts}

--- MODEL IRREAC (the reference) ---
Issue: {model_issue}
Rule Statement: {model_rule_statement}
Rule Exploration: {model_rule_exploration}
Application: {model_application}
Conclusion: {model_conclusion}

--- STUDENT IRAC (provided as ONE block of text — first identify the
Issue, Rule, Application, and Conclusion sections inside it, then grade
each one separately against the model) ---
{student_text}

Grade the student's IRAC against the model. Respond ONLY with valid JSON."""

SOCRATIC_SYSTEM = """You are a law professor using the Socratic method to help a student identify legal issues in a fact pattern.

Rules — follow these exactly:
- Ask ONE question at a time. Never two questions in one response.
- Never give the answer directly. Guide with questions only.
- When the student correctly identifies an issue, acknowledge briefly: "Right — that raises [issue name]. What else do you see?"
- When the student guesses wrong, ask a redirecting question without confirming or denying.
- When ALL key issues have been identified, respond with this exact format:
  "COMPLETE: You've identified all the key issues: [list them]. Ready to generate the full IRREAC?"
- Keep responses under 3 sentences.
- Do not lecture. Do not list things. Ask one question."""

SOCRATIC_PROMPT = """Area of Law: {area}

Facts:
{facts}

Conversation so far:
{history}

Student's last message: {last_message}

Ask your next Socratic question (one question only, under 3 sentences):"""

ZOOM_OUT_SYSTEM = """You are a law professor creating a quick issue map for a student.
Output a map only — no full IRAC, no rule statements, no application.
Each issue: name + one sentence why it arises + strength (Strong/Contested/Weak).
End with suggested analysis order."""

ZOOM_OUT_PROMPT = """Area of Law: {area}

Facts:
{facts}

Produce the issue map. Format:

## Issue Map — {area}

### Threshold Issues
1. [Name] — [One sentence]. Strength: Strong/Contested/Weak

### Substantive Issues
1. [Name] — [One sentence]. Strength: Strong/Contested/Weak

### Suggested Analysis Order
[Brief recommendation]"""


CASE_BRIEF_SYSTEM = """You are a legal research assistant briefing an American court case for a law school student.

Output ONLY valid JSON. No prose before or after.

Briefing rules:
- Be concise but complete. Each section is meant to fit on a flashcard.
- "case_name": include the full citation if visible (Plaintiff v. Defendant, Reporter Cite (Year)). If only the names appear, use them.
- "facts": plain-English narrative of the underlying dispute. 3-6 sentences. Drop procedural detail.
- "procedural_posture": how the case got to this court. Trial court ruling → appellate path. 1-3 sentences.
- "issue": the precise legal question. Frame as "Whether ... given ...".
- "holding": direct answer (Yes/No/Affirmed/Reversed/etc) plus a single-sentence statement of the rule the court announced.
- "reasoning": why the court reached this conclusion. Include the rule applied, key precedents the court relied on, and analysis. This is the longest section.
- "dissent": one-paragraph summary of dissent(s) if present, else "" (empty string).
- "notes": 2-3 short bullets — exam significance, common pitfalls, or how this case is typically tested.

Output schema:
{
  "case_name": "...",
  "facts": "...",
  "procedural_posture": "...",
  "issue": "Whether ...",
  "holding": "...",
  "reasoning": "...",
  "dissent": "",
  "notes": ["...", "..."]
}"""

CASE_BRIEF_PROMPT = """Brief the following case. Respond ONLY with valid JSON matching the schema.

Case text:
{text}

JSON brief:"""


ISSUE_SPOT_SYSTEM = """You are a tough but fair American law school professor running an issue-spotting drill.

Your job is NOT to write a full IRAC. You are only judging COVERAGE: did the student spot every issue the facts raise?

Rules:
- First, internally identify EVERY real issue the facts raise in the given area of law (including procedural, threshold, and sub-issues).
- Then compare to the student's listed issues.
- For each real issue, decide: did the student catch it (full match), or miss it (no plausible match in their list)?
- A loose paraphrase counts as a catch — focus on substance, not exact wording.
- If the student listed something that isn't actually an issue here, put it in "student_extra".
- coverage_score is "<caught> / <total_real_issues>", e.g. "4/6".
- Be specific in rationales — quote a fact that triggers each issue.

Output ONLY valid JSON:
{
  "student_caught": [{"name": "<issue>", "rationale": "<one sentence>"}],
  "student_missed": [{"name": "<issue>", "rationale": "<one sentence>"}],
  "student_extra":  ["<thing student listed that isn't really an issue>"],
  "coverage_score": "X/Y",
  "overall_feedback": "<2-3 sentence holistic note>"
}"""


ISSUE_SPOT_PROMPT = """Area of Law: {area}

Facts:
{facts}

Student's spotted issues (one per line):
{student_issues}

Grade the coverage. Respond ONLY with valid JSON."""


ESSAY_SYSTEM = """You are a tough but fair American law school professor grading a student's
multi-issue essay answer. Bar-exam-style essays raise multiple legal issues and the student
must address each one with full IRAC (Issue, Rule, Application, Conclusion).

Grading procedure:
1. First, internally identify EVERY real issue the facts raise.
2. For each real issue, locate what the student wrote (quote/paraphrase briefly).
   If they didn't address it at all, mark "Missing".
3. Score each issue: Excellent / Good / Needs Work / Missing.
4. Aggregate to a realistic letter grade (most students get B/B+; A is exceptional).
5. Coverage matters — addressing 4 of 6 issues poorly beats addressing 2 of 6 well.
6. Application carries the most weight inside each issue.

Output ONLY valid JSON:
{
  "issues": [
    {
      "issue_name": "<short name>",
      "student_treatment": "<1-2 sentence summary of what the student wrote, or 'Not addressed'>",
      "score": "Excellent | Good | Needs Work | Missing",
      "strengths": "<what they did well, or empty if Missing>",
      "gaps": "<what was missing or wrong>"
    }
  ],
  "coverage_note": "Addressed X of Y issues",
  "overall_grade": "A | A- | B+ | B | B- | C+ | C | C- | D | F",
  "overall_feedback": "<2-3 sentence holistic note>",
  "key_insight": "<single most important fix>"
}"""


ESSAY_PROMPT = """Area of Law: {area}

Facts:
{facts}

Student's essay (multi-issue):
{essay}

Grade the essay. Respond ONLY with valid JSON."""


MBE_SYSTEM = """You are a bar exam question writer creating ONE original MBE-style multiple choice question.

Style guide (mimic the actual MBE):
- Facts: a tight 75-150 word fact pattern. No fluff.
- Call of question: precise — "Who is most likely to prevail?", "Which of the following is the strongest argument...", etc.
- Four choices labeled A, B, C, D. Single best answer.
- Distractors must be plausible — common student mistakes, partially correct, or wrong rule application. Never absurd.
- Test core doctrine in the area, not trivia.
- The correct answer reflects the majority/MBE-tested rule unless the call says otherwise.

For EACH choice (correct AND incorrect), explain WHY in 1-2 sentences. The explanations are the
teaching moment — be specific.

Output ONLY valid JSON:
{
  "facts": "...",
  "call_of_question": "...",
  "choices": [
    {"letter": "A", "text": "..."},
    {"letter": "B", "text": "..."},
    {"letter": "C", "text": "..."},
    {"letter": "D", "text": "..."}
  ],
  "correct_letter": "A | B | C | D",
  "explanations": {
    "A": "Why A is right or wrong",
    "B": "...",
    "C": "...",
    "D": "..."
  },
  "area": "<the area provided>"
}"""


MBE_PROMPT = """Generate one MBE-style question.

Area of Law: {area}
Difficulty: {difficulty}

Output ONLY valid JSON."""


HYPO_SYSTEM = """You are a law professor writing an original MEE-style (Multistate Essay Exam) fact pattern for a law school student.

Style guide:
- Bar-exam realism. Use ordinary names (Alice, Bob, Carol — or invent your own), specific dates, concrete dollar amounts, and named places.
- Raise legal issues CLEARLY through the facts but NEVER name a legal doctrine in the narrative. The student must spot the issues from the facts.
- Hit core doctrine in the given area of law. Avoid trivia.
- If a TOPIC is specified, anchor the fact pattern firmly within that topic. Other areas may incidentally arise but the dominant issues must come from the named topic.
- Word counts:
    Single issue:   80-150 words, 1-2 issues.
    Multi-issue:    200-400 words, 3-6 issues.
    Comprehensive:  400-600 words, 5-8 issues, bar-exam length.

If a "Call of question" should be included, append it on a new paragraph at the end, prefixed exactly with **Question:** (markdown bold). Use OPEN-ENDED phrasing — never name the doctrine. Examples:
  • "**Question:** What rights and remedies do the parties have? Discuss."
  • "**Question:** How should the court rule on each of Alice's claims?"
  • "**Question:** Discuss all defenses available to Bob."

If "no call" is requested, output ONLY the fact pattern with no question and no labels.

Output is plain prose with markdown bold for the optional Question line. NO JSON. NO bullet list of issues. NO analysis. NO topic header."""


HYPO_PROMPT = """Generate one original MEE-style fact pattern.

Area of Law:   {area}
{topic_line}
Complexity:    {complexity}
Call of question: {call}

Fact pattern (plain prose only{call_hint}):"""


DEFAULT_OUTLINE_SYSTEM = """You are writing a concise rule-reference outline for an American law school student.

Your job is RULES, not analysis. Output is markdown text only — no JSON, no preamble.

Style guide:
- Hierarchical: top-level doctrines (## headers), sub-doctrines (###), elements as bullet lists.
- Cite sources: Restatement (Second/Third) §, UCC §, landmark case + year. Plaintext citations, no fancy formatting.
- Note majority vs minority where relevant. Mark MBE-tested rules clearly.
- Keep the whole outline tight — target 700–1200 words. This is a quick reference, not a hornbook.
- Cover: black-letter rules, elements, exceptions, defenses, relevant tests/standards.

DO NOT include: hypos, fact patterns, IRAC examples, lengthy case explanations, or commentary.
ONLY rules, elements, and citations.

Begin directly with the first ## header. No preamble like "Here is your outline:"."""

DEFAULT_OUTLINE_PROMPT = """Write a tight rule-reference outline for {area}.

Use majority/MBE-tested rules unless a minority position is exam-relevant.

Output: markdown only."""


# ── functions ──────────────────────────────────────────────────────────────────

def _chat(system: str | None, user: str, use_json: bool = True) -> dict:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    kwargs = {
        "model": MODEL_NAME,
        "messages": messages,
        "options": _OLLAMA_OPTIONS,
        "keep_alive": _KEEP_ALIVE,
        "think": False,
    }
    if use_json:
        kwargs["format"] = "json"
    return ollama.chat(**kwargs)


def _build_generate_prompt(facts: str, area: str, outline_source: str = "default") -> str:
    """Pick GENERATE_PROMPT or its outline-augmented variant based on source.

    `outline_source`:
      "mine"    — keyword-matched excerpts from the user's uploaded outlines
                  (outlines.py)
      "default" — the AI-generated, lazy-cached built-in outline for `area`
                  (default_outlines.py)
      "none"    — no outline context; LLM uses only its own training knowledge

    All sub-imports are lazy so this module stays importable in environments
    without filesystem state.
    """
    extras = ""
    if outline_source == "mine":
        try:
            import outlines as _outlines
            extras = _outlines.relevant_excerpts(facts, area)
        except Exception:
            extras = ""
    elif outline_source == "default":
        # Use the cached built-in outline IF it already exists. Do NOT
        # trigger a 30-60s on-demand generation here — that would block the
        # IRAC stream's first token by ~45s with no UI feedback ("Starting..."
        # frozen on the progress card). The user explicitly generates each
        # area's outline from the My Outlines tab, where progress is shown.
        # Cache miss = silent fallthrough to no-context generation.
        try:
            import default_outlines as _do
            if _do.exists(area):
                extras = _do.load(area)
                # Cap the inject — built-in outlines target ~1200 words but the
                # LLM occasionally overshoots, and ctx_size is 4096 in Modelfile.
                if extras and len(extras) > 6000:
                    extras = extras[:6000] + "\n[…truncated…]"
        except Exception:
            extras = ""

    if extras:
        return GENERATE_PROMPT_WITH_OUTLINE.format(
            area=area, facts=facts.strip(), excerpts=extras,
        )
    return GENERATE_PROMPT.format(area=area, facts=facts.strip())


def generate_irreac(facts: str, area: str = "Contracts",
                    outline_source: str = "default") -> IRRACOutput:
    prompt = _build_generate_prompt(facts, area, outline_source)
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        format="json",
        options=_OLLAMA_OPTIONS,
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return IRRACOutput(**json.loads(resp["message"]["content"]))


# Section markers detected in the streaming JSON to show live progress
_SECTION_LABELS = {
    '"issue"':           ("I — Issue",           "Identifying the legal issue..."),
    '"rule_statement"':  ("R — Rule Statement",   "Retrieving applicable rules..."),
    '"rule_exploration"':("R — Rule Exploration", "Exploring case law and interpretations..."),
    '"application"':     ("A — Application",      "Applying rules to the facts..."),
    '"conclusion"':      ("C — Conclusion",       "Drafting conclusion..."),
    '"tips"':            ("Tips",                 "Preparing study tips..."),
}


def stream_irreac(facts: str, area: str = "Contracts",
                  outline_source: str = "default"):
    """
    Yields progress events while streaming the IRAC generation.
    Event types:
      ("status", label)   — a new IRAC section has started
      ("token",  text)    — raw token (for optional live display)
      ("done",   IRRACOutput) — generation complete, parsed result

    outline_source: "mine" | "default" | "none" — see _build_generate_prompt.
    Plaintiff/Defendant generation in Both Sides intentionally passes "none"
    so user-specific or built-in outlines don't bias an opposing-counsel
    exercise.
    """
    prompt = _build_generate_prompt(facts, area, outline_source)
    # NOTE: format="json" + stream=True buffers the entire response before yielding
    # any tokens, defeating streaming. We omit format here and parse JSON manually.
    stream = ollama.chat(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        options=_OLLAMA_OPTIONS,
        keep_alive=_KEEP_ALIVE,
        think=False,
    )

    full_text = ""
    seen_sections = set()
    token_count = 0
    _TOKEN_STEP = 40  # emit a "tick" event every N tokens for progress animation

    for chunk in stream:
        token = chunk["message"]["content"]
        full_text += token
        token_count += 1
        yield ("token", token)

        if token_count % _TOKEN_STEP == 0:
            yield ("tick", token_count)

        for marker, (_, label) in _SECTION_LABELS.items():
            if marker in full_text and marker not in seen_sections:
                seen_sections.add(marker)
                yield ("status", label)
                break

    # Extract JSON — model may wrap output in markdown fences or thinking tags
    json_start = full_text.find('{')
    json_end = full_text.rfind('}') + 1
    json_str = full_text[json_start:json_end] if json_start != -1 else full_text
    try:
        result = IRRACOutput(**json.loads(json_str))
    except Exception:
        # Most common cause: num_predict cap truncated the JSON mid-output.
        # Attempt a cheap repair (close unbalanced braces/brackets) before
        # falling back to a full regenerate — the silent 130s retry was a
        # genuinely terrible UX when it kicked in.
        try:
            repaired = _repair_truncated_json(json_str)
            result = IRRACOutput(**json.loads(repaired))
        except Exception:
            # Last resort: deterministic re-call with format=json. Still slow
            # but at least guaranteed-valid output rather than a third failure.
            # Pass outline_source through so the fallback uses the same
            # context the original streaming attempt did.
            result = generate_irreac(facts, area, outline_source)
    yield ("done", result)


def _repair_truncated_json(s: str) -> str:
    """Best-effort repair for JSON truncated mid-output by num_predict.

    Handles the realistic failure modes:
      - missing closing braces/brackets
      - trailing comma after the last value
      - unterminated string at end (closes with a quote)
    Does not attempt full JSON5-style repair; if the structure is too broken
    the caller's outer try/except will fall through.
    """
    s = s.strip().rstrip(',')
    # If we ended inside an unterminated string, close it.
    # Count unescaped quotes — odd number means we're mid-string.
    in_string = False
    escape = False
    for ch in s:
        if escape:
            escape = False
            continue
        if ch == '\\':
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
    if in_string:
        s += '"'
    # Close any unbalanced brackets/braces.
    s += ']' * (s.count('[') - s.count(']'))
    s += '}' * (s.count('{') - s.count('}'))
    return s


def generate_dual_irac(facts: str, area: str = "Contracts") -> DualIRAC:
    """Generate plaintiff's and defendant's strongest IRREAC sequentially.

    Ollama on this hardware cannot truly parallelize — two concurrent calls
    serialize internally with overhead, ending up ~10% slower than sequential.
    Measured on M4/16GB: seq 142s vs parallel 154s. Keeping it sequential
    means the caller can also stream each side independently for better UX.
    """
    def _gen(prompt: str) -> IRRACOutput:
        resp = ollama.chat(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            format="json",
            options=_OLLAMA_OPTIONS,
            keep_alive=_KEEP_ALIVE,
            think=False,
        )
        return IRRACOutput(**json.loads(resp["message"]["content"]))

    plaintiff = _gen(PLAINTIFF_PROMPT.format(area=area, facts=facts.strip()))
    defendant = _gen(DEFENDANT_PROMPT.format(area=area, facts=facts.strip()))
    return DualIRAC(plaintiff=plaintiff, defendant=defendant)


def compare_irac(
    facts: str,
    area: str,
    student_issue: str = "",
    student_rule: str = "",
    student_application: str = "",
    student_conclusion: str = "",
    model_irac: IRRACOutput | None = None,
    student_full_text: str = "",
) -> IRACFeedback:
    """Grade a student IRAC against the AI-drafted model IRREAC.

    The student input can come in two shapes:
      • Section by section: pass `student_issue/rule/application/conclusion`
        and leave `student_full_text` empty.
      • Whole-paste: pass `student_full_text` (the four section args are
        ignored). The grader is told to identify the I/R/A/C sections
        inside the block before scoring each one.
    """
    if model_irac is None:
        raise ValueError("compare_irac requires a model_irac (the AI-drafted reference).")

    if student_full_text.strip():
        prompt = WHOLE_STUDENT_FEEDBACK_PROMPT.format(
            area=area,
            facts=facts.strip(),
            model_issue=model_irac.issue,
            model_rule_statement=model_irac.rule_statement,
            model_rule_exploration=model_irac.rule_exploration,
            model_application=model_irac.application,
            model_conclusion=model_irac.conclusion,
            student_text=student_full_text.strip(),
        )
    else:
        prompt = FEEDBACK_PROMPT.format(
            area=area,
            facts=facts.strip(),
            model_issue=model_irac.issue,
            model_rule_statement=model_irac.rule_statement,
            model_rule_exploration=model_irac.rule_exploration,
            model_application=model_irac.application,
            model_conclusion=model_irac.conclusion,
            student_issue=student_issue.strip() or "(not provided)",
            student_rule=student_rule.strip() or "(not provided)",
            student_application=student_application.strip() or "(not provided)",
            student_conclusion=student_conclusion.strip() or "(not provided)",
        )
    resp = _chat(FEEDBACK_SYSTEM, prompt, use_json=True)
    return IRACFeedback(**json.loads(resp["message"]["content"]))


def generate_default_outline(area: str) -> str:
    """Generate a tight rule-reference outline for the given area of law.

    Returns markdown text. Long output budget (num_predict=2400) because we
    want a 700–1200 word outline; system prompt enforces the upper bound.
    Called by default_outlines.get_or_generate() on first request per area.
    """
    prompt = DEFAULT_OUTLINE_PROMPT.format(area=area)
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": DEFAULT_OUTLINE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        options={"num_predict": 2400},
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return resp["message"]["content"].strip()


def generate_hypo(
    area: str = "Contracts",
    complexity: str = "Multi-issue",
    topic: str = "",
    include_call: bool = True,
) -> str:
    """Generate one fresh MEE-style fact pattern. Plain text — no JSON wrapper.

    Parameters
    ----------
    area : str
        One of AREAS_OF_LAW.
    complexity : str
        "Single issue" | "Multi-issue" | "Comprehensive". Maps to target word
        count and issue count via the system prompt.
    topic : str
        Optional sub-topic from AREA_TOPICS[area]. Empty string means
        "any topic in the area". When provided, the LLM anchors the hypo
        firmly within that topic.
    include_call : bool
        When True (Long Essay / Compare), the fact pattern ends with a
        **Question:** call-of-question paragraph. When False (Issue
        Spotting), only the facts — preserves the spotter exercise.
    """
    topic_line = f"Topic:         {topic}" if topic else "Topic:         (any in this area)"
    call = "Yes — include MEE-style **Question:** paragraph at the end." if include_call else "No — facts only, no question."
    call_hint = "" if include_call else ", facts only — no Question line"
    prompt = HYPO_PROMPT.format(
        area=area, topic_line=topic_line, complexity=complexity,
        call=call, call_hint=call_hint,
    )
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": HYPO_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        options={"num_predict": 1500},
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return resp["message"]["content"].strip()


def generate_mbe_question(area: str = "Contracts", difficulty: str = "Medium") -> MBEQuestion:
    """Generate one fresh MBE-style question. Output budget is generous because
    the JSON has 4 choices + 4 explanations.
    """
    prompt = MBE_PROMPT.format(area=area, difficulty=difficulty)
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": MBE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"num_predict": 2000},
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return MBEQuestion(**json.loads(resp["message"]["content"]))


def grade_essay(facts: str, area: str, essay: str) -> EssayFeedback:
    """Grade a multi-issue essay. Bigger token budget than IRAC since output
    has one feedback block per issue plus aggregates.
    """
    prompt = ESSAY_PROMPT.format(
        area=area, facts=facts.strip(), essay=essay.strip() or "(empty)",
    )
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": ESSAY_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options={"num_predict": 2400},  # multi-issue output runs longer
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return EssayFeedback(**json.loads(resp["message"]["content"]))


def grade_issue_spot(facts: str, area: str, student_issues: str) -> IssueSpottingResult:
    """Grade a student's issue-spotting drill against the facts.

    student_issues is the raw textarea content — the model handles formatting
    (one per line, numbered, bulleted, prose-style — all OK).
    """
    prompt = ISSUE_SPOT_PROMPT.format(
        area=area,
        facts=facts.strip(),
        student_issues=student_issues.strip() or "(none provided)",
    )
    resp = _chat(ISSUE_SPOT_SYSTEM, prompt, use_json=True)
    return IssueSpottingResult(**json.loads(resp["message"]["content"]))


def socratic_next_question(facts: str, area: str, history: list[dict]) -> str:
    """Returns the professor's next Socratic question, or a COMPLETE: message."""
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in history[:-1]
    ) if len(history) > 1 else "(conversation just started)"
    last_message = history[-1]["content"] if history else ""
    prompt = SOCRATIC_PROMPT.format(
        area=area,
        facts=facts.strip(),
        history=history_text,
        last_message=last_message,
    )
    resp = _chat(SOCRATIC_SYSTEM, prompt, use_json=False)
    return resp["message"]["content"].strip()


def stream_zoom_out(facts: str, area: str):
    """
    Streaming variant of zoom_out — yields (token_text, accumulated_text, count)
    so the UI can render a live progress bar and incremental text.
    """
    prompt = ZOOM_OUT_PROMPT.format(area=area, facts=facts.strip())
    stream = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": ZOOM_OUT_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        options=_OLLAMA_OPTIONS,
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    accumulated = ""
    count = 0
    for chunk in stream:
        token = chunk["message"]["content"]
        if not token:
            continue
        accumulated += token
        count += 1
        yield (token, accumulated, count)


# ── Case Brief ────────────────────────────────────────────────────────────────

# Case briefs are longer than IRACs (8 fields, all narrative). Bump the token
# cap so the JSON close-brace isn't truncated mid-reasoning. With 1536, the
# model would frequently drop the last 1-3 fields; 2400 leaves comfortable
# headroom even for opinion-dense Supreme Court cases.
_BRIEF_OLLAMA_OPTIONS = {"num_predict": 2400}


# Section markers detected in the streaming JSON for live progress updates.
_BRIEF_SECTION_LABELS = {
    '"case_name"':          ("Case Name",          "Identifying the case..."),
    '"facts"':              ("Facts",              "Extracting the facts..."),
    '"procedural_posture"': ("Procedural Posture", "Tracing the procedural history..."),
    '"issue"':              ("Issue",              "Framing the legal question..."),
    '"holding"':            ("Holding",            "Distilling the holding..."),
    '"reasoning"':          ("Reasoning",          "Summarizing the court's reasoning..."),
    '"dissent"':            ("Dissent",            "Capturing the dissent..."),
    '"notes"':              ("Exam Notes",         "Compiling exam takeaways..."),
}


def generate_case_brief(text: str) -> CaseBrief:
    """Non-streaming case brief generation. Used as the truncation-fallback path."""
    prompt = CASE_BRIEF_PROMPT.format(text=text.strip())
    resp = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": CASE_BRIEF_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        format="json",
        options=_BRIEF_OLLAMA_OPTIONS,
        keep_alive=_KEEP_ALIVE,
        think=False,
    )
    return CaseBrief(**json.loads(resp["message"]["content"]))


def stream_case_brief(text: str):
    """Yields progress events while streaming the case brief.

    Event types match stream_irreac so the same UI helpers work:
      ("status", label)        — a new brief section has started
      ("token",  text)         — raw token
      ("tick",   count)        — periodic token-counter ping for the progress bar
      ("done",   CaseBrief)    — generation complete, parsed result
    """
    prompt = CASE_BRIEF_PROMPT.format(text=text.strip())
    stream = ollama.chat(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": CASE_BRIEF_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        stream=True,
        options=_BRIEF_OLLAMA_OPTIONS,
        keep_alive=_KEEP_ALIVE,
        think=False,
    )

    full_text = ""
    seen_sections = set()
    token_count = 0
    _TOKEN_STEP = 40

    for chunk in stream:
        token = chunk["message"]["content"]
        full_text += token
        token_count += 1
        yield ("token", token)

        if token_count % _TOKEN_STEP == 0:
            yield ("tick", token_count)

        for marker, (_, label) in _BRIEF_SECTION_LABELS.items():
            if marker in full_text and marker not in seen_sections:
                seen_sections.add(marker)
                yield ("status", label)
                break

    json_start = full_text.find('{')
    json_end = full_text.rfind('}') + 1
    json_str = full_text[json_start:json_end] if json_start != -1 else full_text
    try:
        result = CaseBrief(**json.loads(json_str))
    except Exception:
        # Same repair-then-fall-back-to-non-stream pattern as stream_irreac.
        try:
            repaired = _repair_truncated_json(json_str)
            result = CaseBrief(**json.loads(repaired))
        except Exception:
            result = generate_case_brief(text)
    yield ("done", result)


def check_model_ready() -> bool:
    try:
        models = ollama.list()
        names = [m.model for m in models.models]
        return any(MODEL_NAME in n for n in names)
    except Exception:
        return False
