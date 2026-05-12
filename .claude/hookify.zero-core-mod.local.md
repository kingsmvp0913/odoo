---
name: zero-core-mod
enabled: true
event: file
action: block
conditions:
  - field: file_path
    operator: regex_match
    pattern: "[/\\\\]odoo-\\d+\\.\\d+[/\\\\]"
---

**Hard Blocker: 禁止修改 Odoo Core 檔案**

目標路徑屬於 Odoo core 目錄（`odoo-13.0`、`odoo-14.0`、`odoo-18.0` 等）。

**CLAUDE.md §4 - Zero Core Mod：**
- 自定義模組一律放在專案目錄下的 `custom_addons/` 下
- 功能擴充使用 `_inherit`（Model）、`inherit_id + xpath`（View）、`super()`（Controller）
- 若無法透過標準繼承達成需求，立即回報為 Hard Blocker 並等待用戶指示
