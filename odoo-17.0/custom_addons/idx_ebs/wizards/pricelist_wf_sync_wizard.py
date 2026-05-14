from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class PricelistWfSyncWizard(models.TransientModel):
    _name = "pricelist.wf.sync.wizard"
    _description = "價格表WF同步精靈"

    quote_date_start = fields.Date(string="報價_起始日期")
    quote_date_end = fields.Date(string="報價_結束日期")
    create_date_start = fields.Date(string="建立_起始日期")
    create_date_end = fields.Date(string="建立_結束日期")
    modi_date_start = fields.Date(string="修改_起始日期")
    modi_date_end = fields.Date(string="修改_結束日期")

    @api.constrains(
        "quote_date_start",
        "quote_date_end",
        "create_date_start",
        "create_date_end",
        "modi_date_start",
        "modi_date_end",
    )
    def _check_date_range(self):
        for record in self:
            record._check_single_date_range(
                record.quote_date_start, record.quote_date_end, "報價日期"
            )
            record._check_single_date_range(
                record.create_date_start, record.create_date_end, "建立日期"
            )
            record._check_single_date_range(
                record.modi_date_start, record.modi_date_end, "修改日期"
            )

    def _check_single_date_range(self, start, end, label):
        if start and end and end < start:
            raise ValidationError(_(f"{label}的結束日期不可早於起始日期"))

    def action_confirm(self):
        if not self.env.context.get("active_id"):
            self.env["product.pricelist"].with_delay(priority=15).sync_with_wf(
                quote_date_start=self.quote_date_start,
                quote_date_end=self.quote_date_end,
                create_date_start=self.create_date_start,
                create_date_end=self.create_date_end,
                modi_date_start=self.modi_date_start,
                modi_date_end=self.modi_date_end,
            )
        else:
            self.env["product.pricelist"].sync_with_wf(
                quote_date_start=self.quote_date_start,
                quote_date_end=self.quote_date_end,
                create_date_start=self.create_date_start,
                create_date_end=self.create_date_end,
                modi_date_start=self.modi_date_start,
                modi_date_end=self.modi_date_end,
            )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "WF報價單->odoo價格表同步中",
                "message": "已加入背景任務，請稍候 ☕",
                "type": "info",
                "sticky": False,
                "next": {
                    "type": "ir.actions.client",
                    "tag": "soft_reload",
                },
            },
        }
