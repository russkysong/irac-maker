---
name: irac-compare
description: Compare a student's IRAC draft against a model IRREAC and give section-by-section graded feedback. Use when the user says "grade my IRAC," "compare my answer," "did I get this right," or pastes their own IRAC attempt. Requires both a fact pattern and the student's draft.
---

# IRAC Compare

## Process

1. Collect from the user (in one message if possible):
   - The fact pattern
   - The area of law
   - Their IRAC draft (can be partial — even one section is enough to grade)
2. Generate the model IRREAC internally (do not show it yet).
3. Grade the student's draft section by section against the model:
   - Score each section: **Excellent / Good / Needs Work / Missing**
   - For each section: state what they got right, then what was missing or imprecise
4. Show the model IRREAC side-by-side with the student's draft.
5. Give an overall letter grade and one key insight — the single most important thing to improve.

## Grading Rubric

| Section | Weight | What earns full credit |
|---|---|---|
| Issue | 15% | Framed as a legal question; correct issue identified |
| Rule | 20% | Specific citation; all elements stated |
| Application | 50% | Each element analyzed; counter-argument addressed |
| Conclusion | 15% | Flows from Application; confidence stated |

## Grade Scale

Use a realistic law school curve. Most students score B or B+. A is reserved for work that addresses all elements, all counter-arguments, and includes correct citations.

## Iron Law (for grading)

If the student stated the conclusion before completing the Application, call it out explicitly. This is the most common structural mistake.
