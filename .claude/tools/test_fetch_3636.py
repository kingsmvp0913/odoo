#!/usr/bin/env python3
"""
驗證修正後的 save_task_images 能正確下載 task_service_3636 的圖片
"""
import sys
import os
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _image_utils import save_task_images

try:
    import requests
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

ODOO_URL = "https://service.ideaxpress.biz"
DB_NAME  = "service"
USERNAME = "steven.lin@ideaxpress.biz"
PASSWORD = os.environ.get("ODOO_SERVICE_PASSWORD", "")
TASK_ID  = 3636

if not PASSWORD:
    print("[ERROR] 請設定環境變數 ODOO_SERVICE_PASSWORD")
    sys.exit(1)

session = requests.Session()
session.headers.update({"User-Agent": "Mozilla/5.0"})

auth_resp = session.post(f"{ODOO_URL}/web/session/authenticate", json={
    "jsonrpc": "2.0", "method": "call",
    "params": {"db": DB_NAME, "login": USERNAME, "password": PASSWORD}
}).json()
if "error" in auth_resp:
    print(f"[ERROR] 登入失敗: {auth_resp['error']}")
    sys.exit(1)
print("[OK] 登入成功")

call_url = f"{ODOO_URL}/web/dataset/call_kw"

task_resp = session.post(call_url, json={
    "jsonrpc": "2.0", "method": "call",
    "params": {
        "model": "service.question.feedback", "method": "search_read", "args": [],
        "kwargs": {
            "domain": [["id", "=", TASK_ID]],
            "fields": ["id", "name_seq", "subject", "question_description", "file"],
            "limit": 1
        }
    }
}).json()
task = task_resp.get("result", [{}])[0]
print(f"[INFO] task: {task.get('name_seq')} - {task.get('subject')}")
print(f"[INFO] file IDs: {task.get('file')}")

msg_resp = session.post(call_url, json={
    "jsonrpc": "2.0", "method": "call",
    "params": {
        "model": "mail.message", "method": "search_read", "args": [],
        "kwargs": {
            "domain": [["model", "=", "service.question.feedback"], ["res_id", "=", TASK_ID]],
            "fields": ["date", "body", "attachment_ids"],
            "order": "date desc", "limit": 20
        }
    }
}).json()
messages_data = msg_resp.get("result", [])

msg_bodies = [msg.get("body", "") for msg in messages_data]
msg_att_ids = []
for msg in messages_data:
    msg_att_ids.extend(msg.get("attachment_ids") or [])
file_att_ids = (task.get("file") or []) + msg_att_ids
print(f"[INFO] extra_attachment_ids: {file_att_ids}")

out_dir = Path(tempfile.mkdtemp(prefix="test_3636_"))
saved = save_task_images(
    session, ODOO_URL, call_url,
    "service.question.feedback", TASK_ID, out_dir,
    task.get("question_description") or "",
    msg_bodies,
    extra_attachment_ids=file_att_ids,
)

if saved:
    print(f"\n[OK] 共抓到 {len(saved)} 張圖片:")
    for f in saved:
        fpath = out_dir / f
        print(f"  {f}  ({fpath.stat().st_size} bytes)")
else:
    print("\n[FAIL] 仍然沒有抓到圖片")

print(f"\n[DONE] 檔案存放於: {out_dir}")
