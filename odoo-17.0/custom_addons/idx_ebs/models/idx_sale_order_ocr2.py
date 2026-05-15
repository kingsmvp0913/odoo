from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class SaleOrderOCR2(models.Model):
    _name = "idx.sale.order.ocr2"
    _description = "小動物OCR明細"
    _rec_name = "order_id"
    _order = "id desc"

    order_id = fields.Many2one("sale.order", string="訂單號碼", readonly=True, copy=False)
    product_template_id = fields.Many2one("product.template", string="檢測項目", required=True)
    partner_id = fields.Many2one("res.partner", string="送檢醫院", required=True)
    patient_name = fields.Char(string="病患名稱", required=True)
    owner_name = fields.Char(string="飼主姓名")
    animal_type = fields.Selection([("dog", "犬"), ("cat", "貓")], string="物種")
    breed = fields.Char(string="品系")
    medical_record_number = fields.Char(string="病歷號")
    collect_date = fields.Date(string="採血日期")
    gender = fields.Selection([("male", "公"), ("female", "母")], string="性別")
    neutered = fields.Boolean(string="絕育", default=False)
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

    def action_merge_order2(self):
        created_orders = self.env["idx.merge.order.wizard"]._merge_records_to_orders(
            records=self,
            source_model="idx.sale.order.ocr2",
        )
        return self.env["idx.merge.order.wizard"]._notify_created_orders(created_orders)
    
    @api.depends("patient_name", "partner_id", "partner_id.name")
    def _compute_have_error(self):
        for rec in self:
            patient_name = (rec.patient_name or "").lower()
            partner_name = (rec.partner_id.name or "").lower()
            rec.have_error = "error" in patient_name or "error" in partner_name

