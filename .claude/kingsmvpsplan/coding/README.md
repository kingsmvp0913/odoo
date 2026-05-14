# coding/

測試骨架已就位且紅燈確認，等待 AI 實作程式碼使測試通過的案件。

## 執行流程（coding.ps1）

1. 讀取 `analysis.json`，確認 `odoo_version` 已填寫，否則跳過
2. 呼叫 `Get-OdooConf` 讀取 `odoo.conf`，取得 `test_db_name`
3. 用 `slim_spec.py` 壓縮 `analysis.json`（降低 token 用量）
4. 讀取 `logs/error.log`（traceback），組合 Prompt
5. 呼叫 `senior-software-engineer`（Haiku）**單次執行**：
   - AI 輸出 `@FILE:/@FILE_END` 格式的實作程式碼
   - 寫入對應路徑（含路徑安全守衛）
   - 執行測試（含 `-c odoo.conf` 與 `test_db_name`）
   - **綠燈** → 移至 `final/`
   - **RED** → 更新 `logs/error.log`，顯示 `[RED]`，**等待人工重新執行 coding.ps1**

> **注意**：Windows 分支為單次執行模式，**不自動重試，不 rollback 至 confirm/**。

## 目錄結構

```
coding/
└── task_<id>/
    ├── analysis.json
    ├── logs/
    │   └── error.log      ← 最新一次測試失敗的 traceback（每次執行覆蓋）
    └── debug/
        ├── prompt_<ts>_attempt1.txt    ← 傳入 Agent 的完整 Prompt
        └── output_<ts>_attempt1.txt    ← Agent 原始輸出
```

## 安全守衛（雙重）

- **呼叫端**：路徑含 `..`、以 `/` 或磁碟代號 `[A-Za-z]:\` 開頭的檔案直接拒絕
- **Out-AtomicFile**：`GetFullPath` 解析後確認最終路徑仍在 `baseDir` 範圍內（防逃逸）
- `odoo_version` 或 `test_db_name` 為空時拒絕執行

---

## 人工操作說明

### 觸發實作

```powershell
cd C:\odoo
.\.claude\coding.ps1
```

**前置條件**：`logs/error.log` 已由 `test_coding.ps1` 建立（含紅燈 traceback）。

---

### 情況一：`[RED]` 測試仍未通過

腳本顯示 `[RED]` 後停止，`logs/error.log` 已更新為最新 traceback。

**標準處理流程：**
1. 閱讀 `logs/error.log` 了解當前錯誤
2. 若錯誤明確（如缺少欄位、import 錯誤）→ 直接重跑：
   ```powershell
   .\.claude\coding.ps1
   ```
3. 每次重跑，AI 會讀取最新 `error.log` 並嘗試修正

---

### 情況二：多次重跑仍 RED，懷疑規格問題

查看 `debug/` 目錄中最新的 prompt 與 output：
```
debug/prompt_<最新時間戳>_attempt1.txt   ← AI 收到的完整規格與 traceback
debug/output_<最新時間戳>_attempt1.txt   ← AI 輸出的程式碼
```

判斷方向：
- **AI 輸出空白或格式錯誤**（`[EMPTY OUTPUT]`）→ 可能 Claude API 超時，直接重跑
- **AI 持續生成相同錯誤的程式碼** → 規格可能有矛盾，考慮升級至 confirm/
- **測試本身有邏輯問題** → 需手動修正測試檔後重跑

---

### 情況三：手動升級回 confirm/ 修正規格

若 AI 無法解決（規格矛盾、需求不清晰），手動將案件移回 confirm/：

```powershell
$caseDir = "C:\odoo\.claude\kingsmvpsplan\coding\task_<id>"
$dest    = "C:\odoo\.claude\kingsmvpsplan\confirm\task_<id>"
Move-Item $caseDir $dest -Force
```

移回後：
1. 在 `confirm/task_<id>/analysis.json` 的 `clarification_channel` 補充說明
2. 若有 `blocker.txt`，閱讀後再填答
3. 執行 `analysis.ps1` 重新分析

---

### 情況四：`blocker.txt` 出現在 coding/

`senior-software-engineer` 判定規格無法實作時會寫入 `blocker.txt`（位於案件目錄根層）。

```powershell
Get-Content "C:\odoo\.claude\kingsmvpsplan\coding\task_<id>\blocker.txt"
```

處理同情況三：移回 confirm/ 並修正規格。

---

### 情況五：手動修改 AI 生成的程式碼

若需手動調整程式碼：
- 直接編輯 `odoo-{ver}/custom_addons/{module}/` 下的對應檔案
- 手動執行測試確認：
  ```powershell
  cd C:\odoo
  python odoo-{ver}/odoo-bin -c odoo-{ver}/odoo.conf -i {module} --test-tags=/{module} --stop-after-init -d {test_db_name}
  ```
- 若測試通過，手動將案件目錄移至 `final/`：
  ```powershell
  Move-Item "C:\odoo\.claude\kingsmvpsplan\coding\task_<id>" "C:\odoo\.claude\kingsmvpsplan\final\" -Force
  ```
