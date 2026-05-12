---
name: tool-only-write
enabled: true
event: bash
action: block
conditions:
  - field: command
    operator: regex_match
    # 針對 cat 後接重新導向，以及任何 shell 寫入模式的強化匹配
    pattern: "(cat\\s+>)|(<<\\s*['\"]?\\w+)|(@['\"])|(Out-File)|(Set-Content)|(>\\s*['\"]?\\S+\\.(md|txt|py|xml|csv))"
---

**Hard Block: 偵測到禁止的 Shell 寫入行為**

你正在嘗試使用 `cat >` 或 `heredoc` 寫入檔案。這會觸發 948-byte 長度限制並導致權限詢問。

**請立即停止並改用以下步驟：**
1. 僅使用 `mkdir` 或 `New-Item` 建立目錄。
2. 使用內建的 **`Write`** 工具寫入內容。
3. 使用內建的 **`Edit`** 工具修改內容。
