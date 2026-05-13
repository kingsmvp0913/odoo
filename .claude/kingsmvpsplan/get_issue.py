import os
import requests
from bs4 import BeautifulSoup

# === 1. 設定您的 Odoo 連線資訊 ===
ODOO_URL = "https://odoo.ideaxpress.biz"  # 您的 Odoo 網址
DB_NAME = "odoo"            # 資料庫名稱
USERNAME = "steven.lin@ideaxpress.biz"                 # 登入帳號
PASSWORD = "Ji3cl3gj94!"                 # 密碼或 Token
USER_ID = 79                       # 您的 Odoo 使用者 ID

TARGET_DIR = "start"                       # 目標輸出目錄

# === 2. 輔助函式 ===
def remove_images_only(html_str):
    """僅移除 HTML 中的圖片標籤，保留其餘 HTML 語法"""
    if not html_str or not isinstance(html_str, str):
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for img in soup.find_all("img"):
        img.decompose()
    return str(soup)


def clean_message_body(html_str):
    """處理 Message（移除圖片並轉為純文字）"""
    if not html_str or not isinstance(html_str, str):
        return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for img in soup.find_all("img"):
        img.decompose()
    return soup.get_text(separator="\n", strip=True)


# === 3. 建立連線並登入 Odoo ===
session = requests.Session()
auth_url = f"{ODOO_URL}/web/session/authenticate"
auth_payload = {
    "jsonrpc": "2.0",
    "params": {"db": DB_NAME, "login": USERNAME, "password": PASSWORD},
}

auth_response = session.post(auth_url, json=auth_payload)
if "error" in auth_response.json():
    print("登入失敗：", auth_response.json()["error"])
    exit()

if not os.path.exists(TARGET_DIR):
    os.makedirs(TARGET_DIR)

# === 4. 發送 JSON-RPC 抓取 project.task ===
call_url = f"{ODOO_URL}/web/dataset/call_kw"
task_payload = {
    "jsonrpc": "2.0",
    "params": {
        "model": "project.task",
        "method": "search_read",
        "args": [],
        "kwargs": {
            "domain": [["user_id", "=", USER_ID]],
            # fields 維持不變，name 即為任務標題
            "fields": ["id", "name", "project_id", "stage_id", "description"],
            "limit": 20,
        },
    },
}

task_response = session.post(call_url, json=task_payload).json()
if "error" in task_response:
    print("抓取任務失敗：", task_response["error"])
    exit()

tasks = task_response.get("result", [])

# === 5. 循環處理每筆任務 ===
for task in tasks:
    task_id = task.get("id")
    task_name = task.get("name", "未命名任務")  # 取得任務標題

    # 檢查 start 目錄下是否已有相同 id 的檔案
    file_name = f"task_{task_id}.txt"
    file_path = os.path.join(TARGET_DIR, file_name)

    if os.path.exists(file_path):
        print(f"檔案已存在，跳過處理：{file_path} (任務: {task_name})")
        continue

    # 處理描述：保留 HTML 語法，僅濾除圖片
    clean_description = remove_images_only(task.get("description"))

    # 透過 mail.message 模型，抓取此任務的 Chatter 訊息
    message_payload = {
        "jsonrpc": "2.0",
        "params": {
            "model": "mail.message",
            "method": "search_read",
            "args": [],
            "kwargs": {
                "domain": [
                    ["model", "=", "project.task"],
                    ["res_id", "=", task_id],
                ],
                "fields": ["date", "body"],
                "order": "date desc",
            },
        },
    }

    msg_response = session.post(call_url, json=message_payload).json()
    messages_data = msg_response.get("result", [])

    # 整合所有訊息文字（僅包含時間與不含圖片的紀錄內容）
    message_lines = []
    for msg in messages_data:
        msg_date = msg.get("date", "")
        clean_body = clean_message_body(msg.get("body"))

        if clean_body:
            message_lines.append(f"[{msg_date}] {clean_body}")

    all_messages_text = "\n".join(message_lines) if message_lines else "無訊息內容"

    # === 6. 組裝為您指定的新 TXT 格式（加入 title）並寫入檔案 ===
    file_content = f"""---id---
{task_id}
---title---
{task_name}
---description---
{clean_description}
---message---
{all_messages_text}"""

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    print(f"成功產生檔案：{file_path} (任務: {task_name})")

print("\n所有任務處理完畢！")
