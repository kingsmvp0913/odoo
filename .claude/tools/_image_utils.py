#!/usr/bin/env python3
"""共用圖片下載工具，供 curl.py / curl_service.py 使用"""

import re
import base64
import mimetypes
from pathlib import Path


def extract_img_srcs(html_str):
    if not html_str:
        return []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_str, "html.parser")
    return [img.get("src", "") for img in soup.find_all("img") if img.get("src")]


def _download_url(session, odoo_url, src):
    """下載單一圖片 src（URL 或 data URI），回傳 (bytes, ext) 或 (None, None)"""
    if not src:
        return None, None

    if src.startswith("data:image/"):
        try:
            header, b64data = src.split(",", 1)
            ext_raw = header.split("/")[1].split(";")[0]
            return base64.b64decode(b64data), f".{ext_raw}"
        except Exception:
            return None, None

    url = src if src.startswith("http") else odoo_url.rstrip("/") + src
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "image/png").split(";")[0].strip()
            ext = mimetypes.guess_extension(ct) or ".bin"
            if ext in (".jpe", ".jpeg"):
                ext = ".jpg"
            return resp.content, ext
    except Exception:
        pass
    return None, None


def _safe_filename(images_dir, name):
    """確保 images_dir/name 不重複，回傳最終 Path"""
    p = images_dir / re.sub(r'[^\w\-_.]', '_', name)
    stem, suffix = p.stem, p.suffix
    n = 1
    while p.exists():
        p = images_dir / f"{stem}_{n}{suffix}"
        n += 1
    return p


def save_task_images(session, odoo_url, call_url, model_name, task_id, task_dir, desc_html, msg_html_list):
    """
    下載並儲存任務的所有圖片至 task_dir/images/。
    回傳已存檔名稱清單（相對於 task_dir）。
    """
    images_dir = task_dir / "images"
    saved = []
    desc_idx = 0
    msg_idx = 0

    # 1. ir.attachment（image/* 附件）
    try:
        resp = session.post(call_url, json={
            "jsonrpc": "2.0", "method": "call",
            "params": {
                "model": "ir.attachment", "method": "search_read", "args": [],
                "kwargs": {
                    "domain": [
                        ["res_model", "=", model_name],
                        ["res_id", "=", task_id],
                        ["mimetype", "=like", "image/%"]
                    ],
                    "fields": ["id", "name", "mimetype"],
                    "limit": 50
                }
            }
        }).json()
        for att in resp.get("result", []):
            url = f"{odoo_url}/web/content/{att['id']}?download=true"
            try:
                r = session.get(url, timeout=30)
                if r.status_code == 200:
                    images_dir.mkdir(parents=True, exist_ok=True)
                    fname_raw = att.get("name") or f"attach_{att['id']}.bin"
                    fp = _safe_filename(images_dir, fname_raw)
                    fp.write_bytes(r.content)
                    saved.append(f"images/{fp.name}")
            except Exception:
                pass
    except Exception:
        pass

    # 2. description 內嵌圖片
    for src in extract_img_srcs(desc_html):
        data, ext = _download_url(session, odoo_url, src)
        if data:
            images_dir.mkdir(parents=True, exist_ok=True)
            fp = _safe_filename(images_dir, f"desc_{desc_idx}{ext}")
            fp.write_bytes(data)
            saved.append(f"images/{fp.name}")
            desc_idx += 1

    # 3. message body 內嵌圖片
    for body_html in msg_html_list:
        for src in extract_img_srcs(body_html):
            data, ext = _download_url(session, odoo_url, src)
            if data:
                images_dir.mkdir(parents=True, exist_ok=True)
                fp = _safe_filename(images_dir, f"msg_{msg_idx}{ext}")
                fp.write_bytes(data)
                saved.append(f"images/{fp.name}")
                msg_idx += 1

    return saved
