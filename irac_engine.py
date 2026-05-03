import json
import ollama
from models import IRRACOutput, DualIRAC, IRACFeedback

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

# ── prompts ────────────────────────────────────────────────────────────────────

GENERATE_PROMPT = """Analyze this American law school hypo using IRREAC.
Respond ONLY with valid JSON. No text before or after the JSON.

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


def generate_irreac(facts: str, area: str = "Contracts") -> IRRACOutput:
    prompt = GENERATE_PROMPT.format(area=area, facts=facts.strip())
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


def stream_irreac(facts: str, area: str = "Contracts"):
    """
    Yields progress events while streaming the IRAC generation.
    Event types:
      ("status", label)   — a new IRAC section has started
      ("token",  text)    — raw token (for optional live display)
      ("done",   IRRACOutput) — generation complete, parsed result
    """
    prompt = GENERATE_PROMPT.format(area=area, facts=facts.strip())
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
            result = generate_irreac(facts, area)
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
    student_issue: str,
    student_rule: str,
    student_application: str,
    student_conclusion: str,
    model_irac: IRRACOutput,
) -> IRACFeedback:
    # If the reference doesn't separate Rule Statement from Rule Exploration
    # (e.g. a user-pasted IRAC), pass a placeholder for R2 so the grader
    # doesn't penalize the student for missing case-law commentary that
    # isn't in the reference either.
    rule_exploration = model_irac.rule_exploration.strip()
    if not rule_exploration:
        rule_exploration = "(not provided in reference — do not penalize student for missing this)"
    prompt = FEEDBACK_PROMPT.format(
        area=area,
        facts=facts.strip(),
        model_issue=model_irac.issue,
        model_rule_statement=model_irac.rule_statement,
        model_rule_exploration=rule_exploration,
        model_application=model_irac.application,
        model_conclusion=model_irac.conclusion,
        student_issue=student_issue.strip() or "(not provided)",
        student_rule=student_rule.strip() or "(not provided)",
        student_application=student_application.strip() or "(not provided)",
        student_conclusion=student_conclusion.strip() or "(not provided)",
    )
    resp = _chat(FEEDBACK_SYSTEM, prompt, use_json=True)
    return IRACFeedback(**json.loads(resp["message"]["content"]))


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


def check_model_ready() -> bool:
    try:
        models = ollama.list()
        names = [m.model for m in models.models]
        return any(MODEL_NAME in n for n in names)
    except Exception:
        return False
