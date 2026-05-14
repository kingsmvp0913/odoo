from odoo import _, api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"


    pic_ip = fields.Char(
        string="IP",
        config_parameter="idx_wf_sync.pic_ip",
    )
    pic_id = fields.Char(
        string="帳號",
        config_parameter="idx_wf_sync.pic_id",
    )
    pic_pw = fields.Char(
        string="密碼",
        config_parameter="idx_wf_sync.pic_pw",
    )
    driver = fields.Selection(
        [
            ("FreeTDS", "FreeTDS (for Linux / Docker)"),
            (
                "ODBC Driver 18 for SQL Server",
                "ODBC Driver 18 for SQL Server (for Windows)",
            ),
            (
                "ODBC Driver 17 for SQL Server",
                "ODBC Driver 17 for SQL Server (for Windows)",
            ),
        ],
        string="SQL Server驅動程式",
        config_parameter="idx_wf_sync.driver",
    )
    server_ip = fields.Char(
        string="Server IP",
        config_parameter="idx_wf_sync.server_ip",
    )
    username = fields.Char(
        string="WF帳號",
        config_parameter="idx_wf_sync.username",
    )
    password = fields.Char(
        string="WF密碼",
        config_parameter="idx_wf_sync.password",
    )
    creator = fields.Char(
        string="資料建立者帳號",
        config_parameter="idx_wf_sync.creator",
    )
    usr_group = fields.Char(
        string="資料建立者群組",
        config_parameter="idx_wf_sync.usr_group",
    )
    group_sync_wf = fields.Boolean(
        string="啟用同步Workflow",
        implied_group="idx_wf_sync.group_prod_sync_wf",
        default=False,
    )
