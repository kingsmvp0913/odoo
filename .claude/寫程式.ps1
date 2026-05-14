$root = "C:\odoo"

$confirmDir    = "$root\.claude\kingsmvpsplan\confirm"
$codingDir     = "$root\.claude\kingsmvpsplan\coding"
$finalDir      = "$root\.claude\kingsmvpsplan\final"

$agentPath     = "$root\.claude\agents\senior-software-engineer.md"

# =========================================================
# 🔐 PRODUCTION LOCK SYSTEM
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
# CLAUDE CALL (HAIKU)
# =========================================================
function Invoke-ClaudeHaiku($prompt) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "claude"
    $psi.Arguments = "-p --model claude-haiku-4-5-20251001"
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
        # 只殺此進程樹
        try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
        throw "timeout"
    }

    $resp = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($resp)) { throw "empty" }

    return $resp
}

# =========================================================
# PARSER (含格式錯誤處理)
# =========================================================
function Convert-MultiFileTags($aiOutput, $caseDir) {
    $files = @{}
    $currentFile = $null
    $buffer = New-Object System.Text.StringBuilder

    foreach ($line in ($aiOutput -split "`r?`n")) {
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

        if ($currentFile) {
            $buffer.AppendLine($line) | Out-Null
        }
    }

    if ($currentFile) {
        $files[$currentFile] = $buffer.ToString().Trim()
    }

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
# 🔧 ATOMIC WRITE (AI 產出檔案，含路徑白名單自動修正)
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
# TEST RUNNER
# =========================================================
function Run-TestProcess($exe, $argsArray, $workDir, $timeoutSec = 60) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $exe
    $psi.WorkingDirectory = $workDir
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true

    foreach ($arg in $argsArray) {
        $psi.ArgumentList.Add($arg)
    }

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
# 輔助：儲存 Agent 輸出與 Prompt 供除錯
# =========================================================
function Save-DebugArtifact {
    param($caseDir, $prompt, $rawOutput, $attempt)
    $debugDir = Join-Path $caseDir "debug"
    if (-not (Test-Path $debugDir)) { New-Item -ItemType Directory -Force $debugDir | Out-Null }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $promptFile = Join-Path $debugDir "prompt_${timestamp}_attempt${attempt}.txt"
    $outputFile = Join-Path $debugDir "output_${timestamp}_attempt${attempt}.txt"
    Write-PipelineFile $prompt $promptFile
    Write-PipelineFile $rawOutput $outputFile
}

# =========================================================
# MAIN PIPELINE (支援重試)
# =========================================================
$globalLockFile = "$root\.claude\kingsmvpsplan\global_coding.lock"
if (-not (Acquire-Lock $globalLockFile 300)) {
    Write-Host "[SKIP] 無法取得編碼階段全域鎖"
    exit 1
}

try {
    $cases = Get-ChildItem $codingDir -Directory -ErrorAction SilentlyContinue

    foreach ($case in $cases) {
        $lockPath = Join-Path $case.FullName "process.lock"

        if (-not (Acquire-Lock $lockPath 600)) {
            Write-Host "[SKIP] locked: $($case.Name)"
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

            $maxAttempts = 3
            $success = $false

            for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
                Write-Host "[CODING] $($case.Name) attempt $attempt/$maxAttempts"

                $tracebackPath = Join-Path $case.FullName "logs\error.log"
                $tracebackContent = ""
                if (Test-Path $tracebackPath) {
                    $tracebackContent = Get-Content $tracebackPath -Raw
                }
                $prompt = (Get-Content $agentPath -Raw) +
                          "`n`nSPEC:`n" + ($analysis | ConvertTo-Json -Depth 100 -Compress) +
                          "`n`n<traceback_log>`n$tracebackContent`n</traceback_log>"

                $rawOutput = ""
                try {
                    $rawOutput = Invoke-ClaudeHaiku $prompt
                }
                catch {
                    Write-Host "[ERROR] Claude 呼叫失敗: $_"
                    Save-DebugArtifact -caseDir $case.FullName -prompt $prompt -rawOutput $rawOutput -attempt $attempt
                    continue
                }

                $files = Convert-MultiFileTags $rawOutput $case.FullName
                Save-DebugArtifact -caseDir $case.FullName -prompt $prompt -rawOutput $rawOutput -attempt $attempt

                if ($files.Count -eq 0) {
                    Write-Host "[EMPTY OUTPUT] 跳過此嘗試" -ForegroundColor Yellow
                    continue
                }

                # 寫入檔案（使用強化版 Out-AtomicFile）
                $anyWriteFail = $false
                foreach ($k in $files.Keys) {
                    if ($k -match "\.\." -or $k -match "^/" -or $k -match "^[A-Za-z]:\\") {
                        Write-Host "[SECURITY] 拒絕非法路徑: $k" -ForegroundColor Red
                        $anyWriteFail = $true
                        break
                    }
                    if (-not (Out-AtomicFile $files[$k] $k $projectType $module $odooVersion)) {
                        Write-Host "[WRITE FAIL] $k" -ForegroundColor Red
                        $anyWriteFail = $true
                        break
                    }
                    Write-Host "[FILE] $k"
                }
                if ($anyWriteFail) { continue }

                # 執行測試
                try {
                    switch ($projectType.ToUpper()) {
                        "ODOO" {
                            $odooBin = if ($odooVersion) { "odoo-$odooVersion/odoo-bin" } else { "odoo-bin" }
                    $result = Run-TestProcess "python" @($odooBin,"-i",$module,"--test-tags=/$module","--stop-after-init","-d","odoo") $root
                        }
                        default {
                            $result = Run-TestProcess "pytest" @() $root
                        }
                    }
                }
                catch {
                    Write-Host "[TEST ERROR] $_" -ForegroundColor Red
                    Write-PipelineFile "$_" "$($case.FullName)\logs\error.log"
                    continue
                }

                # 判斷是否綠燈
                $isGreen = ($result.ExitCode -eq 0) -and ($result.Output -notmatch "FAIL|ERROR|Traceback")
                if ($isGreen) {
                    Write-Host "[GREEN] $($case.Name) 測試通過！" -ForegroundColor Green
                    $success = $true
                    break
                } else {
                    Write-Host "[RED] 測試仍失敗，準備重試" -ForegroundColor Red
                    $logDir = Join-Path $case.FullName "logs"
                    if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
                    Write-PipelineFile $result.Output "$logDir\error.log"
                }
            }

            if (-not $success) {
                $blockerMsg = "經過 $maxAttempts 次嘗試，測試仍未通過。請確認 analysis.json 規格或手動介入。"
                Write-PipelineFile $blockerMsg "$($case.FullName)\blocker.txt"
                Write-Host "[BLOCKER] $($case.Name) – $blockerMsg" -ForegroundColor Red
                Release-Lock $lockPath
                $dest = Join-Path $confirmDir $case.Name
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item -LiteralPath $case.FullName -Destination $confirmDir -Force
                Write-Host "[ROLLBACK] $($case.Name) → confirm/" -ForegroundColor Yellow
                continue
            }

            # 測試通過，移至 final
            $dest = Join-Path $finalDir $case.Name
            if (Test-Path $dest) {
                Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue
            }
            Move-Item -LiteralPath $case.FullName -Destination $finalDir -Force
            Write-Host "[FINISH] $($case.Name) 完成開發並通過測試" -ForegroundColor Green
        }
        catch {
            Write-Host "[ERROR] 處理 $($case.Name) 時發生例外: $_" -ForegroundColor Red
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