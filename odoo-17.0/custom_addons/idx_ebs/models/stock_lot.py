from datetime import date
from dateutil.relativedelta import relativedelta
import logging

from odoo.exceptions import ValidationError
from odoo import api, fields, models, _
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class StockLot(models.Model):
    _inherit = "stock.lot"

    # --- 欄位定義 ---
    location_id = fields.Many2one(
        'stock.location',
        'Location',
        compute='_compute_single_location',
        store=True,
        readonly=False,
        inverse='_set_single_location',
        domain="[('usage', '!=', 'view')]",
        group_expand='_read_group_location_id',
        default=lambda self: self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
    )
    alert_date = fields.Datetime(
        string="警示日期", compute="_compute_alert_date", store=False
    )
    valid_days_remaining = fields.Integer(
        string="剩餘有效天數", compute="_compute_valid_days_remaining", store=True
    )
    is_alert = fields.Boolean(
        string="警示日期(紅字)", compute="_compute_is_alert", store=False
    )
    is_valid_days_remaining = fields.Boolean(
        string="剩餘有效天數(紅字)",
        compute="_compute_is_valid_days_remaining",
        store=False,
    )

    crm_lead_id = fields.Many2one("crm.lead", string="關聯商機", help="對應的 CRM 商機")

    expiration_date_str = fields.Char(
        string="到期日(中文)", compute="_compute_expiration_date_str", store=False
    )

    @api.constrains("expiration_date")
    def _check_expiration_date(self):
        for rec in self:
            if rec.expiration_date and rec.expiration_date.date() < date.today():
                raise ValidationError(
                    _("批次 %s 的到期日不可早於今天") % rec.name
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # 若 product_id 未帶入，且有 product_tmpl_id，則自動補唯一變體
            if not vals.get("product_id") and vals.get("product_tmpl_id"):
                tmpl = self.env["product.template"].browse(vals["product_tmpl_id"])
                variant = tmpl.product_variant_id
                if not variant:
                    variant = self.env["product.product"].create({
                        "product_tmpl_id": tmpl.id,
                        "active": True,
                    })
                    _logger.warning(
                        f"Auto-created product.product id={variant.id} for template id={tmpl.id}"
                    )
                vals["product_id"] = variant.id

            # 驗證：必須有產品
            if not vals.get("product_id"):
                raise ValidationError(_("建立批號時必須指定產品！"))

            # 驗證：必須有有效日期
            if not vals.get("expiration_date"):
                raise ValidationError(_("請填寫有效日期後才能建立批號！"))

        lots = super().create(vals_list)
        lots._action_create_crm_lead()
        return lots

    # 複寫原生計算欄位 訪止 stock.lot 沒有location_id
    @api.depends("quant_ids", "quant_ids.quantity")
    def _compute_single_location(self):
        for lot in self:
            quants = lot.quant_ids
            lot.location_id = (
                quants.location_id if len(quants.location_id) == 1 else False
            )

    # --- 計算邏輯 ---
    @api.depends("expiration_date")
    def _compute_expiration_date_str(self):
        for lot in self:
            if lot.expiration_date:
                lot.expiration_date_str = lot.expiration_date.date().strftime(
                    "%Y年%m月%d日"
                )
            else:
                lot.expiration_date_str = _("未知到期日")

    @api.depends("expiration_date")
    def _compute_valid_days_remaining(self):
        today = date.today()
        for rec in self:
            if rec.expiration_date:
                exp_date = rec.expiration_date.date()
                diff = (exp_date - today).days
                rec.valid_days_remaining = max(diff, 0)
            else:
                rec.valid_days_remaining = 0

    @api.depends("expiration_date")
    def _compute_alert_date(self):
        for rec in self:
            rec.alert_date = (
                rec.expiration_date - relativedelta(months=6)
                if rec.expiration_date
                else False
            )

    @api.depends("alert_date")
    def _compute_is_alert(self):
        today = date.today()
        for rec in self:
            rec.is_alert = rec.alert_date.date() <= today if rec.alert_date else False

    @api.depends("expiration_date", "valid_days_remaining")
    def _compute_is_valid_days_remaining(self):
        for rec in self:
            if rec.expiration_date:
                # 這裡邏輯維持你原本的：剩餘天數是否進入最後 6 個月
                threshold_date = rec.expiration_date.date() - relativedelta(months=6)
                days_threshold = (rec.expiration_date.date() - threshold_date).days
                rec.is_valid_days_remaining = rec.valid_days_remaining <= days_threshold
            else:
                rec.is_valid_days_remaining = False

    # --- 核心邏輯：建立商機 ---
    def _action_create_crm_lead(self):
        """核心方法：為符合條件的 Lot 建立 CRM 商機"""
        CrmTeam = self.env["crm.team"]
        CrmLead = self.env["crm.lead"]
        team_name = "L6.即將到期耗材"
        team = CrmTeam.search([("name", "=", team_name)], limit=1)
        if not team:
            team = CrmTeam.create({"name": team_name, "user_id": self.env.uid})

        for lot in self:
            # 180天內到期且尚未建立商機
            if 0 < lot.valid_days_remaining <= 180 and not lot.crm_lead_id:
                last_move = self.env['stock.move.line'].search([
                    ('lot_id', '=', lot.id),
                    ('state', '=', 'done'),
                    ('picking_code', '=', 'outgoing')
                ], order='date desc', limit=1)

                if not last_move or not last_move.picking_id.partner_id:
                    continue

                partner_id = last_move.picking_id.partner_id
                user_id = partner_id.user_id.id

                # 建立商機
                lead = CrmLead.create({
                    "name": f"{lot.product_id.name} {lot.name} {lot.expiration_date_str}",
                    "type": "opportunity",
                    "team_id": team.id,
                    "partner_id": partner_id.id,
                    "user_id": user_id or self.env.uid,
                    "stock_lot_id": lot.id,
                })
                lot.crm_lead_id = lead.id

                if user_id:
                    sales_partner_id = self.env['res.users'].browse(user_id).partner_id.id
                    lot._send_expiration_notification(lead, sales_partner_id)

    def write(self, vals):
        res = super().write(vals)
        if "expiration_date" in vals:
            self._action_create_crm_lead()
        return res

    @api.model
    def _cron_check_expiring_lots(self):
        """每日排程觸發"""
        expiring_lots = self.search(
            [
                ("product_id.product_category_id.name", "=", '耗材'),
                ("valid_days_remaining", "<=", 180),
                ("valid_days_remaining", ">", 0),
                ("crm_lead_id", "=", False),
            ]
        )
        if expiring_lots:
            expiring_lots._action_create_crm_lead()

    def _send_expiration_notification(self, lead, sales_person_id):
        sales_person = self.env['res.partner'].browse(sales_person_id)
        mention_html = f'<a href="#" data-oe-model="res.partner" data-oe-id="{sales_person.id}">@{sales_person.name}</a>'

        notification_body = Markup(
            f"<p>{mention_html} 「{lead.stock_lot_id.product_id.name}」「{lead.stock_lot_id.name}」，"
            f"「{lead.partner_id.name}」 的耗材即將到期！再請協助跟進，謝謝。</p>"
        )

        lead.message_post(
            body=notification_body,
            partner_ids=[sales_person.id],
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )