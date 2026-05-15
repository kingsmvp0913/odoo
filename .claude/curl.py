import os
import sys
import requests
from bs4 import BeautifulSoup

if len(sys.argv) < 7:
    print("[ERROR] 缺少參數。用法: python curl.py <URL> <DB> <USER> <PWD> <USER_ID> <START_DIR> [SKIP_IDS]")
    sys.exit(1)

ODOO_URL   = sys.argv[1]
DB_NAME    = sys.argv[2]
USERNAME   = sys.argv[3]
PASSWORD   = sys.argv[4]
USER_ID    = int(sys.argv[5])
TARGET_DIR = sys.argv[6]
SKIP_IDS   = set(sys.argv[7].split(",")) if len(sys.argv) > 7 and sys.argv[7] else set()

CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

def remove_images_only(html_str):
    if not html_str or not isinstance(html_str, str): return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for img in soup.find_all("img"): img.decompose()
    return str(soup)

def clean_message_body(html_str):
    if not html_str or not isinstance(html_str, str): return ""
    soup = BeautifulSoup(html_str, "html.parser")
    for img in soup.find_all("img"): img.decompose()
    return soup.get_text(separator="\n", strip=True)

session = requests.Session()
session.headers.update({"User-Agent": CHROME_UA})

auth_url = f"{ODOO_URL}/web/session/authenticate"
auth_payload = {"jsonrpc": "2.0", "method": "call", "params": {"db": DB_NAME, "login": USERNAME, "password": PASSWORD}}

try:
    auth_resp = session.post(auth_url, json=auth_payload).json()
    if "error" in auth_resp:
        print(f"[ERROR] Odoo 登入失敗: {auth_resp['error']}")
        sys.exit(1)
except Exception as e:
    print(f"[ERROR] 連線失敗: {e}")
    sys.exit(1)

call_url = f"{ODOO_URL}/web/dataset/call_kw"
task_payload = {
    "jsonrpc": "2.0", "method": "call",
    "params": {
        "model": "project.task", "method": "search_read", "args": [],
        "kwargs": {
            "domain": [["user_id", "=", USER_ID]],
            "fields": ["id", "name", "project_id", "stage_id", "description"],
            "limit": 30
        }
    }
}

task_resp = session.post(call_url, json=task_payload).json()
tasks = task_resp.get("result", [])
if not tasks:
    print("[INFO] 當前沒有指派的 Odoo 任務。")
    sys.exit(0)

for task in tasks:
    task_id = task.get("id")
    task_name = task.get("name", "未命名任務")

    if str(task_id) in SKIP_IDS:
        continue

    file_path = os.path.join(TARGET_DIR, f"task_{task_id}.txt")
    if os.path.exists(file_path):
        continue

    clean_description = remove_images_only(task.get("description"))
    project_name = task["project_id"][1] if task.get("project_id") else "未知專案"
    stage_name   = task["stage_id"][1]   if task.get("stage_id")   else "未知階段"

    message_payload = {
        "jsonrpc": "2.0", "method": "call",
        "params": {
            "model": "mail.message", "method": "search_read", "args": [],
            "kwargs": {
                "domain": [["model", "=", "project.task"], ["res_id", "=", task_id]],
                "fields": ["date", "body"], "order": "date desc"
            }
        }
    }

    msg_resp = session.post(call_url, json=message_payload).json()
    messages_data = msg_resp.get("result", [])

    message_lines = []
    for msg in messages_data:
        clean_body = clean_message_body(msg.get("body"))
        if clean_body:
            message_lines.append(f"[{msg.get('date', '')}] {clean_body}")

    all_messages_text = "\n".join(message_lines) if message_lines else "無訊息內容"

    file_content = f"---id---\n{task_id}\n---title---\n{task_name}\n---project---\n{project_name}\n---stage---\n{stage_name}\n---description---\n{clean_description}\n---message---\n{all_messages_text}"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_content)
    print(f"[ODOO TASK DETECTED] Created task_{task_id}.txt: {task_name}")
