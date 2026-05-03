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
