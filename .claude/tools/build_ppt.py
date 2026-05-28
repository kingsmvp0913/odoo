#!/usr/bin/env python3
"""
Odoo 工時表同步與 PPT 自動生成腳本
自動動態計算「執行當天前兩週的週一至週五」，建立目錄並生成左右雙表格 PPT。
"""

from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

from _odoo_utils import load_config, remove_images_only, create_odoo_session


def get_previous_two_weeks_range():
    today = datetime.now().date()
    this_week_monday = today - timedelta(days=today.weekday())
    two_weeks_ago_monday = this_week_monday - timedelta(weeks=2)
    last_week_friday = two_weeks_ago_monday + timedelta(days=11)
    return two_weeks_ago_monday.strftime("%Y-%m-%d"), last_week_friday.strftime("%Y-%m-%d")


def fetch_pending_tasks(odoo_cfg, service_cfg):
    """
    從兩個來源抓未完成任務，回傳 {project_name: count}。
    service_cfg 為 None 時略過第二來源。
    """
    stats = defaultdict(int)

    # 來源 1：project.task
    session = create_odoo_session(odoo_cfg["url"], odoo_cfg["db"], odoo_cfg["username"], odoo_cfg["password"])
    resp = session.post(f"{odoo_cfg['url']}/web/dataset/call_kw", json={
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "project.task",
            "method": "search_read",
            "args": [],
            "kwargs": {
                "domain": [["user_id", "=", odoo_cfg["user_id"]]],
                "fields": ["project_id"],
                "limit": 200,
            },
        },
    }).json()
    if "result" in resp:
        for task in resp["result"]:
            project_name = task["project_id"][1] if task.get("project_id") else "未知專案"
            stats[project_name] += 1
    else:
        print(f"[WARN] project.task 查詢失敗: {resp.get('error')}")

    # 來源 2：service.question.feedback（選用）
    if service_cfg:
        session2 = create_odoo_session(service_cfg["url"], service_cfg["db"], service_cfg["username"], service_cfg["password"])
        resp2 = session2.post(f"{service_cfg['url']}/web/dataset/call_kw", json={
            "jsonrpc": "2.0",
            "method": "call",
            "params": {
                "model": "service.question.feedback",
                "method": "search_read",
                "args": [],
                "kwargs": {
                    "domain": [
                        ["processing_staff", "in", [service_cfg["user_id"]]],
                        ["state", "in", ["draft", "open"]],
                    ],
                    "fields": ["system"],
                    "limit": 200,
                },
            },
        }).json()
        if "result" in resp2:
            for task in resp2["result"]:
                system_name = task["system"][1] if task.get("system") else "未知系統"
                stats[system_name] += 1
        else:
            print(f"[WARN] service.question.feedback 查詢失敗: {resp2.get('error')}")

    return stats


def _fill_table_header(table, headers, color):
    for col_idx, text in enumerate(headers):
        cell = table.cell(0, col_idx)
        cell.text = text
        cell.fill.solid()
        cell.fill.fore_color.rgb = color


def _apply_table_style(table):
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.name = "Microsoft JhengHei"
                paragraph.font.size = Pt(11)
                paragraph.alignment = PP_ALIGN.CENTER


def generate_ppt(start_date, end_date, project_stats, total_all_hours, pending_stats, output_path):
    dt_start = datetime.strptime(start_date, "%Y-%m-%d").strftime("%m/%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d").strftime("%m/%d")

    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    p = title_box.text_frame.paragraphs[0]
    p.text = f"過去兩周工作進度 {dt_start}~{dt_end}"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.name = "Microsoft JhengHei"

    # ── 左表：過去兩週工時 ──
    left_data = [
        [proj, f"{data['hours']:.1f}hr ({data['hours'] / total_all_hours * 100:.1f}%)", str(len(data["tasks"]))]
        for proj, data in sorted(project_stats.items(), key=lambda x: x[1]["hours"], reverse=True)
    ]
    left_rows = len(left_data) + 1
    left_table = slide.shapes.add_table(
        left_rows, 3, Inches(0.5), Inches(1.5), Inches(4.5), Inches(0.35 * left_rows)
    ).table
    left_table.columns[0].width = Inches(2.2)
    left_table.columns[1].width = Inches(1.5)
    left_table.columns[2].width = Inches(0.8)
    _fill_table_header(left_table, ["項目名稱", "總工時(hr)", "單號數量"], RGBColor(79, 129, 189))
    for row_idx, row_data in enumerate(left_data):
        for col_idx, text in enumerate(row_data):
            left_table.cell(row_idx + 1, col_idx).text = text
    _apply_table_style(left_table)

    # ── 右表：未完成任務 ──
    right_data = [
        [proj, str(count)]
        for proj, count in sorted(pending_stats.items(), key=lambda x: x[1], reverse=True)
    ]
    right_rows = max(len(right_data) + 1, left_rows)
    right_table = slide.shapes.add_table(
        right_rows, 2, Inches(5.3), Inches(1.5), Inches(4.2), Inches(0.35 * right_rows)
    ).table
    right_table.columns[0].width = Inches(3.0)
    right_table.columns[1].width = Inches(1.2)
    _fill_table_header(right_table, ["未完成項目名稱", "單號數量"], RGBColor(79, 129, 189))
    for row_idx, row_data in enumerate(right_data):
        for col_idx, text in enumerate(row_data):
            right_table.cell(row_idx + 1, col_idx).text = text
    _apply_table_style(right_table)

    ppt_file = output_path / "工作週報.pptx"
    prs.save(ppt_file)
    print(f"[SUCCESS] PPT 簡報已成功動態生成至: {ppt_file}")


def main():
    output_path = Path(__file__).parent

    odoo_cfg = load_config("odoo")
    service_cfg = load_config("odoo_service", optional=True)

    start_date, end_date = get_previous_two_weeks_range()
    print(f"[INFO] 觸發日前兩週區間: {start_date} ~ {end_date}")

    # 左表資料：工時統計
    session = create_odoo_session(odoo_cfg["url"], odoo_cfg["db"], odoo_cfg["username"], odoo_cfg["password"])
    ts_resp = session.post(f"{odoo_cfg['url']}/web/dataset/call_kw", json={
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "account.analytic.line",
            "method": "search_read",
            "args": [],
            "kwargs": {
                "domain": [
                    ["user_id", "=", odoo_cfg["user_id"]],
                    ["date", ">=", start_date],
                    ["date", "<=", end_date],
                ],
                "fields": ["name", "date", "unit_amount", "project_id"],
                "order": "date desc",
                "limit": 150,
            },
        },
    }).json()

    if "error" in ts_resp:
        print(f"[ERROR] 工時表查詢失敗: {ts_resp['error']}")
        return

    timesheets = ts_resp.get("result", [])
    if not timesheets:
        print(f"[INFO] 區間 {start_date} ~ {end_date} 內沒有任何工時紀錄。")
        return

    project_stats = defaultdict(lambda: {"hours": 0.0, "tasks": set()})
    total_all_hours = 0.0
    for ts in timesheets:
        if datetime.strptime(ts.get("date", ""), "%Y-%m-%d").date().weekday() in (5, 6):
            continue
        ts_hours = ts.get("unit_amount", 0.0)
        description = remove_images_only(ts.get("name")).strip()
        project_name = ts["project_id"][1] if ts.get("project_id") else "未知專案"
        project_stats[project_name]["hours"] += ts_hours
        if description:
            project_stats[project_name]["tasks"].add(description)
        total_all_hours += ts_hours

    # 右表資料：未完成任務
    print("[INFO] 抓取未完成任務...")
    pending_stats = fetch_pending_tasks(odoo_cfg, service_cfg)

    generate_ppt(start_date, end_date, project_stats, total_all_hours, pending_stats, output_path)


if __name__ == "__main__":
    main()
