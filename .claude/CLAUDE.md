# CLAUDE.md (V7)

## 0. Core Principles
- Challenge proposals that violate Odoo best practices, security, or performance.
- Surface 2–3 interpretations for ambiguous requests. Never guess intent.
- State one core assumption before executing complex tasks.

## 1. Knowledge Retrieval
- Use Skill tool: `graphify query/path/explain`. Wiki: `graphify-out/wiki/index.md`.
- After edits: run `/graphify . --update`.

## 2. Dev Workflow
- `senior-software-engineer` must read specification from `analysis.json`. Do not guess intent.
- Develop strictly per spec. Do not add fields, models, or logic beyond `analysis.json`.
- On any ambiguity or blocker discovered during coding, immediately write the query to a new file named `blocker.txt` inside the task root directory, then STOP execution immediately.

## 3. Edit Protocol
- Store task plans/logs in `.claude/kingsmvpsplan/`.
- Match existing code style exactly. Zero drive-by refactoring.
- Strict `[Step] → [Verify]` flow. Pass before proceeding.

## 4. Odoo Constraints
- Custom modules in `custom_addons/` only. Never modify core files.
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard extension → escalate as Hard Blocker immediately via blocker.txt.

## 5. Output
- Think in English. Output Traditional Chinese (Taiwan).
- No preambles. Start with solution or challenge.
- Use: 專案/資料庫/佈署/變數/函式/模組. Keep English: Variable/Function/Hook/Class/Field/Model.
- Commit: `[Module]: Why (not what)`. File edit: `@Path | Anchor | Action`.
