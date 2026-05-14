import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class IDXMergeOrderWizard(models.TransientModel):
    _name = "idx.merge.order.wizard"
    _description = "合併成訂單 Wizard"

    merge_type = fields.Selection(
        [("1", "人類醫學"), ("2", "小動物")], string="合併類型", required=True
    )
    start_date = fields.Date(string="起始日期", required=True)
    end_date = fields.Date(string="結束日期", required=True)

    @api.constrains("start_date", "end_date")
    def _check_date_range(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValidationError("結束日期不可早於起始日期")

    def action_confirm(self):
        source_model = (
            "idx.sale.order.ocr1" if self.merge_type == "1" else "idx.sale.order.ocr2"
        )

        records = self.env[source_model].search(
            [
                ("create_date", ">=", self.start_date),
                ("create_date", "<=", self.end_date),
                ("order_id", "=", False),
            ]
        )

        if not records:
            raise UserError(_("找不到符合條件的資料"))

        created_orders = self._merge_records_to_orders(
            records=records,
            source_model=source_model,
        )

        message = _("訂單建立成功，單號為：%s") % "、".join(
            created_orders.mapped("name")
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("成功"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    # 合併成訂單邏輯
    def _merge_records_to_orders(self, records, source_model):
        records = records.filtered(lambda rec: not rec.have_error)
        # 依 partner 分組
        records_by_partner = {}
        for rec in records:
            if not rec.product_template_id:
                raise UserError(_("有檢測項目為空的資料，不允許轉為訂單"))

            if rec.product_template_id.detailed_type != "service":
                raise ValidationError(_("檢測項目的產品類型不為【服務類】"))

            if not rec.product_template_id.category:
                raise UserError(
                    _("%s 商品的檢測類別為空，請確認!") % rec.product_template_id.name
                )

            records_by_partner.setdefault(rec.partner_id.id, self.env[source_model])
            records_by_partner[rec.partner_id.id] |= rec

        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]
        SaleOrderReport = self.env["sale.order.report"]
        created_orders = self.env["sale.order"]

        # 依類型決定送檢單 model
        if source_model == "idx.sale.order.ocr1":
            TestRequisition = self.env["idx.test.requisition1"]
        else:
            TestRequisition = self.env["idx.test.requisition2"]

        for partner_id, partner_records in records_by_partner.items():
            partner = self.env["res.partner"].browse(partner_id)

            sale_order = SaleOrder.create(
                {
                    "partner_id": partner.id,
                    "partner_invoice_id": partner.id,
                    "partner_shipping_id": partner.id,
                    "order_source": "ocr",
                    "state": "confirmed",
                    "pricelist_id": self.env["product.pricelist"]
                    .search([("partner_id", "=", partner.id)], limit=1)
                    .id,
                }
            )
            created_orders |= sale_order

            existing_lines = {}

            for rec in partner_records:
                product = rec.product_template_id.product_variant_id
                tmpl_id = rec.product_template_id.id

                if tmpl_id in existing_lines:
                    line = existing_lines[tmpl_id]
                    line.product_uom_qty += 1
                else:
                    line = SaleOrderLine.create(
                        {
                            "order_id": sale_order.id,
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": 1,
                            "name": product.display_name,
                        }
                    )
                    line._compute_price_unit()
                    existing_lines[tmpl_id] = line

                # 建立訂單單身送檢單/報告
                report_name = (
                    rec.patient_name
                    if source_model == "idx.sale.order.ocr1"
                    else rec.owner_name
                )

                report = SaleOrderReport.with_context(skip_ins_requisition=True).create(
                    {
                        "order_id": sale_order.id,
                        "order_line_id": line.id,
                        "product_template_id": tmpl_id,
                        "name": report_name,
                        "inspect_number": rec.inspect_number if source_model == "idx.sale.order.ocr1" else "",
                    }
                )

                # 送檢單
                if source_model == "idx.sale.order.ocr1":
                    TestRequisition.create(
                        {
                            "order_id": sale_order.id,
                            "order_report_id": report.id,
                            "patient_name": rec.patient_name,
                            "inspection_unit": rec.inspection_unit,
                            "gender": rec.gender,
                            "birth_date": rec.birth_date,
                            "sample_type": rec.sample_type,
                            "medical_no" : rec.medical_no,
                        }
                    )
                else:
                    TestRequisition.create(
                        {
                            "order_id": sale_order.id,
                            "order_report_id": report.id,
                            "patient_name": rec.patient_name,
                            "owner_name": rec.owner_name,
                            "animal_type": rec.animal_type,
                            "collect_date": rec.collect_date,
                            "gender": rec.gender,
                            "breed" : rec.breed,
                        }
                    )

            partner_records.write({"order_id": sale_order.id})

        return created_orders

    def _notify_created_orders(self, created_orders):
        order_names = created_orders.mapped("name")
        message = _("訂單建立成功，單號為：%s") % "、".join(order_names)

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("成功"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }
