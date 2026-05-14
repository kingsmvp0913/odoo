from odoo import models, fields, api
from odoo.exceptions import ValidationError


class LoyaltyProgramCode(models.Model):
    _name = "loyalty.program.code"
    _description = "Loyalty Program Code"
    _rec_name = "project_code"
    _order = "project_code asc"
    _sql_constraints = [
        ("project_code_unique", "unique(project_code)", "專案代碼不可重複！")
    ]

    project_code = fields.Char(string="專案代碼", required=True)

    @api.constrains("project_code")
    def _check_project_code(self):
        for record in self:
            if not record.project_code:
                raise ValidationError("專案代碼不可為空！")
