# qa.ps1 - 品管階段主程式（Steps 5–6）
# PS1 僅負責機械工作；AI QA 由 Claude terminal 非同步執行

. (Join-Path $PSScriptRoot "_common.ps1")

Initialize-PipelineDirs

$agentPath     = Join-Path $script:CLAUDE_DIR "agents\qa-analyst.md"
$agentRaw      = Get-Content $agentPath -Raw -Encoding UTF8
$agentTemplate = $agentRaw -replace '(?s)^---.*?---\r?\n', ''

# ============================================================
# STEP 5: coding/ → 寫 QA pending prompt（不等 AI）
# Module 序列鎖：同一模組只啟動一個 QA 任務
# ============================================================
Write-Host "[STEP 5] 準備 QA 任務..." -ForegroundColor Cyan

$qaModulePending = @{}
$codingTasks = Get-ChildItem $script:CODING_DIR -Directory -ErrorAction SilentlyContinue

foreach ($taskDir in $codingTasks) {
    $taskName         = $taskDir.Name
    $taskLock         = Join-Path $taskDir.FullName "process.lock"
    $implementDone    = Join-Path (Get-SystemDir $taskDir.FullName) ".implement_done"
    $qaDone           = Join-Path (Get-SystemDir $taskDir.FullName) ".qa_done"
    $analysisYamlPath = Join-Path $taskDir.FullName "analysis.yaml"

    if (Test-HasBlocker $taskDir.FullName) {
        Write-Host "[BLOCKER] $taskName 已有 blocker 檔案，跳過（需人工處理）" -ForegroundColor Red
        continue
    }

    if (-not (Test-Path $implementDone)) { continue }
    if (Test-Path $qaDone)               { continue }

    # 已有 pending prompt，等待 Claude 處理（超過 30 分鐘則清除重新排隊）
    if (Test-Path (Join-Path (Get-SystemDir $taskDir.FullName) "pending_prompt.txt")) {
        if (Test-PendingStale $taskDir.FullName) {
            Clear-StalePending $taskDir.FullName
        } else {
            Write-Host "[WAIT] $taskName - Claude QA 中" -ForegroundColor DarkGray
            continue
        }
    }

    if (-not (Test-Path $analysisYamlPath)) {
        Write-Host "[ERROR] $taskName 缺少 analysis.yaml" -ForegroundColor Red; continue
    }

    if (-not (Acquire-Lock $taskLock 300)) {
        Write-Host "[SKIP] $taskName 已被鎖定" -ForegroundColor Yellow; continue
    }

    try {
        $yamlContent = Get-Content $analysisYamlPath -Raw -Encoding UTF8
        $parsed      = ConvertFrom-Yaml $yamlContent

        $moduleName  = $parsed['module']
        $odooVersion = $parsed['odoo_version']
        $projectName = $parsed['project_name']

        if (-not $moduleName) {
            Write-Host "[ERROR] $taskName 無法解析 module 名稱" -ForegroundColor Red; continue
        }

        # Module 序列鎖：同一模組只允許一個 QA 任務並行
        if ($qaModulePending.ContainsKey($moduleName)) {
            Write-Host "[QUEUE] $taskName - 模組 $moduleName QA 序列等待，下輪處理" -ForegroundColor DarkYellow
            continue
        }
        $qaModulePending[$moduleName] = $true

        $modulePath = Get-ModulePath -moduleName $moduleName -odooVersion $odooVersion -projectName $projectName
        Write-Host "[INFO] $taskName 準備 QA: $modulePath" -ForegroundColor DarkCyan

        $fullPrompt = $agentTemplate +
            "`n`n【TASK DIRECTORY】`n$($taskDir.FullName)" +
            "`n`n【SPECIFICATION】`n讀取 $analysisYamlPath" +
            "`n`n【IMPLEMENTATION PATH】`n$modulePath" +
            "`n`n完成後依序：(a) 寫入 log/qa_report.yaml 和 system/.qa_done 到【TASK DIRECTORY】(b) 將 system/pending_prompt.txt 內容寫入 log/done_prompt.txt，然後刪除 system/pending_prompt.txt（移動不是複製，來源必須刪除）(c) 刪除 system/.pending_qa flag。"

        Write-PendingPrompt -taskDir $taskDir.FullName -stage "qa" -prompt $fullPrompt
        Write-Host "[OK] $taskName → 等待 Claude QA 檢查" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] STEP 5 ${taskName}: $_" -ForegroundColor Red
    } finally {
        Release-Lock $taskLock
    }
}

# ============================================================
# STEP 6: 依 QA 報告移至 final/ 或退回 confirm/（無 AI）
# ============================================================
Write-Host "`n[STEP 6] 處理 QA 結果..." -ForegroundColor Cyan

$codingTasks2 = Get-ChildItem $script:CODING_DIR -Directory -ErrorAction SilentlyContinue

foreach ($taskDir in $codingTasks2) {
    $taskName     = $taskDir.Name
    $taskLock     = Join-Path $taskDir.FullName "process.lock"
    $qaDone       = Join-Path (Get-SystemDir $taskDir.FullName) ".qa_done"
    $qaReportPath = Join-Path (Get-LogDir    $taskDir.FullName) "qa_report.yaml"

    if (-not (Test-Path $qaDone))       { continue }
    if (-not (Test-Path $qaReportPath)) { continue }

    # 若 system/pending_prompt.txt 仍存在（QA 尚未完成），跳過（超過 30 分鐘則清除）
    if (Test-Path (Join-Path (Get-SystemDir $taskDir.FullName) "pending_prompt.txt")) {
        if (Test-PendingStale $taskDir.FullName) {
            Clear-StalePending $taskDir.FullName
        } else {
            Write-Host "[WAIT] $taskName - Claude QA 尚未完成" -ForegroundColor DarkGray
            continue
        }
    }

    if (-not (Acquire-Lock $taskLock 300)) {
        Write-Host "[SKIP] $taskName 已被鎖定" -ForegroundColor Yellow; continue
    }

    try {
        $qaReport = Get-Content $qaReportPath -Raw -Encoding UTF8
        $parsed   = ConvertFrom-Yaml $qaReport
        $status   = $parsed['status']

        if ($status -eq "PASSED") {
            Release-Lock $taskLock
            $dest = Join-Path $script:FINAL_DIR $taskName
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Move-Item $taskDir.FullName $script:FINAL_DIR -Force
            Write-Host "[OK] $taskName QA 通過 → final/" -ForegroundColor Green

            # if ($taskName -match '^task_(\d+)$') {
            #     Send-OdooTaskMessage -taskId ([int]$matches[1]) -message "<p>【Pipeline】任務已完成，請查看 final/$taskName/</p>"
            # }
        } else {
            # 從 issues: 區塊取得第一個 description（避免誤抓 items 區的欄位）
            $reason = "QA 檢查失敗"
            $afterIssues = if ($qaReport -match '(?s)issues:(.*?)$') { $matches[1] } else { "" }
            if ($afterIssues -match '(?m)^\s*description:\s*"?([^"\r\n]+?)"?\s*$') {
                $reason = $matches[1].Trim().Trim('"').Trim("'")
            }

            Release-Lock $taskLock
            BackToConfirm -taskDir $taskDir.FullName -reason $reason -stage "QA"
        }
    } catch {
        Write-Host "[ERROR] STEP 6 ${taskName}: $_" -ForegroundColor Red
    } finally {
        if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
    }
}

Open-ClaudeTerminal
Write-Host "`n[qa.ps1 完成]" -ForegroundColor Green
