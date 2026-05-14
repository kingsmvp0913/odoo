from odoo import models, fields, api
from odoo.exceptions import ValidationError

from ..services.onedrive_service import OnedriveService


root_dir = "文件/##對帳單專區##"


class AccountStatement(models.Model):
    _name = "account.statement"
    _description = "Account Statement"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "partner_id asc, per_month desc"

    partner_code = fields.Char(string="客戶代號", related="partner_id.partner_code")
    partner_id = fields.Many2one(
        "res.partner",
        string="客戶全名",
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    per_month = fields.Char(string="年月", required=True, tracking=True, size=6)
    pdf_file = fields.Binary(string="PDF下載", attachment=True, readonly=True)
    pdf_filename = fields.Char(string="PDF檔案名稱")
    excel_file = fields.Binary(string="Excel下載", attachment=True, readonly=True)
    excel_filename = fields.Char(string="Excel檔案名稱")

    @api.constrains("per_month")
    def _check_per_month_format(self):
        for record in self:
            if not record.per_month:
                raise ValidationError("年月欄位不可為空。")

            if len(record.per_month) != 6 or not record.per_month.isdigit():
                raise ValidationError(
                    "年月格式錯誤，請使用 'YYYYMM' 格式，例如 '202401' 代表 2024 年 1 月。"
                )

            year = int(record.per_month[:4])
            month = int(record.per_month[4:6])

            if month < 1 or month > 12:
                raise ValidationError("月份必須介於 01 到 12 之間，請檢查您的輸入。")

            if year < 1900 or year > 2200:
                raise ValidationError(
                    "年份必須介於 1900 到 2200 之間，請檢查您的輸入。"
                )

    @api.constrains("per_month", "partner_id")
    def _check_unique_per_month_partner(self):
        for record in self:
            if not record.partner_id:
                raise ValidationError("客戶名稱欄位不可為空。")

            existing_records = self.search(
                [
                    ("per_month", "=", record.per_month),
                    ("partner_id", "=", record.partner_id.id),
                    ("id", "!=", record.id),
                ]
            )
            if existing_records:
                raise ValidationError(
                    f"客戶 {record.partner_id.name} 在 {record.per_month} 已存在對帳單紀錄。"
                )
