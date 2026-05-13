# ==============================================================================
# CONFIG
# ==============================================================================
$basePath     = "C:\odoo"
$projectType  = "Odoo"

$startDir     = "$basePath\.claude\kingsmvpsplan\start"
$confirmDir   = "$basePath\.claude\kingsmvpsplan\confirm"
$templatePath = "$basePath\.claude\agents\requirements-analyst.md"

$currentTime = (Get-Date).ToString("yyyy-MM-dd HH:mm")

# ==============================================================================
# CHECK START
# ==============================================================================
if (-not (Test-Path $startDir)) {
    Write-Host "[ERROR] start dir not found" -ForegroundColor Red
    exit
}

$pendingFiles = Get-ChildItem $startDir -Exclude "README.md"

if ($pendingFiles.Count -eq 0) {
    Write-Host "[INFO] no pending files"
    exit
}

# ==============================================================================
# LOAD AGENT
# ==============================================================================
if (-not (Test-Path $templatePath)) {
    Write-Host "[ERROR] missing agent.md" -ForegroundColor Red
    exit
}

$agent = Get-Content $templatePath -Raw

# ==============================================================================
# LOOP (ONE FILE = ONE REQUEST)
# ==============================================================================
foreach ($file in $pendingFiles) {

    try {

        $caseId = [System.IO.Path]::GetFileNameWithoutExtension($file.Name)
        $content = Get-Content $file.FullName -Raw

        Write-Host "[RUN] processing $caseId" -ForegroundColor Cyan

        # ----------------------------------------------------------------------
        # BUILD PROMPT
        # ----------------------------------------------------------------------
        $prompt = $agent
        $prompt = $prompt.Replace("__CASE_ID__", $caseId)
        $prompt = $prompt.Replace("__PROJECT_TYPE__", $projectType)
        $prompt = $prompt.Replace("__CURRENT_TIME__", $currentTime)

        $prompt += "`n`n【USER BUSINESS REQUIREMENT】`n$content"

        # ----------------------------------------------------------------------
        # CALL CLAUDE
        # ----------------------------------------------------------------------
        $response = $prompt | claude write --no-stream

        # ----------------------------------------------------------------------
        # PARSE JSON
        # ----------------------------------------------------------------------
        $obj = $response | ConvertFrom-Json -ErrorAction Stop

        # ----------------------------------------------------------------------
        # CREATE FOLDER
        # ----------------------------------------------------------------------
        $caseFolder = Join-Path $confirmDir $caseId
        New-Item -ItemType Directory -Force -Path $caseFolder | Out-Null

        Write-Host "[AI] project: $($obj.inferred_target.project)" -ForegroundColor Magenta
        Write-Host "[AI] module : $($obj.inferred_target.module)" -ForegroundColor Magenta

        # ----------------------------------------------------------------------
        # MODE ROUTING
        # ----------------------------------------------------------------------
        if ($obj.execution_mode -eq "MODE_A") {

            $obj.clarification_channel |
                ConvertTo-Json -Depth 10 |
                Out-File "$caseFolder\questions.json" -Encoding utf8

            Write-Host "[MODE A] questions saved" -ForegroundColor Yellow
        }
        else {

            $obj.technical_specification |
                ConvertTo-Json -Depth 20 |
                Out-File "$caseFolder\specification.json" -Encoding utf8

            Write-Host "[MODE B] spec saved" -ForegroundColor Green
        }

        # ----------------------------------------------------------------------
        # MOVE ORIGINAL FILE
        # ----------------------------------------------------------------------
        Move-Item $file.FullName $caseFolder -Force

        Write-Host "[DONE] $caseId completed" -ForegroundColor Gray
    }
    catch {

        Write-Host "[ERROR] failed $($file.Name)" -ForegroundColor Red

        $errorDir = "$confirmDir\error_logs"
        New-Item -ItemType Directory -Force -Path $errorDir | Out-Null

        $response | Out-File "$errorDir\error_$caseId.log"

        continue
    }
}