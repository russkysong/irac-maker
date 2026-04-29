---
name: irac-analyze
description: Generate a structured IRREAC legal analysis (Issue, Rule Statement, Rule Exploration, Application, Conclusion) from a fact pattern. Use when the user provides a legal scenario, hypo, case brief, or says "analyze this," "write an IRAC," or "what are the legal issues here." Works for all American law school subjects: Contracts, Torts, ConLaw, Crim Law, Property, CivPro, Evidence.
---

# IRAC Analyze

## Process

1. If no fact pattern is given, ask for it. One sentence: "Paste the fact pattern and tell me the subject area."
2. If area of law is ambiguous, identify it from the facts — do not ask unless truly unclear.
3. Generate IRREAC:
   - **Issue** — frame as "Whether [legal question] given [key facts]"
   - **Rule Statement** — cite Restatement, UCC section, statute, or landmark case
   - **Rule Exploration** — how courts have interpreted it; majority/minority split if any
   - **Application** — element by element; each element gets its own paragraph; include strongest counter-argument
   - **Conclusion** — direct answer + confidence level (High/Moderate/Low)
4. End with 2–3 common mistakes students make on this issue type.

## Iron Law

Never state the conclusion before completing the Application. Issue first. Conclusion last.

## Checklist before outputting

- [ ] Issue is framed as a yes/no legal question
- [ ] Rule cites a specific source (not "the law says...")
- [ ] Application addresses EACH rule element separately
- [ ] Application includes a counter-argument on the disputed element
- [ ] Conclusion states confidence level

See [IRREAC-FORMAT.md](IRREAC-FORMAT.md) for the full output template.
