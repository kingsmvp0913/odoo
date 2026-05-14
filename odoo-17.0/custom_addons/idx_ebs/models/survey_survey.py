from odoo import api, fields, models, _
import logging
import qrcode
import base64
from io import BytesIO
from odoo.exceptions import ValidationError
from odoo.tools import html2plaintext

_logger = logging.getLogger(__name__)


class SurveySurvey(models.Model):
    _inherit = "survey.survey"

    partner_id = fields.Many2one("res.partner", string="客戶", required=True)
    partner_code = fields.Char(string="客戶代號", related="partner_id.partner_code")
    product_template_id = fields.Many2one(
        "product.template", string="產品", required=True
    )
    category = fields.Selection(
        string="檢測單類別",
        related="product_template_id.category",
        store=True,
        readonly=True,
    )
    qrcode_image = fields.Image(string="QR-Code圖示", readonly=True, copy=False)

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        for record in self:
            if record.partner_id:
                record.user_id = record.partner_id.user_id

    @api.onchange("survey_type")
    def _onchange_survey_type(self):
        if self.survey_type == "survey":
            self.write(
                {
                    "certification": False,
                    "is_time_limited": False,
                    "scoring_type": "no_scoring",
                }
            )
        elif self.survey_type == "live_session":
            self.write(
                {
                    "access_mode": "public",
                    "is_attempts_limited": False,
                    "is_time_limited": False,
                    "progression_mode": "percent",
                    "questions_layout": "page_per_question",
                    "questions_selection": "all",
                    "scoring_type": "scoring_with_answers",
                    "users_can_go_back": False,
                }
            )
        elif self.survey_type == "assessment":
            self.write(
                {
                    "access_mode": "public",
                    "scoring_type": "no_scoring",
                }
            )

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records.filtered("access_token")._generate_qrcode()
        return records

    def write(self, vals):
        if "active" in vals and self.active and not vals.get("active"):
            if not self.user_has_groups('idx_ebs.group_back_document_management') or self.user_has_groups('idx_ebs.group_back_it'):
                raise ValidationError(_("您沒有權限封存QRCode表單"))
        result = super().write(vals)
        if "access_token" in vals and vals.get("access_token"):
            self.filtered("access_token")._generate_qrcode()
        return result

    def _create_answer(self, user=False, partner=False, email=False, test_entry=False, check_attempts=True, **additional_vals):
        """
        覆寫原生方法，自動將問卷的 partner_id 設定到答案
        如果沒有明確指定 partner，則使用問卷設定的 partner_id
        """
        # 如果沒有指定 partner 且問卷有設定 partner_id，使用問卷的 partner
        if not partner and not user and self.partner_id:
            partner = self.partner_id
        
        return super()._create_answer(
            user=user, 
            partner=partner, 
            email=email, 
            test_entry=test_entry, 
            check_attempts=check_attempts, 
            **additional_vals
        )

    def action_regenerate_qrcode(self):
        """手動重新生成 QR code"""
        for record in self:
            if not record.access_token:
                raise ValidationError(_("無法生成 QR code：缺少 access_token"))
            record._generate_qrcode()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("成功"),
                "message": _("QR code 已重新生成"),
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.client", "tag": "soft_reload"},
            },
        }

    def _generate_qrcode(self):
        """生成 QR code 圖片"""
        for record in self:
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
            survey_url = f"{base_url}/survey/start/{record.access_token}"
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_Q,
                box_size=8,
                border=4,
            )
            qr.add_data(survey_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            buffer = BytesIO()
            img.save(buffer, format="PNG")

            record.qrcode_image = base64.b64encode(buffer.getvalue())


class SurveyQuestion(models.Model):
    _inherit = "survey.question"
    category = fields.Selection(
        string="檢測單類別", related="survey_id.category", store=True, readonly=True
    )
    odoo_field_id_from = fields.Selection(
        [
            ("product", "產品"),
            ("note", "內部備註"),
            ("product_desc", "產品說明"),
            ("partner", "客戶"),
            ("address", "客戶地址"),
            ("email", "客戶Email"),
            ("phone", "客戶電話"),
        ],
        string="資料來源欄位",
    )
    odoo_model_id_to = fields.Many2one("ir.model", string="對應模組")
    odoo_field_id_to = fields.Many2one(
        "ir.model.fields", string="對應欄位", index=True, ondelete="set null"
    )

    @api.constrains("odoo_field_id_from", "question_type")
    def _check_odoo_field_from_question_type(self):
        for question in self:
            if question.odoo_field_id_from and question.question_type != "char_box":
                raise ValidationError(
                    _("當有設定「資料來源欄位」時，問題類型只能使用「單行文字方塊」。")
                )

    # 問卷顯示的資料處理
    def _get_default_char_box_value(self):
        self.ensure_one()
        survey = self.survey_id

        if self.odoo_field_id_from == "product":
            return survey.product_template_id.name or ""

        if self.odoo_field_id_from == "note":
            return html2plaintext(survey.product_template_id.description or "")

        if self.odoo_field_id_from == "product_desc":
            return html2plaintext(survey.product_template_id.description_sale or "")

        if self.odoo_field_id_from == "partner":
            return survey.partner_id.name or ""

        if self.odoo_field_id_from == "address":
            return survey.partner_id.contact_address or ""

        if self.odoo_field_id_from == "email":
            return survey.partner_id.email or ""

        if self.odoo_field_id_from == "phone":
            return survey.partner_id.phone or ""

        return ""
