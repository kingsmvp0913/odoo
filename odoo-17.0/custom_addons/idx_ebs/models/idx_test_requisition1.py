from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class IDXTestRequisition1(models.Model):
    _name = "idx.test.requisition1"
    _description = "人類醫學-送檢單"

    order_id = fields.Many2one(comodel_name="sale.order", string="銷售訂單", ondelete="cascade", readonly=True)
    state = fields.Selection(related="order_id.state", string="訂單狀態", store=True, copy=False)
    order_report_id = fields.Many2one(comodel_name="sale.order.report", string="送檢單/報告", ondelete="cascade", readonly=True)
    product_template_id = fields.Many2one(string="檢測項目", related="order_report_id.product_template_id", store=True, readonly=True)
    internal_note = fields.Html(string="檢測備註", related="product_template_id.description", readonly=True)
    partner_id = fields.Many2one(string="客戶", related="order_id.partner_id", store=True, readonly=True)
    inspection_unit = fields.Char(string="送檢單位", inverse="_inverse_inspection_unit")
    patient_name = fields.Char(string="姓名", related="order_report_id.name", store=True, readonly=False, inverse="_inverse_patient_name")
    gender = fields.Selection([("male", "男"),("female", "女"),("other", "其他"),("unknown", "不提供")], string="性別")
    medical_no = fields.Char(string="病歷號碼")
    birth_date = fields.Date(string="出生年月日")
    sample_type = fields.Selection([("serum", "血清"), ("plasma", "血漿"), ("whole_blood", "全血")], string="樣本種類")
    note = fields.Char(string="備註")

    # 送檢單位修改一同更新來源單身送檢單位
    def _inverse_inspection_unit(self):
        if self.order_report_id:
            self.order_report_id.inspection_unit = self.inspection_unit

    # 送檢單姓名修改一同更新來源單身姓名
    def _inverse_patient_name(self):
        if self.order_report_id:
            self.order_report_id.name = self.patient_name

