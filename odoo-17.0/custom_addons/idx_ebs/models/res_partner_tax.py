from odoo import api, models, fields, _
from odoo.exceptions import ValidationError


class ResPartnerTax(models.Model):
    _name = "res.partner.tax"
    _description = "客戶稅別碼設定檔"
    _rec_name = "code"
    _rec_names_search = ["name", "code"]

    code = fields.Char(string="WF稅別碼", copy=False)
    name = fields.Char(string="稅別名稱", required=True, translate=True)
    rate = fields.Float(string="營業稅率 (%)")
    tax_type = fields.Selection(
        [
            ("1", "1.應稅內含"),
            ("2", "2.應稅外加"),
            ("3", "3.零稅率"),
            ("4", "4.免稅"),
            ("9", "9.不計稅"),
        ],
        string="WF課稅別",
        default="1",
        required=True,
        help="選擇此稅別的課稅方式，用於報價和會計計算。",
    )
    odoo_tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Odoo 稅別",
        required=True,
        ondelete="restrict",
        help="對應的 Odoo 會計稅"
    )
    invoice_count = fields.Selection(
        selection=[
            ("1", "1"),
            ("2", "2"),
            ("3", "3"),
            ("4", "4"),
            ("5", "5"),
            ("6", "6"),
            ("7", "7"),
        ],
        string="發票聯數",
    )
    invoice_name = fields.Char(
        string="聯數名稱",
        compute="_compute_invoice_name",
        store=True,  # 這樣才會存到資料庫
    )
    remark = fields.Char(string="備註")

    _sql_constraints = [
        ("code_unique", "unique (code)", "稅別代碼Code已經存在請勿重複!"),
        ("name_unique", "unique (name)", "稅別名稱Name已經存在請勿重複!"),
    ]

    @api.onchange("invoice_count")
    def _compute_invoice_name(self):
        invoice_names = {
            "1": "二聯式",
            "2": "三聯式",
            "3": "二聯式收銀機發票",
            "4": "三聯式收銀機發票",
            "5": "電子計算機發票",
            "6": "免用統一發票",
            "7": "電子發票",
        }
        for rec in self:
            rec.invoice_name = invoice_names.get(rec.invoice_count, "")

    @api.depends("invoice_count")
    def _compute_invoice_name(self):
        invoice_names = {
            "1": "二聯式",
            "2": "三聯式",
            "3": "二聯式收銀機發票",
            "4": "三聯式收銀機發票",
            "5": "電子計算機發票",
            "6": "免用統一發票",
            "7": "電子發票",
        }
        for rec in self:
            rec.invoice_name = invoice_names.get(rec.invoice_count, "")
