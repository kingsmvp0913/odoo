# _pipeline_run.ps1 - Pipeline 完整執行（「開工」hook 觸發用）
# 依序執行 analysis → coding → qa，輸出 stdout 供 Claude context 注入

$kingsmvpsplanDir = Join-Path $PSScriptRoot "kingsmvpsplan"

if (-not $env:ODOO_PASSWORD) {
    Write-Host "[ERROR] 環境變數 ODOO_PASSWORD 未設定，Pipeline 中止。" -ForegroundColor Red
    exit 1
}

# ============================================================
# Loop Counter 管理（防死循環）
# max loop_count = 20 per run；max task_reentries = 2 per task
# ============================================================
$counterFile   = Join-Path $kingsmvpsplanDir "_LOOP_COUNTER.json"
$loopCount     = 0
$startedAt     = Get-Date -Format 'o'
$taskReentries = @{}

if (Test-Path $counterFile) {
    try {
        $existing = Get-Content $counterFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $startedAt     = $existing.run_started_at
        $loopCount     = [int]$existing.loop_count + 1
        if ($existing.task_reentries) {
            $existing.task_reentries.PSObject.Properties | ForEach-Object {
                $taskReentries[$_.Name] = [int]$_.Value
            }
        }
    } catch {}
}

if ($loopCount -gt 20) {
    $firstPending = Get-ChildItem $kingsmvpsplanDir -Recurse -Filter "pending_prompt.txt" `
        -ErrorAction SilentlyContinue | Select-Object -First 1
    $blockerContent = @"
blocker_type: loop
task_id: unknown
timestamp: $(Get-Date -Format 'o')

loop_count: $loopCount
task_reentries: 0
limit_exceeded: loop_count

reason: |
  Pipeline 循環次數超過安全上限 (loop_count=$loopCount > 20)，自動停止以防死循環。
  run_started_at: $startedAt

last_pending_tasks:
  - $(if ($firstPending) { $firstPending.FullName } else { 'none' })

action_required: |
  1. 確認任務是否有循環觸發條件（如 analysis 一直輸出新任務）
  2. 手動解決問題後刪除此 blocker 檔案
  3. 刪除 _LOOP_COUNTER.json 重置計數器
  4. 重新執行 pipeline
"@
    if ($firstPending) {
        $taskDir = Split-Path $firstPending.FullName -Parent
        [System.IO.File]::WriteAllText(
            (Join-Path $taskDir "blocker.loop.txt"),
            $blockerContent,
            [System.Text.Encoding]::UTF8
        )
        Write-Host "[CRITICAL] blocker.loop.txt 已寫入: $taskDir" -ForegroundColor Red
    }
    Write-Host "[CRITICAL] Pipeline loop_count=$loopCount 超過上限 20，中止。" -ForegroundColor Red
    exit 1
}

# 追蹤任務重入（本次執行前已有 pending 的任務計入重入次數）
$existingPending = Get-ChildItem $kingsmvpsplanDir -Recurse -Filter "pending_prompt.txt" `
    -ErrorAction SilentlyContinue
foreach ($pf in $existingPending) {
    $tid = Split-Path (Split-Path $pf.FullName -Parent) -Leaf
    if ($tid -match '^task_\d+$') {
        $taskReentries[$tid] = if ($taskReentries.ContainsKey($tid)) { $taskReentries[$tid] + 1 } else { 1 }
        if ($taskReentries[$tid] -gt 2) {
            $taskDir    = Split-Path $pf.FullName -Parent
            $blockerMsg = @"
blocker_type: loop
task_id: $tid
timestamp: $(Get-Date -Format 'o')

loop_count: $loopCount
task_reentries: $($taskReentries[$tid])
limit_exceeded: task_reentry

reason: |
  $tid 重入次數 $($taskReentries[$tid]) 超過上限 2。
  任務可能陷入反覆 BackToConfirm → rework 循環。

action_required: |
  1. 查看任務目錄內的 qa_report.yaml 和 analysis.yaml
  2. 手動修正根本原因後刪除此 blocker 檔案
  3. 刪除 _LOOP_COUNTER.json 重置計數器
  4. 重新執行 pipeline
"@
            [System.IO.File]::WriteAllText(
                (Join-Path $taskDir "blocker.loop.txt"),
                $blockerMsg,
                [System.Text.Encoding]::UTF8
            )
            Write-Host "[WARN] $tid 重入次數=$($taskReentries[$tid]) 超過 2，已升級為 blocker.loop.txt" -ForegroundColor Yellow
        }
    }
}

# 儲存更新後的計數器
$counterObj = [PSCustomObject]@{
    run_started_at = $startedAt
    loop_count     = $loopCount
    task_reentries = $taskReentries
}
try { $counterObj | ConvertTo-Json | Out-File $counterFile -Encoding UTF8 -Force } catch {}

Write-Host "=== Pipeline 開工 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan
Write-Host "[LOOP] loop_count=$loopCount / 20，run_started_at=$startedAt" -ForegroundColor DarkCyan

# 設定 hook 模式，讓子程序的 Open-ClaudeTerminal 略過開新 terminal
$env:PIPELINE_HOOK_MODE = "1"

Write-Host "`n--- STEP 1-3: 需求分析 (analysis.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $PSScriptRoot "analysis.ps1")

Write-Host "`n--- STEP 4: 實作 (coding.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $PSScriptRoot "coding.ps1")

Write-Host "`n--- STEP 5-6: QA (qa.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File (Join-Path $PSScriptRoot "qa.ps1")

$env:PIPELINE_HOOK_MODE = ""

# 統計待 Claude 處理的任務
$pendingFiles = Get-ChildItem $kingsmvpsplanDir -Recurse -Filter "pending_prompt.txt" -ErrorAction SilentlyContinue
$pendingCount = if ($pendingFiles) { @($pendingFiles).Count } else { 0 }

$waitingFlag = Join-Path $kingsmvpsplanDir "_PIPELINE_WAITING"

if ($pendingCount -gt 0) {
    # 寫入等待標記（含時間戳，TTL 30 分鐘）
    [System.IO.File]::WriteAllText(
        $waitingFlag,
        (Get-Date -Format 'o'),
        [System.Text.Encoding]::UTF8
    )
    Write-Host "`n=== Pipeline 機械工作完成 ===" -ForegroundColor Cyan
    Write-Host "待 Claude 處理: $pendingCount 個任務" -ForegroundColor Magenta
    Write-Host ""
    Write-Host "[CLAUDE-ACTION-REQUIRED] 請依序讀取並完整執行以下 pending_prompt.txt：" -ForegroundColor Magenta
    foreach ($f in $pendingFiles) {
        Write-Host "  - $($f.FullName)" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "每個任務完成後：先寫 .<stage>_done，再 mv pending_prompt.txt done_prompt.txt，刪除 .pending_* flag。" -ForegroundColor Yellow
    Write-Host "全部完成後執行 pwsh -NoProfile -File `"$(Join-Path $PSScriptRoot '_pipeline_run.ps1')`" 推進 Pipeline。" -ForegroundColor Yellow
} else {
    # 成功結束：清除等待標記與計數器
    Remove-Item $waitingFlag  -Force -ErrorAction SilentlyContinue
    Remove-Item $counterFile  -Force -ErrorAction SilentlyContinue
    Write-Host "`n=== Pipeline 完成，無待處理任務 ===" -ForegroundColor Green
}
