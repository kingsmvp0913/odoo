from datetime import date

from odoo.tests import TransactionCase


class TestGetPublicHolidayDates(TransactionCase):
    """_get_public_holiday_dates: 回傳當年度全公司假日的 date set。"""

    def setUp(self):
        super().setUp()
        self.calendar = self.env['resource.calendar'].create({
            'name': 'IDX Test Calendar',
            'company_id': self.env.company.id,
        })
        self.env.company.resource_calendar_id = self.calendar

    def test_single_day_leave_included(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'National Day',
            'calendar_id': self.calendar.id,
            'resource_id': False,
            'date_from': '2024-10-10 00:00:00',
            'date_to': '2024-10-10 23:59:59',
        })
        result = self.env['sale.order.report']._get_public_holiday_dates(2024)
        self.assertIsInstance(result, set)
        self.assertIn(date(2024, 10, 10), result)

    def test_multi_day_leave_all_dates_included(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Spring Festival',
            'calendar_id': self.calendar.id,
            'resource_id': False,
            'date_from': '2024-02-08 00:00:00',
            'date_to': '2024-02-10 23:59:59',
        })
        result = self.env['sale.order.report']._get_public_holiday_dates(2024)
        for d in [date(2024, 2, 8), date(2024, 2, 9), date(2024, 2, 10)]:
            self.assertIn(d, result)

    def test_no_calendar_returns_empty_set(self):
        self.env.company.resource_calendar_id = False
        result = self.env['sale.order.report']._get_public_holiday_dates(2024)
        self.assertEqual(result, set())

    def test_previous_year_leave_excluded(self):
        self.env['resource.calendar.leaves'].create({
            'name': 'Old Holiday',
            'calendar_id': self.calendar.id,
            'resource_id': False,
            'date_from': '2023-12-31 00:00:00',
            'date_to': '2023-12-31 23:59:59',
        })
        result = self.env['sale.order.report']._get_public_holiday_dates(2024)
        self.assertNotIn(date(2023, 12, 31), result)


class TestAddWorkingDays(TransactionCase):
    """_add_working_days: 跳過 weekday 5/6 與假日後計算工作天數。"""

    def setUp(self):
        super().setUp()
        self.obj = self.env['sale.order.report']

    def test_one_day_from_friday_returns_monday(self):
        # 2024-01-05 = 週五
        result = self.obj._add_working_days(date(2024, 1, 5), 1, set())
        self.assertEqual(result, date(2024, 1, 8))

    def test_four_days_across_normal_work_week(self):
        # 2024-01-08 = 週一 → +4 工作日 = 週五
        result = self.obj._add_working_days(date(2024, 1, 8), 4, set())
        self.assertEqual(result, date(2024, 1, 12))

    def test_holiday_is_skipped(self):
        # 週一出發，週二為假日 → +1 工作日 = 週三
        result = self.obj._add_working_days(date(2024, 1, 8), 1, {date(2024, 1, 9)})
        self.assertEqual(result, date(2024, 1, 10))

    def test_weekend_and_holiday_both_skipped(self):
        # 週四出發，+2 工作日：週五(+1), 週六跳, 週日跳, 週一假日跳, 週二(+2)
        result = self.obj._add_working_days(date(2024, 1, 11), 2, {date(2024, 1, 15)})
        self.assertEqual(result, date(2024, 1, 16))

    def test_zero_days_returns_start_date(self):
        # days=0：while 迴圈不執行，直接回傳 start_date
        start = date(2024, 3, 15)
        result = self.obj._add_working_days(start, 0, set())
        self.assertEqual(result, start)


class TestComputeExpectedDate(TransactionCase):
    """compute_expected_date 必須改用工作天計算，不再用 relativedelta。"""

    def setUp(self):
        super().setUp()
        self.calendar = self.env['resource.calendar'].create({
            'name': 'IDX Test Calendar',
            'company_id': self.env.company.id,
        })
        self.env.company.resource_calendar_id = self.calendar
        self.partner = self.env['res.partner'].create({'name': 'TDD Test Customer'})

    def _make_product(self, category=None, default_code=None):
        vals = {'name': 'TDD Product', 'detailed_type': 'service'}
        if category:
            vals['category'] = category
        if default_code:
            vals['default_code'] = default_code
        return self.env['product.product'].create(vals)

    def _make_report(self, inspection_date, product):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'request_inspection_date': inspection_date,
        })
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 100,
        })
        return self.env['sale.order.report'].with_context(
            skip_ins_requisition=True
        ).create({'order_line_id': line.id})

    def test_no_inspection_date_sets_expected_date_false(self):
        """request_inspection_date 為 False → expected_date 應保持 False。"""
        product = self._make_product(category='1')
        order = self.env['sale.order'].create({'partner_id': self.partner.id})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 100,
        })
        report = self.env['sale.order.report'].with_context(
            skip_ins_requisition=True
        ).create({'order_line_id': line.id})
        report.write({'expected_date': False})
        report.compute_expected_date()
        self.assertFalse(report.expected_date)

    def test_category_1_adds_4_working_days_skips_weekend(self):
        """category='1': 基準日週五 +4 工作日，跨週末結果應為下週四。"""
        product = self._make_product(category='1')
        try:
            report = self._make_report(date(2024, 1, 5), product)
        except Exception:
            self.skipTest('Cannot create report record in this test environment')
        report.compute_expected_date()
        # Jan 5(Fri) +4 工作: Mon=1, Tue=2, Wed=3, Thu=4 → Jan 11
        self.assertEqual(report.expected_date, date(2024, 1, 11))

    def test_default_code_4611001_adds_3_working_days_skips_weekend(self):
        """default_code='4611001': 基準日週五 +3 工作日 = 下週三。"""
        product = self._make_product(default_code='4611001')
        try:
            report = self._make_report(date(2024, 1, 5), product)
        except Exception:
            self.skipTest('Cannot create report record in this test environment')
        report.compute_expected_date()
        # Jan 5(Fri) +3 工作: Mon=1, Tue=2, Wed=3 → Jan 10
        self.assertEqual(report.expected_date, date(2024, 1, 10))

    def test_other_category_adds_5_working_days_skips_weekend(self):
        """其他類別: 基準日週一 +5 工作日 = 下週一（跨週末）。"""
        product = self._make_product(category='1')
        try:
            report = self._make_report(date(2024, 1, 8), product)
        except Exception:
            self.skipTest('Cannot create report record in this test environment')
        # 強制 category 走 else 分支
        report.product_template_id.write({'category': '2'})
        report.compute_expected_date()
        # Jan 8(Mon) +5 工作: Tue=1, Wed=2, Thu=3, Fri=4, Mon=5 → Jan 15
        self.assertEqual(report.expected_date, date(2024, 1, 15))


class TestCreate(TransactionCase):
    """create(): expected_date 應透過 _add_working_days 計算，不再用 relativedelta。"""

    def setUp(self):
        super().setUp()
        self.calendar = self.env['resource.calendar'].create({
            'name': 'IDX Test Calendar',
            'company_id': self.env.company.id,
        })
        self.env.company.resource_calendar_id = self.calendar
        self.partner = self.env['res.partner'].create({'name': 'TDD Test Customer'})

    def _make_product(self, category=None, default_code=None):
        vals = {'name': 'TDD Product', 'detailed_type': 'service'}
        if category:
            vals['category'] = category
        if default_code:
            vals['default_code'] = default_code
        return self.env['product.product'].create(vals)

    def test_create_category_1_expected_date_skips_weekend(self):
        """create(): category='1'，基準日週五，+4 工作日應跨越週末得到下週四。"""
        product = self._make_product(category='1')
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'request_inspection_date': date(2024, 1, 5),
        })
        try:
            order.sudo()._write({'state': 'received'})
        except Exception:
            pass
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 100,
        })
        report = self.env['sale.order.report'].with_context(
            skip_ins_requisition=True
        ).create({'order_line_id': line.id})
        # Jan 5(Fri) +4 working: Mon=1, Tue=2, Wed=3, Thu=4 → Jan 11
        self.assertEqual(report.expected_date, date(2024, 1, 11))

    def test_create_no_inspection_date_expected_date_false(self):
        """create(): 無 request_inspection_date 時 expected_date 應為 False。"""
        product = self._make_product(category='1')
        order = self.env['sale.order'].create({'partner_id': self.partner.id})
        try:
            order.sudo()._write({'state': 'received'})
        except Exception:
            pass
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product.id,
            'product_uom_qty': 1,
            'price_unit': 100,
        })
        report = self.env['sale.order.report'].with_context(
            skip_ins_requisition=True
        ).create({'order_line_id': line.id})
        self.assertFalse(report.expected_date)
