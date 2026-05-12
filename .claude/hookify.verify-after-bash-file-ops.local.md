---
name: verify-after-bash-file-ops
enabled: true
event: bash
action: warn
conditions:
  - field: command
    operator: regex_match
    pattern: \bmv\b|\bcp\b|\bmkdir\b|\btouch\b|\bNew-Item\b|\bMove-Item\b|\bCopy-Item\b|\bRename-Item\b
---

**[強制驗證] 檔案系統操作後必須確認結果**

After any file operation, verify in the same response:
```powershell
Test-Path "目標路徑"
Get-Item "目標路徑" | Select-Object FullName, LastWriteTime, Length
```
Do not assume success from zero-error exit. Report and fix if verification fails.
