# testcoding/

需求規格已確認（MODE_B），等待生成測試骨架並驗證紅燈的案件。

## 執行流程（test_coding.ps1）

1. 讀取 `analysis.json`
2. 確認 `odoo_version` 已填寫，否則跳過
3. 呼叫 `Get-OdooConf` 讀取 `odoo.conf`，確認 `test_db_name` 存在，否則跳過
4. 環境檢查（Python / psycopg2 / 資料庫連線）
5. 呼叫 `test-agent`（Sonnet）生成測試骨架與 skeleton 實作檔
6. 寫入 `odoo-{version}/custom_addons/{module}/`
7. 執行測試，驗證**紅燈**（exit ≠ 0 且有 FAIL/ERROR/Traceback）
8. **紅燈確認** → 移至 `coding/`（附 `logs/error.log`）
9. **未達紅燈** → 寫入 `blocker.txt` → rollback 至 `confirm/`

## 紅燈有效條件

| 條件 | 說明 |
|------|------|
| exit code ≠ 0 | 測試執行失敗 |
| 輸出含 FAIL/ERROR/Traceback | 有具體錯誤訊息 |
| 含 "Ran N tests in" | 測試框架確實執行 |
| 不是 "Ran 0 tests" | 測試有被收集到 |

---

## 人工操作說明

### 觸發測試生成

```powershell
cd C:\odoo
.\.claude\test_coding.ps1
```

**前置條件（自動檢查，失敗時人工修復）：**
- `odoo-{ver}/odoo.conf` 存在且含 `test_db_name`
- Python 可執行
- psycopg2 可用
- 可連線至 `test_db_name` 指定的資料庫

---

### 情況一：`[ENV ERROR]` 環境檢查失敗

腳本輸出 `[ENV ERROR]` 時，案件會停留在 `testcoding/`（不移動）。

常見原因與處理：

| 錯誤訊息 | 處理方式 |
|---------|---------|
| `找不到 odoo.conf` | 確認 `odoo-{ver}/odoo.conf` 路徑存在 |
| `odoo.conf 缺少 test_db_name` | 在 `odoo.conf` 末尾加上 `test_db_name = odoo_test` |
| `無法連線到資料庫` | 確認 PostgreSQL 已啟動，且 `test_db_name` 的資料庫已建立 |

修復後直接重跑 `test_coding.ps1`，**無需移動任何目錄**。

---

### 情況二：`[BLOCKER]` — 未達紅燈，案件回滾至 confirm/

案件移回 `confirm/`，含 `blocker.txt`。常見原因：

| blocker 訊息 | 可能原因 | 處理方式 |
|------------|---------|---------|
| `Ran 0 tests` | 測試 class 未繼承 `TransactionCase`，或 `--test-tags` 模組名稱與 manifest 不符 | 開啟 `analysis.json`，在 `clarification_channel` 補充正確模組名稱後重跑 `analysis.ps1` |
| `測試意外通過（綠燈）` | skeleton 帶有實作邏輯，或功能已存在 | 確認需求是否已實作；若 AI 生成有誤，補充說明後重跑 |
| `未偵測到 Ran X tests` | pytest / odoo-bin 未正確啟動 | 確認 Python 環境與 odoo-bin 路徑正確 |

---

### 情況三：`[FILE]` 正常但手動確認骨架

若需確認 AI 生成的測試是否正確，查看：
```
odoo-{ver}/custom_addons/{module}/tests/test_main.py
odoo-{ver}/custom_addons/{module}/models/models.py   ← 應為純骨架，無實作邏輯
```

若骨架有問題，**刪除 testcoding/ 下的案件目錄**後重新執行，test-agent 會重新生成：
```powershell
Remove-Item "C:\odoo\.claude\kingsmvpsplan\testcoding\task_<id>" -Recurse -Force
# 再執行 analysis.ps1 → 案件需先回 confirm/ 後才能再推進
```
