# _pipeline_run_codex.ps1 - Codex CLI 版 Pipeline 入口點
# 共用 .claude/scripts/ 的機械工作；AI 執行改由 codex CLI 直接驅動（不需 Claude Code）
#
# 使用方式：
#   pwsh -NoProfile -File ".codex/scripts/_pipeline_run_codex.ps1"
#
# 必要環境變數：
#   ODOO_PASSWORD         — Odoo 來源 1 密碼
#   CODEX_MODEL           — (選用) 指定模型，預設 o4-mini
#   CODEX_APPROVAL_MODE   — (選用) 預設 full-auto

# 使用 .claude/scripts/_common.ps1（dot-source 後 $PSScriptRoot 仍為 _common.ps1 所在目錄，路徑常數正確）
$commonPath = Join-Path $PSScriptRoot "..\..\.claude\scripts\_common.ps1" | Resolve-Path
. $commonPath

$claudeScriptsDir = Split-Path $commonPath -Parent
# Stage → agent 檔名對應（從 .codex/agents/<name>.toml 讀取 Codex 設定）
$stageAgents = @{
    "analysis" = "requirements-analyst"      # confirm/ → .pending_analysis
    "final"    = "requirements-analyst"      # analysis/ → .pending_final
    "coding"   = "senior-software-engineer"  # coding/ → .pending_coding
    "qa"       = "qa-analyst"               # coding/ → .pending_qa
}

# 告知 stage scripts 要使用 .codex/agents/（env var fallback 機制）
$env:PIPELINE_AGENTS_DIR = Join-Path $PSScriptRoot "..\agents" | Resolve-Path

if (-not $env:ODOO_PASSWORD) {
    Write-Host "[ERROR] 環境變數 ODOO_PASSWORD 未設定，Pipeline 中止。" -ForegroundColor Red
    exit 1
}

# ============================================================
# Loop Counter（防死循環，與 Claude 版共用同一計數器）
# ============================================================
$counterFile = Join-Path $script:PLAN_DIR "_LOOP_COUNTER.json"
$loopCount   = 0
$startedAt   = Get-Date -Format 'o'
$maxLoops    = if ($env:PIPELINE_MAX_LOOPS) { [int]$env:PIPELINE_MAX_LOOPS } else { 20 }
$maxReentries = if ($env:PIPELINE_MAX_REENTRIES) { [int]$env:PIPELINE_MAX_REENTRIES } else { 2 }

if (Test-Path $counterFile) {
    try {
        $existing  = Get-Content $counterFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $startedAt = $existing.run_started_at
        $loopCount = [int]$existing.loop_count + 1
    } catch {}
}

if ($loopCount -gt $maxLoops) {
    Write-Host "[CRITICAL] Pipeline loop_count=$loopCount 超過上限 $maxLoops，中止。" -ForegroundColor Red
    Remove-Item $script:PIPELINE_WAITING -Force -ErrorAction SilentlyContinue
    Remove-Item $counterFile -Force -ErrorAction SilentlyContinue
    exit 1
}

$counterObj = [PSCustomObject]@{ run_started_at = $startedAt; loop_count = $loopCount }
try { $counterObj | ConvertTo-Json -Depth 5 | Out-File $counterFile -Encoding UTF8 -Force } catch {}

Write-Host "=== Codex Pipeline 開工 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan
Write-Host "[LOOP] loop_count=$loopCount / $maxLoops" -ForegroundColor DarkCyan

# ============================================================
# 共用 PS1 階段：需求分析 → 實作 → QA（機械工作，不含 AI 呼叫）
# ============================================================
$env:PIPELINE_HOOK_MODE = "1"

Write-Host "`n--- STEP 1-3: 需求分析 (analysis.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $claudeScriptsDir "analysis.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ABORT] analysis.ps1 失敗，中止。" -ForegroundColor Red
    Remove-Item env:PIPELINE_HOOK_MODE -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}

# ============================================================
# Codex AI 執行：analysis → final → coding → qa
# analysis 與 final 分開呼叫，確保各 stage 的 flag 都被掃到
# ============================================================
Invoke-CodexBatch -Stage "analysis" -StageLabel "初始分析" -AgentName $stageAgents["analysis"]
Invoke-CodexBatch -Stage "final"    -StageLabel "Final 規格" -AgentName $stageAgents["final"]

Write-Host "`n--- STEP 4: 實作 (coding.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $claudeScriptsDir "coding.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ABORT] coding.ps1 失敗，中止。" -ForegroundColor Red
    Remove-Item env:PIPELINE_HOOK_MODE -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}

Invoke-CodexBatch -Stage "coding" -StageLabel "實作" -AgentName $stageAgents["coding"]

Write-Host "`n--- STEP 5-6: QA (qa.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $claudeScriptsDir "qa.ps1")
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ABORT] qa.ps1 失敗，中止。" -ForegroundColor Red
    Remove-Item env:PIPELINE_HOOK_MODE -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}

Invoke-CodexBatch -Stage "qa" -StageLabel "QA" -AgentName $stageAgents["qa"]

Remove-Item env:PIPELINE_HOOK_MODE -ErrorAction SilentlyContinue

# ============================================================
# 最終狀態：有新 pending（如 QA 失敗退回）→ 自動進入下一輪
# ============================================================
$remainingPending = @(Get-ChildItem $script:PLAN_DIR -Recurse -Filter "pending_prompt.txt" -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike "*$($script:STOP_DIR)*" -and $_.FullName -notlike "*$($script:FINAL_DIR)*" })

if ($remainingPending.Count -gt 0) {
    if ($loopCount -lt $maxLoops) {
        Write-Host "`n[LOOP] 偵測到 $($remainingPending.Count) 個新待處理任務，啟動下一輪（loop=$($loopCount+1)）..." -ForegroundColor Cyan
        & $PSCommandPath
    } else {
        Write-Host "`n[WARN] 達到 loop 上限（$maxLoops），停止。仍有 $($remainingPending.Count) 個未完成任務。" -ForegroundColor Yellow
    }
} else {
    Remove-Item $script:PIPELINE_WAITING -Force -ErrorAction SilentlyContinue
    Remove-Item $counterFile -Force -ErrorAction SilentlyContinue
    Write-Host "`n=== Codex Pipeline 完成，無待處理任務 ===" -ForegroundColor Green
}

# ============================================================
# 函式：Codex Batch 執行（掃描 pending 任務並逐一呼叫 codex CLI）
# ============================================================
function Invoke-CodexBatch {
    param([string]$Stage, [string]$StageLabel, [string]$AgentName)

    $pendingFiles = Get-ChildItem $script:PLAN_DIR -Recurse -Filter "pending_prompt.txt" -ErrorAction SilentlyContinue |
        Where-Object {
            $_.FullName -notlike "*$($script:STOP_DIR)*" -and
            $_.FullName -notlike "*$($script:FINAL_DIR)*" -and
            (Test-Path (Join-Path (Split-Path $_.FullName -Parent) ".pending_$Stage"))
        }

    if (-not $pendingFiles -or @($pendingFiles).Count -eq 0) {
        Write-Host "[CODEX] $StageLabel：無待處理任務" -ForegroundColor DarkGray
        return
    }

    Write-Host "`n[CODEX] $StageLabel：$(@($pendingFiles).Count) 個任務..." -ForegroundColor Magenta

    foreach ($pf in @($pendingFiles)) {
        $taskDir  = Split-Path (Split-Path $pf.FullName -Parent) -Parent
        $taskId   = Split-Path $taskDir -Leaf
        $sysDir   = Join-Path $taskDir "system"

        # 已有 blocker 的任務跳過
        if (Test-HasBlocker $taskDir) {
            Write-Host "  [SKIP] $taskId 有 blocker，跳過" -ForegroundColor Yellow
            continue
        }

        # 從 .codex/agents/<name>.toml 讀取 Codex 設定（官方格式：root-level keys）
        $tomlPath    = Join-Path $env:PIPELINE_AGENTS_DIR "$AgentName.toml"
        $tomlContent = Get-Content $tomlPath -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        $agentModel  = if ($tomlContent) { Get-TomlValue $tomlContent "" "model" } else { "gpt-5.5" }
        $agentEffort = if ($tomlContent) { Get-TomlValue $tomlContent "" "model_reasoning_effort" } else { "medium" }
        if (-not $agentModel)  { $agentModel  = "gpt-5.5" }
        if (-not $agentEffort) { $agentEffort = "medium" }

        Write-Host "  [CODEX] 執行 $taskId ($Stage) [$AgentName  model=$agentModel effort=$agentEffort]..." -ForegroundColor Cyan

        # 呼叫 codex exec（非互動模式，stdin 傳入 pending_prompt.txt）
        # -c model/effort           : 從 .toml 讀取，覆蓋 ~/.codex/config.toml 預設值
        # --ask-for-approval never  : 不暫停等待人工確認
        # --sandbox danger-full-access : agent 需要讀寫多個路徑（online_addons、task 目錄）
        # --output-last-message     : 只抓 agent 最後一則回覆，避免解析 TUI 輸出
        $promptContent = Get-Content $pf.FullName -Raw -Encoding UTF8
        $tmpOutput     = [System.IO.Path]::GetTempFileName()
        $output        = $null
        try {
            $promptContent | & codex exec `
                -c "model=`"$agentModel`"" `
                -c "model_reasoning_effort=`"$agentEffort`"" `
                --ask-for-approval never `
                --sandbox danger-full-access `
                --output-last-message $tmpOutput `
                2>&1 | Out-Null
            $exitCode = $LASTEXITCODE
            $output   = Get-Content $tmpOutput -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
        } catch {
            $exitCode = 1
            $output   = "Exception: $_"
        } finally {
            Remove-Item $tmpOutput -Force -ErrorAction SilentlyContinue
        }

        # 解析 ---AGENT-RESULT--- 區塊（agent 最後一則回覆內）
        $resultStatus  = $null
        $resultMessage = $null
        if ($output -match '(?s)---AGENT-RESULT---(.*?)---END-RESULT---') {
            $block = $matches[1]
            if ($block -match 'status:\s*(\w+)')  { $resultStatus  = $matches[1] }
            if ($block -match 'message:\s*(.+)')   { $resultMessage = $matches[1].Trim() }
        }

        if ($resultStatus -eq 'ok') {
            Write-Host "  [OK] $taskId 完成: $resultMessage" -ForegroundColor Green
        } elseif ($resultStatus -eq 'blocker') {
            Write-Host "  [BLOCKER] $taskId: $resultMessage" -ForegroundColor Yellow
        } else {
            # 失敗：寫入 agent_error.txt
            Write-Host "  [FAIL] $taskId (exit=$exitCode): $resultMessage" -ForegroundColor Red
            $logDir = Join-Path $taskDir "log"
            if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
            $errContent = "timestamp: '$(Get-Date -Format 'o')'`ntask_id: $taskId`nstage: $Stage`nexit_code: $exitCode`nresult_status: '$resultStatus'`nresult_message: '$resultMessage'`ncodex_output_tail: |`n$(($output | Select-Object -Last 30) -join "`n  " | ForEach-Object { "  $_" })"
            Atomic-WriteFile (Join-Path $logDir "agent_error.txt") $errContent | Out-Null

            # 寫 blocker.agent.txt 如果 codex 完全沒輸出 AGENT-RESULT
            if (-not $resultStatus) {
                $blockerContent = "blocker_type: agent`ntask_id: $taskId`ntimestamp: '$(Get-Date -Format 'o')'`nstage: $Stage`nreason: |`n  codex CLI 執行未產生 AGENT-RESULT 區塊（exit_code=$exitCode）`naction_required: |`n  查看 log/agent_error.txt，確認 codex CLI 是否正確安裝並已登入"
                Atomic-WriteFile (Join-Path $sysDir "blocker.agent.txt") $blockerContent | Out-Null
                Write-Host "  [BLOCKER] $taskId 已標記 blocker.agent.txt" -ForegroundColor Red
            }
        }
    }
}
