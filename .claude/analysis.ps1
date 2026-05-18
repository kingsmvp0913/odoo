# analysis.ps1 - 需求分析階段主程式（Steps 1–3b）
# PS1 僅負責機械工作（檔案管理）；AI 呼叫由 Claude terminal 非同步執行

. (Join-Path $PSScriptRoot "_common.ps1")

if (-not $env:ODOO_PASSWORD) {
    Write-Host "[ERROR] 環境變數 ODOO_PASSWORD 未設定" -ForegroundColor Red
    exit 1
}

Initialize-PipelineDirs

$agentPath     = Join-Path $script:ROOT ".claude\agents\requirements-analyst.md"
$agentRaw      = Get-Content $agentPath -Raw -Encoding UTF8
$agentTemplate = $agentRaw -replace '(?s)^---.*?---\r?\n', ''

# ============================================================
# STEP 1: 同步 Odoo 任務 → start/task_N/original.txt
# ============================================================
Write-Host "[STEP 1] 同步 Odoo 任務..." -ForegroundColor Cyan

$odooDisableFlag = Join-Path $script:PLAN_DIR "_ODOO_DISABLED"
if (Test-Path $odooDisableFlag) {
    Write-Host "[SKIP] Odoo 同步已停用（刪除 _ODOO_DISABLED 可重新啟用）" -ForegroundColor DarkGray
} else {
    $allDirs      = @($script:START_DIR, $script:CONFIRM_DIR, $script:ANALYSIS_DIR, $script:CODING_DIR, $script:FINAL_DIR)
    $processedIds = @()
    foreach ($dir in $allDirs) {
        if (Test-Path $dir) {
            Get-ChildItem $dir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                if ($_.Name -match '^task_(\d+)$') { $processedIds += $matches[1] }
            }
        }
    }
    $skipIds = ($processedIds | Select-Object -Unique) -join ","

    $pyScript = Join-Path $script:ROOT ".claude\curl.py"
    try {
        $out = python $pyScript $script:ODOO_URL $script:ODOO_DB $script:ODOO_USERNAME $env:ODOO_PASSWORD $script:ODOO_USER_ID $script:START_DIR $skipIds 2>&1
        $out | ForEach-Object { Write-Host $_ }
        if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Odoo 同步失敗，exit: $LASTEXITCODE" -ForegroundColor Yellow }
    } catch {
        Write-Host "[WARN] Odoo 同步例外: $_" -ForegroundColor Yellow
    }
}

# ============================================================
# STEP 2: start/ → confirm/（寫 pending prompt，不等 AI）
# ============================================================
Write-Host "`n[STEP 2] 準備初始分析任務（start/ → confirm/）..." -ForegroundColor Cyan

$lock2 = Join-Path $script:ROOT ".claude\kingsmvpsplan\global_analysis.lock"
if (-not (Acquire-Lock $lock2 300)) {
    Write-Host "[SKIP] 無法取得 STEP 2 全域鎖" -ForegroundColor Yellow
} else {
    try {
        $startTasks = Get-ChildItem $script:START_DIR -Directory -Exclude "README.md" -ErrorAction SilentlyContinue

        foreach ($taskDir in $startTasks) {
            $taskName     = $taskDir.Name
            $originalTxt  = Join-Path $taskDir.FullName "original.txt"
            $analysisDone = Join-Path $taskDir.FullName ".analysis_done"

            if (-not (Test-Path $originalTxt)) {
                Write-Host "[SKIP] $taskName 缺少 original.txt" -ForegroundColor Yellow
                continue
            }

            # 已分析完但未移動（上次意外中斷的容錯）
            if (Test-Path $analysisDone) {
                $taskLock = Join-Path $taskDir.FullName "process.lock"
                if (Acquire-Lock $taskLock 300) {
                    try {
                        $dest = Join-Path $script:CONFIRM_DIR $taskName
                        if (-not (Test-Path $dest)) {
                            Release-Lock $taskLock
                            Move-Item $taskDir.FullName $script:CONFIRM_DIR -Force
                            Write-Host "[MOVE] $taskName 補移到 confirm/" -ForegroundColor DarkCyan
                        }
                    } finally {
                        if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
                    }
                }
                continue
            }

            # 已有 pending prompt，等待 Claude 處理
            if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
                Write-Host "[WAIT] $taskName - Claude 分析中（pending_prompt.txt 存在）" -ForegroundColor DarkGray
                continue
            }

            $taskLock = Join-Path $taskDir.FullName "process.lock"
            if (-not (Acquire-Lock $taskLock 300)) {
                Write-Host "[SKIP] $taskName 已被鎖定" -ForegroundColor Yellow
                continue
            }

            try {
                $req = Get-Content $originalTxt -Raw -Encoding UTF8

                $taskProject = $null
                if ($req -match '---project---\s*[\r\n]+([^\r\n]+)') { $taskProject = $matches[1].Trim() }
                if (-not $taskProject) {
                    Write-Host "[SKIP] $taskName 缺少 ---project--- 欄位" -ForegroundColor Yellow
                    continue
                }

                $odooVersion = Get-ProjectVersion $taskProject
                if (-not $odooVersion) {
                    Write-Host "[CONFIG] $taskName - 專案「$taskProject」未設定版本，請更新 project_version_map.json" -ForegroundColor Red
                    continue
                }

                $currentTime  = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
                $destTaskDir  = Join-Path $script:CONFIRM_DIR $taskName   # 任務移動後的路徑
                $prompt = $agentTemplate `
                    -replace '__CASE_ID__', $taskName `
                    -replace '__CURRENT_TIME__', $currentTime

                $fullPrompt = "ultrathink`n`n" + $prompt +
                    "`n`n【SYSTEM CONFIRMED】odoo_version = `"$odooVersion`" — 固定事實，不得質疑。" +
                    "`n`n【TASK DIRECTORY】`n$destTaskDir" +
                    "`n`n【USER BUSINESS REQUIREMENT】`n<user_requirement>`n$req`n</user_requirement>" +
                    "`n`n將 analysis.yaml 和 .analysis_done 寫入【TASK DIRECTORY】，完成後刪除 pending_prompt.txt 和 .pending_analysis。"

                Write-PendingPrompt -taskDir $taskDir.FullName -stage "analysis" -prompt $fullPrompt

                Release-Lock $taskLock
                $dest = Join-Path $script:CONFIRM_DIR $taskName
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
                try {
                    Move-Item $taskDir.FullName $script:CONFIRM_DIR -Force
                    Write-Host "[OK] $taskName → confirm/ (等待 Claude 初始分析)" -ForegroundColor Green
                } catch {
                    # 搬移失敗：回滾 pending，避免任務目錄分裂（start/ 與 confirm/ 各一份）
                    Remove-Item (Join-Path $taskDir.FullName "pending_prompt.txt") -Force -ErrorAction SilentlyContinue
                    Remove-Item (Join-Path $taskDir.FullName ".pending_analysis")  -Force -ErrorAction SilentlyContinue
                    Write-Host "[ERROR] $taskName 搬移失敗（已回滾 pending）：$_" -ForegroundColor Red
                }
            } catch {
                Write-Host "[ERROR] STEP 2 ${taskName}: $_" -ForegroundColor Red
            } finally {
                if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
            }
        }
    } finally {
        Release-Lock $lock2
    }
}

# ============================================================
# STEP 3a: confirm/ → analysis/（無 AI，檢查答案完整性）
# ============================================================
Write-Host "`n[STEP 3a] 檢查 confirm/ 答案完整性..." -ForegroundColor Cyan

$confirmTasks = Get-ChildItem $script:CONFIRM_DIR -Directory -ErrorAction SilentlyContinue

foreach ($taskDir in $confirmTasks) {
    $taskName     = $taskDir.Name
    $taskLock     = Join-Path $taskDir.FullName "process.lock"
    $analysisDone = Join-Path $taskDir.FullName ".analysis_done"
    $answerDone   = Join-Path $taskDir.FullName ".answer_done"
    $yamlPath     = Join-Path $taskDir.FullName "analysis.yaml"

    # AI 尚未處理（.analysis_done 不存在）→ 跳過
    if (-not (Test-Path $analysisDone)) { continue }
    if (Test-Path $answerDone) { continue }
    if (-not (Test-Path $yamlPath)) { Write-Host "[WARN] $taskName 缺少 analysis.yaml" -ForegroundColor Yellow; continue }

    if (-not (Acquire-Lock $taskLock 300)) {
        Write-Host "[SKIP] $taskName 已被鎖定" -ForegroundColor Yellow
        continue
    }

    try {
        $yaml   = Get-Content $yamlPath -Raw -Encoding UTF8
        $parsed = ConvertFrom-Yaml $yaml

        $isModeB     = ($parsed['execution_mode'] -eq 'MODE_B')
        $noQuestions = -not [regex]::IsMatch($yaml, '(?m)^\s*user_answer:')
        $allAnswered = $isModeB -or $noQuestions -or (-not $parsed['has_null_answer'] -and $parsed['has_any_answer'])

        if (-not $allAnswered) {
            Write-Host "[WAIT] $taskName - 等待填寫 user_answer" -ForegroundColor DarkGray
            continue
        }

        Atomic-WriteFile $answerDone "" | Out-Null

        Release-Lock $taskLock
        $dest = Join-Path $script:ANALYSIS_DIR $taskName
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Move-Item $taskDir.FullName $script:ANALYSIS_DIR -Force
        Write-Host "[OK] $taskName 答案完整 → analysis/" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] STEP 3a ${taskName}: $_" -ForegroundColor Red
    } finally {
        if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
    }
}

# ============================================================
# STEP 3b: analysis/ 產生 MODE_B 最終規格（寫 pending prompt）
# ============================================================
Write-Host "`n[STEP 3b] 準備 MODE_B 最終規格任務..." -ForegroundColor Cyan

$lock3b = Join-Path $script:ROOT ".claude\kingsmvpsplan\global_recheck.lock"
if (-not (Acquire-Lock $lock3b 300)) {
    Write-Host "[SKIP] 無法取得 STEP 3b 全域鎖" -ForegroundColor Yellow
} else {
    try {
        $analysisTasks = Get-ChildItem $script:ANALYSIS_DIR -Directory -ErrorAction SilentlyContinue

        foreach ($taskDir in $analysisTasks) {
            $taskName   = $taskDir.Name
            $taskLock   = Join-Path $taskDir.FullName "process.lock"
            $answerDone = Join-Path $taskDir.FullName ".answer_done"
            $finalDone  = Join-Path $taskDir.FullName ".final_done"
            $yamlPath   = Join-Path $taskDir.FullName "analysis.yaml"

            if (-not (Test-Path $answerDone)) { continue }
            if (Test-Path $finalDone) { continue }

            # 已有 pending prompt，等待 Claude 處理
            if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
                Write-Host "[WAIT] $taskName - Claude 生成 MODE_B 中" -ForegroundColor DarkGray
                continue
            }

            if (-not (Test-Path $yamlPath)) { Write-Host "[WARN] $taskName 缺少 analysis.yaml" -ForegroundColor Yellow; continue }

            if (-not (Acquire-Lock $taskLock 300)) {
                Write-Host "[SKIP] $taskName 已被鎖定" -ForegroundColor Yellow
                continue
            }

            try {
                $currentYaml = Get-Content $yamlPath -Raw -Encoding UTF8
                $currentTime = Get-Date -Format "yyyy-MM-ddTHH:mm:ss"
                $prompt = $agentTemplate `
                    -replace '__CASE_ID__', $taskName `
                    -replace '__CURRENT_TIME__', $currentTime

                # STEP 3b 不搬移任務目錄（仍留在 analysis/）；coding.ps1 STEP 4 才會搬到 coding/
                # WIKI-CACHE 注入：此時 module 已由初始分析填入 analysis.yaml
                $parsedWiki = ConvertFrom-Yaml $currentYaml
                $wikiCache  = Get-WikiCache -moduleName $parsedWiki['module'] -odooVersion $parsedWiki['odoo_version'] -projectName $parsedWiki['project_name']

                $fullPrompt = "ultrathink`n`n" + $wikiCache + $prompt +
                    "`n`n【TASK DIRECTORY】`n$($taskDir.FullName)" +
                    "`n`n【EXISTING ANALYSIS WITH USER ANSWERS】`n<analysis_yaml>`n$currentYaml`n</analysis_yaml>" +
                    "`n`n使用者答案已填寫完畢。產生 MODE_B 完整 technical_specification，更新【TASK DIRECTORY】內的 analysis.yaml 並寫入 .final_done。完成後依序：(a) 寫入 .final_done (b) mv pending_prompt.txt done_prompt.txt (c) 刪除 .pending_final。"

                Write-PendingPrompt -taskDir $taskDir.FullName -stage "final" -prompt $fullPrompt
                Write-Host "[OK] $taskName → 等待 Claude 生成 MODE_B 規格" -ForegroundColor Green
            } catch {
                Write-Host "[ERROR] STEP 3b ${taskName}: $_" -ForegroundColor Red
            } finally {
                Release-Lock $taskLock
            }
        }
    } finally {
        Release-Lock $lock3b
    }
}

# ============================================================
# 狀態摘要 + 開啟 Claude Terminal
# ============================================================
Write-Host "`n=== Pipeline 任務狀態摘要 ===" -ForegroundColor Cyan
$stageMap = [ordered]@{
    start    = $script:START_DIR
    confirm  = $script:CONFIRM_DIR
    analysis = $script:ANALYSIS_DIR
    coding   = $script:CODING_DIR
    final    = $script:FINAL_DIR
}
$total = 0
foreach ($stage in $stageMap.Keys) {
    $dir = $stageMap[$stage]
    if (-not (Test-Path $dir)) { continue }
    Get-ChildItem $dir -Exclude "README.md" -ErrorAction SilentlyContinue | ForEach-Object {
        $hasPending = Test-Path (Join-Path $_.FullName "pending_prompt.txt")
        $suffix = if ($hasPending) { " [待 Claude]" } else { "" }
        Write-Host ("  [{0,-10}]  {1}{2}" -f $stage, $_.Name, $suffix) -ForegroundColor White
        $total++
    }
}
if ($total -eq 0) { Write-Host "  (目前無任何待處理任務)" -ForegroundColor DarkGray }

Open-ClaudeTerminal
Write-Host "`n[analysis.ps1 完成]"
