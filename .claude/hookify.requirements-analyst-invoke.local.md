---
name: requirements-analyst-invoke
enabled: true
event: prompt
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: ^(分析|開始分析)$
---

Pass user message directly to `requirements-analyst`. Add nothing to the prompt. The agent is file-driven: auto-globs `start/` and `confirm/` to select Workflow A or B.
