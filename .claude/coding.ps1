$root = "C:\odoo"

$confirmDir    = "$root\.claude\kingsmvpsplan\confirm"
$codingDir     = "$root\.claude\kingsmvpsplan\coding"
$finalDir      = "$root\.claude\kingsmvpsplan\final"

$agentPath     = "$root\.claude\agents\senior-software-engineer.md"

. "$root\.claude\_common.ps1"

# =========================================================
# CLAUDE CALL (HAIKU, 300s timeout, 3-retry with exponential backoff)
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

    if (-not $p.WaitForExit(300000)) {
        $p.Kill()
        try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
        throw "timeout"
    }

    $resp = $p.StandardOutput.ReadToEnd() + $p.StandardError.ReadToEnd()
    if ([string]::IsNullOrWhiteSpace($resp)) { throw "empty response" }
    return $resp
}

# =========================================================
# 輔助：儲存 Agent 輸出與 Prompt 供除錯
# =========================================================
function Save-DebugArtifact {
    param($caseDir, $prompt, $rawOutput, $attempt)
    $debugDir = Join-Path $caseDir "debug"
    if (-not (Test-Path $debugDir)) { New-Item -ItemType Directory -Force $debugDir | Out-Null }
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    Write-PipelineFile $prompt (Join-Path $debugDir "prompt_${timestamp}_attempt${attempt}.txt")
    Write-PipelineFile $rawOutput (Join-Path $debugDir "output_${timestamp}_attempt${attempt}.txt")
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

            # 讀取 odoo.conf（含 test_db_name）
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

            Write-Host "[CODING] $($case.Name)"

            $tracebackPath = Join-Path $case.FullName "logs\error.log"
            $tracebackContent = ""
            if (Test-Path $tracebackPath) {
                $tracebackContent = Get-Content $tracebackPath -Raw
            }
            $prompt = (Get-Content $agentPath -Raw) +
                      "`n`nSPEC:`n" + ($analysis | ConvertTo-Json -Depth 100 -Compress) +
                      "`n`n<traceback_log>`n$tracebackContent`n</traceback_log>"

            $rawOutput = Invoke-ClaudeHaiku $prompt
            $files = Convert-MultiFileTags $rawOutput $case.FullName
            Save-DebugArtifact -caseDir $case.FullName -prompt $prompt -rawOutput $rawOutput -attempt 1

            if ($files.Count -eq 0) {
                Write-Host "[EMPTY OUTPUT] AI 未產生任何檔案，請手動確認 debug/ 後重新執行" -ForegroundColor Red
                continue
            }

            # 寫入檔案（含路徑安全守衛）
            foreach ($k in $files.Keys) {
                if ($k -match "\.\." -or $k -match "^/" -or $k -match "^[A-Za-z]:\\") {
                    Write-Host "[SECURITY] 拒絕非法路徑: $k" -ForegroundColor Red
                    continue
                }
                if (-not (Out-AtomicFile $files[$k] $k $projectType $module $odooVersion)) {
                    Write-Host "[WRITE FAIL] $k" -ForegroundColor Red
                    continue
                }
                Write-Host "[FILE] $k"
            }

            # 執行測試
            $result = $null
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
                Write-Host "[TEST ERROR] $_" -ForegroundColor Red
                Write-PipelineFile "$_" "$($case.FullName)\logs\error.log"
                continue
            }

            $isGreen = ($result.ExitCode -eq 0) -and ($result.Output -notmatch "FAIL|ERROR|Traceback")
            if ($isGreen) {
                Write-Host "[GREEN] $($case.Name) 測試通過！" -ForegroundColor Green
                $dest = Join-Path $finalDir $case.Name
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item -LiteralPath $case.FullName -Destination $finalDir -Force
                Write-Host "[FINISH] $($case.Name) 完成開發並通過測試" -ForegroundColor Green
            } else {
                Write-Host "[RED] $($case.Name) 測試未通過，請確認後手動重新執行" -ForegroundColor Red
                $logDir = Join-Path $case.FullName "logs"
                if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Force $logDir | Out-Null }
                Write-PipelineFile $result.Output "$logDir\error.log"
            }
        }
        catch {
            Write-Host "[ERROR] 處理 $($case.Name) 時發生例外: $_" -ForegroundColor Red
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
