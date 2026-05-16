# _pipeline_run.ps1 - Pipeline 完整執行（「開工」hook 觸發用）
# 依序執行 analysis → coding → qa，輸出 stdout 供 Claude context 注入

$ROOT = Split-Path $PSScriptRoot -Parent

if (-not $env:ODOO_PASSWORD) {
    Write-Host "[ERROR] 環境變數 ODOO_PASSWORD 未設定，Pipeline 中止。" -ForegroundColor Red
    exit 1
}

# 設定 hook 模式，讓子程序的 Open-ClaudeTerminal 略過開新 terminal
$env:PIPELINE_HOOK_MODE = "1"

Write-Host "=== Pipeline 開工 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" -ForegroundColor Cyan

Write-Host "`n--- STEP 1-3: 需求分析 (analysis.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File "$PSScriptRoot/analysis.ps1"

Write-Host "`n--- STEP 4: 實作 (coding.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File "$PSScriptRoot/coding.ps1"

Write-Host "`n--- STEP 5-6: QA (qa.ps1) ---" -ForegroundColor Yellow
pwsh -NoProfile -File "$PSScriptRoot/qa.ps1"

$env:PIPELINE_HOOK_MODE = ""

# 統計待 Claude 處理的任務
$pendingFiles = Get-ChildItem "$PSScriptRoot/kingsmvpsplan" -Recurse -Filter "pending_prompt.txt" -ErrorAction SilentlyContinue
$pendingCount = if ($pendingFiles) { @($pendingFiles).Count } else { 0 }

if ($pendingCount -gt 0) {
    # 寫入等待標記（供 Claude 識別需處理任務）
    [System.IO.File]::WriteAllText(
        "$PSScriptRoot/kingsmvpsplan/_PIPELINE_WAITING",
        "",
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
    Write-Host "每個任務完成後刪除 pending_prompt.txt 和 .pending_* 標記，再執行下一個。" -ForegroundColor Yellow
    Write-Host "全部完成後執行 pwsh -NoProfile -File `"$ROOT\.claude\_pipeline_run.ps1`" 推進 Pipeline。" -ForegroundColor Yellow
} else {
    Remove-Item "$PSScriptRoot/kingsmvpsplan/_PIPELINE_WAITING" -Force -ErrorAction SilentlyContinue
    Write-Host "`n=== Pipeline 完成，無待處理任務 ===" -ForegroundColor Green
}
