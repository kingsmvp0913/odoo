from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"


    wf_db = fields.Char(string="MSSQL資料庫代號")
    wf_company = fields.Char(string="公司代號")
