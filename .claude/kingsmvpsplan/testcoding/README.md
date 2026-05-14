# testcoding/

需求規格已確認（MODE_B），等待生成測試骨架並驗證紅燈的案件。

## 執行流程（寫測試.ps1）

1. 讀取 `analysis.json`
2. 確認 `odoo_version` 已填寫，否則跳過
3. 環境檢查（Python / psycopg2 / pytest）
4. 呼叫 `test-agent`（Sonnet）生成測試骨架與 skeleton 實作檔
5. 寫入 `odoo-{version}/custom_addons/{module}/`
6. 執行測試，驗證**紅燈**（exit ≠ 0 且有 FAIL/ERROR/Traceback）
7. **紅燈確認** → 移至 `coding/`（附 `logs/error.log`）
8. **未達紅燈** → 寫入 `blocker.txt` → rollback 至 `confirm/`

## 紅燈有效條件

| 條件 | 說明 |
|------|------|
| exit code ≠ 0 | 測試執行失敗 |
| 輸出含 FAIL/ERROR/Traceback | 有具體錯誤訊息 |
| 含 "Ran N tests in" | 測試框架確實執行 |
| 不是 "Ran 0 tests" | 測試有被收集到 |
