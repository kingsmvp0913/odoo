---
name: test-agent-invoke
enabled: true
event: prompt
conditions:
  - field: user_prompt
    operator: regex_match
    pattern: ^(測試|開始測試)$
---

Pass user message directly to `test-agent`. Add nothing to the prompt. The agent is file-driven: auto-globs `test/` for Workflow T.
