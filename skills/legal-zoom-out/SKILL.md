---
name: legal-zoom-out
description: Produce a high-level issue map of a fact pattern before diving into full IRAC analysis. Use when the user is unfamiliar with where to start, says "what issues are here," or needs to understand the legal landscape before writing. Shows all issues, their order of analysis, and which are threshold vs. substantive.
disable-model-invocation: false
---

# Legal Zoom Out

## Process

1. Read the fact pattern.
2. Output an issue map — NOT full IRAC. One paragraph max per issue.
3. Organize issues into two tiers:
   - **Threshold issues** — must be resolved first (standing, jurisdiction, formation, capacity)
   - **Substantive issues** — the main legal questions (liability, defenses, damages)
4. For each issue, give: the issue name, one sentence on why it arises from these facts, and the likely answer (one word: Strong/Contested/Weak).
5. End with: "Which issue do you want to analyze first?"

## Output Format

```
## Issue Map — [Area of Law]

### Threshold Issues
1. [Issue Name] — [One sentence why it arises]. Likely: [Strong/Contested/Weak]

### Substantive Issues
1. [Issue Name] — [One sentence why it arises]. Likely: [Strong/Contested/Weak]
2. [Issue Name] — ...

### Suggested Analysis Order
Start with [threshold issue], then [issue 1], then [issue 2].
```

## What not to include

- No full rule statements
- No application
- No conclusion
- This is a map, not an analysis
