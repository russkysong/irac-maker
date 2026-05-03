from pydantic import BaseModel, Field
from typing import List


class IRRACOutput(BaseModel):
    """
    IRREAC = Issue, Rule Statement, Rule Exploration, Application, Conclusion.
    Two-Rule variant outperforms standard IRAC by ~7 points (2022 research).
    """
    issue: str = Field(description="Legal question framed as whether X given Y")
    rule_statement: str = Field(description="Specific rule with statute/restatement citation")
    rule_exploration: str = Field(description="Court interpretations, key cases, majority vs minority views")
    application: str = Field(description="Element-by-element analysis of facts against each rule component")
    conclusion: str = Field(description="Direct answer with confidence level and one-sentence reason")
    tips: List[str] = Field(description="Common mistakes students make on this type of issue")


class DualIRAC(BaseModel):
    """Both-sides analysis: strongest plaintiff argument vs strongest defendant argument."""
    plaintiff: IRRACOutput
    defendant: IRRACOutput


class SectionFeedback(BaseModel):
    score: str = Field(description="Excellent | Good | Needs Work | Missing")
    strengths: str = Field(description="What the student got right in this section")
    gaps: str = Field(description="What was missing, imprecise, or incorrect")


class IRACFeedback(BaseModel):
    issue: SectionFeedback
    rule: SectionFeedback
    application: SectionFeedback
    conclusion: SectionFeedback
    overall_grade: str = Field(description="Letter grade: A, A-, B+, B, B-, C+, C, C-, D, F")
    key_insight: str = Field(description="The single most important thing the student should improve")
    overall_feedback: str = Field(description="2-3 sentence holistic assessment")


class SpottedIssue(BaseModel):
    """A single issue identified during Issue Spotting grading."""
    name: str = Field(description="Short name for the issue, e.g. 'Mirror image rule' or 'Promissory estoppel'")
    rationale: str = Field(default="", description="One-sentence reason why this issue arises in the facts")


class IssueSpottingResult(BaseModel):
    """Result of grading a student's issue-spotting drill.

    The grader categorizes every issue into one of three buckets and gives
    a coverage score. We accept defaults so a partially-emitted JSON still
    renders rather than crashing.
    """
    student_caught: List[SpottedIssue] = Field(
        default_factory=list,
        description="Real issues the student correctly identified",
    )
    student_missed: List[SpottedIssue] = Field(
        default_factory=list,
        description="Real issues the student did not list",
    )
    student_extra: List[str] = Field(
        default_factory=list,
        description="Items on the student's list that aren't real issues here",
    )
    coverage_score: str = Field(
        default="",
        description="Fraction string, e.g. '4/6' (caught / total real issues)",
    )
    overall_feedback: str = Field(
        default="",
        description="2-3 sentence holistic note for the student",
    )


class EssayIssueFeedback(BaseModel):
    """Per-issue grade inside a multi-issue essay."""
    issue_name: str = Field(default="", description="Short name for the issue")
    student_treatment: str = Field(
        default="",
        description="1-2 sentence summary of what the student wrote about this issue (or 'Not addressed')",
    )
    score: str = Field(default="Missing", description="Excellent | Good | Needs Work | Missing")
    strengths: str = Field(default="", description="What the student did well on this issue")
    gaps: str = Field(default="", description="What was missing or wrong")


class EssayFeedback(BaseModel):
    """Result of grading a multi-issue (bar-exam-style) essay."""
    issues: List[EssayIssueFeedback] = Field(default_factory=list)
    coverage_note: str = Field(
        default="",
        description="Sentence about how many real issues were addressed, e.g. 'Addressed 4 of 6 issues'",
    )
    overall_grade: str = Field(default="", description="Letter grade")
    overall_feedback: str = Field(default="", description="2-3 sentence holistic note")
    key_insight: str = Field(default="", description="The single most important fix")


class MBEChoice(BaseModel):
    """One of the four answer choices on an MBE-style question."""
    letter: str = Field(default="", description="A, B, C, or D")
    text: str = Field(default="", description="The choice text")


class MBEQuestion(BaseModel):
    """An MBE-style multiple-choice question with explanations for every choice."""
    facts: str = Field(default="", description="Fact pattern (75-150 words)")
    call_of_question: str = Field(default="", description="The 'call' — what the question asks")
    choices: List[MBEChoice] = Field(default_factory=list)
    correct_letter: str = Field(default="", description="A | B | C | D")
    explanations: dict = Field(
        default_factory=dict,
        description='Per-choice explanation, keyed by letter: {"A": "...", "B": "..."}',
    )
    area: str = Field(default="", description="Area of law")


class CaseBrief(BaseModel):
    """Structured case brief for law school study.

    All fields default to empty so a model that omits a section still parses
    successfully — the renderer falls back to "Not provided" / hides empty
    sections. Strict validation here would convert a 95%-good response into
    a hard failure, which is worse UX than rendering what we got.
    """
    case_name: str = Field(default="", description="Full citation: Plaintiff v. Defendant, Cite (Year)")
    facts: str = Field(default="", description="Plain-English facts of the dispute")
    procedural_posture: str = Field(default="", description="Procedural history through the courts")
    issue: str = Field(default="", description="Legal question framed as Whether ... given ...")
    holding: str = Field(default="", description="Direct answer with the court's ruling")
    reasoning: str = Field(default="", description="Court's analysis and rationale, including the rule applied")
    dissent: str = Field(default="", description="Summary of dissent if any, else empty string")
    notes: List[str] = Field(default_factory=list, description="Exam-relevant takeaways and significance")
