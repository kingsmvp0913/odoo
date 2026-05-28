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
    """
    動態計算執行當天的「前兩週（上上週與上週）」的週一與週五日期。
    不論在週幾觸發，都能精確對齊。
    """
    today = datetime.now().date()
    this_week_monday = today - timedelta(days=today.weekday())
    two_weeks_ago_monday = this_week_monday - timedelta(weeks=2)
    last_week_friday = two_weeks_ago_monday + timedelta(days=11)
    return two_weeks_ago_monday.strftime("%Y-%m-%d"), last_week_friday.strftime("%Y-%m-%d")


def generate_ppt(start_date, end_date, project_stats, total_all_hours, output_path):
    dt_start = datetime.strptime(start_date, "%Y-%m-%d").strftime("%m/%d")
    dt_end = datetime.strptime(end_date, "%Y-%m-%d").strftime("%m/%d")

    prs = Presentation()
    blank_layout = prs.slide_layouts[6]
    slide = prs.slides.add_slide(blank_layout)

    title_box = slide.shapes.add_textbox(Inches(0.5), Inches(0.4), Inches(9), Inches(0.8))
    tf = title_box.text_frame
    p = tf.paragraphs[0]
    p.text = f"過去兩周工作進度 {dt_start}~{dt_end}"
    p.font.size = Pt(28)
    p.font.bold = True
    p.font.name = "Microsoft JhengHei"

    left_data = []
    for proj, data in sorted(project_stats.items(), key=lambda x: x[1]["hours"], reverse=True):
        proj_hours = data["hours"]
        task_count = len(data["tasks"])
        percentage = (proj_hours / total_all_hours * 100) if total_all_hours > 0 else 0.0
        left_data.append([proj, f"{proj_hours:.1f}hr ({percentage:.1f}%)", str(task_count)])

    left_rows = len(left_data) + 1
    left_table_shape = slide.shapes.add_table(
        left_rows, 3, Inches(0.5), Inches(1.5), Inches(4.5), Inches(0.35 * left_rows)
    )
    left_table = left_table_shape.table
    left_table.columns[0].width = Inches(2.2)
    left_table.columns[1].width = Inches(1.5)
    left_table.columns[2].width = Inches(0.8)

    for col_idx, text in enumerate(["項目名稱", "總工時(hr)", "單號數量"]):
        cell = left_table.cell(0, col_idx)
        cell.text = text
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(79, 129, 189)

    for row_idx, row_data in enumerate(left_data):
        for col_idx, text in enumerate(row_data):
            left_table.cell(row_idx + 1, col_idx).text = text

    right_rows = max(6, left_rows)
    right_table_shape = slide.shapes.add_table(
        right_rows, 2, Inches(5.3), Inches(1.5), Inches(4.2), Inches(0.35 * right_rows)
    )
    right_table = right_table_shape.table
    right_table.columns[0].width = Inches(2.7)
    right_table.columns[1].width = Inches(1.5)

    for col_idx, text in enumerate(["未來兩周工作計畫項目名稱", "預估工時"]):
        cell = right_table.cell(0, col_idx)
        cell.text = text
        cell.fill.solid()
        cell.fill.fore_color.rgb = RGBColor(128, 128, 128)

    for table in [left_table, right_table]:
        for row in table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.name = "Microsoft JhengHei"
                    paragraph.font.size = Pt(11)
                    paragraph.alignment = PP_ALIGN.CENTER

    ppt_file = output_path / "工作週報.pptx"
    prs.save(ppt_file)
    print(f"[SUCCESS] PPT 簡報已成功動態生成至: {ppt_file}")


def main():
    output_path = Path(__file__).parent

    cfg = load_config("odoo")
    session = create_odoo_session(cfg["url"], cfg["db"], cfg["username"], cfg["password"])

    start_date, end_date = get_previous_two_weeks_range()
    print(f"[INFO] 系統自動判定觸發日前兩週區間: {start_date} ~ {end_date}")

    call_url = f"{cfg['url']}/web/dataset/call_kw"
    timesheet_payload = {
        "jsonrpc": "2.0",
        "method": "call",
        "params": {
            "model": "account.analytic.line",
            "method": "search_read",
            "args": [],
            "kwargs": {
                "domain": [
                    ["user_id", "=", cfg["user_id"]],
                    ["date", ">=", start_date],
                    ["date", "<=", end_date],
                ],
                "fields": ["id", "name", "date", "unit_amount", "project_id", "task_id"],
                "order": "date desc",
                "limit": 150,
            },
        },
    }

    ts_resp = session.post(call_url, json=timesheet_payload).json()
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
        ts_date = ts.get("date", "")
        if datetime.strptime(ts_date, "%Y-%m-%d").date().weekday() in (5, 6):
            continue
        ts_hours = ts.get("unit_amount", 0.0)
        ts_description = remove_images_only(ts.get("name")).strip()
        project_name = ts["project_id"][1] if ts.get("project_id") else "未知專案"
        project_stats[project_name]["hours"] += ts_hours
        if ts_description:
            project_stats[project_name]["tasks"].add(ts_description)
        total_all_hours += ts_hours

    generate_ppt(start_date, end_date, project_stats, total_all_hours, output_path)


if __name__ == "__main__":
    main()
