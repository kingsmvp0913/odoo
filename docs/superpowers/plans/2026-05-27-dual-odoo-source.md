# 雙 Odoo 來源支援 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支援兩個獨立 Odoo 實例抓取任務，目錄以前綴區分（`task_odoo_N` / `task_service_N`），現有 `task_N` 目錄保留不動。

**Architecture:** 在 `curl.py` 新增 `prefix` 參數讓呼叫端決定目錄前綴；`analysis.ps1` STEP 1 連續呼叫兩次 `curl.py`（各自維護獨立 skip list）；`Send-OdooTaskMessage` 改為接受 dir name 並對 service 來源 early return；pipeline regex 更新以識別新格式目錄。

**Tech Stack:** Python 3, PowerShell 7, Odoo JSON-RPC

---

## 檔案改動地圖

| 檔案 | 類型 | 改動說明 |
|------|------|---------|
| `C:\odoo\.claude\tools\curl.py` | Modify | 新增 `prefix` 位置參數（argv[7]），SKIP_IDS 移至 argv[8]；目錄名 `f"{prefix}{task_id}"` |
| `C:\odoo\.claude\tools\curl_service.py` | **Create** | 新建：專門處理 `service.question.feedback` 模型；domain `processing_staff in [USER_ID]` + `state in ['draft','open']`；欄位：`name_seq`、`subject`、`question_description`、`system`、`state`、`classification` |
| `C:\odoo\.claude\scripts\_common.ps1` | Modify | L24-28：新增 service 來源常數；L435-444：`Send-OdooTaskMessage` 改簽名、加路由 |
| `C:\odoo\.claude\scripts\analysis.ps1` | Modify | STEP 1（L20-45）：來源1呼叫 `curl.py`，來源2呼叫 `curl_service.py`；各自獨立 skip list |
| `C:\odoo\.claude\scripts\_pipeline_run.ps1` | Modify | L31 + L251：regex `^task_\d+$` → `^task_(odoo_\|service_)?\d+$` |
| `C:\odoo\.claude\scripts\qa.ps1` | Modify | L136-138：更新註解內的 `Send-OdooTaskMessage` 呼叫格式（不啟用，只修正格式） |

---

## Task 1：更新 `curl.py` 新增 prefix 參數

**Files:**
- Modify: `C:\odoo\.claude\tools\curl.py:29-40`

- [ ] **Step 1：確認現有參數解析**

  讀 `curl.py` L29-40，確認目前 argv 順序為：
  ```
  argv[1]=URL  argv[2]=DB  argv[3]=USER  argv[4]=PWD  argv[5]=USER_ID  argv[6]=START_DIR  argv[7]=SKIP_IDS(optional)
  ```

- [ ] **Step 2：修改 `main()` 的參數解析與目錄建立邏輯**

  將 `curl.py` L29-40 和 L99 改為：

  ```python
  def main():
      if len(sys.argv) < 8:
          print("[ERROR] 參數不足。用法: python curl.py <URL> <DB> <USER> <PWD> <USER_ID> <START_DIR> <PREFIX> [SKIP_IDS]")
          sys.exit(1)

      ODOO_URL  = sys.argv[1]
      DB_NAME   = sys.argv[2]
      USERNAME  = sys.argv[3]
      PASSWORD  = sys.argv[4]
      USER_ID   = int(sys.argv[5])
      START_DIR = sys.argv[6]
      PREFIX    = sys.argv[7]
      SKIP_IDS  = set(sys.argv[8].split(",")) if len(sys.argv) > 8 and sys.argv[8] else set()
  ```

  並將 L99 的目錄建立行改為：

  ```python
  task_dir = start_path / f"{PREFIX}{task_id}"
  ```

- [ ] **Step 3：語法驗證**

  執行：
  ```
  python -m py_compile C:\odoo\.claude\tools\curl.py
  ```
  預期：無輸出（無錯誤）

- [ ] **Step 4：快速功能驗證**

  執行（預期因參數不足而印出 error 訊息並 exit 1）：
  ```
  python C:\odoo\.claude\tools\curl.py
  ```
  預期輸出：`[ERROR] 參數不足。用法: python curl.py ...`

- [ ] **Step 5：Commit**

  ```
  git add .claude/tools/curl.py
  git commit -m "[curl.py]: add prefix parameter for dual-source directory naming"
  ```

---

## Task 2：更新 `_common.ps1` — service 常數與 `Send-OdooTaskMessage`

**Files:**
- Modify: `C:\odoo\.claude\scripts\_common.ps1:24-28` (Odoo 常數區)
- Modify: `C:\odoo\.claude\scripts\_common.ps1:435-444` (Send-OdooTaskMessage)

- [ ] **Step 1：在 Odoo 連線常數區新增 service 來源常數（L28 之後）**

  在 `_common.ps1` 的 `# Odoo 連線常數` 區塊（L23-L27）結尾新增：

  ```powershell
  # 來源 2（service）— URL/DB/USERNAME 寫死，密碼從 env var 讀
  $script:ODOO_SERVICE_URL      = "https://service.example.com"   # TODO: 填入實際 service URL
  $script:ODOO_SERVICE_DB       = "service_db"                     # TODO: 填入實際 DB name
  $script:ODOO_SERVICE_USERNAME = "service@example.com"            # TODO: 填入實際帳號
  $script:ODOO_SERVICE_USER_ID  = if ($env:ODOO_SERVICE_USER_ID) { [int]$env:ODOO_SERVICE_USER_ID } else { 1 }
  ```

  注意：`ODOO_SERVICE_PASSWORD` 不宣告為 script 變數，直接在呼叫時用 `$env:ODOO_SERVICE_PASSWORD`。

- [ ] **Step 2：重寫 `Send-OdooTaskMessage`（L435-444）**

  將整個函式替換為：

  ```powershell
  function Send-OdooTaskMessage {
      param([string]$taskDirName, [string]$message)

      # service 來源尚未啟用通知，直接略過
      if ($taskDirName -match '_service_') { return }

      if (-not $env:ODOO_PASSWORD) { return }
      $disableFlag = Join-Path $script:PLAN_DIR "_ODOO_DISABLED"
      if (Test-Path $disableFlag) { Write-Host "[SKIP] Odoo 通知已停用" -ForegroundColor DarkGray; return }
      $py = Join-Path $script:CLAUDE_DIR "tools\send_message.py"
      if (-not (Test-Path $py)) { return }

      # 支援 task_123、task_odoo_123 兩種格式
      if ($taskDirName -match '^task_(?:odoo_)?(\d+)$') {
          $tid = [int]$matches[1]
      } else {
          Write-Host "[WARN] Send-OdooTaskMessage: 無法解析 task ID from '$taskDirName'" -ForegroundColor Yellow
          return
      }

      $r = python $py $script:ODOO_URL $script:ODOO_DB $script:ODOO_USERNAME $env:ODOO_PASSWORD $tid $message 2>&1
      if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Odoo 訊息失敗: $r" -ForegroundColor Yellow }
  }
  ```

- [ ] **Step 3：語法驗證**

  在 PowerShell 執行：
  ```powershell
  $null = [System.Management.Automation.Language.Parser]::ParseFile(
      "C:\odoo\.claude\scripts\_common.ps1", [ref]$null, [ref]$null)
  Write-Host "Parse OK"
  ```
  預期：`Parse OK`

- [ ] **Step 4：Commit**

  ```
  git add .claude/scripts/_common.ps1
  git commit -m "[_common.ps1]: add service source constants and update Send-OdooTaskMessage routing"
  ```

---

## Task 3：更新 `analysis.ps1` STEP 1 — 雙來源同步

**Files:**
- Modify: `C:\odoo\.claude\scripts\analysis.ps1:20-45`

- [ ] **Step 1：讀取現有 STEP 1 程式碼確認邊界**

  重讀 `analysis.ps1` L20-45，確認：
  - skip list 建立邏輯（L26-35）
  - curl.py 呼叫行（L38-39）

- [ ] **Step 2：替換整個 STEP 1 區塊（L20-45）**

  用以下內容替換原本的 `# STEP 1` 區塊：

  ```powershell
  # ============================================================
  # STEP 1: 同步 Odoo 任務 → start/task_N/original.txt
  # ============================================================
  Write-Host "[STEP 1] 同步 Odoo 任務..." -ForegroundColor Cyan

  $odooDisableFlag = Join-Path $script:PLAN_DIR "_ODOO_DISABLED"
  if (Test-Path $odooDisableFlag) {
      Write-Host "[SKIP] Odoo 同步已停用（刪除 _ODOO_DISABLED 可重新啟用）" -ForegroundColor DarkGray
  } else {
      $allDirs = @($script:START_DIR, $script:CONFIRM_DIR, $script:ANALYSIS_DIR, $script:CODING_DIR, $script:FINAL_DIR)

      # 建立來源 1（odoo）skip list：同時識別 task_N（舊）和 task_odoo_N（新）
      $odooSkipIds = @()
      foreach ($dir in $allDirs) {
          if (Test-Path $dir) {
              Get-ChildItem $dir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                  if ($_.Name -match '^task_(?:odoo_)?(\d+)$') { $odooSkipIds += $matches[1] }
              }
          }
      }
      $odooSkipStr = ($odooSkipIds | Select-Object -Unique) -join ","

      # 建立來源 2（service）skip list
      $serviceSkipIds = @()
      foreach ($dir in $allDirs) {
          if (Test-Path $dir) {
              Get-ChildItem $dir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
                  if ($_.Name -match '^task_service_(\d+)$') { $serviceSkipIds += $matches[1] }
              }
          }
      }
      $serviceSkipStr = ($serviceSkipIds | Select-Object -Unique) -join ","

      $pyScript1 = Join-Path $script:CLAUDE_DIR "tools\curl.py"
      $pyScript2 = Join-Path $script:CLAUDE_DIR "tools\curl_service.py"

      # 來源 1：odoo（ideaxpress，project.task）
      try {
          $out = python $pyScript1 $script:ODOO_URL $script:ODOO_DB $script:ODOO_USERNAME $env:ODOO_PASSWORD $script:ODOO_USER_ID $script:START_DIR "task_odoo_" $odooSkipStr 2>&1
          $out | ForEach-Object { Write-Host $_ }
          if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Odoo 來源 1 同步失敗，exit: $LASTEXITCODE" -ForegroundColor Yellow }
      } catch {
          Write-Host "[WARN] Odoo 來源 1 同步例外: $_" -ForegroundColor Yellow
      }

      # 來源 2：service（service.question.feedback，若未設定密碼則略過）
      if ($env:ODOO_SERVICE_PASSWORD) {
          try {
              $out = python $pyScript2 $script:ODOO_SERVICE_URL $script:ODOO_SERVICE_DB $script:ODOO_SERVICE_USERNAME $env:ODOO_SERVICE_PASSWORD $script:ODOO_SERVICE_USER_ID $script:START_DIR "task_service_" $serviceSkipStr 2>&1
              $out | ForEach-Object { Write-Host $_ }
              if ($LASTEXITCODE -ne 0) { Write-Host "[WARN] Odoo 來源 2 同步失敗，exit: $LASTEXITCODE" -ForegroundColor Yellow }
          } catch {
              Write-Host "[WARN] Odoo 來源 2 同步例外: $_" -ForegroundColor Yellow
          }
      } else {
          Write-Host "[SKIP] ODOO_SERVICE_PASSWORD 未設定，略過來源 2 同步" -ForegroundColor DarkGray
      }
  }
  ```

- [ ] **Step 3：語法驗證**

  ```powershell
  $null = [System.Management.Automation.Language.Parser]::ParseFile(
      "C:\odoo\.claude\scripts\analysis.ps1", [ref]$null, [ref]$null)
  Write-Host "Parse OK"
  ```
  預期：`Parse OK`

- [ ] **Step 4：停用 Odoo 的情況下快跑驗證（不真正呼叫 Odoo）**

  ```powershell
  # 建立停用旗標
  $null | Out-File "C:\odoo\.claude\kingsmvpsplan\_ODOO_DISABLED"
  # 執行 analysis.ps1（只跑 STEP 1 部分不影響後續）—— 確認 [SKIP] 輸出
  # 驗證完後刪除旗標
  Remove-Item "C:\odoo\.claude\kingsmvpsplan\_ODOO_DISABLED" -Force
  ```
  預期輸出含：`[SKIP] Odoo 同步已停用`

- [ ] **Step 5：Commit**

  ```
  git add .claude/scripts/analysis.ps1
  git commit -m "[analysis.ps1]: dual-source sync with separate skip lists and prefixes"
  ```

---

## Task 4：更新 `_pipeline_run.ps1` task ID regex

**Files:**
- Modify: `C:\odoo\.claude\scripts\_pipeline_run.ps1:31`
- Modify: `C:\odoo\.claude\scripts\_pipeline_run.ps1:251`

- [ ] **Step 1：更新 L31 的 reentry count regex**

  將：
  ```powershell
  if ($tid -match '^task_\d+$') {
  ```
  改為：
  ```powershell
  if ($tid -match '^task_(odoo_|service_)?\d+$') {
  ```

- [ ] **Step 2：更新 L251 的 pipeline summary regex**

  將：
  ```powershell
  Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^task_\d+$' } | ForEach-Object {
  ```
  改為：
  ```powershell
  Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^task_(odoo_|service_)?\d+$' } | ForEach-Object {
  ```

- [ ] **Step 3：語法驗證**

  ```powershell
  $null = [System.Management.Automation.Language.Parser]::ParseFile(
      "C:\odoo\.claude\scripts\_pipeline_run.ps1", [ref]$null, [ref]$null)
  Write-Host "Parse OK"
  ```
  預期：`Parse OK`

- [ ] **Step 4：確認 regex 正確性**

  在 PowerShell 執行下列驗證：
  ```powershell
  $pattern = '^task_(odoo_|service_)?\d+$'
  @("task_123", "task_odoo_456", "task_service_789", "task_abc", "task_") | ForEach-Object {
      "$_ → $($_ -match $pattern)"
  }
  ```
  預期輸出：
  ```
  task_123 → True
  task_odoo_456 → True
  task_service_789 → True
  task_abc → False
  task_ → False
  ```

- [ ] **Step 5：Commit**

  ```
  git add .claude/scripts/_pipeline_run.ps1
  git commit -m "[_pipeline_run.ps1]: extend task ID regex to support odoo_ and service_ prefixes"
  ```

---

## Task 5：更新 `qa.ps1` 中的註解呼叫格式

**Files:**
- Modify: `C:\odoo\.claude\scripts\qa.ps1:136-138`

- [ ] **Step 1：更新 L136-138 的已註解呼叫**

  將：
  ```powershell
  # if ($taskName -match '^task_(\d+)$') {
  #     Send-OdooTaskMessage -taskId ([int]$matches[1]) -message "<p>【Pipeline】任務已完成，請查看 final/$taskName/</p>"
  # }
  ```
  改為：
  ```powershell
  # if ($taskName -match '^task_(odoo_|service_)?\d+$') {
  #     Send-OdooTaskMessage -taskDirName $taskName -message "<p>【Pipeline】任務已完成，請查看 final/$taskName/</p>"
  # }
  ```

- [ ] **Step 2：語法驗證**

  ```powershell
  $null = [System.Management.Automation.Language.Parser]::ParseFile(
      "C:\odoo\.claude\scripts\qa.ps1", [ref]$null, [ref]$null)
  Write-Host "Parse OK"
  ```
  預期：`Parse OK`

- [ ] **Step 3：Commit**

  ```
  git add .claude/scripts/qa.ps1
  git commit -m "[qa.ps1]: update commented Send-OdooTaskMessage call to new signature"
  ```

---

## Task 6：更新 spec 文件狀態

**Files:**
- Modify: `docs/superpowers/specs/2026-05-26-dual-odoo-source-design.md`

- [ ] **Step 1：將 spec 文件狀態從「進行中」改為「已實作」**

  將 spec 文件 L3 從：
  ```
  **狀態**：進行中，待明日繼續確認後實作
  ```
  改為：
  ```
  **狀態**：已實作（2026-05-27）
  ```

  並在「待確認事項」區塊填入確認結果：
  ```markdown
  ## 確認結果（2026-05-27）

  - [x] 來源 1 URL/DB/USERNAME 保持寫死，只有密碼用 env var（現狀不變）
  - [x] `send_message.py` 路由：service 來源 early return（目前不發通知）；odoo 來源支援 task_N 和 task_odoo_N 兩種格式
  - [x] Task ID regex 更新為 `^task_(odoo_|service_)?\d+$`
  ```

- [ ] **Step 2：Commit**

  ```
  git add docs/superpowers/specs/2026-05-26-dual-odoo-source-design.md
  git commit -m "[docs]: mark dual-odoo-source spec as implemented"
  ```

---

## 注意事項

1. **現有 `task_N` 目錄**：保留不動，pipeline regex 已支援（`(odoo_|service_)?` 是 optional）
2. **Service 來源啟用條件**：只要設定 `ODOO_SERVICE_PASSWORD` 環境變數即可啟用，其他常數在 `_common.ps1` 填好後即生效
3. **Service 常數 TODO**：`_common.ps1` 中三個 TODO 值（URL/DB/USERNAME）需要使用者填入實際的 service Odoo 資訊後才能真正同步
