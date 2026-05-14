$root = "C:\odoo"

$confirmDir    = "$root\.claude\kingsmvpsplan\confirm"
$testcodingDir = "$root\.claude\kingsmvpsplan\testcoding"
$codingDir     = "$root\.claude\kingsmvpsplan\coding"

$agentPath     = "$root\.claude\agents\test-agent.md"

. "$root\.claude\_common.ps1"

# =========================================================
# 環境檢查函數
# =========================================================
function Test-Environment {
    param([string]$projectType, [string]$module, [hashtable]$dbConf = $null)
    $ok = $true
    $errors = @()
    if ($projectType.ToUpper() -eq "ODOO") {
        if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
            $ok = $false
            $errors += "python 命令不在 PATH 中"
        }
        $dbName = if ($dbConf) { $dbConf.db_name } else { 'odoo' }
        $dbUser = if ($dbConf) { $dbConf.db_user } else { 'odoo' }
        $dbPwd  = if ($dbConf) { $dbConf.db_password } else { '' }
        $dbHost = if ($dbConf) { $dbConf.db_host } else { 'localhost' }
        $dbPort = if ($dbConf) { $dbConf.db_port } else { '5432' }
        $dbCheck = python -c "import psycopg2; psycopg2.connect(dbname='$dbName', user='$dbUser', password='$dbPwd', host='$dbHost', port=$dbPort)" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $ok = $false
            $errors += "無法連線到資料庫 '$dbName' ($dbHost`:$dbPort)，請確認 odoo.conf 設定"
        }
    } else {
        if (-not (Get-Command "pytest" -ErrorAction SilentlyContinue)) {
            $ok = $false
            $errors += "pytest 不在 PATH 中"
        }
    }
    return @{ ok = $ok; errors = $errors }
}

# =========================================================
# ODOO CONF READER
# =========================================================
function Get-IniVal($text, $key, $default = $null) {
    if ($text -match "(?m)^\s*$([regex]::Escape($key))\s*=\s*(.+?)\s*$") { return $matches[1].Trim() }
    return $default
}

function Get-OdooConf($odooVersion) {
    $candidates = @(
        "$root\odoo-$odooVersion\odoo.conf",
        "$root\odoo-$odooVersion\debian\odoo.conf",
        "$root\odoo-$odooVersion\server\odoo.conf"
    )
    $confPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $confPath) {
        throw "找不到 odoo.conf，已搜尋：$($candidates -join ' | ')"
    }
    Write-Host "[CONF] 讀取 $confPath" -ForegroundColor DarkCyan
    $raw = Get-Content $confPath -Raw -Encoding UTF8
    return @{
        path        = $confPath
        db_host     = (Get-IniVal $raw 'db_host'     'localhost')
        db_port     = (Get-IniVal $raw 'db_port'     '5432')
        db_user     = (Get-IniVal $raw 'db_user'     'odoo')
        db_password = (Get-IniVal $raw 'db_password' '')
        db_name     = (Get-IniVal $raw 'test_db_name' $null)
    }
}

# =========================================================
# CLAUDE CALL (300s timeout, 3-retry with exponential backoff)
# =========================================================
function Invoke-ClaudeWithTimeout($prompt) {
    return Invoke-ClaudeStream -prompt $prompt -model "claude-sonnet-4-6" -maxAttempts 3
}

# =========================================================
# MAIN PIPELINE
# =========================================================
$globalLockFile = "$root\.claude\kingsmvpsplan\global_testcoding.lock"
if (-not (Acquire-Lock $globalLockFile 300)) {
    Write-Host "[SKIP] 無法取得測試階段全域鎖"
    exit 1
}

try {
    $cases = Get-ChildItem $testcodingDir -Directory -ErrorAction SilentlyContinue

    foreach ($case in $cases) {
        $lockPath = Join-Path $case.FullName "process.lock"
        if (-not (Acquire-Lock $lockPath 600)) {
            Write-Host "[SKIP] 鎖定中: $($case.Name)"
            continue
        }

        $isLockReleased = $false

        try {
            $analysisPath = "$($case.FullName)\analysis.json"
            if (-not (Test-Path $analysisPath)) { continue }

            $analysis = Get-Content $analysisPath -Raw | ConvertFrom-Json
            $projectType = $analysis.inferred_target.project
            $module = $analysis.inferred_target.module
            $odooVersion = $analysis.inferred_target.odoo_version
            if ([string]::IsNullOrWhiteSpace($projectType)) { $projectType = "GENERIC" }

            # 提前檢查 odoo_version
            if ($projectType.ToUpper() -eq "ODOO" -and [string]::IsNullOrWhiteSpace($odooVersion)) {
                Write-Host "[ERROR] $($case.Name) – odoo_version 未填寫，請返回 confirm/ 補充後重試。" -ForegroundColor Red
                continue
            }

            # 從 analysis.json 的 odoo_version 找對應資料夾的 odoo.conf
            $odooConf = $null
            if ($projectType.ToUpper() -eq "ODOO") {
                try {
                    $odooConf = Get-OdooConf $odooVersion
                } catch {
                    Write-Host "[ERROR] $($case.Name) – $_" -ForegroundColor Red
                    continue
                }
                if (-not $odooConf.db_name) {
                    Write-Host "[ERROR] $($case.Name) – odoo-$odooVersion\odoo.conf 缺少 test_db_name，請補上後重試" -ForegroundColor Red
                    continue
                }
            }

            # 環境檢查
            $envCheck = Test-Environment -projectType $projectType -module $module -dbConf $odooConf
            if (-not $envCheck.ok) {
                $errMsg = "環境檢查失敗: $($envCheck.errors -join ', ')"
                Write-Host "[ENV ERROR] $($case.Name) - $errMsg" -ForegroundColor Red
                Write-PipelineFile $errMsg "$($case.FullName)\environment_error.log"
                continue
            }

            Write-Host "[TDD] $($case.Name) generating tests..."
            $prompt = (Get-Content $agentPath -Raw) + "`n`nSPEC:`n" + ($analysis | ConvertTo-Json -Depth 100 -Compress)

            $rawAiOutput = ""
            try {
                $rawAiOutput = Invoke-ClaudeWithTimeout $prompt
                $files = Convert-MultiFileTags $rawAiOutput $case.FullName
            }
            catch {
                Write-Host "[ERROR] AI failed $($case.Name)"
                continue
            }

            if ($files.Count -eq 0) { continue }

            $writeSuccess = $true
            foreach ($k in $files.Keys) {
                if (-not (Out-AtomicFile $files[$k] $k $projectType $module $odooVersion)) {
                    $writeSuccess = $false
                    break
                }
                Write-Host "[FILE] $k"
            }

            if (-not $writeSuccess) { continue }

            # =====================================================
            # RUN TEST & 嚴格紅燈檢查
            # =====================================================
            try {
                switch ($projectType.ToUpper()) {
                    "ODOO" {
                        $odooBin = "odoo-$odooVersion/odoo-bin"
                        $dbName  = $odooConf.db_name
                        $result = Run-TestProcess "python" @($odooBin, "-c", "odoo-$odooVersion/odoo.conf", "-i", $module, "--test-tags=/$module", "--stop-after-init", "-d", $dbName) $root
                    }
                    default {
                        $result = Run-TestProcess "pytest" @() $root
                    }
                }
            }
            catch {
                Write-Host "[TEST EXEC ERROR] $_"
                continue
            }

            $isExitCodeFail       = ($result.ExitCode -ne 0)
            $isLogContainsFailure = ($result.Output -match "FAIL" -or $result.Output -match "ERROR" -or $result.Output -match "Traceback")
            $hasTestRun           = ($result.Output -match "Ran \d+ tests? in")
            $isZeroTestsRun       = ($projectType.ToUpper() -eq "ODOO" -and $result.Output -match "Ran 0 tests")

            $isValidRed = $isExitCodeFail -and $isLogContainsFailure -and (-not $isZeroTestsRun) -and $hasTestRun

            if (-not $isValidRed) {
                if ($isZeroTestsRun) {
                    $blockerMsg = "測試執行結果為 Ran 0 tests – 請檢查測試檔案是否正確繼承 TransactionCase 或 pytest 約定"
                } elseif (-not $hasTestRun) {
                    $blockerMsg = "測試輸出中未偵測到 'Ran X tests' – 可能測試框架未正確執行"
                } elseif (-not $isExitCodeFail -or -not $isLogContainsFailure) {
                    $blockerMsg = "測試意外通過（綠燈），但 TDD 要求測試必須先紅燈。請確認測試涵蓋了尚未實作的功能。"
                } else {
                    $blockerMsg = "測試執行未產生有效的紅燈狀態（未知原因）"
                }
                Write-Host "[BLOCKER] $($case.Name) – $blockerMsg" -ForegroundColor Red
                Write-PipelineFile $blockerMsg "$($case.FullName)\blocker.txt"

                Release-Lock $lockPath
                $isLockReleased = $true

                $dest = Join-Path $confirmDir $case.Name
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item -LiteralPath $case.FullName -Destination $confirmDir -Force
                Write-Host "[ROLLBACK] $($case.Name) → confirm/" -ForegroundColor Yellow
                continue
            }

            # 記錄測試錯誤詳情
            $logDir = Join-Path $case.FullName "logs"
            if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
            $errorLog = Join-Path $logDir "error.log"
            $errorLines = $result.Output -split "`r?`n" | Where-Object { $_ -match "FAIL" -or $_ -match "ERROR" -or $_ -match "Traceback" -or $_ -match "Exception" -or $_ -match "Ran 0 tests" }
            $errorContent = if ($errorLines) { $errorLines -join "`n" } else { $result.Output }
            Write-PipelineFile $errorContent $errorLog

            # 移動至 coding
            $dest = Join-Path $codingDir $case.Name
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
            Move-Item -LiteralPath $case.FullName -Destination $codingDir -Force
            Write-Host "[ADVANCE] $($case.Name) (RED confirmed)" -ForegroundColor Green

            # 滾動式清理備份
            $historicalBaks = Get-ChildItem $codingDir -Directory -Filter "$($case.Name)_bak_*" -ErrorAction SilentlyContinue | Sort-Object CreationTime -Descending
            if ($historicalBaks.Count -gt 3) {
                $historicalBaks | Select-Object -Skip 3 | ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
            }
        }
        catch {
            Write-Host "[ERROR] 處理案件 $($case.Name) 時發生例外: $_" -ForegroundColor Red
        }
        finally {
            if (-not $isLockReleased) { Release-Lock $lockPath }
        }
    }
}
finally {
    Release-Lock $globalLockFile
}

Write-Host "[DONE]"
