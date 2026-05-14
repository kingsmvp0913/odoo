$root = "C:\odoo"

$confirmDir    = "$root\.claude\kingsmvpsplan\confirm"
$testcodingDir = "$root\.claude\kingsmvpsplan\testcoding"
$codingDir     = "$root\.claude\kingsmvpsplan\coding"

$agentPath     = "$root\.claude\agents\test-agent.md"

# =========================================================
# 鎖函數 (與分析.ps1 共用介面)
# =========================================================
function Acquire-Lock {
    param([string]$lockPath, [int]$ttlSeconds = 600)
    $lockObj = @{
        pid        = $PID
        host       = $env:COMPUTERNAME
        created    = (Get-Date).ToString("o")
        ttlSeconds = $ttlSeconds
    }

    $maxAttempts = 3
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        $stream = $null
        try {
            $stream = [System.IO.File]::Open($lockPath, 'CreateNew', 'Write', 'None')
            $writer = New-Object System.IO.StreamWriter($stream)
            $writer.Write(($lockObj | ConvertTo-Json -Depth 5))
            $writer.Flush()
            return $true
        }
        catch [System.IO.IOException] {
            if (-not (Test-Path $lockPath)) { continue }
            try {
                $existing = Get-Content $lockPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
                $age = (Get-Date) - [DateTime]::Parse($existing.created)
                $isExpired    = $age.TotalSeconds -gt $existing.ttlSeconds
                $isDeadProcess = -not (Get-Process -Id $existing.pid -ErrorAction SilentlyContinue)
                if ($isExpired -or $isDeadProcess) {
                    Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
                    continue
                }
                return $false
            }
            catch {
                Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
                continue
            }
        }
        catch {
            return $false
        }
        finally {
            if ($null -ne $stream) { $stream.Close() }
        }
    }
    return $false
}

function Release-Lock {
    param([string]$lockPath)
    if (-not (Test-Path $lockPath)) { return }
    try {
        $lock = Get-Content $lockPath -Raw | ConvertFrom-Json
        if ($lock.pid -eq $PID -and $lock.host -eq $env:COMPUTERNAME) {
            Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
        }
    }
    catch {
        Remove-Item $lockPath -Force -ErrorAction SilentlyContinue
    }
}

# =========================================================
# 環境檢查函數
# =========================================================
function Test-Environment {
    param([string]$projectType, [string]$module)
    $ok = $true
    $errors = @()
    if ($projectType.ToUpper() -eq "ODOO") {
        if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
            $ok = $false
            $errors += "python 命令不在 PATH 中"
        }
        $dbCheck = python -c "import psycopg2; psycopg2.connect(dbname='odoo', user='odoo', password='odoo', host='localhost')" 2>&1
        if ($LASTEXITCODE -ne 0) {
            $ok = $false
            $errors += "無法連線到 Odoo 資料庫，請確認資料庫配置"
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
# CLAUDE CALL (SAFE WITH PROCESS TREE KILL)
# =========================================================
function Invoke-ClaudeWithTimeout($prompt) {
    $maxAttempts = 3; $attempt = 1; $waitSec = 2

    while ($attempt -le $maxAttempts) {
        try {
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "claude"
            $psi.Arguments = "-p --model claude-sonnet-4-6"
            $psi.RedirectStandardInput = $true
            $psi.RedirectStandardOutput = $true
            $psi.RedirectStandardError = $true
            $psi.UseShellExecute = $false
            $psi.CreateNoWindow = $true

            $p = New-Object System.Diagnostics.Process
            $p.StartInfo = $psi
            $p.Start() | Out-Null

            $writer = New-Object System.IO.StreamWriter($p.StandardInput.BaseStream, [System.Text.Encoding]::UTF8)
            $writer.Write($prompt)
            $writer.Close()

            if (-not $p.WaitForExit(30000)) {
                $p.Kill()
                # 只殺此進程樹，不影響其他 claude 實例
                try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
                throw "timeout"
            }

            $resp = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd()
            if ([string]::IsNullOrWhiteSpace($resp)) { throw "empty" }

            Start-Sleep -Milliseconds (Get-Random -Min 200 -Max 800)
            return $resp
        }
        catch {
            Write-Host "[RETRY] attempt $attempt failed: $_"
            Start-Sleep -Seconds $waitSec
            $waitSec *= 2; $attempt++
        }
    }
    throw "Claude failed"
}

# =========================================================
# SAFE PARSER (LINE BY LINE) + 格式錯誤處理
# =========================================================
function Convert-MultiFileTags($aiOutput, $caseDir) {
    $files = @{}
    $currentFile = $null
    $buffer = New-Object System.Text.StringBuilder

    $lines = $aiOutput -split "`r?`n"
    foreach ($line in $lines) {
        $t = $line.Trim()
        if ($t -match '^@FILE:(.+)$') {
            if ($currentFile) {
                $files[$currentFile] = $buffer.ToString().Trim()
                $buffer.Clear() | Out-Null
            }
            $currentFile = $Matches[1].Trim()
            continue
        }
        if ($t -eq '@FILE_END') {
            if ($currentFile) {
                $files[$currentFile] = $buffer.ToString().Trim()
                $currentFile = $null
                $buffer.Clear() | Out-Null
            }
            continue
        }
        if ($currentFile) { $buffer.AppendLine($line) | Out-Null }
    }
    if ($currentFile) { $files[$currentFile] = $buffer.ToString().Trim() }

    # 🔴 若解析出 0 個檔案，儲存 AI 原始輸出並印出明確錯誤
    if ($files.Count -eq 0) {
        $rawOutputPath = Join-Path $caseDir "ai_raw_output_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
        $aiOutput | Out-File $rawOutputPath -Encoding utf8 -Force
        Write-Host "[FATAL] AI 輸出格式錯誤，未產生任何檔案。原始輸出已儲存至: $rawOutputPath" -ForegroundColor Red
        Write-Host "[FATAL] 請檢查 AI 是否遵循 @FILE: / @FILE_END 格式" -ForegroundColor Red
    }
    return $files
}

# =========================================================
# PIPELINE INTERNAL FILE WRITE (絕對路徑，僅供內部日誌)
# =========================================================
function Write-PipelineFile($content, $absolutePath) {
    try {
        $tmp = "$absolutePath.tmp"
        $dir = Split-Path $absolutePath
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
        [System.IO.File]::WriteAllText($tmp, $content, [System.Text.Encoding]::UTF8)
        Move-Item -Force $tmp $absolutePath
    }
    catch {
        if (Test-Path "$absolutePath.tmp") { Remove-Item "$absolutePath.tmp" -Force -ErrorAction SilentlyContinue }
    }
}

# =========================================================
# ATOMIC WRITE (AI 產出檔案，支援路徑白名單自動修正)
# =========================================================
function Out-AtomicFile($content, $path, $projectType, $module, $odooVersion = "") {
    $normPath = $path.Replace("\", "/")
    $fixedPath = $normPath

    if ($projectType.ToUpper() -eq "ODOO") {
        $expectedPrefix = "custom_addons/$module/"
        if ($normPath -notlike "$expectedPrefix*") {
            $stripped = $normPath -replace '^(custom_addons/[^/]+/|custom_addons/)', ''
            $fixedPath = "$expectedPrefix$stripped"
            Write-Host "[PATH FIX] $normPath → $fixedPath" -ForegroundColor Yellow
        }
        $projectDir = if ($odooVersion) { "odoo-$odooVersion" } else { "odoo-14.0" }
        $baseDir = Join-Path $root $projectDir
    } else {
        if ($normPath -notlike "tests/*" -and $normPath -notlike "src/*" -and $normPath -ne "requirements.txt" -and $normPath -ne "package.json") {
            $fixedPath = "tests/$normPath"
            Write-Host "[PATH FIX] $normPath → $fixedPath" -ForegroundColor Yellow
        }
        $baseDir = $root
    }

    $finalAbsolute = Join-Path $baseDir $fixedPath
    try {
        $tmp = "$finalAbsolute.tmp"
        $dir = Split-Path $finalAbsolute
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
        $content | Out-File $tmp -Encoding utf8 -Force
        Move-Item -Force $tmp $finalAbsolute
        return $true
    }
    catch {
        if (Test-Path "$finalAbsolute.tmp") { Remove-Item "$finalAbsolute.tmp" -Force -ErrorAction SilentlyContinue }
        return $false
    }
}

# =========================================================
# TEST EXECUTION
# =========================================================
function Run-TestProcess($exe, $argsArray, $workDir, $timeoutSec = 60) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.WorkingDirectory = $workDir
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    foreach ($arg in $argsArray) { $psi.ArgumentList.Add($arg) }

    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    $p.Start() | Out-Null

    if (-not $p.WaitForExit($timeoutSec * 1000)) {
        $p.Kill()
        throw "test timeout"
    }

    return @{
        ExitCode = $p.ExitCode
        Output   = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd()
    }
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

        try {
            $analysisPath = "$($case.FullName)\analysis.json"
            if (-not (Test-Path $analysisPath)) { continue }

            $analysis = Get-Content $analysisPath -Raw | ConvertFrom-Json
            $projectType = $analysis.inferred_target.project
            $module = $analysis.inferred_target.module
            $odooVersion = $analysis.inferred_target.odoo_version
            if ([string]::IsNullOrWhiteSpace($projectType)) { $projectType = "GENERIC" }

            # 環境檢查
            $envCheck = Test-Environment -projectType $projectType -module $module
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

            if ($files.Count -eq 0) {
                # 已在 Convert-MultiFileTags 中儲存原始輸出並印出錯誤，直接跳過
                continue
            }

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
                        $odooBin = if ($odooVersion) { "odoo-$odooVersion/odoo-bin" } else { "odoo-bin" }
                    $result = Run-TestProcess "python" @($odooBin, "-i", $module, "--test-tags=/$module", "--stop-after-init", "-d", "odoo") $root
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

            $isExitCodeFail = ($result.ExitCode -ne 0)
            $isLogContainsFailure = ($result.Output -match "FAIL" -or $result.Output -match "ERROR" -or $result.Output -match "Traceback")
            $hasTestRun = ($result.Output -match "Ran \d+ tests? in")
            $isZeroTestsRun = ($projectType.ToUpper() -eq "ODOO" -and $result.Output -match "Ran 0 tests")

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
            if (Test-Path $dest) {
                Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
            }
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
            Release-Lock $lockPath
        }
    }
}
finally {
    Release-Lock $globalLockFile
}

Write-Host "[DONE]"