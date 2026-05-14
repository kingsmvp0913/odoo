# confirm/

需求分析中、等待人工確認或補充資料的案件。

## 目錄結構

```
confirm/
└── task_<id>/
    ├── analysis.json      ← AI 產出的規格（MODE_A 或 MODE_B）
    ├── task_<id>.txt      ← 原始任務（從 start/ 搬來）
    ├── patches/           ← 預留
    ├── process.lock       ← 執行期間鎖
    ├── blocker.txt        ← 存在時代表案件從後段回滾（需人工處理）
    └── analysis.json.bak  ← 重新分析前的備份（存在時）
```

---

## 人工操作說明

### 情況一：`execution_mode == "MODE_A"`（AI 有待確認問題）

開啟 `analysis.json`，找到 `clarification_channel` 陣列，在對應問題的 `user_answer` 欄位填入具體答案：

```json
{
  "id": 1,
  "category": "business_logic",
  "question": "審核通過後是否需要發送 Email 通知？",
  "user_answer": "是，發送給負責人與主管，使用現有的 mail.template"
}
```

**填寫原則：**
- 答案必須具體可執行，不能只是「是」或「沒問題」
- AI 會驗證答案是否足以解析規格，若判定不足會維持 MODE_A 並顯示 `[INCOMPLETE]`
- 若對某個問題暫時無法回答，可跳過（保留 `null`），先回答其他問題

填完後執行：
```powershell
.\.claude\analysis.ps1
```

---

### 情況二：`[INCOMPLETE]`（AI 認為答案不夠具體）

`analysis.ps1` 輸出 `[INCOMPLETE]` 表示 AI 驗證了答案，但認為細節不足以完成規格。

處理步驟：
1. 重新開啟 `analysis.json`，找到仍為空或過於簡短的 `user_answer`
2. 補充更多技術細節（例如指明欄位名稱、具體邏輯條件、UI 位置）
3. 再次執行 `analysis.ps1`

---

### 情況三：Odoo 版本（通常自動填入）

`inferred_target.odoo_version` 必須有值，否則案件無法晉升 testcoding/。

`analysis.ps1` 會依據任務的 `---project---` 欄位查詢 `project_version_map.json` 自動注入版本號，**通常不需手動填寫**。若仍顯示 MODE_A 且問題涉及 `odoo_version`，請確認 `project_version_map.json` 已設定對應專案。

---

### 情況四：`execution_mode == "MODE_B"` 且 `is_complete == true`

`analysis.ps1` 會自動將案件移至 `testcoding/`，**無需手動操作**。

---

### 情況五：`blocker.txt` 存在（從 testcoding/ 或 coding/ 回滾）

當後段腳本發現無法繼續時，案件會帶著 `blocker.txt` 回滾至此目錄。

處理步驟：
1. 閱讀 `blocker.txt` 了解失敗原因
2. 依原因修正：
   - **測試跑 0 個**：`analysis.json` 的 `inferred_target.module` 可能不正確，或測試結構規格有誤 → 修正後於 `clarification_channel` 補充說明，重跑 `analysis.ps1`
   - **測試意外綠燈**：規格中描述的功能可能已存在，或 test-agent 生成了帶有實作的骨架 → 在 `user_answer` 補充說明後重跑
   - **規格矛盾**：閱讀 `blocker.txt` 具體描述，修正 `analysis.json` 中的 `technical_specification` 後重跑
3. 刪除 `blocker.txt`（或保留做記錄）
4. 執行 `analysis.ps1`

---

### 情況六：手動放棄案件

若案件確認不需要繼續：
```powershell
Remove-Item "C:\odoo\.claude\kingsmvpsplan\confirm\task_<id>" -Recurse -Force
```

---

## 自動行為備註

- `analysis.ps1` 在重新分析前會備份 `analysis.json` → `analysis.json.bak`；失敗時自動還原，**不需手動介入**
- `process.lock` 若殘留（前次執行異常中止），TTL 超期後下次執行自動清除
