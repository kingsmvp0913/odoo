from odoo import api, fields, models


class AvailableDownload(models.Model):
    _name = "available.download"
    _description = "可下載報告"
    _sql_constraints = [
        ("name_unique_constraint", "unique(name)", "報告類型不可重複！")
    ]

    name = fields.Char(string="報告類型", required=True)
