from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

def _default_post_date(self):
    return fields.Date.today()

class IdxFrontNews(models.Model):
    _name = "idx.front.news"
    _description = "訊息公告"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'subject'
    _order = 'sequence'
    
    sequence = fields.Integer(string='顯示順序')

    subject = fields.Char(string='主旨', required=True)
    @api.constrains('subject')
    def _check_subject(self):
        for rec in self:
            if rec.subject and len(rec.subject) < 2:
                raise ValidationError(_('主旨不能少於2個字'))
    
    type = fields.Selection([('last', '最新產品公告'),
                             ('stop', '產品停產公告'),
                             ('increase', '產品漲價公告'),
                             ('other', '其他')], string='類別', required=True, default='last')
    state = fields.Selection([('draft', '草稿'),
                          ('post', '發布'),
                          ('invalid', '失效')], string='訊息處理狀態', default='draft')
    def action_state_post(self):
        for rec in self:
            rec.state = 'post'
    def action_state_invalid(self):
        for rec in self:
            rec.state = 'invalid'
    
    name = fields.Text(string='內容')
    image = fields.Image(string="圖片")
    user_id = fields.Many2one('res.users', string='公告負責人')
    user_email = fields.Char(string='公告負責人mail', related='user_id.email')
    user_phone = fields.Char(string='公告負責人電話')
    news_more_ids = fields.One2many('idx.front.news.more', 'news_id', string='公告諮詢')
    post_date = fields.Date(string='發布日期', default=_default_post_date, tracking=True)
    note = fields.Text(string='備註', compute='_compute_note')
    order_number = fields.Char(string='單號', required=True, copy=False)
    active = fields.Boolean(string="Active?", default=True)
    working_date = fields.Integer(string="工作日")
    
    def name_get(self):
        result = []        
        for rec in self:
            name = "%s - %s" % (dict(rec._fields['type'].selection).get(rec.type), rec.subject)
            result.append((rec.id, name))
        return result
    
    @api.model
    def create(self, vals):
        seq = self.env['ir.sequence'].next_by_code('front.news') or '/'
        vals['order_number'] = seq
        record = super(IdxFrontNews, self).create(vals)
        return record
    
    @api.depends('subject')
    def _compute_note(self):
        for rec in self:
            if rec.subject and rec.subject == '產品公告':
                rec.note = '產品公告備註：'
            else:
                rec.note = ''

    @api.onchange('user_id')
    def onchange_user_id(self):
        for rec in self:
            if rec.user_id:
                rec.user_phone = rec.user_id.partner_id.phone

    # 報修單上的相關人員
    def open_related_lines(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("idx_repair_manage_system.action_idx_repair_related")
        action['domain'] = [
            ('repair_id', '=', self.id)
        ]
        action['context'] = {'default_repair_id': self.id}
        return action    

class IDXRepairRelated(models.Model):
    _name = 'idx.repair.related'
    _description = "相關人員"

    repair_id = fields.Many2one('idx.front.news', string='公告單據', required=True)
    user_id = fields.Many2one('res.users', string='相關人員')
    

class IdxFrontNewsMore(models.Model):
    _name = 'idx.front.news.more'
    _description = "公告諮詢"

    news_id = fields.Many2one('idx.front.news')
    connect_name = fields.Char(string='聯絡人姓名')
    connect_mail = fields.Char(string='聯絡人mail')
    connect_phone = fields.Char(string='聯絡人電話')
    

    