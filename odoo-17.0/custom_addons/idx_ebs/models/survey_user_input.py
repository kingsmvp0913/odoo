from odoo import models


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    def _mark_done(self):
        res = super()._mark_done()

        # 需使用的 model
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']
        SaleOrderReport = self.env['sale.order.report']
        TestRequisition1 = self.env['idx.test.requisition1']
        TestRequisition2 = self.env['idx.test.requisition2']
        SkinSymptom = self.env['idx.skin.symptom']

        for user_input in self:
            survey = user_input.survey_id
            testrequest_vals = {}

            # 若為小動物-送檢單先做預設
            if survey.category == '1':
                testrequest_vals['skin_symptom_ids'] = []

            #轉換商品id product.template → product.product
            product_id = self.env['product.product'].search([("product_tmpl_id", "=", survey.product_template_id.id)], limit=1)

            # 確認是否有購物車訂單單身
            order_line = SaleOrderLine.search([
                ('order_id.partner_id', '=', survey.partner_id.id),
                ('order_id.state', '=', 'draft'),
                ('product_id', '=', product_id.id),
                ('order_id.website_id', '!=', False),
            ], limit=1)

            # 若沒有訂單單身，則建立訂單單頭/單身
            if not order_line:
                order = SaleOrder.search([
                    ('partner_id', '=', survey.partner_id.id),
                    ('state', '=', 'draft'),
                    ('website_id', '!=', False),
                    ('access_token', '!=', False)
                ], limit=1)

                # 若沒有訂單單頭，則建立單頭
                if not order:
                    website = self.env['website'].get_current_website()
                    order = SaleOrder.create({
                        'partner_id': survey.partner_id.id,
                        'website_id': website.id,
                        'order_source': 'qrcode',
                        'state': 'draft',
                        'pricelist_id': self.env["product.pricelist"].search([("partner_id", "=", survey.partner_id.id)], limit=1).id,
                    })

                # 建立訂單單身
                order_line = SaleOrderLine.create({
                    'order_id': order.id,
                    'product_id': product_id.id,
                    'product_uom_qty': 1,
                })

            # 確認訂單單身數量是否有超過送檢單
            qty = order_line.product_uom_qty  # 訂單單身數量
            report_qty = SaleOrderReport.search_count([('order_line_id', '=', order_line.id)])  # 送檢單數量

            # 若數量相同的話加1
            if qty == report_qty:
                order_line.write({'product_uom_qty': qty + 1})

            # 建立訂單單身送檢單/報告資料
            report_vals = {
                'order_id': order_line.order_id.id,
                'order_line_id': order_line.id,
                'product_template_id': survey.product_template_id.id,
            }

            # 抓出問卷答案
            lines = user_input.user_input_line_ids
            for line in lines:
                answer_type = line.answer_type
                value = None

                if answer_type == 'char_box':
                    value = line.value_char_box
                elif answer_type == 'text_box':
                    value = line.value_text_box
                elif answer_type == 'numerical_box':
                    value = line.value_numerical_box
                elif answer_type == 'date':
                    value = line.value_date
                elif answer_type == 'datetime':
                    value = line.value_datetime
                elif answer_type == 'suggestion':
                    value = line.suggested_answer_id.value

                if not value:
                    continue

                model_name = line.question_id.odoo_model_id_to.display_name
                field_desc = line.question_id.odoo_field_id_to.field_description

                # 單身送檢單 + 人類醫學送檢單
                if model_name == '人類醫學-送檢單':

                    # 姓名
                    if field_desc == '姓名':
                        report_vals['name'] = value
                        continue

                    # 送檢單位
                    if field_desc == '送檢單位':
                        testrequest_vals['inspection_unit'] = value
                        continue

                    # 性別
                    if field_desc == '性別':
                        testrequest_vals['gender'] = {'男': 'male', '女': 'female', '其他': 'other', '不提供': 'unknown'}.get(value)
                        continue

                    # 病歷號碼
                    if field_desc == '病歷號碼':
                        testrequest_vals['medical_no'] = value
                        continue

                    # 出生年月日
                    if field_desc == '出生年月日':
                        testrequest_vals['birth_date'] = value
                        continue

                    # 樣本種類
                    if field_desc == '樣本種類':
                        testrequest_vals['sample_type'] = {'血清': 'serum', '血漿': 'plasma', '全血': 'whole_blood'}.get(value)
                        continue

                    # 備註
                    if field_desc == '備註':
                        testrequest_vals['note'] = value
                        continue

                # 單身送檢單 + 小動物送檢單
                if model_name == '小動物-送檢單':

                    # 送檢醫師
                    if field_desc == '送檢醫師':
                        testrequest_vals['doctor_name'] = value

                    # 飼主名稱
                    if field_desc == '飼主姓名':
                        testrequest_vals['owner_name'] = value
                        continue

                    # 病患名稱
                    if field_desc == '病患名稱':
                        testrequest_vals['patient_name'] = value
                        continue

                    # 物種
                    if field_desc == '物種':
                        testrequest_vals['animal_type'] = {'犬': 'dog', '貓': 'cat'}.get(value)
                        continue

                    # 品系
                    if field_desc == '品系':
                        testrequest_vals['breed'] = value
                        continue

                    # 體重
                    if field_desc == '體重(kg)':
                        testrequest_vals['weight'] = value
                        continue

                    # 採血日期
                    if field_desc == '採血日期':
                        testrequest_vals['collect_date'] = value
                        continue

                    # 皮膚症狀包括
                    if field_desc == '皮膚症狀包括':
                        symptom = SkinSymptom.search([('name', '=', value)], limit=1)

                        if symptom:
                            testrequest_vals['skin_symptom_ids'].append(symptom.id)
                        continue

                    # 性別
                    if field_desc == '性別':
                        testrequest_vals['gender'] = {'公': 'male', '母': 'female'}.get(value)
                        continue

                    # 是否絕育
                    if field_desc == '是否絕育':
                        testrequest_vals['neutered'] = value
                        continue

                    # 年齡(yo)
                    if field_desc == '年齡(yo)':
                        testrequest_vals['age'] = value
                        continue

                    # 家中是否有飼養其他動物
                    if field_desc == '家中是否有飼養其他動物':
                        testrequest_vals['has_other_animals'] = value
                        continue

                    # 若是，則物種與數量為
                    if field_desc == '若是，則物種與數量為':
                        testrequest_vals['other_animals_count'] = value
                        continue

                    # 是否有跳蚤病史
                    if field_desc == '是否有跳蚤病史':
                        testrequest_vals['flea_history'] = {'是(正在感染)': 'infected', '是(已除蚤)': 'treated', '否': 'no', '不確定': 'unknown'}.get(value)
                        continue

                    # 生活環境改變
                    if field_desc == '生活環境改變':
                        testrequest_vals['environment_changed'] = value
                        continue

                    # 若是，則簡述環境變化(如由市中心遷居近郊)
                    if field_desc == '若是，則簡述環境變化(如由市中心遷居近郊)':
                        testrequest_vals['environment_change_desc'] = value
                        continue

                    # 第一次發作之年齡為
                    if field_desc == '第一次發作之年齡為':
                        testrequest_vals['first_onset_age'] = value
                        continue

                    # 反覆發作數年
                    if field_desc == '反覆發作數年':
                        testrequest_vals['recurrent_years'] = value
                        continue

                    # 若是，則持續多久
                    if field_desc == '若是，則持續多久':
                        testrequest_vals['recurrent_duration'] = value
                        continue

                    # 主要臨床症狀類型為何種類型
                    if field_desc == '主要臨床症狀類型為何種類型':
                        testrequest_vals['symptom_type'] = {'皮膚型': 'skin', '呼吸道': 'respiratory', '消化道': 'digestive'}.get(value)
                        continue

                    # 一年至少三個月以上發作
                    if field_desc == '一年至少三個月以上發作':
                        testrequest_vals['long_term_attack'] = value
                        continue

                    # 皮膚症狀包括
                    if field_desc == '皮膚症狀包括':
                        symptom = self.env['idx.skin.symptom'].search([('name', '=', value)], limit=1)

                        if symptom:
                            testrequest_vals['skin_symptom_ids'].append(symptom.id)
                            continue

                    # 外來寄生蟲(種別)
                    if field_desc == '外來寄生蟲(種別)':
                        testrequest_vals['parasite_type'] = value
                        continue

                    # 繼發性感染(病原)
                    if field_desc == '繼發性感染(病原)':
                        testrequest_vals['secondary_infection'] = value
                        continue

                    # 臨床症狀好發期
                    if field_desc == '臨床症狀好發期':
                        testrequest_vals['symptom_period'] = {'季節性': 'seasonal', '非季節性(整年都有)': 'non_seasonal', '非季節性但特定季節更嚴重': 'specific'}.get(value)
                        continue

                    # 在什麼季節或特定期間症狀最為嚴重
                    if field_desc == '在什麼季節或特定期間症狀最為嚴重':
                        testrequest_vals['severe_season'] = {'春季': 'spring', '夏季': 'summer','秋季': 'autumn', '冬季': 'winter'}.get(value)
                        continue

                    # 或哪些月份特別嚴重
                    if field_desc == '或哪些月份特別嚴重':
                        testrequest_vals['severe_months'] = value
                        continue

            # 建立訂單單身送檢單/報告
            report = SaleOrderReport.with_context(
                skip_ins_requisition=True
            ).create(report_vals)

            # 建立送檢單資料
            testrequest_vals['order_id'] = order_line.order_id.id
            testrequest_vals['order_report_id'] = report.id

            # 建立人類醫學 / 小動物送檢單
            if survey.category == '0':
                TestRequisition1.create(testrequest_vals)
            else:
                TestRequisition2.create(testrequest_vals)

        return res
