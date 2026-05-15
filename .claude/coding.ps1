# coding.ps1 - 實作階段主程式（Step 4）
# PS1 僅負責機械工作（檔案管理）；AI 呼叫由 Claude terminal 非同步執行

$script:ROOT = "C:\odoo"
. "$script:ROOT\.claude\_common.ps1"

Initialize-PipelineDirs

Write-Host "[STEP 4] 準備實作任務（analysis/ → coding/）..." -ForegroundColor Cyan

$agentPath     = Join-Path $script:ROOT ".claude\agents\senior-software-engineer.md"
$agentRaw      = Get-Content $agentPath -Raw -Encoding UTF8
$agentTemplate = $agentRaw -replace '(?s)^---.*?---\r?\n', ''

$analysisTasks = Get-ChildItem $script:ANALYSIS_DIR -Directory -ErrorAction SilentlyContinue

foreach ($taskDir in $analysisTasks) {
    $taskName        = $taskDir.Name
    $taskLock        = Join-Path $taskDir.FullName "process.lock"
    $finalDone       = Join-Path $taskDir.FullName ".final_done"
    $implementDone   = Join-Path $taskDir.FullName ".implement_done"
    $analysisYamlPath = Join-Path $taskDir.FullName "analysis.yaml"

    if (-not (Test-Path $finalDone))     { continue }
    if (Test-Path $implementDone)        { continue }

    # 已有 pending prompt，等待 Claude 處理
    if (Test-Path (Join-Path $taskDir.FullName "pending_prompt.txt")) {
        Write-Host "[WAIT] $taskName - Claude 實作中" -ForegroundColor DarkGray
        continue
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

        $modulePath  = Get-ModulePath -moduleName $moduleName -odooVersion $odooVersion -projectName $projectName
        $destTaskDir = Join-Path $script:CODING_DIR $taskName   # 任務移動後的路徑

        Write-Host "[INFO] $taskName → $modulePath" -ForegroundColor DarkCyan

        $fullPrompt = $agentTemplate +
            "`n`n【TASK DIRECTORY】`n$destTaskDir" +
            "`n`n【SPECIFICATION】`n讀取 $($destTaskDir)\analysis.yaml 取得完整規格。" +
            "`n`n【OUTPUT PATH】`n$modulePath" +
            "`n`n【RULES】`n1. 若模組目錄已存在，先讀取現有程式碼再修改`n2. 依規格寫入所有實作檔案`n3. 完成後寫入 .implement_done 到【TASK DIRECTORY】`n4. 刪除 pending_prompt.txt 和 .pending_coding"

        Write-PendingPrompt -taskDir $taskDir.FullName -stage "coding" -prompt $fullPrompt

        Release-Lock $taskLock
        $dest = Join-Path $script:CODING_DIR $taskName
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Move-Item $taskDir.FullName $script:CODING_DIR -Force
        Write-Host "[OK] $taskName → coding/ (等待 Claude 實作)" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] ${taskName}: $_" -ForegroundColor Red
    } finally {
        if ($script:LockHandles.ContainsKey($taskLock)) { Release-Lock $taskLock }
    }
}

Open-ClaudeTerminal
Write-Host "`n[coding.ps1 完成]" -ForegroundColor Green
