# =========================================================
# SHARED PIPELINE FUNCTIONS - sourced by analysis.ps1 / test_coding.ps1 / coding.ps1
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
                $isExpired     = $age.TotalSeconds -gt $existing.ttlSeconds
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
        catch { return $false }
        finally { if ($null -ne $stream) { $stream.Close() } }
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
    catch { Remove-Item $lockPath -Force -ErrorAction SilentlyContinue }
}

function Convert-MultiFileTags($aiOutput, $caseDir) {
    $files = @{}
    $currentFile = $null
    $buffer = New-Object System.Text.StringBuilder

    foreach ($line in ($aiOutput -split "`r?`n")) {
        $t = $line.Trim()
        if ($t -match '^@FILE:(.+)$') {
            if ($currentFile) { $files[$currentFile] = $buffer.ToString().Trim(); $buffer.Clear() | Out-Null }
            $currentFile = $Matches[1].Trim()
            continue
        }
        if ($t -eq '@FILE_END') {
            if ($currentFile) { $files[$currentFile] = $buffer.ToString().Trim(); $currentFile = $null; $buffer.Clear() | Out-Null }
            continue
        }
        if ($currentFile) { $buffer.AppendLine($line) | Out-Null }
    }
    if ($currentFile) { $files[$currentFile] = $buffer.ToString().Trim() }

    if ($files.Count -eq 0) {
        $rawOutputPath = Join-Path $caseDir "ai_raw_output_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
        $aiOutput | Out-File $rawOutputPath -Encoding utf8 -Force
        Write-Host "[FATAL] AI 輸出格式錯誤，未產生任何檔案。原始輸出已儲存至: $rawOutputPath" -ForegroundColor Red
        Write-Host "[FATAL] 請檢查 AI 是否遵循 @FILE: / @FILE_END 格式" -ForegroundColor Red
    }
    return $files
}

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

# $root must be defined in the calling script before dot-sourcing
function Out-AtomicFile($content, $path, $projectType, $module, $odooVersion) {
    $normPath = $path.Replace("\", "/")
    $fixedPath = $normPath

    if ($projectType.ToUpper() -eq "ODOO") {
        if ([string]::IsNullOrWhiteSpace($odooVersion)) {
            Write-Host "[ERROR] odoo_version 未填寫，無法判斷目標目錄，跳過: $normPath" -ForegroundColor Red
            return $false
        }
        $expectedPrefix = "custom_addons/$module/"
        if ($normPath -notlike "$expectedPrefix*") {
            $stripped = $normPath -replace '^(custom_addons/[^/]+/|custom_addons/)', ''
            $fixedPath = "$expectedPrefix$stripped"
            Write-Host "[PATH FIX] $normPath → $fixedPath" -ForegroundColor Yellow
        }
        $baseDir = Join-Path $root "odoo-$odooVersion"
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

function Invoke-ClaudeStream {
    param(
        [string]$prompt,
        [string]$model,
        [int]$timeoutMs = 300000,
        [int]$maxAttempts = 3
    )
    $attempt = 1
    $waitSec = 2

    while ($attempt -le $maxAttempts) {
        $p = $null
        try {
            $psi = New-Object System.Diagnostics.ProcessStartInfo
            $psi.FileName = "claude"
            $psi.Arguments = "-p --model $model"
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

            # Async stderr prevents deadlock while we stream stdout
            $stderrTask = $p.StandardError.ReadToEndAsync()

            # Stream stdout with deadline enforcement
            $stdoutSb = New-Object System.Text.StringBuilder
            $sw = [System.Diagnostics.Stopwatch]::StartNew()
            while (-not $p.StandardOutput.EndOfStream) {
                $remaining = [Math]::Max(1, $timeoutMs - [int]$sw.ElapsedMilliseconds)
                $readTask = $p.StandardOutput.ReadLineAsync()
                if (-not $readTask.Wait($remaining)) {
                    $p.Kill()
                    try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
                    throw "timeout"
                }
                $line = $readTask.Result
                if ($null -ne $line) {
                    Write-Host $line
                    $stdoutSb.AppendLine($line) | Out-Null
                }
            }
            $p.WaitForExit(5000) | Out-Null

            $resp    = $stdoutSb.ToString().Trim()
            $errText = $stderrTask.Result.Trim()
            if ([string]::IsNullOrWhiteSpace($resp) -and -not [string]::IsNullOrWhiteSpace($errText)) {
                $resp = $errText
            }

            if ([string]::IsNullOrWhiteSpace($resp)) { throw "empty response" }

            Start-Sleep -Milliseconds (Get-Random -Min 200 -Max 800)
            return $resp
        }
        catch {
            Write-Host "[RETRY] $model attempt $attempt failed: $_" -ForegroundColor Yellow
            Start-Sleep -Seconds $waitSec
            $waitSec *= 2
            $attempt++
        }
    }
    throw "Claude ($model) failed after $maxAttempts retries"
}

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
