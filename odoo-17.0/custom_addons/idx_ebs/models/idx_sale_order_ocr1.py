from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderOCR1(models.Model):
    _name = "idx.sale.order.ocr1"
    _description = "人類醫學OCR明細"
    _rec_name = "order_id"

    order_id = fields.Many2one("sale.order", string="訂單號碼", readonly=True, copy=False)
    partner_id = fields.Many2one("res.partner", string="客戶", required=True)
    inspection_unit = fields.Char(string="送檢單位")
    patient_name = fields.Char(string="姓名", required=True)
    gender = fields.Selection([("male", "男"),("female", "女")], string="性別")
    medical_no = fields.Char(string="病歷號碼")
    inspect_number = fields.Char(string="送檢流水編號")
    inspection_date = fields.Date(string="採檢日期")
    birth_date = fields.Date(string="出生年月日")
    sample_type = fields.Selection([("serum", "血清"), ("plasma", "血漿"), ("whole_blood", "全血")], string="樣本種類")
    product_template_id = fields.Many2one("product.template", string="檢測項目", required=True)
    note = fields.Char(string="備註")
    detect_error = fields.Char(string="偵測錯誤", readonly=True)
    send_date = fields.Date(string="收件日期", related="order_id.request_inspection_date", store=True)
    category = fields.Selection(string="檢測單類別", related="product_template_id.category", store=True)
    order_source = fields.Char(string="訂單來源", default="OCR", readonly=True)
    state = fields.Selection(string="訂單狀態", related="order_id.state", store=True, copy=False)
    have_error = fields.Boolean(string="資料有誤", compute="_compute_have_error")
    image_file = fields.Binary(string="圖片檔", attachment=True, copy=False)
    image_file_name = fields.Char(string="圖片檔名", copy=False)

    @api.constrains('product_template_id')
    def _check_product_template_service(self):
        for rec in self:
            if rec.product_template_id and rec.product_template_id.detailed_type != 'service':
                raise ValidationError(_("檢測項目的產品類型不為【服務類】，不可選擇"))

    def unlink(self):
        for rec in self:
            if rec.order_id:
                raise ValidationError(_("此送檢單已建立訂單，無法刪除"))
        return super().unlink()

    def action_merge_order1(self):
        created_orders = self.env["idx.merge.order.wizard"]._merge_records_to_orders(
            records=self,
            source_model="idx.sale.order.ocr1",
        )
        return self.env["idx.merge.order.wizard"]._notify_created_orders(created_orders)

    @api.depends("patient_name", "partner_id", "partner_id.name")
    def _compute_have_error(self):
        for rec in self:
            patient_name = (rec.patient_name or "").lower()
            partner_name = (rec.partner_id.name or "").lower()
            rec.have_error = "error" in patient_name or "error" in partner_name
