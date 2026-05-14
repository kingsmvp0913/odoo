from odoo import api, models, _, fields
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"
    _rec_names_search = ["name", "full_name", "partner_code"]

    name = fields.Char(string="客戶簡稱", tracking=4)
    full_name = fields.Char(string="客戶全名")
    partner_code = fields.Char(string="客戶代號")
    vat = fields.Char(string="統一編號", index=True)
    class_type = fields.Selection(
        [("C", "公司"), ("P", "客人"), ("E", "員工")],
        string="類別",
        default="P",
        tracking=1,
    )
    related_company_ids = fields.Many2many(
        "related.company",
        "related_company_rel",
        "partner_id",
        "related_company_id",
        string="關係公司",
    )
    partner_class_ids = fields.Many2many(
        "res.partner.class",
        "res_partner_class_rel",
        "partner_id",
        "class_id",
        string="客戶類別",
    )
    wf_tax_id = fields.Many2one("res.partner.tax", string="WF稅別碼")
    wf_tax_type = fields.Selection(
        string="WF課稅別",
        related="wf_tax_id.tax_type",
    )
    odoo_tax_id = fields.Many2one(
        comodel_name="account.tax",
        string="Odoo稅別",
        related="wf_tax_id.odoo_tax_id",
        store=True,
    )
    available_download_ids = fields.Many2many(
        "available.download",
        "res_partner_available_download_rel",
        "partner_id",
        "download_id",
        string="報告下載",
    )

    @api.model_create_multi
    def create(self, vals_list):
        is_from_user = self.env.context.get("from_user_create", False)

        for vals in vals_list:
            if is_from_user:
                vals["class_type"] = "E"

            if not vals.get("full_name") and vals.get("name"):
                vals["full_name"] = vals["name"]

        partners = super().create(vals_list)
        return partners

    @api.constrains("full_name")
    def _check_full_name_not_empty(self):
        for record in self:
            if not record.full_name:
                raise ValidationError("客戶全名欄位不可為空。")

    @api.depends("full_name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.full_name or ""
