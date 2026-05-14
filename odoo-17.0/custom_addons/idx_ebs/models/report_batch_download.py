# -*- coding: utf-8 -*-
import base64
import io
import logging
import zipfile
from datetime import datetime, timedelta

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ReportBatchDownload(models.Model):
    _name = "report.batch.download"
    _description = "批次報告下載任務"
    _order = "create_date desc"

    name = fields.Char("任務名稱", required=True, default="批次下載任務")
    partner_id = fields.Many2one("res.partner", "客戶", required=True, ondelete="cascade")
    order_id = fields.Many2one("sale.order", "訂單", ondelete="cascade")
    state = fields.Selection(
        [
            ("pending", "等待中"),
            ("processing", "處理中"),
            ("done", "完成"),
            ("failed", "失敗"),
        ],
        string="狀態",
        default="pending",
        required=True,
    )
    report_ids = fields.Many2many("sale.order.report", string="報告清單")
    download_pdf = fields.Boolean("下載 PDF", default=True)
    download_excel = fields.Boolean("下載 Excel", default=True)
    zip_file = fields.Binary("ZIP 檔案")
    zip_filename = fields.Char("ZIP 檔案名稱")
    error_message = fields.Text("錯誤訊息")
    progress = fields.Integer("進度", default=0)
    total_reports = fields.Integer("總報告數", default=0)

    def action_process_batch_download(self):
        """執行批次下載任務（用於 queue_job）"""
        self.ensure_one()
        
        if self.state != "pending":
            _logger.warning(f"任務 {self.id} 狀態不是 pending，跳過執行")
            return

        self.write({"state": "processing", "progress": 0})

        try:
            from ..services.onedrive_service import OnedriveService
            root_dir = "文件/##報告專區##"
            
            # 建立 ZIP 檔案
            zip_buffer = io.BytesIO()
            onedrive_service = OnedriveService()
            first_downloads = []
            total = len(self.report_ids)
            processed = 0

            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                for report in self.report_ids:
                    if not (report.upload_date and report.inspect_number and report.name):
                        _logger.warning(f"報告 {report.id} 資訊不完整，跳過")
                        processed += 1
                        self.progress = int((processed / total) * 100) if total else 0
                        continue

                    # 記錄首次下載
                    if not report.download_date:
                        first_downloads.append(report.id)

                    formatted_date = report.upload_date.strftime("%Y%m%d")
                    year = report.upload_date.year
                    month = str(report.upload_date.month).zfill(2)

                    # 下載 PDF
                    if self.download_pdf:
                        try:
                            pdf_dir = f"{root_dir}/{year}年/{month}月/{formatted_date}/PDF"
                            pdf_filename = f"{formatted_date}-{report.name}{report.inspect_number}.pdf"
                            pdf_content = onedrive_service.get_file_content(
                                self.env, pdf_dir, pdf_filename
                            )
                            if pdf_content:
                                pdf_bytes = base64.b64decode(pdf_content)
                                zip_file.writestr(f"PDF/{pdf_filename}", pdf_bytes)
                            else:
                                _logger.warning(f"找不到 PDF 檔案: {pdf_filename}")
                        except Exception as e:
                            _logger.error(f"下載 PDF {pdf_filename} 時出錯: {str(e)}")

                    # 下載 Excel
                    if self.download_excel:
                        try:
                            excel_dir = f"{root_dir}/{year}年/{month}月/{formatted_date}/Excel"
                            excel_filename = f"{formatted_date}-{report.name}{report.inspect_number}.xlsx"
                            excel_content = onedrive_service.get_file_content(
                                self.env, excel_dir, excel_filename
                            )
                            if excel_content:
                                excel_bytes = base64.b64decode(excel_content)
                                zip_file.writestr(f"Excel/{excel_filename}", excel_bytes)
                            else:
                                _logger.warning(f"找不到 Excel 檔案: {excel_filename}")
                        except Exception as e:
                            _logger.error(f"下載 Excel {excel_filename} 時出錯: {str(e)}")

                    processed += 1
                    self.progress = int((processed / total) * 100) if total else 0

            # 更新首次下載的報告
            if first_downloads:
                reports_to_update = self.env["sale.order.report"].browse(first_downloads)
                reports_to_update.write(
                    {"download_date": fields.Date.context_today(reports_to_update)}
                )

            # 儲存 ZIP 檔案
            zip_buffer.seek(0)
            zip_filename = f"批次報告_{datetime.now().strftime('%Y%m%d')}.zip"
            
            self.write({
                "state": "done",
                "zip_file": base64.b64encode(zip_buffer.read()),
                "zip_filename": zip_filename,
                "progress": 100,
            })
            
            # 發送 bus 通知給前端
            self._send_bus_notification("done")
            
            _logger.info(f"批次下載任務 {self.id} 完成")

        except Exception as e:
            error_msg = f"批次下載失敗：{str(e)}"
            _logger.error(error_msg)
            self.write({
                "state": "failed",
                "error_message": error_msg,
            })
            
            # 發送 bus 通知給前端
            self._send_bus_notification("failed")

    def _send_bus_notification(self, status):
        """發送 bus 消息給前端用戶"""
        self.ensure_one()
        
        # 準備消息內容
        message = {
            "type": "batch_download_complete",
            "task_id": self.id,
            "order_id": self.order_id.id if self.order_id else None,
            "order_name": self.order_id.name if self.order_id else None,
            "status": status,
            "total_reports": self.total_reports,
            "zip_filename": self.zip_filename,
            "error_message": self.error_message if status == "failed" else None,
        }
        
        # 發送給該客戶的所有用戶
        users = self.partner_id.user_ids
        if users:
            for user in users:
                channel = f"report_batch_download_{user.id}"
                self.env["bus.bus"]._sendone(channel, "notification", message)
                _logger.info(f"已發送 bus 通知到 channel: {channel}")

    @api.model
    def cleanup_old_tasks(self, days=7):
        """清理超過指定天數的已完成或失敗任務"""
        date_limit = fields.Datetime.now() - timedelta(days=days)
        old_tasks = self.search([
            ("state", "in", ["done", "failed"]),
            ("create_date", "<", date_limit),
        ])
        old_tasks.unlink()
        _logger.info(f"已清理 {len(old_tasks)} 個舊的批次下載任務")
