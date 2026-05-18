# coding.ps1 - 實作階段主程式（Step 4）
# PS1 僅負責機械工作（檔案管理）；AI 呼叫由 Claude terminal 非同步執行

. (Join-Path $PSScriptRoot "_common.ps1")

Initialize-PipelineDirs

Write-Host "[STEP 4] 準備實作任務（analysis/ → coding/）..." -ForegroundColor Cyan

$agentPath     = Join-Path $script:CLAUDE_DIR "agents\senior-software-engineer.md"
$agentRaw      = Get-Content $agentPath -Raw -Encoding UTF8
$agentTemplate = $agentRaw -replace '(?s)^---.*?---\r?\n', ''

# Module 序列鎖：收集 coding/ 中已有活動任務的模組（不重複處理同一模組）
$activeModules = @{}
Get-ChildItem $script:CODING_DIR -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $yamlPath = Join-Path $_.FullName "analysis.yaml"
    if (Test-Path $yamlPath) {
        try {
            $p = ConvertFrom-Yaml (Get-Content $yamlPath -Raw -Encoding UTF8)
            if ($p['module']) { $activeModules[$p['module']] = $true }
        } catch {}
    }
}

$analysisTasks = Get-ChildItem $script:ANALYSIS_DIR -Directory -ErrorAction SilentlyContinue

foreach ($taskDir in $analysisTasks) {
    $taskName         = $taskDir.Name
    $taskLock         = Join-Path $taskDir.FullName "process.lock"
    $finalDone        = Join-Path $taskDir.FullName ".final_done"
    $implementDone    = Join-Path $taskDir.FullName ".implement_done"
    $analysisYamlPath = Join-Path $taskDir.FullName "analysis.yaml"

    if (Test-HasBlocker $taskDir.FullName) {
        Write-Host "[BLOCKER] $taskName 已有 blocker 檔案，跳過（需人工處理）" -ForegroundColor Red
        continue
    }

    if (-not (Test-Path $finalDone))  { continue }
    if (Test-Path $implementDone)     { continue }

    # 已有 pending prompt，等待 Claude 處理（超過 30 分鐘則清除重新排隊）
    if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
        if (Test-PendingStale $taskDir.FullName) {
            Clear-StalePending $taskDir.FullName
        } else {
            Write-Host "[WAIT] $taskName - Claude 實作中" -ForegroundColor DarkGray
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

        if (-not (Test-YamlComplete $analysisYamlPath)) {
            $blockerPath = Join-Path $taskDir.FullName "blocker.spec.txt"
            $blockerMsg = "technical_specification 不完整（缺少 model_name），無法開始實作。請重新產生規格。"
            Atomic-WriteFile $blockerPath $blockerMsg | Out-Null
            Write-Host "[BLOCKER] $taskName YAML 規格不完整，已寫入 blocker.spec.txt" -ForegroundColor Red
            continue
        }

        # Module 序列鎖：同一模組只允許一個活動任務
        if ($activeModules.ContainsKey($moduleName)) {
            Write-Host "[QUEUE] $taskName - 模組 $moduleName 序列等待（已有活動任務），下輪處理" -ForegroundColor DarkYellow
            continue
        }
        $activeModules[$moduleName] = $true

        $modulePath  = Get-ModulePath -moduleName $moduleName -odooVersion $odooVersion -projectName $projectName
        $destTaskDir = Join-Path $script:CODING_DIR $taskName

        Write-Host "[INFO] $taskName → $modulePath" -ForegroundColor DarkCyan

        # WIKI-CACHE 注入：在 Agent prompt 中 prepend 模組相關 wiki 內容
        $wikiCache = Get-WikiCache -moduleName $moduleName -odooVersion $odooVersion -projectName $projectName

        $fullPrompt = "ultrathink`n`n" + $wikiCache + $agentTemplate +
            "`n`n【TASK DIRECTORY】`n$destTaskDir" +
            "`n`n【SPECIFICATION】`n讀取 $($destTaskDir)\analysis.yaml 取得完整規格。" +
            "`n`n【OUTPUT PATH】`n$modulePath" +
            "`n`n【RULES】`n1. 若模組目錄已存在，先讀取現有程式碼再修改`n2. 依規格寫入所有實作檔案`n3. 完成後依序：(a) 寫入 .implement_done 到【TASK DIRECTORY】(b) mv pending_prompt.txt done_prompt.txt (c) 刪除 .pending_coding flag"

        Write-PendingPrompt -taskDir $taskDir.FullName -stage "coding" -prompt $fullPrompt

        Release-Lock $taskLock
        $dest = Join-Path $script:CODING_DIR $taskName
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        try {
            Move-Item $taskDir.FullName $script:CODING_DIR -Force
            Write-Host "[OK] $taskName → coding/ (等待 Claude 實作)" -ForegroundColor Green
        } catch {
            Write-Host "[ERROR] $taskName Move 失敗，清除 pending: $_" -ForegroundColor Red
            Remove-Item (Join-Path $taskDir.FullName 'pending_prompt.txt') -Force -ErrorAction SilentlyContinue
            Remove-Item (Join-Path $taskDir.FullName '.pending_coding') -Force -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Host "[ERROR] ${taskName}: $_" -ForegroundColor Red
    } finally {
        if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
    }
}

Open-ClaudeTerminal
Write-Host "`n[coding.ps1 完成]" -ForegroundColor Green
