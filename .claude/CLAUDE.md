# CLAUDE.md (V8)

## 0. Hard Rules
- NEVER modify core Odoo files. Custom code in `custom_addons/` only.
- NEVER guess intent. Surface 2–3 interpretations when ambiguous; state one core assumption before complex tasks.
- NEVER add fields/models/logic beyond `analysis.yaml` spec.
- NEVER request human confirmation mid-pipeline.
- On any blocker: write `blocker.<type>.txt` to task dir → STOP immediately. Report **file path only**, never content.
- Think in English. Output Traditional Chinese (Taiwan). No preambles.
- Challenge proposals that violate Odoo best practices, security, or performance.

## 1. Paths
- **Task root**: `.claude/kingsmvpsplan/<stage>/<task_id>/`
- **Spec file**: `<task_root>/analysis.yaml`
- **Pipeline flag**: `.claude/kingsmvpsplan/_PIPELINE_WAITING` (relative to project root; TTL 30 min — skip if older)
- PS1 scripts run on the user's Windows machine; their `C:\` absolute paths are correct for that context. When Claude executes on Linux, translate `C:\odoo` → project root, `C:\online_addons` → `/online_addons`.

## 2. Knowledge Retrieval (Decision Tree)
Execute in order. Stop as soon as sufficient.
1. **Graphify** → `<online_addons_root>/graphify-out/wiki/index.md` (cached snapshot; read **once** per pipeline run by main orchestrator, inject summary into sub-Agent prompts)
2. **Serena** → Only if Graphify wiki lacks the specific symbol definition or call chain
3. **Context7** → Only to confirm Odoo native API (field types, decorators, method signatures) for the target version

Sub-Agents **must not** re-read the Graphify wiki independently; use the summary injected in their prompt.

## 3. Task Spec

`analysis.yaml` minimum required fields:
```yaml
case_id: ""
module: ""
odoo_version: ""
project_name: null   # null → version-only path; string → project path
execution_mode: "MODE_A | MODE_B"
```
- **Stage source**: read `.pending_<stage>` flag filename inside task dir. Valid values: `confirm → analysis → final → coding → qa`.
- `qa` is a sub-stage of coding and shares the same module serial lock.
- task_id format: `task_<N>` (e.g. `task_3919`).

## 4. Edit Protocol
- Plans/logs → `.claude/kingsmvpsplan/`.
- Match existing code style exactly. Zero drive-by refactoring.
- Strict `[Step] → [Verify]` flow:
  - Python: `python -m py_compile <file>`
  - XML: `xmllint --noout <file>`
  - Module loadable: `odoo-bin -d test --stop-after-init -i <module>` (if available)
- **Completion order**: write `.<stage>_done` marker **first** → then `mv pending_prompt.txt done_prompt.txt` (never delete before writing marker).

## 5. Odoo Constraints
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard Odoo extension → write `blocker.tech.txt` immediately.
- Commit: `[Module]: Why (not what)`. File edit: `@Path | Anchor | Action`.

## 6. Output Style
繁中術語：專案/資料庫/佈署/模組. Keep English: Variable/Function/Hook/Class/Field/Model/Method/Controller.

## 7. Pipeline
Triggers (either):
- User types「開工」→ Hook injects PS1 output into context; process the `[CLAUDE-ACTION-REQUIRED]` block
- `.claude/kingsmvpsplan/_PIPELINE_WAITING` exists AND mtime < 30 min

Full pipeline spec: **`.claude/pipeline.md`**

## 8. Blocker Types
| File | Situation |
|------|-----------|
| `blocker.spec.txt` | Spec unclear; user clarification needed |
| `blocker.tech.txt` | Cannot implement via standard Odoo extension |
| `blocker.agent.txt` | Agent execution error |
| `blocker.loop.txt` | Pipeline loop exceeded safety limit |

On blocker: STOP immediately. Report the file path to user. Do not display content.
