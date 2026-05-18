# Pipeline 工作流程優化計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復 3 個穩定性 Bug、2 個準確率問題，並在不降低前兩項品質的前提下削減 ~40% token 消耗

**Architecture:** 所有變更限於 `.claude/scripts/*.ps1` 和 `.claude/agents/*.md`；不觸碰核心 Odoo 程式碼。穩定性修復優先，accuracy 次之，token 最後。

**Tech Stack:** PowerShell 7+, Claude Agents (Sonnet), YAML, Odoo 14–17

---

## 審計發現摘要

| # | 類別 | 嚴重度 | 說明 |
|---|------|--------|------|
| S1 | 穩定性 | 🔴 Critical | `pending_prompt.txt` 無超時機制 → Agent 崩潰 = 永久 hang |
| S2 | 穩定性 | 🔴 Critical | STEP 3a 無全域鎖 → 並行 pipeline run 重複處理 |
| S3 | 穩定性 | 🟠 High | PS1 不跳過有 blocker 的任務 → blocker 任務無限循環 |
| S4 | 穩定性 | 🟡 Medium | STEP 2 先 Release-Lock 再 Move-Item → 時間窗競爭 |
| A1 | 準確率 | 🟠 High | coding.ps1 不驗證 `technical_specification` 存在 |
| A2 | 準確率 | 🟡 Medium | QA agent 的 `no_sql_in_loops` 誤將 `mapped()` 列為違規 |
| T1 | Token | 🟠 High | 全部 stage 都加 `ultrathink` → QA/MODE_A 不需要 |
| T2 | Token | 🟡 Medium | QA agent 注入 wiki cache（QA 主要讀程式碼，非架構） |
| T3 | Token | 🟡 Medium | agent 模板有大量裝飾符號（`---` 分隔線）消耗無效 token |
| T4 | Token | 🟡 Medium | coding/QA agent 帶 `memory: project`，每次載入 project memory |

---

## Task 1: 修復 stale pending_prompt 超時機制（S1）

**Files:**
- Modify: `.claude/scripts/_common.ps1`
- Modify: `.claude/scripts/analysis.ps1`
- Modify: `.claude/scripts/coding.ps1`
- Modify: `.claude/scripts/qa.ps1`

**背景：** 當 Claude Agent session 中途崩潰，`pending_prompt.txt` 永遠留在任務目錄。所有 PS1 的 `[WAIT]` 邏輯會一直跳過這個任務，造成永久 hang。

- [ ] **Step 1: 在 `_common.ps1` 新增 `Test-PendingStale` 函數**

在 `Write-PendingPrompt` 函數之後，新增：

```powershell
function Test-PendingStale {
    param([string]$taskDir, [int]$AgeMinutes = 30)
    $pendingPath = Join-Path $taskDir "pending_prompt.txt"
    if (-not (Test-Path $pendingPath)) { return $false }
    $age = (Get-Date) - (Get-Item $pendingPath).LastWriteTime
    return $age.TotalMinutes -gt $AgeMinutes
}

function Clear-StalePending {
    param([string]$taskDir)
    $taskName = Split-Path $taskDir -Leaf
    Write-Host "[STALE] $taskName pending_prompt.txt 超過 30 分鐘，清除重新排隊" -ForegroundColor Yellow
    Remove-Item (Join-Path $taskDir "pending_prompt.txt") -Force -ErrorAction SilentlyContinue
    # .pending_* flag 保留，讓下一輪 PS1 重新判斷並寫入新 pending_prompt
    Get-Item (Join-Path $taskDir ".pending_*") -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}
```

- [ ] **Step 2: 在 `analysis.ps1` STEP 2 的 `[WAIT]` 區塊套用超時清除**

找到 `analysis.ps1` 第 88-90 行（`已有 pending prompt，等待 Claude 處理`）：

```powershell
# 舊：
if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
    Write-Host "[WAIT] $taskName - Claude 分析中（pending_prompt.txt 存在）" -ForegroundColor DarkGray
    continue
}
```

改為：

```powershell
if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
    if (Test-PendingStale $taskDir.FullName) {
        Clear-StalePending $taskDir.FullName
    } else {
        Write-Host "[WAIT] $taskName - Claude 分析中（pending_prompt.txt 存在）" -ForegroundColor DarkGray
        continue
    }
}
```

- [ ] **Step 3: 對 `analysis.ps1` STEP 3b、`coding.ps1` STEP 4、`qa.ps1` STEP 5 套用相同模式**

每個 `[WAIT]` 區塊（各 3 個地方）都套用同樣的超時判斷。Pattern 相同：
```powershell
if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
    if (Test-PendingStale $taskDir.FullName) {
        Clear-StalePending $taskDir.FullName
    } else {
        Write-Host "[WAIT] $taskName - Claude XXX 中" -ForegroundColor DarkGray
        continue
    }
}
```

- [ ] **Step 4: 驗證**

手動建立一個假的 `pending_prompt.txt`（需要修改時間戳到 31 分鐘前）：
```powershell
$f = ".claude/kingsmvpsplan/confirm/task_test/pending_prompt.txt"
New-Item -ItemType File -Force $f
(Get-Item $f).LastWriteTime = (Get-Date).AddMinutes(-35)
pwsh -NoProfile -File ".claude/scripts/analysis.ps1"
# 預期輸出：[STALE] task_test pending_prompt.txt 超過 30 分鐘，清除重新排隊
```

---

## Task 2: 修復 STEP 3a 缺少全域鎖（S2）

**Files:**
- Modify: `.claude/scripts/analysis.ps1`

**背景：** STEP 2 和 STEP 3b 都有全域鎖（`global_analysis.lock`、`global_recheck.lock`），但 STEP 3a（答案完整性檢查）沒有。兩個同時執行的 pipeline run 可能對同一個任務各寫一個 `.answer_done` 並嘗試 `Move-Item`。

- [ ] **Step 1: 在 STEP 3a 開頭加全域鎖**

找到 `analysis.ps1` 第 154-155 行（`STEP 3a` 區塊）：

```powershell
# 舊：
Write-Host "`n[STEP 3a] 檢查 confirm/ 答案完整性..." -ForegroundColor Cyan

$confirmTasks = Get-ChildItem $script:CONFIRM_DIR -Directory -ErrorAction SilentlyContinue
```

改為：

```powershell
Write-Host "`n[STEP 3a] 檢查 confirm/ 答案完整性..." -ForegroundColor Cyan

$lock3a = Join-Path $script:PLAN_DIR "global_answer_check.lock"
if (-not (Acquire-Lock $lock3a 300)) {
    Write-Host "[SKIP] 無法取得 STEP 3a 全域鎖" -ForegroundColor Yellow
} else {
    try {
        $confirmTasks = Get-ChildItem $script:CONFIRM_DIR -Directory -ErrorAction SilentlyContinue
        # ... (原有的 foreach 迴圈移入 try 區塊)
    } finally {
        Release-Lock $lock3a
    }
}
```

- [ ] **Step 2: 將原有 `foreach ($taskDir in $confirmTasks)` 迴圈縮排移入 `try` 區塊**

原有邏輯不變，僅加 try/finally wrapper。

- [ ] **Step 3: 驗證**

```powershell
# 驗證鎖檔生成
$lock3a = ".claude/kingsmvpsplan/global_answer_check.lock"
# 執行 analysis.ps1 時觀察是否出現鎖檔，完成後自動清除
pwsh -NoProfile -File ".claude/scripts/analysis.ps1"
Test-Path $lock3a  # 預期: False（已釋放）
```

---

## Task 3: PS1 跳過含 blocker 的任務（S3）

**Files:**
- Modify: `.claude/scripts/_common.ps1`
- Modify: `.claude/scripts/analysis.ps1`
- Modify: `.claude/scripts/coding.ps1`
- Modify: `.claude/scripts/qa.ps1`

**背景：** 任務目錄中有 `blocker.*.txt` 時，PS1 不會跳過，下一輪仍重新排隊 → 同一規格讓 Agent 再跑一次，必然再產一個 blocker，無限循環。

- [ ] **Step 1: 在 `_common.ps1` 新增 `Test-HasBlocker` 函數**

```powershell
function Test-HasBlocker {
    param([string]$taskDir)
    return [bool](Get-Item (Join-Path $taskDir "blocker.*.txt") -ErrorAction SilentlyContinue | Select-Object -First 1)
}
```

- [ ] **Step 2: `analysis.ps1` STEP 2 — 跳過 blocker 任務**

在 `start/` 任務迴圈中，`if (-not (Test-Path $originalTxt))` 之前加：

```powershell
if (Test-HasBlocker $taskDir.FullName) {
    Write-Host "[BLOCKER] $taskName 已有 blocker 檔案，跳過（需人工處理）" -ForegroundColor Red
    continue
}
```

- [ ] **Step 3: `analysis.ps1` STEP 3a — 跳過 blocker 任務**

在 `confirm/` 迴圈中，`if (-not (Test-Path $analysisDone))` 之前加相同的 blocker 檢查。

- [ ] **Step 4: `coding.ps1` STEP 4 — 跳過 blocker 任務**

在 `analysis/` 迴圈中，`if (-not (Test-Path $finalDone))` 之前加相同的 blocker 檢查。

- [ ] **Step 5: `qa.ps1` STEP 5 — 跳過 blocker 任務**

在 `coding/` 迴圈中，`if (-not (Test-Path $implementDone))` 之前加相同的 blocker 檢查。

- [ ] **Step 6: 驗證**

```powershell
# 建立假 blocker
New-Item ".claude/kingsmvpsplan/analysis/task_test/blocker.spec.txt" -Force -Value "test"
pwsh -NoProfile -File ".claude/scripts/coding.ps1"
# 預期: [BLOCKER] task_test 已有 blocker 檔案，跳過（需人工處理）
Remove-Item ".claude/kingsmvpsplan/analysis/task_test" -Recurse -Force
```

---

## Task 4: 修復 STEP 2 lock 競爭窗（S4）

**Files:**
- Modify: `.claude/scripts/analysis.ps1`

**背景：** 目前 STEP 2 的順序是 `Release-Lock` → `Move-Item`，在兩者之間有短暫競爭窗口。正確順序應該是 Move-Item 成功後才釋放鎖，或利用 try/finally 保證釋放。

- [ ] **Step 1: 重構 STEP 2 的 lock 釋放邏輯**

找到 `analysis.ps1` 第 93-149 行（`Acquire-Lock $taskLock` 區塊），將 try 區塊改為：

```powershell
try {
    # ... 原有建立 prompt 邏輯不變 ...
    Write-PendingPrompt -taskDir $taskDir.FullName -stage "analysis" -prompt $fullPrompt

    # Move-Item 移在 lock 釋放前
    $dest = Join-Path $script:CONFIRM_DIR $taskName
    if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
    try {
        Move-Item $taskDir.FullName $script:CONFIRM_DIR -Force
        Write-Host "[OK] $taskName → confirm/ (等待 Claude 初始分析)" -ForegroundColor Green
    } catch {
        # 搬移失敗：回滾 pending
        Remove-Item (Join-Path $taskDir.FullName "pending_prompt.txt") -Force -ErrorAction SilentlyContinue
        Remove-Item (Join-Path $taskDir.FullName ".pending_analysis")  -Force -ErrorAction SilentlyContinue
        Write-Host "[ERROR] $taskName 搬移失敗（已回滾 pending）：$_" -ForegroundColor Red
    }
} catch {
    Write-Host "[ERROR] STEP 2 ${taskName}: $_" -ForegroundColor Red
} finally {
    # 確保 lock 最後才釋放
    if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
}
```

注意：移除獨立的 `Release-Lock $taskLock` 呼叫（原第 128 行），改由 `finally` 統一處理。

- [ ] **Step 2: 驗證語法**

```powershell
pwsh -NoProfile -Command "& { . '.claude/scripts/_common.ps1'; Write-Host 'syntax ok' }"
pwsh -NoProfile -File ".claude/scripts/analysis.ps1" 2>&1 | Select-Object -First 20
# 預期：無 ParseException，看到正常的 STEP 1-3 輸出
```

---

## Task 5: pre-coding YAML completeness 驗證（A1）

**Files:**
- Modify: `.claude/scripts/coding.ps1`
- Modify: `.claude/scripts/_common.ps1`

**背景：** `coding.ps1` 只檢查 `.final_done` 存在，不驗證 `technical_specification` 是否已填入。空規格 → 空模組 → QA fail → BackToConfirm 無限迴圈。

- [ ] **Step 1: 在 `_common.ps1` 新增 `Test-YamlComplete` 函數**

```powershell
function Test-YamlComplete {
    param([string]$yamlPath)
    if (-not (Test-Path $yamlPath)) { return $false }
    $content = Get-Content $yamlPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    if (-not $content) { return $false }
    # technical_specification 必須存在且有 odoo_models 內容
    $hasTechSpec  = $content -match '(?m)^technical_specification:'
    $hasModel     = $content -match '(?m)^\s+model_name:\s*\S'
    return $hasTechSpec -and $hasModel
}
```

- [ ] **Step 2: `coding.ps1` 加入驗證**

在 `if (-not (Test-Path $analysisYamlPath))` 區塊之後，`if (-not $moduleName)` 之前加：

```powershell
if (-not (Test-YamlComplete $analysisYamlPath)) {
    $blockerMsg = "technical_specification 不完整或缺少 model_name，無法開始實作。請重新產生規格。"
    $blockerPath = Join-Path $taskDir.FullName "blocker.spec.txt"
    Atomic-WriteFile $blockerPath $blockerMsg | Out-Null
    Write-Host "[BLOCKER] $taskName YAML 規格不完整，已寫入 blocker.spec.txt" -ForegroundColor Red
    continue
}
```

- [ ] **Step 3: 驗證**

```powershell
# 建立空規格任務
$testDir = ".claude/kingsmvpsplan/analysis/task_test2"
New-Item $testDir -ItemType Directory -Force
Set-Content "$testDir/analysis.yaml" "case_id: test`nmodule: test_mod`nodoo_version: 17.0`nexecution_mode: MODE_B`ntechnical_specification:`n  odoo_models: []"
Set-Content "$testDir/.final_done" ""
Set-Content "$testDir/.answer_done" ""
pwsh -NoProfile -File ".claude/scripts/coding.ps1"
# 預期: [BLOCKER] task_test2 YAML 規格不完整
Test-Path "$testDir/blocker.spec.txt"  # 預期: True
Remove-Item $testDir -Recurse -Force
```

---

## Task 6: 修正 QA agent `mapped()` 誤判（A2）

**Files:**
- Modify: `.claude/agents/qa-analyst.md`

**背景：** `no_sql_in_loops` 把 `mapped()` 列為違規，但 `mapped()` 是 Odoo ORM 批次讀取的**推薦**方式（正是用來避免 N+1 問題），不應判為失敗。

- [ ] **Step 1: 修改 qa-analyst.md 的 check #7**

找到：
```
7. **no_sql_in_loops**
   FAIL if `search()` / `browse()` / `mapped()` appears inside a for-loop body.
   Suggest using `mapped()`, `filtered()`, or batch read instead.
```

改為：
```
7. **no_sql_in_loops**
   FAIL if `search()` or `browse()` appears inside a for-loop body (N+1 query).
   `mapped()` and `filtered()` inside loops are ALLOWED — they are ORM helpers, not DB queries.
   Suggest using `mapped()` or `filtered()` to replace loop-internal `search()`/`browse()`.
```

- [ ] **Step 2: 驗證**

```powershell
# 確認文件修改正確
Select-String -Path ".claude/agents/qa-analyst.md" -Pattern "mapped\(\)" | ForEach-Object { $_.Line }
# 預期輸出不含「FAIL if ... mapped()」
```

---

## Task 7: 移除 MODE_A 和 QA 的 ultrathink（T1）

**Files:**
- Modify: `.claude/scripts/analysis.ps1`
- Modify: `.claude/scripts/qa.ps1`

**背景：**
- MODE_A（初始分析）：只需提問，不需深度推理 → 移除 ultrathink
- MODE_B（最終規格）：複雜架構設計 → 保留 ultrathink
- Coding：複雜實作 → 保留 ultrathink
- QA：按清單核查程式碼，規則明確 → 移除 ultrathink

預估節省：~50% QA token + ~30% MODE_A token（extended thinking 是最貴的部分）。

- [ ] **Step 1: `analysis.ps1` STEP 2 — MODE_A 移除 ultrathink**

找到 `analysis.ps1` STEP 2 的 prompt 建構（第 121 行）：
```powershell
$fullPrompt = "ultrathink`n`n" + $prompt + ...
```

改為：
```powershell
$fullPrompt = $prompt + ...
```

MODE_B（STEP 3b，第 253 行）保持 `"ultrathink`n`n" + $wikiCache + $prompt + ...` 不動。

- [ ] **Step 2: `qa.ps1` STEP 5 — QA 移除 ultrathink**

找到 `qa.ps1` 第 70 行：
```powershell
$fullPrompt = "ultrathink`n`n" + $wikiCache + $agentTemplate + ...
```

改為：
```powershell
$fullPrompt = $wikiCache + $agentTemplate + ...
```

- [ ] **Step 3: 驗證 STEP 3b 和 coding 仍有 ultrathink**

```powershell
Select-String -Path ".claude/scripts/analysis.ps1" -Pattern "ultrathink"
# 預期：只在 STEP 3b 出現
Select-String -Path ".claude/scripts/coding.ps1" -Pattern "ultrathink"
# 預期：STEP 4 仍有
Select-String -Path ".claude/scripts/qa.ps1" -Pattern "ultrathink"
# 預期：無任何匹配
```

---

## Task 8: 移除 QA 的 wiki cache 注入（T2）

**Files:**
- Modify: `.claude/scripts/qa.ps1`

**背景：** QA agent 主要讀取模組檔案並對照 spec，不需要架構圖。wiki cache 注入只在驗證繼承鏈時有用，而 QA agent 已有 Serena 作備用。每個 QA 任務節省最多 200 行（~3,000 token）。

- [ ] **Step 1: 移除 `qa.ps1` STEP 5 的 wiki cache**

找到 `qa.ps1` 第 67-68 行：
```powershell
# WIKI-CACHE 注入
$wikiCache = Get-WikiCache -moduleName $moduleName -odooVersion $odooVersion -projectName $projectName
```

刪除這兩行，並將第 70-74 行的 `$wikiCache +` 移除：

```powershell
# 舊：
$fullPrompt = $wikiCache + $agentTemplate + ...
# 改為（Task 7 已移除 ultrathink）：
$fullPrompt = $agentTemplate + ...
```

- [ ] **Step 2: 更新 qa-analyst.md 的知識檢索說明**

在 `KNOWLEDGE RETRIEVAL` 區塊，移除 wiki cache 指示（第 3 點）：

找到：
```
3. **Graphify wiki**: If `[WIKI-CACHE]` is in your prompt, use it to verify inheritance chains.
```

改為：
```
3. **Graphify wiki**: Read `graphify-out/wiki/index.md` ONLY if Serena cannot confirm an inheritance chain. Do NOT read proactively.
```

- [ ] **Step 3: 驗證**

```powershell
Select-String -Path ".claude/scripts/qa.ps1" -Pattern "wikiCache|Get-WikiCache"
# 預期：無任何匹配
```

---

## Task 9: 壓縮 agent 模板裝飾符（T3）

**Files:**
- Modify: `.claude/agents/requirements-analyst.md`
- Modify: `.claude/agents/senior-software-engineer.md`
- Modify: `.claude/agents/qa-analyst.md`

**背景：** 每個 agent 模板都有多行 `--------------------------------------------------` 分隔線。每行 50 個字元，約 8-10 行 = 400-500 token 純雜訊。三個 agent × 多次呼叫累積可觀。

- [ ] **Step 1: requirements-analyst.md — 壓縮分隔線**

將所有 `--------------------------------------------------` 行替換為空行（單行空白分隔即可）。同時去除每個區塊標題前後多餘的空行（保留一行）。

預計從 ~144 行壓縮到 ~110 行。

- [ ] **Step 2: senior-software-engineer.md — 同上**

預計從 ~100 行壓縮到 ~75 行。

- [ ] **Step 3: qa-analyst.md — 同上**

預計從 ~140 行壓縮到 ~105 行。

- [ ] **Step 4: 驗證不影響語意**

壓縮後，逐一確認每個 section 標題、rules、schema 欄位都在：
```powershell
Select-String ".claude/agents/requirements-analyst.md" -Pattern "OUTPUT CONTRACT|MODE RULES|YAML SCHEMA|KNOWLEDGE RETRIEVAL"
Select-String ".claude/agents/senior-software-engineer.md" -Pattern "OUTPUT CONTRACT|IMPLEMENTATION RULES|BLOCKER PROTOCOL|VERIFY AFTER"
Select-String ".claude/agents/qa-analyst.md" -Pattern "OUTPUT CONTRACT|KNOWLEDGE RETRIEVAL|no_sql_in_loops|no_hardcoded_ids"
# 預期：每個關鍵標題各出現一次
```

---

## Task 10: 移除 coding/QA agent 的 `memory: project`（T4）

**Files:**
- Modify: `.claude/agents/senior-software-engineer.md`
- Modify: `.claude/agents/qa-analyst.md`

**背景：** `memory: project` 讓 agent 在每次呼叫時載入 project memory。requirements-analyst 需要 project context（理解業務），但 coding/QA agent 只需要 spec + 程式碼，不需要 project memory。

- [ ] **Step 1: `senior-software-engineer.md` frontmatter 移除 memory**

找到：
```yaml
---
name: "senior-software-engineer"
description: "Odoo Module Implementer"
model: sonnet
color: red
memory: project
---
```

改為：
```yaml
---
name: "senior-software-engineer"
description: "Odoo Module Implementer"
model: sonnet
color: red
---
```

- [ ] **Step 2: `qa-analyst.md` frontmatter 移除 memory**

同上，移除 `memory: project` 行。

- [ ] **Step 3: 驗證**

```powershell
Select-String ".claude/agents/senior-software-engineer.md" -Pattern "memory:"
Select-String ".claude/agents/qa-analyst.md" -Pattern "memory:"
# 預期：無匹配（requirements-analyst.md 仍保有 memory: project）
Select-String ".claude/agents/requirements-analyst.md" -Pattern "memory:"
# 預期：memory: project
```

---

## 執行前後 Token 估算

| Stage | 現在 | 優化後 | 節省 |
|-------|------|--------|------|
| MODE_A 分析 | ultrathink + 144行模板 | 110行模板（無 ultrathink） | ~60% |
| MODE_B 規格 | ultrathink + wiki + 144行 | ultrathink + wiki + 110行 | ~10% |
| Coding | ultrathink + wiki + 100行 | ultrathink + wiki + 75行 | ~8% |
| QA | ultrathink + wiki + 140行 | 105行（無 ultrathink、無 wiki） | ~70% |

**整體估算：每個完整 task_N 週期節省 35-45% token**

---

## 執行順序建議

執行 Task 1-4（穩定性）→ 驗證 pipeline 跑通 → 執行 Task 5-6（準確率）→ 驗證 QA 通過 → 執行 Task 7-10（Token）

穩定性修復間有相依性（Task 3 依賴 Task 1 的 `_common.ps1` 函數），建議同一 session 按序執行。
