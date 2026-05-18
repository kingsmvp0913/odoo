# CLAUDE.md (V8.2)

## 0. Hard Rules
- NEVER modify core Odoo files. Custom code in `C:/online_addons/` only (never `custom_addons/`).
- NEVER guess intent. Surface 2–3 interpretations when ambiguous; state one core assumption before complex tasks. When still uncertain after surfacing interpretations, ask — do not proceed on a guess.
- Stop when confused. Name what's unclear before continuing.
- NEVER add fields/models/logic beyond `analysis.yaml` spec.
- NEVER request human confirmation mid-pipeline.
- On any blocker: write `blocker.<type>.txt` to `system/` in task dir → STOP immediately. Report **file path only**, never content.
- Think in English. Output Traditional Chinese (Taiwan). No preambles.
- Challenge proposals that violate Odoo best practices, security, or performance.
- NEVER modify any workflow (pipeline scripts, PS1 files, CLAUDE.md, agent prompts, hook configs, pipeline spec) without explicit user approval.

## 1. Paths
- **Task root**: `.claude/kingsmvpsplan/<stage>/<task_id>/`
- **Spec file**: `<task_root>/analysis.yaml`
- **Pipeline flag**: `.claude/kingsmvpsplan/_PIPELINE_WAITING` (content = ISO timestamp; TTL 30 min)
- **Loop counter**: `.claude/kingsmvpsplan/_LOOP_COUNTER.json`
- PS1 scripts run on the user's machine; paths are computed via `$PSScriptRoot` (cross-platform). When Claude executes on Linux, translate `C:\odoo` → project root, `C:\online_addons` → `/online_addons` (or `$ONLINE_ADDONS_DIR` env var).

## 2. Knowledge Retrieval (Decision Tree)
Execute in order. Stop as soon as sufficient.
1. **Graphify** → `<online_addons_root>/graphify-out/wiki/index.md`
   - Main orchestrator reads **once** per pipeline run, injects as `[WIKI-CACHE]` block into sub-Agent prompts
   - Sub-Agents with `[WIKI-CACHE]` in prompt **must not** re-read wiki
   - **If wiki file not found → skip entirely, do NOT manually explore files, go to step 2**
2. **Serena** → Use when Graphify wiki is absent OR lacks a specific symbol/call chain
   - **On `tool_use_error` or no response → immediately write `system/blocker.agent.txt` → STOP. Do NOT retry.**
   - **Session query cap: max 3 distinct Serena queries per agent session. If still insufficient → write `system/blocker.agent.txt` → STOP.**
3. **Context7** → Only to confirm Odoo native API (field types, decorators, method signatures) for the target version
   - On any failure → skip silently (non-blocking; proceed with available context)

**WIKI-CACHE injection procedure** (main orchestrator, before spawning sub-Agents):
```
1. Read <online_addons_root>/graphify-out/wiki/index.md
2. If file not found → skip injection entirely (sub-Agent will use Serena directly)
3. If found → extract lines mentioning the target module (max 200 lines)
4. Prepend to each sub-Agent prompt:
   [WIKI-CACHE]
   <extracted lines>
   [/WIKI-CACHE]
```

## 3. Task Spec

**Unified Marker Table** — authoritative reference for all Agents and PS1 scripts:

| Claude stage | pending flag (in `system/`) | done marker (in `system/`) | Physical dir |
|---|---|---|---|
| analysis (initial) | `.pending_analysis` | `.analysis_done` | `confirm/` |
| answer-check | _(PS1 only, no pending)_ | `.answer_done` | `confirm/` → `analysis/` |
| final (MODE_B) | `.pending_final` | `.final_done` | `analysis/` |
| final low-conf | _(none — PS1 detects)_ | `.low_confidence` → routes back to confirm/ | `analysis/` → `confirm/` |
| coding | `.pending_coding` | `.implement_done` | `coding/` |
| qa | `.pending_qa` | `.qa_done` | `coding/` |
| archive | _(none)_ | _(none)_ | `final/` ← QA-passed tasks |

**Task dir layout**:
```
<task_dir>/
├── analysis.yaml          ← spec（根目錄）
├── original.txt           ← 原始需求（根目錄）
├── process.lock           ← 臨時排他鎖（根目錄）
├── system/                ← 狀態機檔案（PS1 讀寫）
│   ├── pending_prompt.txt
│   ├── .pending_<stage>
│   ├── .<stage>_done
│   ├── blocker.*.txt
│   └── _reentry_count
└── log/                   ← 執行記錄（人工查閱）
    ├── done_prompt.txt
    ├── back_reason.txt
    ├── qa_report.yaml
    └── agent_error.txt
```

- **Stage source**: read `system/.pending_<stage>` flag filename inside task dir. Valid Claude-facing stages: `analysis`, `final`, `coding`, `qa`.
- `final/` directory = QA-passed archive, **not** a processing stage.
- `qa` shares the same module serial lock as `coding`.
- task_id format: `task_<N>` where N is digits only (e.g. `task_3919`).

`analysis.yaml` minimum required fields:
```yaml
case_id: ""
module: ""
odoo_version: ""
project_name: null   # null → version-only path; string → project path
execution_mode: "MODE_A | MODE_B"
```

## 4. Edit Protocol
- Plans/logs → `.claude/kingsmvpsplan/`.
- **Minimum code that solves the problem.** No speculative features. No abstractions for single-use code. (Test: would a senior engineer call this overcomplicated?)
- Touch only what you must. Don't clean up adjacent code, comments, or formatting that isn't yours.
- Match existing code style exactly. Zero drive-by refactoring.
- Before adding code, read exports, immediate callers, and shared utilities. "Looks orthogonal" is dangerous — if unsure why code is structured a certain way, ask.
- If a codebase convention seems harmful, surface it explicitly. Don't fork silently.
- Strict `[Step] → [Verify]` flow:
  - Python: `python -m py_compile <file>`
  - XML: `xmllint --noout <file>`
  - Module loadable: `odoo-bin -d test --stop-after-init -i <module>` (if available)
- **Completion order** (atomic protocol):
  1. Write done marker (e.g. `system/.implement_done`)
  2. `mv system/pending_prompt.txt log/done_prompt.txt`
  3. Delete `system/.pending_<stage>` flag
  - Never delete before writing marker.

## 5. Odoo Constraints
- Models: `_inherit`. Views: `inherit_id` + `xpath`. Controllers: `super()`.
- Cannot achieve via standard Odoo extension → write `system/blocker.tech.txt` immediately.
- Commit: `[Module]: Why (not what)`. File edit: `@Path | Anchor | Action`.

## 6. Output Style
繁中術語：專案/資料庫/佈署/模組. Keep English: Variable/Function/Hook/Class/Field/Model/Method/Controller.

## 7. Pipeline
Triggers (either):
- User types「開工」→ Hook runs `_pipeline_run.ps1`; process the `[CLAUDE-ACTION-REQUIRED]` block in output
- `.claude/kingsmvpsplan/_PIPELINE_WAITING` exists AND content timestamp < 30 min ago

**重要**：Pipeline 只能由使用者明確輸入「開工」來觸發。即使 `_PIPELINE_WAITING` 存在且未超過 30 分鐘，也**禁止**自動啟動。未收到「開工」指令前保持待命。

Full pipeline spec: **`.claude/pipeline.md`**

## 8. Blocker Types
| File | Situation |
|------|-----------|
| `blocker.spec.txt` | Spec unclear; user clarification needed |
| `blocker.tech.txt` | Cannot implement via standard Odoo extension |
| `blocker.agent.txt` | Agent execution error |
| `blocker.loop.txt` | Pipeline loop exceeded safety limit |

Templates in `.claude/templates/`. On blocker: STOP immediately. Report file path only, never content.

## 9. General Engineering Rules

**Rule 4 — Goal-Driven Execution**: Define success criteria before starting. Iterate until verified. Don't follow steps mechanically; define success and drive to it. Strong success criteria enable independent looping.

**Rule 6 — Token Budgets (not advisory)**: Per-task: 4,000 tokens. Per-session: 30,000 tokens. If approaching the limit, summarize and start fresh. Surface the breach explicitly — do not silently overrun.

**Rule 7 — Surface Conflicts, Don't Average Them**: If two patterns contradict, pick one (more recent / more tested). Explain why. Flag the other for cleanup. Don't blend conflicting patterns.

**Rule 9 — Tests Verify Intent**: Tests must encode WHY behavior matters, not just WHAT it does. A test that can't fail when business logic changes is wrong.

**Rule 10 — Checkpoint After Every Significant Step**: Summarize what was done, what's verified, and what's left. Don't continue from a state you can't describe back. If you lose track, stop and restate. (Note: "NEVER request human confirmation mid-pipeline" applies to tool permission prompts, not to genuine requirement uncertainty.)

**Rule 12 — Fail Loud**: "Completed" is wrong if anything was skipped silently. "Tests pass" is wrong if any were skipped. Default to surfacing uncertainty, not hiding it.
