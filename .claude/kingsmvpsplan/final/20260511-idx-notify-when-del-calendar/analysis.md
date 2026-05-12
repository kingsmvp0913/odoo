目標專案: odoo-14.0
來源檔案: a1.txt
分析時間: 2026-05-11 14:30
狀態: ✅ 需求確認完畢，可進入開發

---

# 一、待確認項目

> 以下問題必須由需求方回答後，開發才能繼續推進。

## ❓ 待釐清問題

（所有問題已確認，無待釐清項目）

---

# 二、開發分析書

> 以下內容已依所有已確認答案更新。

## 📋 需求摘要

在 Odoo 14 calendar 模組的基礎上，新建自訂模組 `idx_notify_when_del_calendar`。
功能：當 `calendar.event` 記錄被刪除，且該事件不屬於請假申請（`res_model != 'hr.leave'`）時，系統自動以電子郵件通知所有 `state != 'declined'` 的與會人員，告知會議已取消。

已確認條件：
- 通知對象：`attendee_ids` 中 `state != 'declined'` 的人員
- 觸發時機：有任何刪除動作（含循環會議子事件）均通知
- 發件人：執行刪除操作的當前使用者（`env.user`）
- ICS 附件：附帶 `METHOD:CANCEL` 的 ICS 取消附件
- 多語言：依 `object.partner_id.lang` 渲染
- 失敗容錯：無有效 email 者靜默略過，寫入 log 警告

---

## 🔍 需求解析

### 功能一：新增「會議取消」郵件樣板

身份: As a 系統管理員
目標: I want to 在 mail.template 中建立一個「會議取消」樣板，掛載於 calendar.attendee Model
價值: So that 取消通知郵件有統一格式，未來可由管理員自行修改信件內容

驗收條件:
- Given 系統已安裝 idx_notify_when_del_calendar，When 進入「設定 > 技術 > 電子郵件 > 郵件樣板」，Then 可看到名稱為「Calendar: Meeting Cancelled」的樣板，掛載於 calendar.attendee
- Given 樣板存在，When 觸發發送，Then 信件主旨為「${object.event_id.name}: Cancelled」，內文列出：會議名稱、原訂時間、地點（若有）、與會人員清單
- Given 與會人員 partner 設定了 lang，When 發送，Then 信件以該 partner 的語言渲染（lang 欄位為空時 fallback 至系統預設語言）
- Given 樣板的 email_from，When 發送，Then 使用執行刪除操作的使用者 email（`user.email_formatted`），而非會議建立者

### 功能二：刪除 calendar.event 時觸發取消通知

身份: As a 會議建立者或有權限的使用者
目標: I want to 刪除 calendar.event 記錄時，系統自動寄出取消通知給所有有效與會人員
價值: So that 與會人員不會因為不知道會議取消而白跑

驗收條件:
- Given 一筆 `res_model != 'hr.leave'` 的 calendar.event 有 3 位 partner，其中 1 位 state='declined'，When 該事件被 unlink()，Then 2 位非拒絕的 partner 各收到一封取消通知郵件，已拒絕者不收到
- Given 一筆 `res_model == 'hr.leave'` 的 calendar.event，When 被 unlink()，Then 不發送任何取消通知郵件
- Given 循環會議（recurrence）的其中一筆子事件被刪除，When unlink()，Then 該子事件的有效 attendee 均收到取消通知
- Given calendar.event 的所有有效 attendee 均無有效 email，When unlink()，Then 系統靜默跳過（不拋例外），並於 log 記錄警告
- Given unlink() 在事務中途失敗（super().unlink() 拋出例外），When 例外被拋出，Then 取消通知不發送（通知必須在 super().unlink() 成功後才執行）
- Given calendar.event 有效 attendee 中部分無 email，When unlink()，Then 有 email 的 partner 收到通知，無 email 的靜默略過並記 log

### 功能三：生成 METHOD:CANCEL ICS 附件

身份: As a 與會人員
目標: I want to 收到帶有 ICS 取消附件的通知郵件
價值: So that 日曆軟體能自動識別並從行事曆中移除該會議

驗收條件:
- Given 取消通知郵件發送，When 收件人開啟附件，Then 附件為有效的 .ics 檔，其中包含 `METHOD:CANCEL`、`STATUS:CANCELLED`，且 `UID` 與原事件一致
- Given vobject 套件未安裝，When unlink()，Then 系統記錄警告並繼續發送不含 ICS 附件的純 HTML 郵件（降級處理，不中斷通知流程）

---

## 📊 優先級建議

| 功能 | 優先級 | 理由 |
|------|--------|------|
| 新增「會議取消」mail.template | Must Have | 無樣板則無法發信，是整個功能的前提 |
| unlink() override + 過濾 hr.leave | Must Have | 核心業務邏輯，直接對應需求 |
| state != 'declined' 過濾 | Must Have | 需求方確認，排除已拒絕的與會人員 |
| 發件人改用 env.user | Must Have | 需求方確認，使用刪除操作的當前使用者 |
| ICS METHOD:CANCEL 附件 | Must Have | 需求方確認附帶；需自訂生成邏輯（現有 _get_ics_file 不支援 CANCEL） |
| 多語言渲染支援 | Must Have | 需求方確認，依 partner.lang 渲染 |
| 失敗靜默略過 + log | Must Have | 需求方確認，不中斷主流程 |

---

## 🔗 相依性

- 核心模組 `calendar`（Odoo 14 標準）：繼承 `calendar.event.unlink()`
- `calendar.attendee._notify_attendees`：參考發信結構，但因發件人（email_from 寫死為 event.user_id）不符需求，需在自訂模組另行實作取消通知方法
- `calendar.event._get_ics_file()`：現有實作不支援 `METHOD:CANCEL`，需新增 `_get_cancel_ics_file()` 方法，手動設定 `cal.method = 'CANCEL'` 及 `event.status = 'CANCELLED'`
- Python 套件 `vobject`：ICS 生成依賴此套件；若未安裝需降級處理（只發 HTML 郵件）
- `hr_holidays`：不直接相依，過濾條件以字串比對（`res_model != 'hr.leave'`），hr_holidays 未安裝時不報錯

### 重要技術約束（unlink 前必須快取資料）

`super().unlink()` 執行後，`attendee_ids` 關聯及 `res_model`、`name`、`start`、`stop`、`location` 等欄位均已消失，無法再讀取。
因此取消通知所需的所有資料必須在 `super().unlink()` 呼叫**之前**完整快取至 Python 字典，通知在 `super().unlink()` 成功回傳後才使用快取資料發送。

---

## 📁 相關專案資料夾

- `odoo-14.0/addons/calendar/models/calendar_event.py` — 參考現有 `unlink()`（L854-873），繼承覆寫插入點；關鍵：unlink 前需先快取 attendee 及 event 資料
- `odoo-14.0/addons/calendar/models/calendar_attendee.py` — 參考 `_send_mail_to_attendees`（L82-111）、`_notify_attendees`（L113-147）、`_prepare_notification_attachment_values`（L157-162）發信結構
- `odoo-14.0/addons/calendar/models/calendar_event.py` — 參考 `_get_ics_file()`（L422-480），作為自訂 `_get_cancel_ics_file()` 的基準，加入 `METHOD:CANCEL` 及 `STATUS:CANCELLED`
- `odoo-14.0/addons/calendar/data/mail_data.xml` — 參考現有樣板結構（invitation / changedate），作為新「取消」樣板的格式基準；email_from 改為 `${user.email_formatted}`
- `odoo-14.0/custom_addons/idx_notify_when_del_calendar/` — 【新建】本次需求的實作模組
