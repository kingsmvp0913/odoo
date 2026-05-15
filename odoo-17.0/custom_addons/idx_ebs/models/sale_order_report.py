import logging
from datetime import datetime, timedelta, date
import re

from odoo import api, models, fields, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta

from ..services.tcat_service import TcatService
from ..services.post_service import PostService

_logger = logging.getLogger(__name__)


class SaleOrderReport(models.Model):
    _name = "sale.order.report"
    _description = "送檢單/報告"
    _order = "order_line_id,name"

    order_id = fields.Many2one(
        comodel_name="sale.order",
        string="銷售訂單",
        ondelete="cascade",
        index=True,
    )
    state = fields.Selection(
        related="order_id.state", string="訂單狀態", store=True, copy=False
    )
    order_line_id = fields.Many2one(
        comodel_name="sale.order.line",
        string="訂單序號",
        ondelete="cascade",
        required=True,
        index=True,
    )
    product_template_id = fields.Many2one(
        "product.template",
        string="商品",
        related="order_line_id.product_template_id",
        store=True,
    )
    default_code = fields.Char(
        related="product_template_id.default_code", string="品號"
    )
    category = fields.Selection(
        related="product_template_id.category",
        string="送檢單類別",
    )
    inspect_number = fields.Char(string="送檢流水編號", copy=False)
    name = fields.Char(string="姓名")
    partner_id = fields.Many2one(related="order_id.partner_id", string="客戶")
    inspection_unit = fields.Char(string="送檢單位", readonly=True, copy=False)
    inspection_order = fields.Char(
        string="送檢單", default="檢體資料", readonly=True, copy=False
    )
    download_pdf_report = fields.Char(
        string="PDF報告", default="下載", readonly=True, copy=False
    )
    download_excel_report = fields.Char(
        string="Excel報告", default="下載", readonly=True, copy=False
    )
    upload_date = fields.Date(string="檔案建立日期", copy=False)
    note = fields.Char(string="備註", copy=False)
    mail = fields.Char(string="Mail寄送", copy=False)
    carrier = fields.Selection(
        string="物流",
        selection=[
            ("tcat", "黑貓"),
            ("post", "中華郵政"),
        ],
        copy=False,
    )
    resv_number = fields.Char(string="預約單號", copy=False)
    carrier_number = fields.Char(string="物流編號", copy=False)
    carrier_type = fields.Char(string="物流狀態", readonly=True, copy=False)
    intl_carrier = fields.Selection(
        string="國外物流",
        selection=[
            ("fedex", "FEDEX"),
            ("dhl", "DHL"),
            ("ups", "UPS"),
            ("sf", "順豐"),
            ("ems", "EMS"),
            ("other", "其他"),
        ],
        copy=False,
    )
    intl_carrier_number = fields.Char(string="國外物流編號", copy=False)
    download_date = fields.Date(string="報告下載日期", copy=False)
    partner_pick = fields.Boolean(string="客戶親取", default=False, copy=False)
    pic_personally = fields.Binary(string="親取照片", copy=False)
    pic_personally_filename = fields.Char(string="親取照片檔名", copy=False)
    pick_date = fields.Date(string="親取日期", readonly=True, copy=False)
    delivery_date = fields.Date(string="報告送達日", readonly=True, copy=False)
    fliphtml5_book_url = fields.Char(string="FlipHTML5 連結")
    expected_date = fields.Date(string="預計交貨日")

    def _get_public_holiday_dates(self, year: int) -> set:
        company = self.env.company
        calendar = company.resource_calendar_id
        if not calendar:
            return set()

        leaves = self.env['resource.calendar.leaves'].search([
            ('calendar_id', '=', calendar.id),
            ('resource_id', '=', False),
            ('date_from', '>=', fields.Datetime.to_datetime(str(year) + '-01-01 00:00:00')),
            ('date_from', '<',  fields.Datetime.to_datetime(str(year + 1) + '-01-01 00:00:00')),
        ])

        holiday_dates = set()
        for leave in leaves:
            d = leave.date_from.date()
            end = leave.date_to.date()
            while d <= end:
                holiday_dates.add(d)
                d += timedelta(days=1)
        return holiday_dates

    def _add_working_days(self, start_date, days: int, holiday_dates: set):
        current = start_date
        count = 0
        while count < days:
            current += timedelta(days=1)
            if current.weekday() not in (5, 6) and current not in holiday_dates:
                count += 1
        return current

    def compute_expected_date(self):
        for rec in self:
            base = rec.order_id.request_inspection_date
            if not base:
                rec.expected_date = False
                continue

            holiday_dates = self._get_public_holiday_dates(base.year)

            if rec.category == '1':
                days = 4
            elif rec.category == '2':
                days = 3
            else:
                days = 5

            rec.expected_date = self._add_working_days(base, days, holiday_dates)

    def _sanitize_filename(self, vals):
        """ 清理檔名中的空格與括號，避免 Odoo 17 JS 報錯 """
        if 'pic_personally_filename' in vals and vals['pic_personally_filename']:
            original_name = vals['pic_personally_filename']
            clean_name = re.sub(r'[() ]', '_', original_name)
            vals['pic_personally_filename'] = clean_name
        return vals

    def action_download_pdf(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/idx/report/download/{self.id}/pdf",
            "target": "new",
        }

    def action_download_excel(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/idx/report/download/{self.id}/excel",
            "target": "new",
        }

    def write(self, vals):
        # 處理檔名
        self._sanitize_filename(vals)
        # 必須在 super().write() 之前讀取原始值，
        # 否則寫入後 rec.pic_personally 已是新值，條件判斷會失效
        if "pic_personally" in vals:
            new_pic = vals.get("pic_personally")
            for rec in self:
                origin_pic = rec.pic_personally
                # 從無到有：設定今天的日期
                if not origin_pic and new_pic:
                    vals["pick_date"] = fields.Date.context_today(rec)
                # 從有到無：清空日期
                elif origin_pic and not new_pic:
                    vals["pick_date"] = False

        # 物流串接：在 super().write() 之前處理 carrier_type，
        # 確保快取或非同步查詢的結果能正確寫入 DB
        if not self.env.context.get("carrier") and (
            "carrier" in vals or "carrier_number" in vals
        ):
            # 處理 carrier_type 邏輯
            for rec in self:
                carrier = vals.get("carrier", rec.carrier)
                carrier_number = vals.get("carrier_number", rec.carrier_number)

                if carrier or carrier_number:
                    vals["carrier_type"] = False

                    cache_hours, cacheData = self.sudo().get_logistics_cache(
                        carrier=carrier, carrier_number=carrier_number
                    )
                    if cacheData:
                        expire_time = (
                            cacheData.create_date
                            + timedelta(hours=cache_hours)
                            + timedelta(hours=8)
                        ).strftime("%Y-%m-%d %H:%M:%S")

                        vals["carrier_type"] = cacheData.carrier_type

                        carrier_name = "黑貓" if carrier == "tcat" else "中華郵政"

                        self._notify_user_sync(
                            status=True,
                            message=f"{carrier_name}[{carrier_number}]，物流狀態已從暫存中取得，若需要更即時的物流狀態，請於 {expire_time} 後重新查詢。",
                        )
                    else:
                        self._notify_user_sync(
                            status=True,
                            message=f"正在為您查詢{'黑貓' if carrier == 'tcat' else '中華郵政'}之物流編號[{carrier_number}]的最新物流狀態，請稍候片刻。",
                        )
                        rec.with_delay(priority=5)._fetch_carrier_type(
                            uuid="",
                            origin_carrier=carrier,
                            origin_carrier_number=carrier_number,
                        )

        if "carrier_type" in vals:
            new_status = vals.get("carrier_type")
            for rec in self:
                # 狀態是「報告完成」或「報告已寄出」才允許改動日期
                if rec.state in ['reported', 'sent_report']:
                    carrier = vals.get("carrier", rec.carrier)
                    is_delivered = (
                            (carrier == "tcat" and new_status == "順利送達") or
                            (carrier == "post" and new_status == "投遞成功")
                    )

                    # 符合送達條件且原本沒日期才補上
                    if is_delivered and not rec.delivery_date:
                        vals["delivery_date"] = fields.Date.today()

                    # 如果狀態被清空，則清空日期
                    elif not new_status:
                        vals["delivery_date"] = False

        res = super().write(vals)
        self.mapped("order_line_id")._apply_auto_note()
        return res

    def unlink(self):
        lines = self.mapped("order_line_id")
        res = super().unlink()
        # 刪掉 report 後更新 line.note
        lines._apply_auto_note()
        return res

    def _fetch_carrier_type(
        self, uuid=None, origin_carrier=None, origin_carrier_number=None
    ):
        """
        取得物流狀態
        @param uuid: 任務識別碼
        @param origin_carrier_number: 原始物流編號
        """
        self.ensure_one()

        try:
            result = []
            service = TcatService() if self.carrier == "tcat" else PostService()
            result = service._fetch_carrier_type(
                env=self.env,
                carrier_number=origin_carrier_number,
            )
            self.env.cr.commit()
            carrier_type, message = "", "查無物流狀態"

            if result:
                message = result.get("message", "")
                if result["success"]:
                    carrier_type = result.get("carrier_type", "")
                    if (
                        origin_carrier == self.carrier
                        and origin_carrier_number == self.carrier_number
                    ):
                        self.with_context(carrier=True).write(
                            {"carrier_type": carrier_type}
                        )
                    _logger.info(f"物流狀態查詢成功: {message}")
                else:
                    _logger.error(message)

                # 從後台查詢物流狀態，發送通知
                if not uuid:
                    self._notify_user_sync(
                        status=result["success"],
                        message=(
                            f"查詢{'[黑貓]' if origin_carrier == 'tcat' else '[中華郵政]'}之物流編號[{origin_carrier_number}]，與資料庫中紀錄的物流資料不符，故物流狀態不做更新。請重新確認。"
                            if (
                                result
                                and result["success"]
                                and (
                                    origin_carrier != self.carrier
                                    or origin_carrier_number != self.carrier_number
                                )
                            )
                            else (
                                "物流狀態查詢成功，請重新整理頁面以查看最新狀態！"
                                if result and result["success"]
                                else message
                            )
                        ),
                    )

        except Exception as e:
            message = f"查詢物流狀態時發生錯誤!"
            _logger.error(f"查詢物流狀態時發生錯誤: {str(e)}")
        finally:
            self.env["logistics.cache"].create(
                {
                    "uuid": uuid or "",
                    "carrier": origin_carrier or "",
                    "carrier_number": origin_carrier_number or "",
                    "carrier_type": carrier_type or "",
                    "fetch_message": (
                        f"查詢{'[黑貓]' if origin_carrier == 'tcat' else '[中華郵政]'}之物流編號[{origin_carrier_number}]，與資料庫中紀錄的物流資料不符，故物流狀態不做更新。請重新確認。"
                        if (
                            result
                            and result["success"]
                            and (
                                origin_carrier != self.carrier
                                or origin_carrier_number != self.carrier_number
                            )
                        )
                        else message
                    ),
                }
            )

    @api.constrains("order_line_id")
    def _check_order_line_product(self):
        for rec in self:
            if not rec.order_line_id:
                continue

            product = rec.product_template_id

            # 必須是服務類
            if product.detailed_type != "service":
                raise UserError(
                    _(f"商品{product.display_name}，不是服務類商品，不可選擇!")
                )

            # 必須有檢測單類別
            if not product.category:
                raise UserError(
                    _(f"商品{product.display_name}，未設定檢測單類別，請先設定")
                )

    # 單身[檢體資料]按鈕
    def action_open_inspection_order(self):
        # 人類醫學
        if self.product_template_id.category == "0":
            model = "idx.test.requisition1"
        else:
            model = "idx.test.requisition2"

        requisition = self.env[model].search(
            [("order_report_id", "=", self.id)], limit=1
        )

        if not requisition:
            raise UserError(_("找不到對應的送檢單"))

        return {
            "type": "ir.actions.act_window",
            "name": "送檢單",
            "res_model": model,
            "view_mode": "form",
            "res_id": requisition.id,
            "target": "current",
        }

    # 產生送檢單資料
    @api.model_create_multi
    def create(self, vals_list):
        # 處理檔名
        for vals in vals_list:
            self._sanitize_filename(vals)
            # 預設交貨日期
            order_line_id = vals.get("order_line_id")
            if order_line_id:
                order_line_id = self.env["sale.order.line"].browse(order_line_id)
                order_id = order_line_id.order_id

                # 判斷狀態是否符合更新條件
                if order_id.state in ['received', 'active']:
                    base_date = order_id.request_inspection_date
                    holiday_dates = self._get_public_holiday_dates(base_date.year)
                    if order_line_id.product_template_id.category == '1':
                        expected_date = self._add_working_days(base_date, 4, holiday_dates)
                    elif order_line_id.product_template_id.category == '2':
                        expected_date = self._add_working_days(base_date, 3, holiday_dates)
                    else:
                        expected_date = self._add_working_days(base_date, 5, holiday_dates)
                    # 直接塞入準備建立的資料中
                    vals['expected_date'] = expected_date

        reports = super().create(vals_list)
        reports.mapped("order_line_id")._apply_auto_note()

        # 有skip_ins_requisition就不產生送檢單
        if self.env.context.get("skip_ins_requisition"):
            return reports

        for vals in vals_list:
            order_line_id = vals.get("order_line_id")
            if not order_line_id:
                continue

            order_line = self.env["sale.order.line"].browse(order_line_id)

            # 該訂單明細允許的最大數量
            max_qty = int(order_line.product_uom_qty or 0)

            # 已存在的送檢單數量
            exist_count = self.search_count([("order_line_id", "=", order_line.id)])

            # 確認送檢單數量
            if exist_count > max_qty:
                raise UserError(
                    _(
                        f"訂單明細商品 : {order_line.product_template_id.name}，"
                        f"數量為 {max_qty}，無法建立 {exist_count} 筆送檢單。"
                    )
                )

        for report in reports:
            carrier, carrier_number = report.carrier, report.carrier_number
            product = report.product_template_id

            # 物流狀態查詢(前台建立時會帶skip_ins_requisition，故不會重複觸發)
            if carrier and carrier_number:
                cache_hours, cacheData = self.sudo().get_logistics_cache(
                    carrier=carrier, carrier_number=carrier_number
                )
                if cacheData:
                    expire_time = (
                        cacheData.create_date
                        + timedelta(hours=cache_hours)
                        + timedelta(hours=8)
                    ).strftime("%Y-%m-%d %H:%M:%S")

                    report.with_context({"carrier": True}).write(
                        {"carrier_type": cacheData.carrier_type}
                    )

                    carrier_name = "黑貓" if carrier == "tcat" else "中華郵政"

                    self._notify_user_sync(
                        status=True,
                        message=f"{carrier_name}[{carrier_number}]，物流狀態已從暫存中取得，若需要更即時的物流狀態，請於 {expire_time} 後重新查詢。",
                    )
                else:
                    self._notify_user_sync(
                        status=True,
                        message=f"正在為您查詢{'黑貓' if carrier == 'tcat' else '中華郵政'}之物流編號[{carrier_number}]的最新物流狀態，請稍候片刻。",
                    )
                    report.with_delay(priority=5)._fetch_carrier_type(
                        uuid="",
                        origin_carrier=carrier,
                        origin_carrier_number=carrier_number,
                    )

            # 要服務類商品
            if product.detailed_type != "service":
                continue

            # 要有檢測單類別
            if not product.category:
                continue

            # 確認model
            if product.category == "0":
                Model = report.env["idx.test.requisition1"]
                name_field = "patient_name"
            else:
                Model = report.env["idx.test.requisition2"]
                name_field = "owner_name"

            # 防止重複建立
            exists = Model.search([("order_report_id", "=", report.id)], limit=1)
            if exists:
                continue

            # 建立送檢單
            Model.create(
                {
                    "order_id": report.order_id.id,
                    "order_report_id": report.id,
                    name_field: report.name,
                }
            )

        return reports

    def get_logistics_cache(self, carrier, carrier_number):
        """
        取得物流快取資料
        @param carrier: 物流方式
        @param carrier_number: 物流編號
        @return: [list] [cache_hours, cacheData]
        """
        # 將物流狀態暫存兩小時，避免頻繁查詢
        cache_hours, cacheData = 2, None

        cacheData = (
            self.env["logistics.cache"]
            .sudo()
            .search(
                [
                    ("carrier", "=", carrier),
                    ("carrier_number", "=", carrier_number),
                    ("carrier_type", "!=", ""),
                    (
                        "create_date",
                        ">=",
                        fields.Datetime.to_string(
                            fields.Datetime.now() - timedelta(hours=cache_hours)
                        ),
                    ),
                ],
                limit=1,
            )
        )
        return [cache_hours, cacheData]

    @api.model
    def _cron_update_carrier_type(self) -> None:
        """
        排程：批次更新所有設有物流編號之送檢單的物流狀態。
        相同 (carrier, carrier_number) 組合只查詢一次 API，
        其餘同組記錄從 cache 取值，不重複打 API。
        """
        COMPLETED_STATUS = {"tcat": "順利送達", "post": "投遞成功"}

        records = self.search(
            [
                ("carrier", "!=", False),
                ("carrier_number", "!=", False),
            ]
        ).filtered(lambda r: r.carrier_type != COMPLETED_STATUS.get(r.carrier))
        _logger.info(f"[排程] 開始批次更新物流狀態，共 {len(records)} 筆")

        queried = set()
        for rec in records:
            key = (rec.carrier, rec.carrier_number)
            if key not in queried:
                # 第一筆：打 API，結果會寫入 cache
                rec._fetch_carrier_type(
                    uuid="cron",
                    origin_carrier=rec.carrier,
                    origin_carrier_number=rec.carrier_number,
                )
                queried.add(key)
            else:
                # 後續同組：從 cache 取值直接寫入，不重複打 API
                _, cache_data = self.sudo().get_logistics_cache(
                    carrier=rec.carrier, carrier_number=rec.carrier_number
                )
                if cache_data:
                    rec.with_context(carrier=True).write(
                        {"carrier_type": cache_data.carrier_type}
                    )

        _logger.info("[排程] 物流狀態批次更新完成")

    def _notify_user_sync(self, status=False, message="") -> None:
        """
        發送右上角的彈出通知
        @param status: 串接物流狀態
        """
        if not status:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "warning",
                    "title": "串接物流狀態",
                    "message": message,
                },
            )
        else:
            self.env["bus.bus"]._sendone(
                self.env.user.partner_id,
                "simple_notification",
                {
                    "type": "success",
                    "title": "串接物流狀態",
                    "message": message,
                },
            )

        self.env.cr.commit()

    def _check_duplicate_submission(self):
        """檢查是否有90天內重複的送檢紀錄"""
        today = datetime.today()
        ninety_days_ago = today - timedelta(days=90)

        for rec in self:
            model_name = 'idx.test.requisition1' if rec.category == '0' else 'idx.test.requisition2'
            requisition_id = self.env[model_name].search([('order_report_id', '=', rec.id)], limit=1)

            if not requisition_id:
                continue

            domain = [
                ('patient_name', '=', requisition_id.patient_name),
                ('create_date', '>=', ninety_days_ago),
                ('id', '!=', requisition_id.id)
            ]

            if rec.category == '0':
                domain.append(('birth_date', '=', requisition_id.birth_date))
            else:
                domain.append(('owner_name', '=', requisition_id.owner_name))

            if self.env[model_name].search_count(domain) > 0:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("重複送檢警告"),
                        "message": _("該訂單於90天內已有送檢紀錄。"),
                        "sticky": True,
                        "type": "warning",
                        "next": {"type": "ir.actions.client", "tag": "soft_reload"},
                    },
                }
        return None