# CLAUDE.md (V7)

## 0. Core Principles
- Challenge proposals that violate Odoo best practices, security, or performance.
- Surface 2–3 interpretations for ambiguous requests. Never guess intent.
- State one core assumption before executing complex tasks.

## 1. Knowledge Retrieval
- Use Skill tool: `graphify query/path/explain`. Wiki: `graphify-out/wiki/index.md`.
- After edits: run `/graphify . --update`.

## 1.5 Tool Restrictions
- `mcp__serena__initial_instructions`: requirements-analyst (A), senior-software-engineer (C), test-agent (T) only.
- `brainstorming` skill: senior-software-engineer C1 only.
- `code-review / pr-review-toolkit / security-guidance`: test-agent only.

## 2. Agent Routing
- "分析" / "開始分析" (exact) → invoke `requirements-analyst`.
- "開發" / "開始開發" (exact) → invoke `senior-software-engineer`.
- Any other phrasing → stay in Main Agent (even containing "分析" or "開發").

### Dev Workflow
1. `senior-software-engineer` reads `coding/<task>/analysis.md`. Do not re-invoke `requirements-analyst`.
2. Develop strictly per spec. Do not add beyond `analysis.md`.
3. On any ambiguity: append to `❓ 待釐清問題`, move `coding/<task>/` → `confirm/<task>/`, output questions only, stop.
4. Unanswered `❓` = blocker. Move back to `confirm/`, stop.

## 3. Edit Protocol
- Use Write/Edit tools only. Shell for directory creation (`mkdir`, `New-Item`) only.
- Store task plans/logs in `.claude/kingsmvpsplan/`.
- Match existing code style exactly. Zero drive-by refactoring.
- Strict `[Step] → [Verify]` flow. Pass before proceeding.

## 4. Odoo Constraints
- Custom modules in `custom_addons/` only. Never modify core files.
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard extension → escalate as Hard Blocker immediately.

## 5. Output
- Think in English. Output Traditional Chinese (Taiwan).
- No preambles. Start with solution or challenge.
- Use: 專案/資料庫/佈署/變數/函式/模組. Keep English: Variable/Function/Hook/Class/Field/Model.
- Commit: `[Module]: Why (not what)`. File edit: `@Path | Anchor | Action`.
