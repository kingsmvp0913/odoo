from odoo import models, fields, api, _


class IDXCreateNewsWizard(models.TransientModel):
    _name = "idx.create.news.wizard"
    _description = '建立訊息公告'
    
    user_id = fields.Many2one('res.users', string='負責人')
    post_date = fields.Date(string='發布日期')

    def create_news(self):
        vals = {
            'subject': 'wizard產生公告',
            'user_id': self.user_id.id,
            'post_date': self.post_date,
        }
        self.env['idx.front.news'].create(vals)