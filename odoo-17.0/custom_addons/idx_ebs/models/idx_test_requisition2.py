from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class IDXTestRequisition1(models.Model):
    _name = "idx.test.requisition2"
    _description = "小動物-送檢單"

    order_id = fields.Many2one(comodel_name="sale.order", string="銷售訂單", ondelete="cascade", readonly=True)
    state = fields.Selection(related="order_id.state", string="訂單狀態", store=True, copy=False)
    order_report_id = fields.Many2one(comodel_name="sale.order.report", string="送檢單/報告", ondelete="cascade", readonly=True)
    product_template_id = fields.Many2one(string="檢測項目", related="order_report_id.product_template_id", store=True, readonly=True)
    internal_note = fields.Html(string="檢測備註", related="product_template_id.description", readonly=True)
    partner_id = fields.Many2one(string="送檢醫院", related="order_id.partner_id", store=True, readonly=True)
    doctor_name = fields.Char(string="送檢醫師")
    partner_address = fields.Char(string="醫院地址", related="partner_id.contact_address",readonly=True)
    partner_email = fields.Char(string="Email", related="partner_id.email", readonly=True)
    partner_phone = fields.Char(string="電話", related="partner_id.phone", readonly=True)
    patient_name = fields.Char(string="病患名稱")
    owner_name = fields.Char(string="飼主姓名", related="order_report_id.name", store=True, readonly=False, inverse="_inverse_patient_name")
    animal_type = fields.Selection([("dog", "犬"), ("cat", "貓")], string="物種")
    breed = fields.Char(string="品系")
    weight = fields.Float(string="體重(kg)")
    collect_date = fields.Date(string="採血日期")
    gender = fields.Selection([("male", "公"), ("female", "母")],string="性別")
    neutered = fields.Boolean(string="是否絕育", default=False)
    age = fields.Char(string="年齡(yo)")
    has_other_animals = fields.Boolean(string="家中是否有飼養其他動物")
    other_animals_count = fields.Integer(string="若是，則物種與數量為")
    flea_history = fields.Selection([("infected", "是(正在感染)"), ("treated", "是(已除蚤)"), ("no", "否"), ("unknown", "不確定")], string="是否有跳蚤病史")
    environment_changed = fields.Boolean(string="生活環境改變")
    environment_change_desc = fields.Char(string="若是，則簡述環境變化(如由市中心遷居近郊)")
    first_onset_age = fields.Char(string="第一次發作之年齡為")
    recurrent_years = fields.Boolean(string="反覆發作數年")
    recurrent_duration = fields.Char(string="若是，則持續多久")
    symptom_type = fields.Selection([("skin", "皮膚型"), ("respiratory", "呼吸道"), ("digestive", "消化道")], string="主要臨床症狀類型為何種類型")
    long_term_attack = fields.Boolean(string="一年至少三個月以上發作")
    skin_symptom_ids = fields.Many2many("idx.skin.symptom", string="皮膚症狀包括")
    parasite_type = fields.Char(string="外來寄生蟲(種別)")
    secondary_infection = fields.Char(string="繼發性感染(病原)")
    symptom_period = fields.Selection([("seasonal", "季節性"), ("non_seasonal", "非季節性(整年都有)"), ("specific", "非季節性但特定季節更嚴重")], string="臨床症狀好發期")
    severe_season = fields.Selection([("spring", "春季"), ("summer", "夏季"), ("autumn", "秋季"), ("winter", "冬季")], string="在什麼季節或特定期間症狀最為嚴重")
    severe_months = fields.Char(string="或哪些月份特別嚴重")
    corticosteroids_note = fields.Char(string="藥物成分名、劑量和給予途徑")
    corticosteroids_last_date = fields.Date(string="最後一次給藥時間")
    corticosteroids_effect = fields.Selection([("better", "改善"), ("same", "無感"), ("worse", "惡化")], string="改善/無感/惡化")
    antihistamine_note = fields.Char(string="藥物成分名、劑量和給予途徑")
    antihistamine_last_date = fields.Date(string="最後一次給藥時間")
    antihistamine_effect = fields.Selection([("better", "改善"), ("same", "無感"), ("worse", "惡化")], string="改善/無感/惡化")
    antibiotics_note = fields.Char(string="藥物成分名、劑量和給予途徑")
    antibiotics_last_date = fields.Date(string="最後一次給藥時間")
    antibiotics_effect = fields.Selection([("better", "改善"), ("same", "無感"), ("worse", "惡化")], string="改善/無感/惡化")
    antifungal_note = fields.Char(string="藥物成分名、劑量和給予途徑")
    antifungal_last_date = fields.Date(string="最後一次給藥時間")
    antifungal_effect = fields.Selection([("better", "改善"), ("same", "無感"), ("worse", "惡化")], string="改善/無感/惡化")
    other_med_note = fields.Char(string="藥物成分名、劑量和給予途徑")
    other_med_last_date = fields.Date(string="最後一次給藥時間")
    other_med_effect = fields.Selection([("better", "改善"), ("same", "無感"), ("worse", "惡化")], string="改善/無感/惡化")

    # 送檢單飼主姓名修改一同更新來源單身姓名
    def _inverse_patient_name(self):
        if self.order_report_id:
            self.order_report_id.name = self.owner_name

class IDXSkinSymptom(models.Model):
    _name = "idx.skin.symptom"
    _description = "皮膚症狀"

    name = fields.Char(required=True)