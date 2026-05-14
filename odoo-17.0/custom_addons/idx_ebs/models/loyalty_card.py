import logging
from datetime import timedelta

from odoo import models, fields, api
from markupsafe import Markup

_logger = logging.getLogger(__name__)


class LoyaltyCard(models.Model):
    _name = "loyalty.card"
    _inherit = ["loyalty.card", "mail.thread", "mail.activity.mixin"]

    partner_id = fields.Many2one(
        "res.partner",
        string="業務夥伴",
        index=True,
        required=True,
        tracking=True,
        ondelete="restrict",
    )
    expiration_date = fields.Date(string="過期日期", tracking=True)
    serial_number = fields.Char(
        string="流水編號",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "loyalty.card.serial.number"
        ),
    )
    project_code = fields.Many2one(
        related="program_id.project_code",
        string="專案代碼",
        ondelete="restrict",
    )
    valid_days = fields.Integer(
        string="有效天數",
        compute="_compute_valid_days",
        store=False,
    )
    notified_expiration = fields.Boolean(
        string="已通知過期",
        default=False,
    )
    lead_ids = fields.One2many(
        "crm.lead",
        "loyalty_card_id",
        string="相關商機",
    )
    lead_count = fields.Integer(
        string="商機數量",
        compute="_compute_lead_count",
    )

    @api.model_create_multi
    def create(self, vals_list):
        program_ids = [vals.get('program_id') for vals in vals_list if vals.get('program_id')]
        programs = self.sudo().env['loyalty.program'].browse(program_ids)
        program_map = {p.id: p for p in programs}
        for vals in vals_list:
            program_id = vals.get('program_id')
            target_program = program_map.get(program_id)
            if not target_program or target_program.program_type != 'buy_x_get_y':
                continue
            if not vals.get('partner_id'):
                vals['partner_id'] = self.sudo().env.user.partner_id.id
        records = super().create(vals_list)
        # 當有效天數<=30天且尚未通知過負責人員，則直接發通知給負責人員，並將notified_expiration設為True
        for card in records:
            if card.expiration_date:
                delta = card.expiration_date - fields.Date.today()
                valid_days = delta.days if delta.days > 0 else 0
                if valid_days <= 30 and not card.notified_expiration:
                    if card.program_id.head and card.program_id.head.partner_id:
                        partner = card.program_id.head.partner_id.id
                        card.send_expiration_notification(partner)
                    else:
                        _logger.warning(
                            f"Loyalty Program {card.program_id.id} 的負責人員沒有設置partner_id。"
                        )
        return records

    def write(self, vals):
        res = super().write(vals)
        # 當有效天數<=30天且尚未通知過負責人員，則直接發通知給負責人員，並將notified_expiration設為True
        # 當有效天數>30天時，將notified_expiration設為False，以便未來再次接近過期時能夠通知
        # 只有在更改過期日期時才進行檢查
        if vals.get("expiration_date"):
            expiration_date = fields.Date.from_string(vals["expiration_date"])
            delta = expiration_date - fields.Date.today()
            valid_days = delta.days if delta.days > 0 else 0
            if valid_days <= 30 and not self.notified_expiration:
                if self.program_id.head and self.program_id.head.partner_id:
                    partner = self.program_id.head.partner_id.id
                    self.send_expiration_notification(partner)
                else:
                    _logger.warning(
                        f"Loyalty Program {self.program_id.id} 的負責人員沒有設置partner_id。"
                    )
            elif valid_days > 30:
                self.notified_expiration = False
        return res

    @api.depends("lead_ids")
    def _compute_lead_count(self):
        """
        計算相關商機數量
        """
        for card in self:
            card.lead_count = len(card.lead_ids)

    @api.depends("expiration_date")
    def _compute_valid_days(self):
        """
        變更過期日期自動計算有效天數
        """
        for card in self:
            if card.expiration_date:
                delta = card.expiration_date - fields.Date.today()
                card.valid_days = delta.days if delta.days > 0 else 0
            else:
                card.valid_days = 0

    def mention_person(self, user_id):
        """
        標記用戶html組裝
        @param user_id: 用戶ID或用戶ID列表
        """
        if not user_id:
            return ""
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        user_partners = self.env["res.partner"].browse(user_id)
        mentions = [
            f'<a href="{base_url}/web#model=res.partner&amp;id={p.id}" class="o_mail_redirect" target="_blank" data-oe-model="res.partner" data-oe-id="{p.id}" style="text-decoration: none; border-radius: 3px; padding: 4px; border-color:#cbc6db; background-color: #cbc6db; color: #008f8c;">@{p.name}</a>'
            for p in user_partners
        ]
        return " ".join(mentions)

    @api.model
    def _cron_check_expiring_cards(self):
        """每天檢查即將到期的卡片並發送通知"""
        today = fields.Date.today()
        expiring_cards = self.search(
            [
                ("expiration_date", "<=", today + timedelta(days=30)),
                ("expiration_date", ">=", today),
                ("notified_expiration", "=", False),
            ]
        )
        for card in expiring_cards:
            if card.program_id.head and card.program_id.head.partner_id:
                partner = card.program_id.head.partner_id.id
                card.send_expiration_notification(partner)
            else:
                _logger.warning(
                    f"排程執行 Loyalty Program {card.program_id.id} 的負責人員沒有設置partner_id。"
                )

    def send_expiration_notification(self, head):
        """
        即將過期優惠券發送通知
        @param head: 負責人員
        """
        mention_person = self.mention_person(head)
        self.message_post(
            body=Markup(
                f"<p>{mention_person}「{self.program_id.name}」「{self.code}」，「{self.partner_id.name}」 的抵用劵期限即將到期! 再請協助跟進，謝謝</p>"
            ),
            partner_ids=[head],
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        self.notified_expiration = True
        # 優惠券快到期會自動創建商機
        try:
            team = self.env["crm.team"].search(
                [("name", "=", "L5.即將到期抵用劵")], limit=1
            )
            if not team:
                team = self.env["crm.team"].create(
                    {
                        "name": "L5.即將到期抵用劵",
                    }
                )
            lead = self.env["crm.lead"].create(
                {
                    "name": f"{self.program_id.name} {self.serial_number}",
                    "team_id": team.id,
                    "partner_id": self.partner_id.id,
                    "user_id": self.program_id.head.id,
                    "type": "opportunity",
                    "loyalty_card_id": self.id,
                }
            )
            self.lead_ids = [(4, lead.id)]
        except Exception as e:
            _logger.error(f"查找crm.team失敗: {e}")

    def action_open_leads(self):
        """打開相關商機視圖"""
        self.ensure_one()
        return {
            "name": "相關商機",
            "type": "ir.actions.act_window",
            "res_model": "crm.lead",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.lead_ids.ids)],
        }
