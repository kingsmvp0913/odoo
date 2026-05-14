import logging
import requests
import base64
from datetime import datetime

from odoo import models, fields

from ..services.onedrive_service import OnedriveService

_logger = logging.getLogger(__name__)
root_dir = "文件/##對帳單專區##"


class SyncOnedriveWizard(models.TransientModel):
    _name = "idx.sync.onedrive.wizard"
    _description = "OneDrive 同步精靈"

    per_year = fields.Selection(
        selection="_get_year_selection",
        string="年份",
        required=True,
        default=lambda self: str(datetime.now().year),
    )
    per_month = fields.Selection(
        selection=[
            ("01", "1月"),
            ("02", "2月"),
            ("03", "3月"),
            ("04", "4月"),
            ("05", "5月"),
            ("06", "6月"),
            ("07", "7月"),
            ("08", "8月"),
            ("09", "9月"),
            ("10", "10月"),
            ("11", "11月"),
            ("12", "12月"),
        ],
        string="月份",
        required=True,
        default=lambda self: datetime.now().strftime("%m"),
    )

    def _get_year_selection(self):
        current_year = datetime.now().year
        return [
            (str(year), str(year))
            for year in range(current_year - 20, current_year + 1)
        ]

    def action_sync_onedrive(self):
        """執行從 OneDrive 同步對帳單的動作"""
        active_model = self.env.context.get("active_model")
        if active_model != "account_statement":
            return

        self.with_delay(priority=10).job_sync_onedrive()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "OneDrive 同步中",
                "message": "已加入背景任務，請稍候 ☕",
                "type": "info",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }

    def job_sync_onedrive(self):
        self.ensure_one()

        dir_path = f"{root_dir}/{self.per_year}年/{self.per_year}{self.per_month}"

        files = OnedriveService().get_files(self.env, dir_path)
        if not files:
            self._notify_user_sync(
                status=False,
                message=f"Onedrive 目錄不存在: {dir_path}，請確認後重新同步！",
            )
            return
        filtered_files = self._filter_existing_partners(files)
        if not filtered_files:
            self._notify_user_sync(
                status=False, message="沒有與對帳單檔名匹配的客戶，請確認後重新同步！"
            )
            return

        self._ins_account_statements(filtered_files)
        self._notify_user_sync(status=True)

    def _filter_existing_partners(self, files) -> dict:
        """
        篩選出存在於odoo聯絡人資料表的資料
        @param files: dict {檔案名稱: 檔案內容}
        @return: dict {partner_id: {full_name, partner_code, pdf_url, excel_url}}
        """
        filtered_files, lose_partners = {}, []
        for file_name, content in files.items():
            try:
                name_without_ext = file_name.rsplit(".", 1)[0]
                # 副檔名
                name_ext = file_name.rsplit(".", 1)[1].lower()
                # 客戶全名&客戶代號
                name_part = name_without_ext.split("-", 1)[1]

                partner = self.env["res.partner"].search(
                    [
                        ("full_name", "=", name_part[:-7]),
                        ("partner_code", "=", name_part[-7:]),
                    ],
                    limit=1,
                )
                if partner:
                    if partner.id not in filtered_files:
                        filtered_files[partner.id] = {
                            "full_name": partner.full_name,
                            "partner_code": partner.partner_code,
                            "pdf_url": None,
                            "excel_url": None,
                        }

                    download_url = content.get("@microsoft.graph.downloadUrl")
                    if name_ext == "pdf":
                        filtered_files[partner.id]["pdf_url"] = download_url
                    elif name_ext == "xlsx":
                        filtered_files[partner.id]["excel_url"] = download_url
                else:
                    lose_partners.append(name_part)
            except Exception:
                _logger.exception("整理檔案資料時出錯: %s", file_name)

        if lose_partners:
            self._notify_user_sync(
                status=False,
                message=f"以下客戶資料不存在於 Odoo 系統，請確認後補齊資料: {', '.join(lose_partners)}",
            )
        return filtered_files

    def _ins_account_statements(self, files: dict) -> None:
        """
        將對帳單資料寫入 account.statement
        @param files: dict {partner_id: {full_name, partner_code, pdf_url, excel_url}}
        """
        AccountStatement = self.env["account.statement"]
        per_month_str = f"{self.per_year}{self.per_month}"

        for partner_id, file_info in files.items():
            vals = {
                "partner_id": partner_id,
                "per_month": per_month_str,
            }

            # 下載 PDF
            if file_info.get("pdf_url"):
                try:
                    response = requests.get(file_info["pdf_url"], timeout=30)
                    response.raise_for_status()
                    vals.update(
                        {
                            "pdf_file": base64.b64encode(response.content).decode(
                                "utf-8"
                            ),
                            "pdf_filename": f"{file_info['full_name']}-{file_info['partner_code']}.pdf",
                        }
                    )
                except requests.RequestException as e:
                    # 記錄錯誤但繼續處理
                    _logger.error(f"下載 PDF 失敗 (partner_id: {partner_id}): {e}")

            # 下載 Excel
            if file_info.get("excel_url"):
                try:
                    response = requests.get(file_info["excel_url"], timeout=30)
                    response.raise_for_status()
                    vals.update(
                        {
                            "excel_file": base64.b64encode(response.content).decode(
                                "utf-8"
                            ),
                            "excel_filename": f"{file_info['full_name']}-{file_info['partner_code']}.xlsx",
                        }
                    )
                except requests.RequestException as e:
                    _logger.error(f"下載 Excel 失敗 (partner_id: {partner_id}): {e}")

            # 更新或建立記錄
            existing_record = AccountStatement.search(
                [
                    ("partner_id", "=", partner_id),
                    ("per_month", "=", per_month_str),
                ],
                limit=1,
            )
            if existing_record:
                existing_record.write(vals)
            else:
                AccountStatement.create(vals)

            self.env.cr.commit()

    def _notify_user_sync(self, status=False, message="") -> None:
        """
        發送右上角的彈出通知
        @param status: 同步狀態
        """
        if not status:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "warning",
                    "title": "同步異常",
                    "message": message,
                },
            )
        else:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "success",
                    "title": "同步完成",
                    "message": f"對帳單已成功同步至 Odoo 系統！",
                },
            )

        self.env.cr.commit()
