from odoo import fields, models, api
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    enable_sync_onedrive = fields.Boolean(
        string="啟用同步OneDrive",
        config_parameter="idx_ebs.enable_sync_onedrive",
        default=False,
    )
    onedrive_email = fields.Char(
        string="OneDrive帳號(Email)", config_parameter="idx_ebs.onedrive_email"
    )
    tenant_id = fields.Char(string="Tenant ID", config_parameter="idx_ebs.tenant_id")
    client_id = fields.Char(string="Client ID", config_parameter="idx_ebs.client_id")
    client_secret = fields.Char(
        string="Client Secret", config_parameter="idx_ebs.client_secret"
    )
    enable_tcat = fields.Boolean(
        string="啟用黑貓串接",
        config_parameter="idx_ebs.enable_tcat",
        default=False,
    )
    tcat_endpoint = fields.Char(
        string="黑貓API端點",
        config_parameter="idx_ebs.tcat_endpoint",
    )
    enable_post = fields.Boolean(
        string="啟用中華郵政串接",
        config_parameter="idx_ebs.enable_post",
        default=False,
    )
    customer_id = fields.Char(
        string="契約客戶代號", config_parameter="idx_ebs.customer_id"
    )
    customer_token = fields.Char(
        string="契約客戶授權碼", config_parameter="idx_ebs.customer_token"
    )
    enable_sync_ocr = fields.Boolean(
        string="啟用OCR辨識", config_parameter="idx_ebs.enable_sync_ocr", default=False
    )
    ocr_url = fields.Char(string="OCR辨識API URL", config_parameter="idx_ebs.ocr_url")
    ocr_api_token = fields.Char(
        string="OCR辨識API Token", config_parameter="idx_ebs.ocr_api_token"
    )
    ocr_key = fields.Char(string="OCR辨識金鑰", config_parameter="idx_ebs.ocr_key")
    ocr_iv = fields.Char(string="OCR辨識向量", config_parameter="idx_ebs.ocr_iv")
    encrypt_data = fields.Char(
        string="OCR辨識加密金鑰", config_parameter="idx_ebs.encrypt_data"
    )

    enable_sync_fliphtml5 = fields.Boolean(string="啟用電子書串接", config_parameter="idx_ebs.enable_sync_fliphtml5", default=False)
    fliphtml5_access_id = fields.Char(string='電子書AccessID', config_parameter='fliphtml5.access_id')
    fliphtml5_access_key = fields.Char(string='電子書AccessKey', config_parameter='fliphtml5.access_key')

    @api.constrains("onedrive_email", "tenant_id", "client_id", "client_secret")
    def _check_onedrive_config(self):
        for record in self:
            if record.enable_sync_onedrive:
                if not (
                    record.onedrive_email
                    and record.tenant_id
                    and record.client_id
                    and record.client_secret
                ):
                    raise ValidationError(
                        "啟用同步OneDrive功能時，OneDrive帳號(Email)、Tenant ID、Client ID及Client Secret皆為必填欄位。"
                    )

    @api.constrains("customer_id", "customer_token")
    def _check_tcat_config(self):
        for record in self:
            if record.enable_tcat:
                if not (record.customer_id and record.customer_token):
                    raise ValidationError(
                        "啟用黑貓串接功能時，契約客戶代號及契約客戶授權碼皆為必填欄位。"
                    )
