# Skill: test-writer-odoo

## Description
根據目標 Odoo 專案版本，自動生成對應框架的測試腳本。支援 Python 單元測試與各代 JS 測試框架。

## Guidelines
1. **環境判斷**: 執行前檢查 `odoo-bin` 版本或 `__manifest__.py`。
2. **Python 測試 (通用)**: 
   - 繼承 `odoo.tests.common.TransactionCase`。
   - 檔案路徑: `{module}/tests/test_{name}.py`。
3. **JavaScript 測試 (版本分支)**:
   - **Odoo 13-15 (Legacy)**: 使用 `QUnit` 框架與 `web.test_utils`。
   - **Odoo 16-17 (OWL)**: 使用 OWL Component 測試語法。
   - **Odoo 18-19 (Hoot)**: 必須使用最新的 `Hoot` 測試框架 (e.g., `describe`, `it`, `expect`)。
4. **輸出約束**: 
   - 需求模式：產出於 `/testcoding` 目錄下指定的專案路徑。
   - 程式碼必須包含 Setup 資料，確保可獨立運行。

## Usage Example
"針對 odoo-13.0 的會計標題需求，生成一個檢查 DOM 元素是否包含 '@@@@' 的 QUnit 測試。"
