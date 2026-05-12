---
name: senior-software-engineer-invoke
enabled: true
event: prompt
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: ^(開發|開始開發)$
---

Pass user message directly to `senior-software-engineer`. Add nothing to the prompt. The agent is file-driven: auto-globs `coding/` to select Workflow C or D.
