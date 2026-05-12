---
name: verify-before-stop
enabled: true
event: stop
action: warn
conditions:
  - field: transcript
    operator: regex_match
    pattern: name":\s*"Write|name":\s*"Edit|name":\s*"MultiEdit
---

**[強制驗證] 本次 session 有檔案操作，停止前必須確認實際完成**

在宣告任何任務完成或停止之前，你必須逐一驗證本次 session 中所有宣稱的檔案操作：

**檢查清單（每項必須有實際指令輸出作為證據）**：

- [ ] 新建的檔案 → 用 `Glob` 或 `Test-Path` 確認存在
- [ ] 修改的檔案 → 用 `(Get-Item path).LastWriteTime` 或 `stat` 確認時間戳為當前操作
- [ ] 移動的檔案 → 確認新路徑存在、舊路徑不存在
- [ ] Agent 子任務的輸出 → 不得只相信子 Agent 的口頭報告，必須直接讀取或確認檔案

**嚴禁**：
- 報告「已建立 X 檔案」而未實際驗證
- 轉述子 Agent 的結果而不自行確認
- 憑工具呼叫無錯誤就假設操作成功

若任何驗證失敗，必須修復後重新驗證，再行停止。
