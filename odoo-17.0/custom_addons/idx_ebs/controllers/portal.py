# -*- coding: utf-8 -*-
import base64
import re
import logging
import urllib.parse
from urllib.parse import quote
import io
import zipfile
from datetime import datetime, timedelta
from itertools import groupby as groupbyelem
from operator import itemgetter
from PyPDF2 import PdfReader, PdfWriter
import json
import requests
import time
import hashlib
import hmac
import email.utils


from odoo import http, _, fields
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.addons.sale.controllers.portal import CustomerPortal as SaleCustomerPortal


from ..services.onedrive_service import OnedriveService

root_dir = "文件/##報告專區##"
_logger = logging.getLogger(__name__)


class SalePortalController(SaleCustomerPortal):
    def _encrypt_pdf(self, base64_content, password):
        """使用密碼加密 PDF 檔案"""
        try:
            # 解碼 base64 內容
            pdf_bytes = base64.b64decode(base64_content)

            # 建立 PDF reader 和 writer
            pdf_reader = PdfReader(io.BytesIO(pdf_bytes))
            pdf_writer = PdfWriter()

            # 複製所有頁面到 writer
            for page in pdf_reader.pages:
                pdf_writer.add_page(page)

            # 加密 PDF
            pdf_writer.encrypt(password)

            # 將加密後的 PDF 寫入記憶體
            output_buffer = io.BytesIO()
            pdf_writer.write(output_buffer)
            output_buffer.seek(0)

            # 編碼回 base64
            encrypted_content = base64.b64encode(output_buffer.read()).decode("utf-8")

            return encrypted_content

        except Exception as e:
            _logger.error(f"PDF 加密失敗: {str(e)}")
            # 如果加密失敗，回傳原始內容
            return base64_content

    @http.route(
        "/web/idx/report/download/<int:report_id>/<string:download_type>",
        type="http",
        auth="user",
    )
    def backend_report_download(self, report_id, download_type, **kw):
        """後台報告下載 — 直接從 OneDrive 取得檔案並回傳給瀏覽器"""
        if download_type not in ("pdf", "excel"):
            return request.make_response("Invalid download type", status=400)

        report = request.env["sale.order.report"].browse(report_id)
        if not report.exists():
            return request.make_response("找不到對應的報告記錄", status=404)

        if not (report.upload_date and report.inspect_number and report.name):
            return request.make_response("報告記錄缺少必要資訊，無法下載", status=404)

        is_pdf = download_type == "pdf"
        formatted_date = report.upload_date.strftime("%Y%m%d")
        dir_path = (
            f"{root_dir}/{report.upload_date.year}年/"
            f"{str(report.upload_date.month).zfill(2)}月/{formatted_date}"
        )
        file_name = f"{formatted_date}-{report.name}{report.inspect_number}.{'pdf' if is_pdf else 'xlsx'}"

        try:
            file_content_b64 = OnedriveService().get_file_content(
                request.env, dir_path, file_name
            )
        except Exception as e:
            _logger.error("後台下載報告時出錯: %s", e)
            return request.make_response("取得檔案時發生錯誤，請稍後再試", status=500)

        if not file_content_b64:
            return request.make_response(
                "找不到對應的報告檔案，請聯絡管理員", status=404
            )

        # 人醫 PDF 加密（與前台邏輯相同）
        if is_pdf:
            requisition = (
                request.env["idx.test.requisition1"]
                .sudo()
                .search([("order_report_id", "=", report.id)], limit=1)
            )
            if requisition and requisition.birth_date:
                file_content_b64 = self._encrypt_pdf(
                    file_content_b64, requisition.birth_date.strftime("%Y%m%d")
                )

        file_content = base64.b64decode(file_content_b64)
        content_type = (
            "application/pdf"
            if is_pdf
            else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        headers = [
            ("Content-Type", content_type),
            ("Content-Disposition", f"attachment; filename*=UTF-8''{quote(file_name)}"),
            ("Content-Length", str(len(file_content))),
        ]
        return request.make_response(file_content, headers=headers)

    @http.route(
        "/my/orders/report/download",
        type="json",
        auth="user",
        website=True,
    )
    def report_download(self, report_id=None, download_type=None, **kw):
        """下載報告 API"""
        if not report_id or download_type not in ("pdf", "excel"):
            return {"success": False, "message": "缺少必要參數"}

        # 驗證該用戶是否啟用下載功能
        partner = request.env.user.partner_id
        if download_type == "pdf" and not partner.available_download_ids.filtered(
            lambda d: d.name == "PDF"
        ):
            return {"success": False, "message": "您沒有PDF下載權限，請聯絡管理員。"}
        if download_type == "excel" and not partner.available_download_ids.filtered(
            lambda d: d.name == "Excel"
        ):
            return {"success": False, "message": "您沒有Excel下載權限，請聯絡管理員。"}

        try:
            report = request.env["sale.order.report"].sudo().browse(int(report_id))
            if not report.exists():
                return {"success": False, "message": "找不到對應的報告記錄"}

            if not (report.upload_date and report.inspect_number):
                return {"success": False, "message": "報告記錄缺少必要資訊，無法下載。"}

            formatted_date = report.upload_date.strftime("%Y%m%d")
            dir_path = f"{root_dir}/{report.upload_date.year}年/{str(report.upload_date.month).zfill(2)}月/{formatted_date}"
            file_name = f"{formatted_date}-{report.name}{report.inspect_number}.{ 'pdf' if download_type == 'pdf' else 'xlsx'}"

            file_content = OnedriveService().get_file_content(
                request.env, dir_path, file_name
            )
            if not file_content:
                return {
                    "success": False,
                    "message": "找不到對應的報告檔案，請聯絡管理員。",
                }

            first_download = not report.download_date
            # 回傳 base64 內容供前端下載
            if first_download:
                report.write({"download_date": fields.Date.context_today(report)})

            # 人醫PDF加密
            if download_type == "pdf":
                requisition = (
                    request.env["idx.test.requisition1"]
                    .sudo()
                    .search([("order_report_id", "=", report.id)], limit=1)
                )
                if requisition and requisition.birth_date:
                    password = requisition.birth_date.strftime("%Y%m%d")
                    file_content = self._encrypt_pdf(file_content, password)

            return {
                "success": True,
                "file_content": file_content,
                "file_name": file_name,
                "first_download": first_download,
                "content_type": (
                    "application/pdf"
                    if download_type == "pdf"
                    else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                ),
            }

        except Exception as e:
            _logger.error("下載報告時出錯: %s", str(e))
            return {"success": False, "message": "下載報告時發生錯誤，請稍後再試。"}

    @http.route(
        "/my/orders/report/batch_download",
        type="json",
        auth="user",
        website=True,
    )
    def batch_report_download(
        self, report_infos=None, download_pdf=False, download_excel=False, **kw
    ):
        """批次下載報告 API - 建立背景任務"""
        if not report_infos or not isinstance(report_infos, list):
            return {"success": False, "message": "缺少必要參數"}

        if not download_pdf and not download_excel:
            return {"success": False, "message": "請至少選擇一種下載格式"}

        # 驗證該用戶是否啟用下載功能
        partner = request.env.user.partner_id
        if download_pdf and not partner.available_download_ids.filtered(
            lambda d: d.name == "PDF"
        ):
            return {"success": False, "message": "您沒有PDF下載權限，請聯絡管理員。"}
        if download_excel and not partner.available_download_ids.filtered(
            lambda d: d.name == "Excel"
        ):
            return {"success": False, "message": "您沒有Excel下載權限，請聯絡管理員。"}

        try:
            # 取得報告 ID 列表
            report_ids = [
                int(info.get("id")) for info in report_infos if info.get("id")
            ]

            if not report_ids:
                return {"success": False, "message": "沒有有效的報告資料"}

            # 取得訂單 ID（從第一個報告取得）
            order_id = kw.get("order_id")
            if not order_id:
                # 從報告中取得訂單 ID
                first_report = (
                    request.env["sale.order.report"].sudo().browse(report_ids[0])
                )
                order_id = (
                    first_report.order_line_id.order_id.id
                    if first_report.order_line_id
                    else None
                )

            # 建立批次下載任務
            task = (
                request.env["report.batch.download"]
                .sudo()
                .create(
                    {
                        "name": f"批次下載任務 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                        "partner_id": partner.commercial_partner_id.id,
                        "order_id": order_id,
                        "report_ids": [(6, 0, report_ids)],
                        "download_pdf": download_pdf,
                        "download_excel": download_excel,
                        "total_reports": len(report_ids),
                    }
                )
            )

            # 使用 queue_job 執行背景任務
            task.with_delay(priority=5).action_process_batch_download()
            _logger.info(f"批次下載任務 {task.id} 已加入佇列")

            return {
                "success": True,
                "task_id": task.id,
                "message": "批次下載任務已啟動，請稍後查看下載進度",
            }

        except Exception as e:
            _logger.error(f"建立批次下載任務時出錯: {str(e)}")
            return {
                "success": False,
                "message": f"建立批次下載任務時發生錯誤：{str(e)}",
            }

    @http.route(
        "/my/orders/report/batch_download/status/<int:task_id>",
        type="json",
        auth="user",
        website=True,
    )
    def batch_download_status(self, task_id, **kw):
        """查詢批次下載任務狀態"""
        try:
            partner = request.env.user.partner_id
            task = (
                request.env["report.batch.download"]
                .sudo()
                .search(
                    [
                        ("id", "=", task_id),
                        ("partner_id", "=", partner.commercial_partner_id.id),
                    ],
                    limit=1,
                )
            )

            if not task:
                return {"success": False, "message": "找不到該任務"}

            return {
                "success": True,
                "state": task.state,
                "progress": task.progress,
                "total_reports": task.total_reports,
                "error_message": task.error_message or "",
                "order_id": task.order_id.id if task.order_id else None,
                "order_name": task.order_id.name if task.order_id else None,
            }

        except Exception as e:
            _logger.error(f"查詢任務狀態時出錯: {str(e)}")
            return {"success": False, "message": "查詢任務狀態時發生錯誤"}

    @http.route(
        "/my/orders/report/batch_download/download/<int:task_id>",
        type="http",
        auth="user",
        website=True,
    )
    def batch_download_file(self, task_id, **kw):
        """下載批次下載任務的 ZIP 檔案"""
        try:
            partner = request.env.user.partner_id
            task = (
                request.env["report.batch.download"]
                .sudo()
                .search(
                    [
                        ("id", "=", task_id),
                        ("partner_id", "=", partner.commercial_partner_id.id),
                        ("state", "=", "done"),
                    ],
                    limit=1,
                )
            )

            if not task or not task.zip_file:
                return request.not_found()

            zip_content = base64.b64decode(task.zip_file)
            quoted_filename = urllib.parse.quote(task.zip_filename or "批次報告.zip")

            return request.make_response(
                zip_content,
                headers=[
                    ("Content-Type", "application/zip"),
                    (
                        "Content-Disposition",
                        f"attachment; filename*=UTF-8''{quoted_filename}",
                    ),
                ],
            )

        except Exception as e:
            _logger.error(f"下載 ZIP 檔案時出錯: {str(e)}")
            return request.not_found()

    @http.route(
        "/my/orders/report/upload_pic",
        type="json",
        auth="user",
        website=True,
    )
    def upload_pic_personally(self, **kw):
        """上傳親取照片 API"""
        report_id = kw.get("report_id")
        file_data = kw.get("file_data")  # base64 編碼的檔案內容
        file_name = kw.get("file_name", "")

        if not report_id or not file_data:
            return {"success": False, "message": "缺少必要參數"}

        # 取得報告記錄
        report = request.env["sale.order.report"].sudo().browse(int(report_id))
        if not report.exists():
            return {"success": False, "message": "找不到對應的報告記錄"}

        # 驗證是否為該用戶的訂單
        partner = request.env.user.partner_id
        if report.partner_id.id != partner.commercial_partner_id.id:
            return {"success": False, "message": "無權限上傳此報告的照片"}

        # 檢查是否已上傳過照片
        if report.pick_date:
            return {"success": False, "message": "已上傳過照片，無法重複上傳"}

        # 驗證副檔名是否為照片格式
        allowed_extensions = (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")
        file_ext = file_name.lower().split(".")[-1] if "." in file_name else ""
        if not file_ext or f".{file_ext}" not in allowed_extensions:
            return {
                "success": False,
                "message": f"只接受照片格式 ({', '.join(allowed_extensions)})",
            }

        # 寫入照片
        report.write(
            {
                "pic_personally": file_data,
                "pic_personally_filename": file_name,
            }
        )

        return {"success": True, "message": "上傳成功"}

    @http.route(
        "/my/orders/report/save_carrier",
        type="json",
        auth="user",
        website=True,
    )
    def save_carrier_reports(self, report_data=None, **kw):
        """儲存物流資料 API"""
        if not report_data or not isinstance(report_data, list):
            return {"success": False, "message": "缺少必要參數"}

        try:
            partner = request.env.user.partner_id
            updated_count = 0

            for data in report_data:
                report_id = data.get("report_id")
                if not report_id:
                    continue

                report = request.env["sale.order.report"].sudo().browse(int(report_id))
                if not report.exists():
                    continue

                # 驗證是否為該用戶的訂單
                if report.partner_id.id != partner.commercial_partner_id.id:
                    continue

                # 準備更新的資料
                vals = {}
                if data.get("mail") != report.mail:
                    vals["mail"] = data.get("mail")
                if data.get("carrier") != report.carrier:
                    vals["carrier"] = data.get("carrier")
                    vals["carrier_type"] = False  # 清除物流狀態
                if data.get("resv_number") != report.resv_number:
                    vals["resv_number"] = data.get("resv_number")
                if data.get("carrier_number") != report.carrier_number:
                    vals["carrier_number"] = data.get("carrier_number")
                    vals["carrier_type"] = False  # 清除物流狀態
                if data.get("intl_carrier_number") != report.intl_carrier_number:
                    vals["intl_carrier_number"] = data.get("intl_carrier_number")

                intl_carrier = (
                    data.get("intl_carrier") if data.get("intl_carrier") else False
                )
                if intl_carrier != report.intl_carrier:
                    vals["intl_carrier"] = intl_carrier

                # 更新記錄
                if vals:
                    report.with_context({"carrier": True}).write(vals)
                    updated_count += 1

            return {
                "success": True,
                "message": f"成功儲存 {updated_count} 筆資料",
            }

        except Exception as e:
            _logger.error(f"儲存物流資料時出錯: {str(e)}")
            return {"success": False, "message": "儲存時發生錯誤，請稍後再試。"}

    @http.route(
        "/my/orders/report/fetch_carrier_type",
        type="json",
        auth="user",
        website=True,
    )
    def fetch_carrier_type(
        self, uuid=None, report_id=None, carrier=None, carrier_number=None, **kw
    ):
        """取得物流狀態 API"""
        if not (uuid and report_id and carrier and carrier_number):
            return {"success": False, "message": "缺少必要參數"}

        try:
            carrier = "tcat" if carrier == "黑貓" else "post"
            reportData = request.env["sale.order.report"].sudo().browse(int(report_id))

            if not reportData:
                return {
                    "success": False,
                    "message": "資料庫內找不到對應的送檢報告。",
                }

            cache_hours, cacheData = (
                request.env["sale.order.report"]
                .sudo()
                .get_logistics_cache(carrier=carrier, carrier_number=carrier_number)
            )

            if cacheData:
                # 因時區問題，需加8小時調整顯示
                expire_time = (
                    cacheData.create_date
                    + timedelta(hours=cache_hours)
                    + timedelta(hours=8)
                ).strftime("%Y-%m-%d %H:%M:%S")

                reportData.with_context({"carrier": True}).write(
                    {
                        "carrier": carrier,
                        "carrier_number": carrier_number,
                        "carrier_type": cacheData.carrier_type,
                    }
                )

                return {
                    "success": True,
                    "from_cache": True,
                    "carrier_type": cacheData.carrier_type,
                    "message": f"物流狀態已從暫存中取得，若需要更即時的物流狀態，請於 {expire_time} 後重新查詢。",
                }
            else:
                # 將當前的任務識別碼傳入，用於背景任務通知使用
                reportData.with_delay(priority=5)._fetch_carrier_type(
                    uuid=uuid,
                    origin_carrier=carrier,
                    origin_carrier_number=carrier_number,
                )

                return {
                    "success": True,
                    "message": "已送出查詢請求，請稍後於此頁面查看結果。",
                }

        except Exception as e:
            request.env.cr.rollback()
            _logger.error(f"查詢物流狀態時出錯: {str(e)}")
            return {"success": False, "message": "查詢物流狀態時發生錯誤，請稍後再試。"}

    @http.route(
        "/my/orders/report/get_carrier_status",
        type="json",
        auth="user",
        website=True,
    )
    def get_carrier_status(self, uuid=None, report_id=None, **kw):
        """獲取物流狀態 API（用於輪詢）"""
        if not (uuid and report_id):
            return {"success": False, "error": True, "error_message": "缺少必要參數"}

        try:
            cacheData = (
                request.env["logistics.cache"]
                .sudo()
                .search([("uuid", "=", uuid)], limit=1)
            )

            if not cacheData:
                # 還在處理中
                return {
                    "success": False,
                    "error": False,
                }

            # 檢查快取資料中是否有 carrier_type，沒有的話就要印fetch_message
            if not cacheData.carrier_type:
                return {
                    "success": True,
                    "error": False,
                    "message": cacheData.fetch_message or "查無物流狀態",
                }
            reportData = request.env["sale.order.report"].sudo().browse(int(report_id))

            return {
                "success": True,
                "error": False,
                "reload": True,
                "message": (
                    f"查詢{'[黑貓]' if cacheData.carrier == 'tcat' else '[中華郵政]'}之物流編號[{cacheData.carrier_number}]，與資料庫中紀錄的物流資料不符，故物流狀態不做更新。請重新確認。"
                    if (
                        cacheData.carrier != reportData.carrier
                        or cacheData.carrier_number != reportData.carrier_number
                    )
                    else "物流狀態查詢成功，即將前往頁面以查看最新狀態！"
                ),
            }
        except Exception as e:
            _logger.error(f"獲取物流狀態時出錯: {str(e)}")
            return {
                "success": False,
                "error": True,
                "error_message": "獲取狀態時發生錯誤",
            }

    def _prepare_orders_domain(self, partner):
        """覆寫原本的 domain，顯示該用戶所有訂單"""
        return [("partner_id", "child_of", [partner.commercial_partner_id.id])]

    def _get_sale_searchbar_inputs(self):
        """定義搜尋輸入選項"""
        return {
            "name": {"label": _("銷售訂單"), "input": "name"},
            "date_order": {"label": _("報價日期"), "input": "date_order"},
            "request_inspection_date": {
                "label": _("收件日期"),
                "input": "request_inspection_date",
            },
            "carrier_number": {
                "label": _("物流編號"),
                "input": "carrier_number",
            },
            "intl_carrier_number": {
                "label": _("國外物流編號"),
                "input": "intl_carrier_number",
            },
        }

    def _get_sale_searchbar_groupby(self):
        """定義分組選項"""
        return {
            "none": {"input": "none", "label": _("無")},
            "order_source": {"input": "order_source", "label": _("訂單來源")},
            "state": {"input": "state", "label": _("訂單狀態")},
        }

    def _get_state_label_mapping(self):
        """定義訂單狀態映射至前台顯示標籤"""
        return {
            "draft": "報價中",
            "sent": "報價已送出",
            "confirmed": "訂單待確認",
            "received": "已收件",
            "active": "訂單已成立",
            "wf_confirm": "訂單已成立",  # 與 active 相同
            "inspected": "訂單已成立",  # 與 active 相同
            "reported": "報告完成",
            "sent_report": "報告已寄出",
            "cancel": "已取消",
        }

    def _get_order_state_display_label(self, order):
        """取得訂單狀態的前台顯示標籤"""
        state_mapping = self._get_state_label_mapping()
        return state_mapping.get(order.state, "未設定")

    def _get_sale_search_domain(self, search_in, search):
        """根據搜尋條件回傳 domain"""
        search_domain = []
        if search and search_in:
            if search_in == "name":
                search_domain = [("name", "ilike", search)]
            elif search_in == "carrier_number":
                search_domain = [
                    ("order_line.report_ids.carrier_number", "ilike", search)
                ]
            elif search_in == "intl_carrier_number":
                search_domain = [
                    ("order_line.report_ids.intl_carrier_number", "ilike", search)
                ]
            elif search_in in ("date_order", "request_inspection_date"):
                try:
                    current_year = datetime.now().year
                    date_start = None
                    date_end = None

                    # 完整日期格式（年-月-日）
                    for date_format in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
                        try:
                            date_obj = datetime.strptime(search, date_format).date()
                            date_start = date_obj
                            date_end = date_obj + timedelta(days=1)
                            break
                        except ValueError:
                            continue

                    # 月-日格式（搜尋所有年份的該月該日）
                    if not date_start:
                        for date_format in ("%m-%d", "%m/%d"):
                            try:
                                # 驗證日期格式是否正確
                                datetime.strptime(
                                    f"{current_year}-{search}", f"%Y-{date_format}"
                                )
                                # 使用模糊搜尋來匹配所有年份的該月該日
                                search_domain = [
                                    (search_in, "ilike", f"-{search.replace('/', '-')}")
                                ]
                                return search_domain
                            except ValueError:
                                continue

                    # 月日格式（無分隔符，搜尋所有年份的該月該日，例如 0204）
                    if not date_start and len(search) == 4 and search.isdigit():
                        try:
                            # 驗證是否為有效的月日格式
                            month = int(search[:2])
                            day = int(search[2:])
                            datetime(current_year, month, day)  # 驗證日期有效性
                            # 使用模糊搜尋來匹配所有年份的該月該日
                            search_domain = [
                                (search_in, "ilike", f"-{search[:2]}-{search[2:]}")
                            ]
                            return search_domain
                        except ValueError:
                            pass

                    # 年-月格式
                    if not date_start:
                        for date_format in ("%Y-%m", "%Y/%m"):
                            try:
                                date_obj = datetime.strptime(search, date_format).date()
                                date_start = date_obj
                                # 計算該月的最後一天
                                next_month = date_obj.month % 12 + 1
                                next_year = date_obj.year + (
                                    1 if date_obj.month == 12 else 0
                                )
                                date_end = datetime(next_year, next_month, 1).date()
                                break
                            except ValueError:
                                continue

                    # 年月格式（無分隔符，6位數字）
                    if not date_start and len(search) == 6 and search.isdigit():
                        try:
                            date_obj = datetime.strptime(search, "%Y%m").date()
                            date_start = date_obj
                            next_month = date_obj.month % 12 + 1
                            next_year = date_obj.year + (
                                1 if date_obj.month == 12 else 0
                            )
                            date_end = datetime(next_year, next_month, 1).date()
                        except ValueError:
                            pass

                    # 僅年份（4位數字）
                    if not date_start and len(search) == 4 and search.isdigit():
                        try:
                            year = int(search)
                            date_start = datetime(year, 1, 1).date()
                            date_end = datetime(year + 1, 1, 1).date()
                        except ValueError:
                            pass

                    # 僅月份或日期（1-2位數字，需同時搜尋月份和日期）
                    if not date_start and search.isdigit() and 1 <= int(search) <= 31:
                        padded_search = search.zfill(2)
                        # 使用 OR 條件：匹配該月份的所有日期 或 所有月份的該日
                        search_domain = [
                            "|",
                            (
                                search_in,
                                "ilike",
                                f"-{padded_search}-",
                            ),  # 匹配月份（如 -02-）
                            (
                                search_in,
                                "ilike",
                                f"-{padded_search}",
                            ),  # 匹配日期（如 -02 結尾）
                        ]
                        return search_domain
                    elif date_start and date_end:
                        search_domain = [
                            (search_in, ">=", date_start),
                            (search_in, "<", date_end),
                        ]
                except Exception as e:
                    _logger.warning(f"日期搜尋解析失敗: {str(e)}")
                    search_domain = []
        return search_domain

    def _prepare_sale_portal_rendering_values(
        self,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        quotation_page=False,
        **kwargs,
    ):
        """覆寫原本的方法，加入搜尋和分組功能"""
        SaleOrder = request.env["sale.order"]

        if not sortby:
            sortby = "date"

        partner = request.env.user.partner_id
        values = self._prepare_portal_layout_values()

        if quotation_page:
            url = "/my/quotes"
            domain = self._prepare_quotations_domain(partner)
        else:
            url = "/my/orders"
            domain = self._prepare_orders_domain(partner)

        searchbar_sortings = self._get_sale_searchbar_sortings()
        searchbar_inputs = self._get_sale_searchbar_inputs()
        searchbar_groupby = self._get_sale_searchbar_groupby()

        sort_order = searchbar_sortings[sortby]["order"]

        if date_begin and date_end:
            domain += [
                ("create_date", ">", date_begin),
                ("create_date", "<=", date_end),
            ]

        # 處理搜尋
        search = kwargs.get("search", "")
        search_in = kwargs.get("search_in", "name")
        if search_in not in searchbar_inputs:
            search_in = "name"
        search_domain = self._get_sale_search_domain(search_in, search)
        domain += search_domain

        # 處理分組
        groupby = kwargs.get("groupby", "none")
        if groupby not in searchbar_groupby:
            groupby = "none"

        # 根據分組調整排序（確保相同分組的訂單連續排列）
        if groupby == "order_source":
            sort_order = f"order_source, {sort_order}"
        elif groupby == "state":
            sort_order = f"state, {sort_order}"

        pager_values = portal_pager(
            url=url,
            total=SaleOrder.search_count(domain),
            page=page,
            step=self._items_per_page,
            url_args={
                "date_begin": date_begin,
                "date_end": date_end,
                "sortby": sortby,
                "search": search,
                "search_in": search_in,
                "groupby": groupby,
            },
        )
        orders = SaleOrder.search(
            domain,
            order=sort_order,
            limit=self._items_per_page,
            offset=pager_values["offset"],
        )

        # 處理分組顯示
        if groupby == "order_source":
            grouped_orders = [
                SaleOrder.concat(*g)
                for k, g in groupbyelem(orders, itemgetter("order_source"))
            ]
            grouped_orders_dict = None
        elif groupby == "state":
            # 按前台顯示標籤分組，而非 DB 的 state 值
            # 返回字典結構 {顯示標籤: recordset}
            grouped_orders_dict = {}
            for order in orders:
                label = self._get_order_state_display_label(order)
                if label not in grouped_orders_dict:
                    grouped_orders_dict[label] = SaleOrder
                grouped_orders_dict[label] |= order
            grouped_orders = (
                list(grouped_orders_dict.values()) if grouped_orders_dict else []
            )
        else:
            grouped_orders = [orders] if orders else []
            grouped_orders_dict = None

        values.update(
            {
                "date": date_begin,
                "quotations": orders.sudo() if quotation_page else SaleOrder,
                "orders": orders.sudo() if not quotation_page else SaleOrder,
                "page_name": "quote" if quotation_page else "order",
                "pager": pager_values,
                "default_url": url,
                "searchbar_sortings": searchbar_sortings,
                "sortby": sortby,
                "searchbar_inputs": searchbar_inputs,
                "search_in": search_in,
                "search": search,
                "searchbar_groupby": searchbar_groupby,
                "groupby": groupby,
                "grouped_orders": grouped_orders,
                "grouped_orders_dict": grouped_orders_dict,  # 狀態分組使用
            }
        )

        return values


class PortalController(CustomerPortal):
    @http.route(["/my/qrcode"], type="http", auth="user", website=True)
    def portal_my_qrcode(self, **kw):

        partner = request.env.user.partner_id
        surveys = (
            request.env["survey.survey"]
            .sudo()
            .search([("partner_id", "=", partner.id)])
        )
        values = {"surveys": surveys}

        return request.render("idx_ebs.idx_qrcode_portal", values)

    # QR-code 下載
    @http.route(
        "/my/qrcode/download/<int:survey_id>", type="http", auth="user", website=True
    )
    def portal_download_qrcode(self, survey_id, **kw):

        survey = request.env["survey.survey"].sudo().browse(survey_id)
        if not survey.exists():
            return request.not_found()

        if survey.partner_id != request.env.user.partner_id:
            return request.not_found()

        if not survey.qrcode_image:
            return request.not_found()

        partner_name = self._safe_filename(survey.partner_id.name)
        product_name = self._safe_filename(survey.product_template_id.display_name)
        filename = f"QR-code_{partner_name}_{product_name}.png"
        filename_utf8 = quote(filename)

        filecontent = base64.b64decode(survey.qrcode_image)

        return request.make_response(
            filecontent,
            headers=[
                ("Content-Type", "image/png"),
                (
                    "Content-Disposition",
                    f"attachment; filename*=UTF-8''{filename_utf8}",
                ),
            ],
        )

    def _safe_filename(self, name):
        if not name:
            # 避免特殊符號出現錯誤
            return ""
        return re.sub(r'[\\/:*?"<>|]+', "_", name)

    @http.route(
        ["/my/account_statement", "/my/account_statement/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_account_statement(self, page=1, **kw):
        page = int(page or 1)
        per_page = 15

        values = {
            "default_url": "/my/account_statement",
            "page_name": "account_statement",
        }
        partner_id = request.env.user.partner_id.id

        if not partner_id:
            return request.render("idx_ebs.portal_my_account_statement", values)

        AccountStatement = request.env["account.statement"]
        domain = [("partner_id", "=", partner_id)]

        search = kw.get("search")
        if search:
            search = search.replace("-", "").replace("/", "")
            domain.append(("per_month", "ilike", search))

        total_count = AccountStatement.search_count(domain)
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        page = min(page, total_pages)

        account_statements = AccountStatement.search(
            domain,
            order="per_month desc",
            limit=per_page,
            offset=(page - 1) * per_page,
        )

        values.update(
            {
                "account_statements": account_statements,
                "searchbar_inputs": {
                    "per_month": {"label": _("按年月搜尋"), "input": "per_month"},
                },
                "search_in": "per_month",
                "pager": request.website.pager(
                    url="/my/account_statement",
                    total=total_count,
                    page=page,
                    step=per_page,
                    url_args={"search": search} if search else None,
                ),
                "pager_url": "/my/account_statement",
                "search": search,
            }
        )

        return request.render("idx_ebs.portal_my_account_statement", values)

    @http.route(
        "/my/account_statement/<int:statement_id>/download/pdf",
        type="http",
        auth="user",
        website=True,
    )
    def download_account_statement_pdf(self, statement_id):
        statement = request.env["account.statement"].sudo().browse(statement_id)

        if not statement or not statement.pdf_file:
            return request.not_found()
        if statement.partner_id != request.env.user.partner_id:
            return request.not_found()

        pdf_content = base64.b64decode(statement.pdf_file)

        filename = f"對帳單_{statement.per_month}.pdf"
        quoted_filename = urllib.parse.quote(filename)

        return request.make_response(
            pdf_content,
            headers=[
                ("Content-Type", "application/pdf"),
                (
                    "Content-Disposition",
                    "attachment; filename*=UTF-8''%s" % quoted_filename,
                ),
            ],
        )

    @http.route(
        "/my/account_statement/<int:statement_id>/download/excel",
        type="http",
        auth="user",
        website=True,
    )
    def download_account_statement_excel(self, statement_id):
        statement = request.env["account.statement"].sudo().browse(statement_id)

        if not statement or not statement.excel_file:
            return request.not_found()
        if statement.partner_id != request.env.user.partner_id:
            return request.not_found()

        content = base64.b64decode(statement.excel_file)
        filename = f"對帳單_{statement.per_month}.xlsx"
        quoted_filename = urllib.parse.quote(filename)

        return request.make_response(
            content,
            headers=[
                (
                    "Content-Type",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
                (
                    "Content-Disposition",
                    "attachment; filename*=UTF-8''%s" % quoted_filename,
                ),
            ],
        )

class FlipHTML5Controller(http.Controller):
    @http.route("/my/orders/report/get_flipbook_url", type="json", auth="user", website=True)
    def get_flipbook_url(self, report_id=None, **kw):
        """獲取或生成 FlipHTML5 電子書網址"""
        if not report_id:
            return {"success": False, "message": "缺少必要參數"}

        report = request.env["sale.order.report"].sudo().browse(int(report_id))
        if not report.exists():
            return {"success": False, "message": "找不到對應的報告記錄"}

        if report.fliphtml5_book_url:
            return {"success": True, "book_url": report.fliphtml5_book_url, "first_download": False}

        # 取得金鑰與設定
        get_param = request.env['ir.config_parameter'].sudo().get_param
        enable_flip = get_param('idx_ebs.enable_sync_fliphtml5')

        def clean_header_str(s):
            if not s: return ""
            return re.sub(r'[^\x20-\x7E]', '', str(s)).strip()

        access_id = clean_header_str(get_param('fliphtml5.access_id'))
        access_secret = clean_header_str(get_param('fliphtml5.access_key'))

        if not enable_flip or not access_id or not access_secret:
            return {"success": False, "message": "電子書功能未啟用或未設定金鑰"}

        try:
            # --- 1. 獲取加密密碼 ---
            book_password = None
            requisition = request.env["idx.test.requisition1"].sudo().search([
                ("order_report_id", "=", report.id)
            ], limit=1)
            if requisition and requisition.birth_date:
                book_password = requisition.birth_date.strftime("%Y%m%d")

            # --- 2. 從 OneDrive 獲取 PDF 內容 ---
            if not (report.upload_date and report.inspect_number and report.name):
                return {"success": False, "message": "報告資訊不足，無法從雲端抓取檔案"}

            formatted_date = report.upload_date.strftime("%Y%m%d")
            dir_path = (
                f"{root_dir}/{report.upload_date.year}年/"
                f"{str(report.upload_date.month).zfill(2)}月/{formatted_date}"
            )
            file_name = f"{formatted_date}-{report.name}{report.inspect_number}.pdf"

            file_content_b64 = OnedriveService().get_file_content(
                request.env, dir_path, file_name
            )
            if not file_content_b64:
                return {"success": False, "message": f"雲端找不到檔案: {file_name}"}

            pdf_data = base64.b64decode(file_content_b64)
            now_gmt = email.utils.formatdate(usegmt=True)

            # 簽名函數
            def get_auth_header(path, params=None):
                resource = path
                if params:
                    sorted_keys = sorted(params.keys())
                    query_string = "&".join([f"{k}={params[k]}" for k in sorted_keys])
                    resource = f"{path}?{query_string}"
                sign_string = f"{now_gmt}\n{resource}"
                hashed = hmac.new(access_secret.encode('utf-8'), sign_string.encode('utf-8'), hashlib.sha1)
                signature = base64.b64encode(hashed.digest()).decode('utf-8')
                return f"{access_id}:{signature}"

            # --- Step A: 上傳檔案至 FlipHTML5 ---
            upload_path = "/api/common/upload-file"
            upload_headers = {
                'Date': now_gmt,
                'x-yzw-apiversion': '0.1.0',
                'Authorization': get_auth_header(upload_path)
            }
            files = {'file': (file_name, pdf_data, 'application/pdf')}
            upload_res = requests.post("https://api.fliphtml5.com" + upload_path, headers=upload_headers, files=files,
                                       timeout=40).json()

            if upload_res.get('code') != 'OK':
                return {"success": False, "message": f"FlipHTML5 上傳失敗: {upload_res.get('msg')}"}

            file_src = upload_res['data']['fileSrc']
            if file_src.startswith('//'):
                file_src = 'https:' + file_src

            # --- Step B: 建立電子書 ---
            create_path = "/api/book/create-book-multi"
            create_params = {
                'description': f'Report: {report.inspect_number}',
                'filePath': json.dumps([{"link": file_src}]),
                'title': report.name or 'Report'
            }
            create_headers = {
                'Date': now_gmt, 'x-yzw-apiversion': '0.1.0',
                'Authorization': get_auth_header(create_path, create_params),
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            create_res = requests.post("https://api.fliphtml5.com" + create_path, headers=create_headers,
                                       data=create_params, timeout=30).json()

            if create_res.get('code') != 'OK':
                return {"success": False, "message": f"FlipHTML5 建立失敗: {create_res.get('msg')}"}

            book_id = str(create_res['data']['bookId'])
            book_url = create_res['data']['bookUrl']

            # --- Step C: 設定存取控制 (如果存在生日則加密) ---
            if book_password:
                privacy_path = "/api/book/set-book-privacy"
                privacy_params = {
                    'bookId': book_id,
                    'isPublic': '0',  # 0 代表密碼訪問
                    'purviewList': json.dumps({"password": [book_password]})
                }
                privacy_headers = {
                    'Date': now_gmt, 'x-yzw-apiversion': '0.1.0',
                    'Authorization': get_auth_header(privacy_path, privacy_params),
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                privacy_res = requests.post("https://api.fliphtml5.com" + privacy_path, headers=privacy_headers,
                                            data=privacy_params, timeout=20).json()
                if privacy_res.get('code') != 'OK':
                    _logger.error("FlipHTML5 加密失敗: %s", privacy_res.get('msg'))

            # --- Step D: 轉換狀態檢查 ---
            progress_path = "/api/book/get-book-progress"
            progress_params = {'bookId': book_id}
            for i in range(5):
                time.sleep(2)
                prog_headers = {'Date': now_gmt, 'x-yzw-apiversion': '0.1.0',
                                'Authorization': get_auth_header(progress_path, progress_params)}
                prog_res = requests.post("https://api.fliphtml5.com" + progress_path, headers=prog_headers,
                                         data=progress_params, timeout=10).json()
                status = str(prog_res.get('data', {}).get('converStatus'))
                if status == '5':
                    break
                elif status in ['6', '-2', '4']:
                    return {"success": False, "message": "電子書轉換失敗，請聯絡管理員"}

            # 完成後寫入 URL
            report.sudo().write({'fliphtml5_book_url': book_url})
            return {"success": True, "book_url": book_url}

        except Exception as e:
            _logger.exception("FlipHTML5 整合發生錯誤")
            return {"success": False, "message": f"系統錯誤: {str(e)}"}