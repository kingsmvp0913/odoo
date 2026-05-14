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
    return Invoke-ClaudeStream -prompt $prompt -model "claude-haiku-4-5-20251001" -maxAttempts 3
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

            $maxAttempts = 3
            $success = $false

            for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
                Write-Host "[CODING] $($case.Name) attempt $attempt/$maxAttempts"

                $tracebackPath = Join-Path $case.FullName "logs\error.log"
                $tracebackContent = ""
                if (Test-Path $tracebackPath) {
                    $tracebackContent = Get-Content $tracebackPath -Raw
                }
                $slimSpec = python "$root\.claude\slim_spec.py" $analysisPath 2>&1
                if ($LASTEXITCODE -ne 0) { throw "slim_spec.py failed: $slimSpec" }
                $prompt = (Get-Content $agentPath -Raw) +
                          "`n`nSPEC:`n" + $slimSpec +
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

                # 寫入檔案（含路徑安全守衛）
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
                            $odooBin = "odoo-$odooVersion/odoo-bin"
                            $result = Run-TestProcess "python" @($odooBin, "-i", $module, "--test-tags=/$module", "--stop-after-init", "-d", "odoo") $root
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
                $isLockReleased = $true

                $dest = Join-Path $confirmDir $case.Name
                if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
                Move-Item -LiteralPath $case.FullName -Destination $confirmDir -Force
                Write-Host "[ROLLBACK] $($case.Name) → confirm/" -ForegroundColor Yellow
                continue
            }

            # 測試通過，移至 final
            $dest = Join-Path $finalDir $case.Name
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force -ErrorAction SilentlyContinue }
            Move-Item -LiteralPath $case.FullName -Destination $finalDir -Force
            Write-Host "[FINISH] $($case.Name) 完成開發並通過測試" -ForegroundColor Green
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
