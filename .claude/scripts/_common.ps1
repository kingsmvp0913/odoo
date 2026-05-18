# _common.ps1 - 共用函數庫

# ============================================================
# 路徑常數
# ============================================================
$script:CLAUDE_DIR       = Split-Path -Parent $PSScriptRoot
$script:ROOT             = Split-Path -Parent $script:CLAUDE_DIR
$script:ONLINE_ADDONS_DIR = if ($env:ONLINE_ADDONS_DIR) { $env:ONLINE_ADDONS_DIR } elseif ($IsLinux) { "/online_addons" } else { "C:\online_addons" }

$script:PLAN_DIR     = Join-Path $script:CLAUDE_DIR "kingsmvpsplan"

$script:START_DIR    = Join-Path $script:PLAN_DIR "start"
$script:CONFIRM_DIR  = Join-Path $script:PLAN_DIR "confirm"
$script:ANALYSIS_DIR = Join-Path $script:PLAN_DIR "analysis"
$script:CODING_DIR   = Join-Path $script:PLAN_DIR "coding"
$script:FINAL_DIR    = Join-Path $script:PLAN_DIR "final"

$script:PIPELINE_WAITING     = Join-Path $script:PLAN_DIR "_PIPELINE_WAITING"
$script:PROJECT_VERSION_MAP_PATH = Join-Path $script:CLAUDE_DIR "project_version_map.json"

# ============================================================
# Odoo 連線常數
# ============================================================
$script:ODOO_URL      = "https://odoo.ideaxpress.biz"
$script:ODOO_DB       = "odoo"
$script:ODOO_USERNAME = "steven.lin@ideaxpress.biz"
$script:ODOO_USER_ID  = if ($env:ODOO_USER_ID) { [int]$env:ODOO_USER_ID } else { 79 }

# ============================================================
# 編碼設定
# ============================================================
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ============================================================
# 檔案鎖（真正排他鎖：持有 handle 直到 Release-Lock）
# ============================================================
$script:LockHandles = @{}

function Acquire-Lock {
    param(
        [string]$LockPath,
        [int]$TimeoutSeconds = 300
    )
    $startTime = Get-Date
    while ($true) {
        try {
            $handle = [System.IO.File]::Open($LockPath, 'OpenOrCreate', 'ReadWrite', 'None')
            $script:LockHandles[$LockPath] = $handle
            return $true
        } catch {
            if ((Get-Date) - $startTime -gt [TimeSpan]::FromSeconds($TimeoutSeconds)) {
                Write-Host "[LOCK] 逾時無法取得: $LockPath" -ForegroundColor Red
                return $false
            }
            Start-Sleep -Milliseconds 500
        }
    }
}

function Release-Lock {
    param([string]$LockPath)
    if ($script:LockHandles.ContainsKey($LockPath)) {
        try { $script:LockHandles[$LockPath].Close(); $script:LockHandles[$LockPath].Dispose() } catch {}
        $script:LockHandles.Remove($LockPath)
    }
    Remove-Item $LockPath -Force -ErrorAction SilentlyContinue
}

# ============================================================
# 目錄初始化
# ============================================================
function Initialize-PipelineDirs {
    @($script:START_DIR, $script:CONFIRM_DIR, $script:ANALYSIS_DIR, $script:CODING_DIR, $script:FINAL_DIR) | ForEach-Object {
        if (-not (Test-Path $_)) { New-Item -ItemType Directory -Force $_ | Out-Null }
    }
}

# ============================================================
# 模組路徑函數
# ============================================================
function Get-OnlineAddonsRoot {
    param([string]$odooVersion, [string]$projectName = $null, [string]$moduleName = $null)
    if (-not [string]::IsNullOrWhiteSpace($projectName)) {
        $dirEntry = Get-ProjectDir -projectName $projectName
        if ($null -eq $dirEntry) {
            Write-Host "[WARN] project_dir_map 找不到 '$projectName'，直接用 project_name 當目錄名（可能錯誤）" -ForegroundColor Yellow
            $dirEntry = $projectName
        }

        # 陣列：掃描找到模組實際所在目錄；找不到則用第一個（新模組預設）
        if ($dirEntry -is [System.Array] -or $dirEntry -is [System.Collections.IList]) {
            $dirs = @($dirEntry)
            if ($moduleName) {
                foreach ($d in $dirs) {
                    $candidate = Join-Path $script:ONLINE_ADDONS_DIR $d
                    if (Test-Path (Join-Path $candidate $moduleName)) {
                        return $candidate
                    }
                }
            }
            # 找不到 → 回退第一個目錄
            $dirName = $dirs[0]
        } else {
            $dirName = "$dirEntry"
        }

        $p = Join-Path $script:ONLINE_ADDONS_DIR $dirName
        if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force $p | Out-Null }
        return $p
    }
    $major = $odooVersion -replace '\.0$', ''
    $p = Join-Path $script:ONLINE_ADDONS_DIR $major
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Force $p | Out-Null }
    return $p
}

function Get-ModulePath {
    param([string]$moduleName, [string]$odooVersion, [string]$projectName = $null)
    return Join-Path (Get-OnlineAddonsRoot -odooVersion $odooVersion -projectName $projectName -moduleName $moduleName) $moduleName
}

# ============================================================
# YAML 序列化（支援巢狀物件與物件陣列）
# ============================================================
function Format-YamlScalar {
    param($val)
    if ($null -eq $val) { return 'null' }
    if ($val -is [bool]) { return $val.ToString().ToLower() }
    if ($val -is [int] -or $val -is [long] -or $val -is [double]) { return "$val" }
    $s = "$val"
    if ($s -eq '' -or $s -match '[\r\n]' -or $s -match '^\s|\s$' -or $s -match '[:#\[\]{}&*!|>''"%@`]') {
        return "'" + ($s -replace "'", "''") + "'"
    }
    return $s
}

function Write-YamlObject {
    param($obj, [int]$indent, [string]$prefix = '')
    $sp = ' ' * $indent
    $lines = @()
    $props = if ($obj -is [hashtable]) { $obj.GetEnumerator() } else { $obj.PSObject.Properties }
    $first = $true
    foreach ($p in $props) {
        $lead = if ($first -and $prefix) { "$prefix$($p.Name)" } else { "$sp$($p.Name)" }
        $v = $p.Value
        if ($null -eq $v) {
            $lines += "${lead}: null"
        } elseif ($v -is [hashtable] -or $v -is [PSCustomObject]) {
            $lines += "${lead}:"
            $lines += Write-YamlObject $v ($indent + 2)
        } elseif ($v -is [System.Collections.IList]) {
            $lines += "${lead}:"
            foreach ($item in $v) {
                if ($null -eq $item) {
                    $lines += "$sp  - null"
                } elseif ($item -is [hashtable] -or $item -is [PSCustomObject]) {
                    $lines += Write-YamlObject $item ($indent + 4) "$sp  - "
                } else {
                    $lines += "$sp  - $(Format-YamlScalar $item)"
                }
            }
        } else {
            $lines += "${lead}: $(Format-YamlScalar $v)"
        }
        $first = $false
    }
    return $lines
}

function ConvertTo-Yaml {
    param($obj)
    if ($null -eq $obj) { return 'null' }
    if ($obj -is [hashtable] -or $obj -is [PSCustomObject]) {
        return (Write-YamlObject $obj 0) -join "`n"
    }
    return Format-YamlScalar $obj
}

# ============================================================
# YAML 反序列化（萃取關鍵欄位，支援 CRLF）
# ============================================================
function ConvertFrom-Yaml {
    param([string]$yaml)
    $result = @{}

    if ($yaml -match '(?m)^execution_mode:\s*(\S+)') { $result['execution_mode'] = $matches[1] }
    # \s* — supports both root-level and indented module fields; strip surrounding quotes
    if ($yaml -match '(?m)^\s*module:\s*["'']?([^"''\r\n]+?)["'']?\s*$') { $result['module'] = $matches[1].Trim() }
    # Strip surrounding single or double quotes; handle both indented and root-level
    if ($yaml -match '(?m)^(?:\s+)?odoo_version:\s*["'']?([^"''\r\n]+?)["'']?\s*$') {
        $result['odoo_version'] = $matches[1].Trim()
    }
    if ($yaml -match '(?m)^(?:\s+)?project_name:\s*["'']?([^"''\r\n]+?)["'']?\s*$') {
        $val = $matches[1].Trim()
        # project_name: null in YAML becomes the string "null" via regex — convert to $null
        $result['project_name'] = if ($val -eq 'null') { $null } else { $val }
    }
    if ($yaml -match '(?m)^status:\s*(\S+)') { $result['status'] = $matches[1] }

    $result['has_null_answer'] = [regex]::IsMatch($yaml, "(?m)^\s*user_answer:\s*(null|`"`"|''|)?\s*$")
    $result['has_any_answer']  = [regex]::IsMatch($yaml, '(?m)^\s*user_answer:\s*\S')
    $result['is_mode_b']       = ($result['execution_mode'] -eq 'MODE_B')

    return $result
}

# ============================================================
# 原子性寫檔
# ============================================================
function Atomic-WriteFile {
    param([string]$path, [string]$content)
    try {
        $dir = Split-Path $path -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Force $dir | Out-Null }
        $tmp = "$path.tmp"
        [System.IO.File]::WriteAllText($tmp, $content, [System.Text.Encoding]::UTF8)
        Move-Item -Force $tmp $path
        return $true
    } catch {
        Remove-Item "$path.tmp" -Force -ErrorAction SilentlyContinue
        return $false
    }
}

# ============================================================
# Pipeline Pending Prompt（寫入後由 Claude 非同步執行）
# ============================================================
function Write-PendingPrompt {
    param([string]$taskDir, [string]$stage, [string]$prompt)
    Atomic-WriteFile (Join-Path $taskDir "pending_prompt.txt") $prompt | Out-Null
    Atomic-WriteFile (Join-Path $taskDir ".pending_$stage") "" | Out-Null
}

# ============================================================
# Stale Pending 偵測（Agent 崩潰保護）
# ============================================================
function Test-PendingStale {
    param([string]$taskDir, [int]$AgeMinutes = 30)
    $pendingPath = Join-Path $taskDir "pending_prompt.txt"
    if (-not (Test-Path $pendingPath)) { return $false }
    $age = (Get-Date) - (Get-Item $pendingPath).LastWriteTime
    return $age.TotalMinutes -gt $AgeMinutes
}

function Clear-StalePending {
    param([string]$taskDir)
    $taskName = Split-Path $taskDir -Leaf
    Write-Host "[STALE] $taskName pending_prompt.txt 超過 30 分鐘，清除重新排隊" -ForegroundColor Yellow
    Remove-Item (Join-Path $taskDir "pending_prompt.txt") -Force -ErrorAction SilentlyContinue
    # .pending_* flag 也清除，讓下一輪 PS1 重新判斷 stage 並寫入新 pending_prompt
    Get-ChildItem $taskDir -Filter ".pending_*" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
}

function Test-HasBlocker {
    param([string]$taskDir)
    return [bool](Get-ChildItem $taskDir -Filter "blocker.*.txt" -ErrorAction SilentlyContinue | Select-Object -First 1)
}

# ============================================================
# 開啟 Claude Terminal（PS1 結束後觸發 AI 處理）
# ============================================================
function Open-ClaudeTerminal {
    # Hook 模式：Claude 已在執行，不開新 terminal
    if ($env:PIPELINE_HOOK_MODE -eq "1") {
        Write-Host "[PIPELINE] Hook 模式，略過開啟新 Terminal" -ForegroundColor DarkGray
        return
    }

    $pendingFiles = Get-ChildItem $script:PLAN_DIR -Recurse -Filter "pending_prompt.txt" -ErrorAction SilentlyContinue
    if (-not $pendingFiles -or $pendingFiles.Count -eq 0) {
        Write-Host "[PIPELINE] 無待處理 AI 任務" -ForegroundColor DarkGray
        return
    }

    Write-Host "[PIPELINE] $($pendingFiles.Count) 個任務等待 AI 處理，開啟 Claude..." -ForegroundColor Magenta

    # 寫入等待標記（含 ISO 時間戳，供 TTL 判斷），Claude 讀到後自動處理 pending 任務
    Atomic-WriteFile $script:PIPELINE_WAITING (Get-Date -Format 'o') | Out-Null

    # 優先用 Windows Terminal，否則開新 PowerShell 視窗
    if (Get-Command "wt" -ErrorAction SilentlyContinue) {
        Start-Process "wt" -ArgumentList @(
            "new-tab", "--startingDirectory", "`"$script:ROOT`"", "--", "claude"
        )
    } else {
        Start-Process "pwsh" -ArgumentList @(
            "-NoExit", "-Command", "Set-Location `"$script:ROOT`"; claude"
        ) -WindowStyle Normal
    }
}

# ============================================================
# 專案版本映射 & 目錄映射
# ============================================================
$script:ProjectVersionMap = $null
$script:ProjectDirMap     = $null

function Load-ProjectVersionMap {
    if ($null -ne $script:ProjectVersionMap) { return $script:ProjectVersionMap }
    $script:ProjectVersionMap = @{}
    $script:ProjectDirMap     = @{}
    if (Test-Path $script:PROJECT_VERSION_MAP_PATH) {
        try {
            $j = Get-Content $script:PROJECT_VERSION_MAP_PATH -Raw -Encoding UTF8 | ConvertFrom-Json
            $j.project_version_map.PSObject.Properties | ForEach-Object { $script:ProjectVersionMap[$_.Name] = $_.Value }
            if ($j.project_dir_map) {
                $j.project_dir_map.PSObject.Properties | ForEach-Object { $script:ProjectDirMap[$_.Name] = $_.Value }
            }
            Write-Host "[CONFIG] 載入 project_version_map.json，共 $($script:ProjectVersionMap.Count) 個專案，$($script:ProjectDirMap.Count) 個目錄對應" -ForegroundColor DarkCyan
        } catch {
            Write-Host "[WARN] 無法解析 project_version_map.json: $_" -ForegroundColor Yellow
        }
    }
    return $script:ProjectVersionMap
}

function Get-ProjectVersion {
    param([string]$projectName)
    $map = Load-ProjectVersionMap
    if ($map.ContainsKey($projectName)) { return $map[$projectName] }
    return $null
}

function Get-ProjectDir {
    param([string]$projectName)
    Load-ProjectVersionMap | Out-Null
    if ($script:ProjectDirMap -and $script:ProjectDirMap.ContainsKey($projectName)) {
        return $script:ProjectDirMap[$projectName]
    }
    return $null
}

# ============================================================
# WIKI 快取注入（供 PS1 在寫入 pending_prompt 前 prepend）
# ============================================================
function Get-WikiCache {
    param([string]$moduleName, [string]$odooVersion, [string]$projectName = $null)
    if (-not $moduleName) { return "" }

    $addonsRoot = Get-OnlineAddonsRoot -odooVersion $odooVersion -projectName $projectName -moduleName $moduleName

    $wikiPath = Join-Path $addonsRoot "graphify-out\wiki\index.md"
    if (-not (Test-Path $wikiPath)) { return "" }

    try {
        $lines   = Get-Content $wikiPath -Encoding UTF8
        $matched = @($lines | Where-Object { $_ -match [regex]::Escape($moduleName) })
        if ($matched.Count -eq 0) { return "" }
        $block = ($matched | Select-Object -First 200) -join "`n"
        return "[WIKI-CACHE]`n$block`n[/WIKI-CACHE]`n`n"
    } catch { return "" }
}

# ============================================================
# 現有模組快取
# ============================================================
$script:RepoModulesCache = $null

function Get-ExistingModules {
    if ($null -ne $script:RepoModulesCache) { return $script:RepoModulesCache }
    $all = @()
    if (Test-Path $script:ONLINE_ADDONS_DIR) {
        Get-ChildItem $script:ONLINE_ADDONS_DIR -Directory | ForEach-Object {
            $all += Get-ChildItem $_.FullName -Directory | Select-Object -ExpandProperty Name
        }
    }
    $script:RepoModulesCache = $all | Select-Object -Unique
    return $script:RepoModulesCache
}

# ============================================================
# Odoo 訊息發送
# ============================================================
function Send-OdooTaskMessage {
    param([int]$taskId, [string]$message)
    if (-not $env:ODOO_PASSWORD) { return }
    $disableFlag = Join-Path $script:PLAN_DIR "_ODOO_DISABLED"
    if (Test-Path $disableFlag) { Write-Host "[SKIP] Odoo 通知已停用" -ForegroundColor DarkGray; return }
    $py = Join-Path $script:CLAUDE_DIR "tools\send_message.py"
    if (-not (Test-Path $py)) { return }
    $r = python $py $script:ODOO_URL $script:ODOO_DB $script:ODOO_USERNAME $env:ODOO_PASSWORD $taskId $message 2>&1
    if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Odoo 訊息失敗: $r" -ForegroundColor Yellow }
}

# ============================================================
# 退回 confirm/ 機制（清除所有標記含 pending files）
# ============================================================
function BackToConfirm {
    param([string]$taskDir, [string]$reason, [string]$stage)

    $taskName       = Split-Path $taskDir -Leaf
    $confirmTaskDir = Join-Path $script:CONFIRM_DIR $taskName

    # 移動前先釋放 process.lock（Windows 持有 handle 時無法 Move-Item）
    $lockPath = Join-Path $taskDir "process.lock"
    if ($script:LockHandles.ContainsKey($lockPath)) { Release-Lock $lockPath }
    Remove-Item $lockPath -Force -ErrorAction SilentlyContinue

    if (Test-Path $confirmTaskDir) { Remove-Item $confirmTaskDir -Recurse -Force }
    try {
        Move-Item $taskDir $script:CONFIRM_DIR -Force
    } catch {
        Write-Host "[ERROR] BackToConfirm Move-Item 失敗: $_" -ForegroundColor Red
        return
    }

    # 清除所有 .done 標記與 pending 檔案
    @('.analysis_done', '.answer_done', '.final_done', '.implement_done', '.qa_done',
      '.pending_analysis', '.pending_final', '.pending_coding', '.pending_qa',
      'pending_prompt.txt', 'done_prompt.txt',
      'blocker.spec.txt', 'blocker.tech.txt', 'blocker.agent.txt', 'blocker.loop.txt',
      'agent_error.txt') | ForEach-Object {
        Remove-Item (Join-Path $confirmTaskDir $_) -Force -ErrorAction SilentlyContinue
    }

    # _REENTRY_COUNT 遞增（供 _pipeline_run.ps1 偵測重入次數上限）
    $reentryFile = Join-Path $confirmTaskDir '_REENTRY_COUNT'
    $count = 0
    if (Test-Path $reentryFile) {
        try { $count = [int](Get-Content $reentryFile -Raw -ErrorAction SilentlyContinue) } catch {}
    }
    Atomic-WriteFile $reentryFile ([string]($count + 1)) | Out-Null

    $content = "退回時間: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')`n退回階段: $stage`n退回原因: $reason`n`n請修正後重新填寫 analysis.yaml 中的 user_answer。"
    Atomic-WriteFile (Join-Path $confirmTaskDir 'BACK_REASON.txt') $content | Out-Null

    Write-Host "[BACK] $taskName 從 $stage 退回 confirm/  原因: $reason" -ForegroundColor Yellow

    # if ($taskName -match '^task_(\d+)$') {
    #     Send-OdooTaskMessage -taskId ([int]$matches[1]) -message "<p>【Pipeline】任務已從 <b>$stage</b> 退回。原因: $reason</p>"
    # }
}
