from odoo import models, fields, api
import pyodbc
from datetime import date, datetime
import logging
from odoo.exceptions import ValidationError, UserError, AccessError, RedirectWarning
from odoo.tools.translate import _
import pytz
import re

_logger = logging.getLogger(__name__)


class WFMapping(models.Model):
    _name = "wf.mapping"
    _description = "WF檔案對照表"
    _rec_name = "wf_model_id"

    odoo_model_id = fields.Many2one("ir.model", string="Odoo型號", index=True)
    odoo_model_model = fields.Char(
        string="Odoo型號代號", related="odoo_model_id.model", store=True
    )
    odoo_model_name = fields.Char(
        string="Odoo型號說明", related="odoo_model_id.name", index=True
    )
    wf_model_id = fields.Char(string="WF檔案代號", required=True, index=True)
    wf_model_name = fields.Char(string="WF檔案名稱", required=True, index=True)
    wf_prid = fields.Char(string="WF程式代號", required=True, index=True)
    line_ids = fields.One2many(
        "wf.mapping.line", "mapping_id", string="欄位對照", copy=False, auto_join=True
    )
    sub_ids = fields.One2many(
        "wf.mapping.sub", "mapping_id", string="副表對照", copy=False
    )
    extra_domain = fields.Char(
        string="額外Domain",
        help="額外的搜尋條件，格式為Odoo的domain語法，例如：[('field_name', '=', 'value')]",
    )
    main_type = fields.Selection(
        [("1", "主檔單頭"), ("2", "主檔單身"), ("3", "交易單頭"), ("4", "交易單身")],
        string="主檔/交易類型",
    )
    code_type = fields.Selection([("1", "日編"), ("2", "月編")], string="編碼方式")
    year_digits = fields.Selection(
        [("2", "西元後2碼"), ("4", "西元4碼")], string="年碼數"
    )
    serial_digits = fields.Integer(string="流水碼數")
    code_format = fields.Char(string="編碼格式", readonly=True, store=True)
    wf_s_field = fields.Char(string="WF單別欄位", help="存放單別的欄位名稱")
    wf_slip = fields.Char(string="WF單別")
    wf_b_field = fields.Char(string="WF單號欄位", help="存放單號的欄位名稱")
    odoo_s_field = fields.Many2one(
        "ir.model.fields",
        string="Odoo對應WF單別欄位",
        domain=[("model_id", "=", odoo_model_id)],
    )
    odoo_b_field = fields.Many2one(
        "ir.model.fields",
        string="Odoo對應WF單號欄位",
        domain=[("model_id", "=", odoo_model_id)],
    )
    sync_info_ids = fields.One2many(
        "wf.mapping.sync.info", "mapping_id", string="同步後資訊紀錄"
    )

    _sql_constraints = [
        ("wf_model_id_unique", "unique(wf_model_id)", "WF檔案代號必須唯一！")
    ]

    @api.onchange("main_type", "code_type", "year_digits", "serial_digits")
    def _onchange_code_format(self):
        if self.main_type == "3":
            year_len = int(self.year_digits) if self.year_digits else 2
            serial_digits = self.serial_digits if self.serial_digits else 1
            if self.code_type == "1":  # 日編
                prefix_len = year_len + 4
                fmt = ("YY" if self.year_digits == "2" else "YYYY") + "MMDD"
            else:  # 月編
                prefix_len = year_len + 2
                fmt = ("YY" if self.year_digits == "2" else "YYYY") + "MM"
            max_serial = 11 - prefix_len
            if serial_digits > max_serial:
                self.serial_digits = max_serial
                serial_digits = max_serial
            serial_fmt = "N" * serial_digits
            self.code_format = fmt + serial_fmt
        else:
            self.code_format = False
            self.code_type = False
            self.year_digits = False
            self.serial_digits = False

    @api.constrains("main_type", "code_type", "year_digits", "serial_digits")
    def _check_code_format_rules(self):
        for rec in self:
            if rec.main_type == "3":
                year_len = int(rec.year_digits)
                prefix_len = year_len + (4 if rec.code_type == "1" else 2)
                if rec.serial_digits > 11 - prefix_len:
                    raise ValidationError("流水碼數過長，總長度不可超過11碼。")

    def _odoo_to_wf_create(
        self, wf_model, record_ids, database, wf_company, wf_slip=None
    ):
        """通用方法：將指定模型的資料同步到 WF 資料庫"""
        # 新增判斷 context 是否要跳過重複主表
        skip_duplicate = self.env.context.get("skip_duplicate_main", False)
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            return False
        model_name = mapping.odoo_model_model
        records = (
            self.env[model_name]
            .sudo()
            .search([("id", "in", record_ids)] + eval(mapping.extra_domain or "[]"))
        )
        if not records.exists():
            raise ValidationError(_("無odoo資料需要同步!"))

        connection_params = self._get_connection_parameters(database)
        failed_records = []
        main_batch = []
        sub_batches = {}
        slip_numbers = {}  # 用於記錄每筆主表的單號

        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                # **若為交易主檔新增，表示有單據自動編碼的議題，需要連到異質DB取出目前最大碼**
                if mapping.main_type == "3":
                    code_field = mapping.wf_s_field
                    number_field = mapping.wf_b_field
                    code_val = wf_slip if wf_slip else mapping.wf_slip
                    now = datetime.now()
                    year_fmt = "%y" if mapping.year_digits == "2" else "%Y"
                    prefix = (
                        str(now.strftime(year_fmt + "%m%d"))
                        if mapping.code_type == "1"
                        else str(now.strftime(year_fmt + "%m"))
                    )
                    serial_digits = int(mapping.serial_digits or 3)
                    sql = (
                        f"SELECT MAX(RIGHT([{number_field}], {serial_digits})) "
                        f"FROM {mapping.wf_model_id} WHERE [{code_field}] = ? AND LEFT([{number_field}], {len(prefix)}) = ?"
                    )
                    cursor.execute(sql, (code_val, prefix))
                    row = cursor.fetchone()
                    max_code = int(row[0]) if row and row[0] else 0
                    new_slip_num = str(prefix) + str(max_code + 1).zfill(serial_digits)
                else:
                    new_slip_num = None

                # 準備主表與明細資料
                for record in records:
                    columns, values, condition_where = (
                        mapping._pre_ins_columns_and_values(
                            record,
                            connection_params["creator"],
                            connection_params["usr_group"],
                            wf_company,
                            mapping,
                            cursor,
                            slip_num=new_slip_num,
                            sync_method="ins",
                        )
                    )
                    main_batch.append(
                        (
                            columns,
                            values,
                            record.id,
                            condition_where,
                            record.display_name,
                        )
                    )
                    slip_numbers[record.id] = new_slip_num  # 記錄單號

                    for sub in mapping.sub_ids:
                        sub_mapping = (
                            self.env["wf.mapping"]
                            .sudo()
                            .search([("wf_model_id", "=", sub.wf_model_id)], limit=1)
                        )
                        sub_records = (
                            record
                            if sub.is_same_parent
                            else getattr(
                                record, sub.odoo_field_id.name, []
                            ).filtered_domain(eval(sub_mapping.extra_domain or "[]"))
                        )
                        sub_batches.setdefault(record.id, []).extend(
                            [
                                sub._prepare_sub_batch(
                                    sub_mapping,
                                    line,
                                    connection_params["creator"],
                                    connection_params["usr_group"],
                                    wf_company,
                                    mapping,
                                    sub,
                                    record,
                                    cursor,
                                    slip_num=new_slip_num,
                                )
                                for line in sub_records
                            ]
                        )
                    if mapping.main_type == "3":
                        new_slip_num = str(int(new_slip_num) + 1)  # 更新下一個單號

                # 開始寫入MSSQL
                success_main_ids = []
                for (
                    columns,
                    values,
                    record_id,
                    condition_where,
                    record_display_name,
                ) in main_batch:
                    # 檢查重複
                    if not mapping._check_duplicate_key(
                        cursor, condition_where, mapping.wf_model_id
                    ):
                        if skip_duplicate:
                            continue  # 直接跳過，不記錄錯誤
                        error_msg = _("WF 檔案表 %s 已存在 %s 的資料。") % (
                            record_display_name,
                            mapping.wf_model_name,
                        )
                        failed_records.append(
                            {
                                "record_id": record_id,
                                "display_name": record_display_name,
                                "error": error_msg,
                                "type": "main",
                            }
                        )
                        continue
                    self._batch_insert_records(
                        cursor, [(columns, values)], mapping.wf_model_id
                    )
                    success_main_ids.append(record_id)

                for main_id in success_main_ids:
                    for sub_batch in sub_batches.get(main_id, []):
                        try:
                            self._batch_insert_records(
                                cursor,
                                [(sub_batch["ins_columns"], sub_batch["ins_values"])],
                                sub_batch["wf_model_id"],
                            )
                        except Exception as e:
                            print(f"Error inserting sub batch for main_id {main_id}: {e}")
                            failed_records.append(
                                {
                                    "record_id": main_id,
                                    "display_name": sub_batch.get("values", [])[
                                        0
                                    ],  # 假設第一個值為 display_name
                                    "error": str(e),
                                    "type": "sub ins",
                                }
                            )

        except Exception as e:
            self._handle_error(e)

        if failed_records:
            error_messages = "\n".join(
                [
                    f"【資料】{item.get('display_name','')} ，【主副表】{item['type']}{'【副表】: '+str(item['line_index']) if item.get('line_index') is not None else ''}: {item['error']}"
                    for item in failed_records
                ]
            )
            raise ValidationError(_("資料同步失敗清單：\n") + error_messages)

        self._update_sync_info_fields(mapping, record_ids, wf_slip, slip_numbers)

        return True

    def _odoo_to_wf_update(self, wf_model, record_ids, database, wf_company):
        """通用方法：將指定模型的資料更新到 WF 資料庫"""
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            return False
        model_name = mapping.odoo_model_model
        records = (
            self.env[model_name]
            .sudo()
            .search([("id", "in", record_ids)] + eval(mapping.extra_domain or "[]"))
        )
        if not records.exists():
            raise ValidationError(_("無odoo資料需要同步!"))

        connection_params = self._get_connection_parameters(database)
        failed_records = []
        main_batch = []
        sub_batches = {}

        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                # 準備主表與明細資料
                for record in records:
                    columns, values, condition_where = (
                        mapping._pre_ins_columns_and_values(
                            record,
                            connection_params["creator"],
                            connection_params["usr_group"],
                            wf_company,
                            mapping,
                            cursor,
                            slip_num=None,
                            sync_method="upd",
                        )
                    )
                    main_batch.append(
                        (
                            columns,
                            values,
                            record.id,
                            condition_where,
                            record.display_name,
                        )
                    )

                    for sub in mapping.sub_ids:
                        sub_mapping = (
                            self.env["wf.mapping"]
                            .sudo()
                            .search([("wf_model_id", "=", sub.wf_model_id)], limit=1)
                        )
                        sub_records = (
                            record
                            if sub.is_same_parent
                            else getattr(
                                record, sub.odoo_field_id.name, []
                            ).filtered_domain(eval(sub_mapping.extra_domain or "[]"))
                        )
                        sub_batches.setdefault(record.id, []).extend(
                            [
                                sub._prepare_sub_batch(
                                    sub_mapping,
                                    line,
                                    connection_params["creator"],
                                    connection_params["usr_group"],
                                    wf_company,
                                    mapping,
                                    sub,
                                    record,
                                    cursor,
                                    slip_num=None,
                                )
                                for line in sub_records
                            ]
                        )

                # 開始更新MSSQL
                success_main_ids = []
                for (
                    columns,
                    values,
                    record_id,
                    condition_where,
                    record_display_name,
                ) in main_batch:
                    if mapping._check_duplicate_key(
                        cursor, condition_where, mapping.wf_model_id
                    ):
                        msg = _(
                            "此筆資料過去已有同步WF，但現在WF查無此筆資料，無法將Odoo資料同步修改到WF。"
                        )
                        failed_records.append(
                            {
                                "record_id": record_id,
                                "display_name": record_display_name,
                                "error": msg,
                                "type": "main",
                            }
                        )
                        continue
                    self._batch_update_records(
                        cursor,
                        [(columns, values)],
                        mapping.wf_model_id,
                        condition_where,
                    )
                    success_main_ids.append(record_id)

                sub_batches_grouped = {}
                for main_id in success_main_ids:
                    for sub_batch in sub_batches.get(main_id, []):
                        wf_model_id = sub_batch["wf_model_id"]
                        sub_batches_grouped.setdefault(main_id, {}).setdefault(
                            wf_model_id, []
                        ).append(sub_batch)

                for main_id, grouped_batches in sub_batches_grouped.items():
                    for wf_model_id, sub_batch_list in grouped_batches.items():
                        excluded_records_condition = ""
                        main_condition = ""

                        if sub_batch_list:
                            main_condition = sub_batch_list[0].get(
                                "main_condition_where", ""
                            )

                        for sub_batch in sub_batch_list:
                            try:
                                if not mapping._check_duplicate_key(
                                    cursor,
                                    sub_batch["condition_where"],
                                    sub_batch["wf_model_id"],
                                ):
                                    self._batch_update_records(
                                        cursor,
                                        [
                                            (
                                                sub_batch["upd_columns"],
                                                sub_batch["upd_values"],
                                            )
                                        ],
                                        sub_batch["wf_model_id"],
                                        sub_batch["condition_where"],
                                    )
                                else:
                                    self._batch_insert_records(
                                        cursor,
                                        [
                                            (
                                                sub_batch["ins_columns"],
                                                sub_batch["ins_values"],
                                            )
                                        ],
                                        sub_batch["wf_model_id"],
                                    )
                            except Exception as e:
                                display_name = (
                                    sub_batch.get("display_name") or f"ID: {main_id}"
                                )
                                failed_records.append(
                                    {
                                        "record_id": main_id,
                                        "display_name": display_name,
                                        "error": str(e),
                                        "type": "sub ins or upd",
                                    }
                                )

                            # 累計排除條件
                            if sub_batch["condition_where"]:
                                excluded_records_condition = (
                                    f"{excluded_records_condition} OR {sub_batch['condition_where']}"
                                    if excluded_records_condition
                                    else sub_batch["condition_where"]
                                )

                        # 删除
                        if main_condition and excluded_records_condition:
                            try:
                                delete_where = f"{main_condition} AND NOT ({excluded_records_condition})"
                                delete_query = (
                                    f"DELETE FROM {wf_model_id} WHERE {delete_where}"
                                )
                                cursor.execute(delete_query)
                            except Exception as e:
                                display_name = f"WF檔案: {wf_model_id}, 主ID: {main_id}"
                                failed_records.append(
                                    {
                                        "record_id": main_id,
                                        "display_name": display_name,
                                        "error": str(e),
                                        "type": "sub del",
                                    }
                                )
        except Exception as e:
            self._handle_error(e)

        if failed_records:
            error_messages = "\n".join(
                [
                    f"- Record ID: {item['record_id']}\n  Display Name: {item.get('display_name', '')}\n  Type: {item['type']}{' Line: ' + str(item['line_index']) if item.get('line_index') is not None else ''}\n  Error: {item['error']}"
                    for item in failed_records
                ]
            )
            formatted_message = (
                _("以下資料更新同步失敗：\n\n以下是錯誤清單：\n\n") + error_messages
            )
            raise ValidationError(formatted_message)

        self._update_sync_info_fields(mapping, record_ids, slip_numbers=None)

        return True

    def _odoo_to_wf_update2(
        self, wf_model, record_ids, database, wf_company, columns, values
    ):
        """通用方法：將特定資料更新到 WF 資料庫"""
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            return False
        model_name = mapping.odoo_model_model
        records = (
            self.env[model_name]
            .sudo()
            .search([("id", "in", record_ids)] + eval(mapping.extra_domain or "[]"))
        )
        if not records.exists():
            raise ValidationError(_("無odoo資料需要同步!"))

        connection_params = self._get_connection_parameters(database)
        failed_records = []

        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                # 準備單表資料
                for record in records:
                    _, _, condition_where = mapping._pre_ins_columns_and_values(
                        record,
                        connection_params["creator"],
                        connection_params["usr_group"],
                        wf_company,
                        mapping,
                        cursor,
                        slip_num=None,
                        sync_method="upd",
                    )

                    # 開始更新MSSQL
                    success_main_ids = []
                    if mapping._check_duplicate_key(
                        cursor, condition_where, mapping.wf_model_id
                    ):
                        msg = _(
                            "此筆資料過去已有同步WF，但現在WF查無此筆資料，無法將Odoo資料同步修改到WF。"
                        )
                        failed_records.append(
                            {
                                "record_id": record.id,
                                "display_name": record.display_name,
                                "error": msg,
                                "type": "main",
                            }
                        )
                        continue
                    self._batch_update_records(
                        cursor,
                        [(columns, values)],
                        mapping.wf_model_id,
                        condition_where,
                    )
                    success_main_ids.append(record.id)

        except Exception as e:
            self._handle_error(e)

        if failed_records:
            error_messages = "\n".join(
                [
                    f"- Record ID: {item['record_id']}\n  Display Name: {item.get('display_name', '')}\n  Type: {item['type']}{' Line: ' + str(item['line_index']) if item.get('line_index') is not None else ''}\n  Error: {item['error']}"
                    for item in failed_records
                ]
            )
            formatted_message = (
                _("以下資料更新同步失敗：\n\n以下是錯誤清單：\n\n") + error_messages
            )
            raise ValidationError(formatted_message)

        self._update_sync_info_fields(mapping, record_ids, slip_numbers=None)

        return True

    def _odoo_to_wf_delete(self, wf_model, record_ids, database, wf_company):
        """通用方法：刪除 WF 資料庫中指定模型的資料"""
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            return False
        model_name = mapping.odoo_model_model
        records = (
            self.env[model_name]
            .sudo()
            .search([("id", "in", record_ids)] + eval(mapping.extra_domain or "[]"))
        )
        if not records.exists():
            raise ValidationError(_("無odoo資料需要同步!"))

        connection_params = self._get_connection_parameters(database)
        failed_records = []
        main_batch = []
        sub_batches = {}

        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                # 準備主表與明細資料
                for record in records:
                    columns, values, condition_where = (
                        mapping._pre_ins_columns_and_values(
                            record,
                            connection_params["creator"],
                            connection_params["usr_group"],
                            wf_company,
                            mapping,
                            cursor,
                            slip_num=None,
                            sync_method="upd",
                        )
                    )
                    main_batch.append(
                        (
                            columns,
                            values,
                            record.id,
                            condition_where,
                            record.display_name,
                        )
                    )

                    for sub in mapping.sub_ids:
                        sub_mapping = (
                            self.env["wf.mapping"]
                            .sudo()
                            .search([("wf_model_id", "=", sub.wf_model_id)], limit=1)
                        )
                        sub_records = (
                            record
                            if sub.is_same_parent
                            else getattr(
                                record, sub.odoo_field_id.name, []
                            ).filtered_domain(eval(sub_mapping.extra_domain or "[]"))
                        )
                        sub_batches.setdefault(record.id, []).extend(
                            [
                                sub._prepare_sub_batch(
                                    sub_mapping,
                                    line,
                                    connection_params["creator"],
                                    connection_params["usr_group"],
                                    wf_company,
                                    mapping,
                                    sub,
                                    record,
                                    cursor,
                                    slip_num=None,
                                )
                                for line in sub_records
                            ]
                        )

                # 開始刪除MSSQL
                for *_, condition_where, _ in main_batch:
                    try:
                        cursor.execute(
                            f"DELETE FROM {wf_model} WHERE {condition_where}"
                        )
                    except Exception as e:
                        display_name = f"WF檔案: {wf_model}, 主ID: {record.id}"
                        failed_records.append(
                            {
                                "record_id": record.id,
                                "display_name": display_name,
                                "error": str(e),
                                "type": "sub del",
                            }
                        )

                for main_id, sub_list in sub_batches.items():
                    for sub in sub_list:
                        try:
                            cursor.execute(
                                f"DELETE FROM {sub['wf_model_id']} WHERE {sub['condition_where']}"
                            )
                        except Exception as e:
                            display_name = (
                                f"WF檔案: {sub['wf_model_id']}, 主ID: {main_id}"
                            )
                            failed_records.append(
                                {
                                    "record_id": main_id,
                                    "display_name": display_name,
                                    "error": str(e),
                                    "type": "sub del",
                                }
                            )

        except Exception as e:
            self._handle_error(e)

        if failed_records:
            error_messages = "\n".join(
                [
                    f"- Record ID: {item['record_id']}\n  Display Name: {item.get('display_name', '')}\n  Type: {item['type']}\n  Error: {item['error']}"
                    for item in failed_records
                ]
            )
            formatted_message = (
                _("以下資料還原失敗：\n\n以下是錯誤清單：\n\n") + error_messages
            )
            raise ValidationError(formatted_message)

        self._update_sync_info_fields(mapping, record_ids, slip_numbers=None)

        return True

    def _handle_error(self, error):
        """統一錯誤處理"""
        _logger.error(f"MSSQL 連線或操作失敗： {str(error)}")
        raise ValidationError(_("MSSQL 連線或操作失敗：%s") % str(error))

    def _batch_insert_records(self, cursor, batch_data, wf_model_id):
        """批次插入資料"""
        for columns, values in batch_data:
            column_names = ", ".join(columns)
            placeholders = ", ".join(["?"] * len(values))
            cursor.executemany(
                f"INSERT INTO {wf_model_id} ({column_names}) VALUES ({placeholders})",
                [values],
            )

    def _batch_update_records(self, cursor, batch_data, wf_model_id, condition_where):
        """批次插入資料"""
        for columns, values in batch_data:
            update_query = (
                f"UPDATE {wf_model_id} SET "
                + ", ".join([f"{col} = ?" for col in columns])
                + f" WHERE ({condition_where})"
            )
            cursor.executemany(update_query, [values])

    def _pre_ins_columns_and_values(
        self,
        record,
        connection_creator,
        connection_usr_group,
        company_name,
        mapping,
        cursor,
        slip_num=None,
        sync_method="ins",
    ):
        """準備欄位與值"""

        # 準備 key 值的判斷條件
        key_conditions = [
            f"({line.wf_field_code} = '{self._get_wf_value(record, line, cursor, mapping_slip=mapping.wf_slip, slip_num=slip_num, s_field_id=mapping.wf_s_field, b_field_id=mapping.wf_b_field)}')"
            for line in self.line_ids.filtered(lambda l: l.wf_key)
            if self._get_wf_value(
                record,
                line,
                cursor,
                mapping_slip=mapping.wf_slip,
                slip_num=slip_num,
                s_field_id=mapping.wf_s_field,
                b_field_id=mapping.wf_b_field,
            )
            is not None
        ]
        condition_where = " AND ".join(key_conditions) if key_conditions else ""

        if sync_method == "ins":
            columns = [line.wf_field_code for line in self.line_ids]
            values = [
                self._get_wf_value(
                    record,
                    line,
                    cursor,
                    mapping_slip=mapping.wf_slip,
                    slip_num=slip_num,
                    s_field_id=mapping.wf_s_field,
                    b_field_id=mapping.wf_b_field,
                )
                for line in self.line_ids
            ]
            fixed_columns = ["COMPANY", "CREATOR", "USR_GROUP", "CREATE_DATE", "FLAG"]
            fixed_values = [
                company_name,
                connection_creator,
                connection_usr_group,
                datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y%m%d"),
                1,
            ]
        else:
            columns = [
                line.wf_field_code
                for line in self.line_ids.filtered(
                    lambda l: l.wf_key is False and l.snyc_type == "F"
                )
            ]
            values = [
                self._get_wf_value(
                    record,
                    line,
                    cursor,
                    mapping_slip=mapping.wf_slip,
                    slip_num=slip_num,
                    s_field_id=mapping.wf_s_field,
                    b_field_id=mapping.wf_b_field,
                )
                for line in self.line_ids.filtered(
                    lambda l: l.wf_key is False and l.snyc_type == "F"
                )
            ]
            fixed_columns = ["MODIFIER", "MODI_DATE", "FLAG"]
            fixed_values = [
                connection_creator,
                datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y%m%d"),
                2,
            ]

        return columns + fixed_columns, values + fixed_values, condition_where

    def _get_wf_value(
        self,
        record,
        line,
        cursor=None,
        mapping_slip=None,
        slip_num=None,
        s_field_id=None,
        b_field_id=None,
    ):
        val = lambda name, default=None: getattr(record, name, default)
        if line.snyc_type == "F":
            ttype = line.odoo_field_ttype

            if mapping_slip and s_field_id and line.wf_field_code == s_field_id:
                field_value = val(line.odoo_field_name)

                return (
                    field_value
                    if isinstance(field_value, str)
                    else getattr(field_value, line.odoo_related_name, mapping_slip)
                )
            if slip_num and b_field_id and line.wf_field_code == b_field_id:
                return slip_num

            if ttype == "boolean":
                return "Y" if val(line.odoo_field_name, False) else "N"
            if ttype == "date" or ttype == "datetime":
                date = val(line.odoo_field_name)
                return date.strftime("%Y%m%d") if date else ""
            if ttype in ["float", "integer"]:
                return val(line.odoo_field_name, 0) or 0
            if ttype == "text":
                return val(line.odoo_field_name, "") or ""
            if ttype == "char":
                return val(line.odoo_field_name, "") or ""
            if line.odoo_field_relation:
                related = val(line.odoo_field_name)
                return getattr(related, line.odoo_related_name, "") if related else ""
            return val(line.odoo_field_name, "")
        if line.snyc_type == "C":
            return line.wf_def_c
        if line.snyc_type == "N":
            return line.wf_def_n
        if line.snyc_type == "D":
            fmt = (line.wf_def_d or "").upper()
            now = datetime.now()
            fmt_map = {
                "YYYY": "%Y",
                "YY": "%y",
                "MM": "%m",
                "DD": "%d",
                "YYMM": "%y%m",
                "YYYYMM": "%Y%m",
                "YYMMDD": "%y%m%d",
                "YYYYMMDD": "%Y%m%d",
                "MMDD": "%m%d",
            }
            if fmt in fmt_map:
                return now.strftime(fmt_map[fmt])
            try:
                fmt_pattern = re.sub(
                    r"(YYYY|YY|MM|DD)", lambda m: fmt_map[m.group(0)], fmt
                )
                return now.strftime(fmt_pattern)
            except Exception:
                return now.strftime("%Y%m%d")
        if line.snyc_type == "B":
            return line.wf_def_b
        if line.snyc_type == "S":
            return " "
        if line.snyc_type == "A":

            def replacer(match):
                code = match.group(1)
                mapping_line = line.mapping_id.line_ids.filtered(
                    lambda l: l.wf_field_code == code
                )
                return (
                    self._get_wf_value(
                        record,
                        mapping_line[0],
                        cursor,
                        mapping_slip=None,
                        slip_num=None,
                        s_field_id=None,
                        b_field_id=None,
                    )
                    if mapping_line
                    else ""
                )

            return re.sub(r"\{([A-Za-z0-9_]+)\}", replacer, line.wf_def_a or "")

        if line.snyc_type == "W":
            orign_code = line.wf_orign_field
            orign_line = line.mapping_id.line_ids.filtered(
                lambda l: l.wf_field_code == orign_code
            )
            if not orign_line:
                return ""
            orign_value = self._get_wf_value(
                record,
                orign_line[0],
                cursor,
                mapping_slip=None,
                slip_num=None,
                s_field_id=None,
                b_field_id=None,
            )
            if not (
                line.wf_related_model
                and line.wf_related_key
                and line.wf_related_field
                and orign_value
            ):
                return ""
            sql = f"SELECT {line.wf_related_field} FROM {line.wf_related_model} WHERE {line.wf_related_key} = ?"
            try:
                cursor.execute(sql, orign_value)
                row = cursor.fetchone()
                return row[0] if row else ""
            except Exception as e:
                _logger.error(f"WF關聯查詢失敗: {str(e)}")
                return ""

        return ""

    def _check_duplicate_key(self, cursor, condition_where, wf_model_id):
        """檢查是否有重複的 KEY"""
        if not condition_where:
            return True  # 如果沒有條件，直接返回 True

        query = f"SELECT COUNT(*) FROM {wf_model_id} WHERE {condition_where}"
        try:
            cursor.execute(query)
            result = cursor.fetchone()
            return result[0] == 0  # 回傳 False 表示有重複值，True 表示無重複
        except Exception as e:
            _logger.error(f"Error checking duplicate key: {str(e)}")
            raise ValidationError(_("Error checking duplicate key: %s") % str(e))

    def _get_connection_parameters(self, database):
        """獲取 MSSQL 連線參數"""

        # 取得 WF 資料庫連線設定
        driver = self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.driver")
        server_ip = (
            self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.server_ip")
        )
        username = self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.username")
        password = self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.password")
        creator = self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.creator")
        usr_group = (
            self.env["ir.config_parameter"].sudo().get_param("idx_wf_sync.usr_group")
        )

        if not driver or not server_ip or not username or not password or not database:
            raise ValidationError(
                _(
                    "請先設定 WF MSSQL 伺服器連線資訊 (driver, server_ip, username, password, database)。"
                )
            )
        return {
            "connection_string": f"DRIVER={driver};SERVER={server_ip};PORT=1433;DATABASE={database};UID={username};PWD={password};Encrypt=no;TrustServerCertificate=yes;TDS_Version=7.1",
            "creator": creator,
            "usr_group": usr_group,
        }

    def _wf_to_odoo_update_part(
        self,
        wf_model,
        return_fields,
        key_fields,
        key_values_list,
        odoo_model,
        odoo_key_fields,
        wf_db,
        lines,
    ):
        """
        批次從 WF 查詢特定資料，根據 mapping 對照表，將資料同步到 Odoo 指定模型中的指定欄位
        :param wf_model: WF 資料表名
        :param return_fields: 需要查詢的 WF 欄位列表
        :param key_fields: WF 查詢用 key 欄位列表
        :param key_values_list: 多組 key 值列表 (list of tuple)
        :param odoo_model: Odoo 模型名
        :param odoo_key_fields: Odoo 對應 key 欄位列表
        :param wf_db: WF 資料庫名
        """
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            raise ValidationError(_("找不到指定的WF對照表。"))

        mapping_lines = (
            self.env["wf.mapping.line"]
            .sudo()
            .search(
                [
                    ("mapping_id", "=", mapping.id),
                    ("wf_field_code", "in", return_fields),
                ],
                order="id",
            )
        )

        if not mapping_lines:
            raise ValidationError(_("找不到指定欄位的對照明細。"))

        connection_params = self._get_connection_parameters(wf_db)
        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                # 組合 where 條件
                where_clauses = " OR ".join(
                    f"({' AND '.join([f'{key} = ?' for key in key_fields])})"
                    for key_values in key_values_list
                )
                sql = f"SELECT {','.join(key_fields + return_fields)} FROM {wf_model} WHERE {where_clauses}"
                params = [item for key_tuple in key_values_list for item in key_tuple]

                cursor.execute(sql, params)
                rows = cursor.fetchall()

                wf_data = {
                    tuple(map(lambda x: str(x).strip(), row[: len(key_fields)])): [
                        (
                            str(value).strip()
                            if isinstance(value, str)
                            else (
                                value.strftime("%Y-%m-%d")
                                if isinstance(value, datetime)
                                else (
                                    float(value)
                                    if isinstance(value, (int, float))
                                    else value
                                )
                            )
                        )
                        for value in row[len(key_fields) :]
                    ]
                    for row in rows
                }
        except Exception as e:
            raise ValidationError(_("WF 資料庫連線失敗: %s") % str(e))

        for odoo_rec in lines:
            key_tuple = tuple(odoo_rec[k] for k in odoo_key_fields)
            str_key_tuple = tuple(map(lambda x: str(x).strip(), key_tuple))
            if str_key_tuple in wf_data:
                vals = {
                    line.odoo_field_name: wf_data[str_key_tuple][idx]
                    for idx, line in enumerate(mapping_lines)
                }
                odoo_rec.write(vals)
            else:
                _logger.warning(
                    f"找不到匹配的 WF 記錄: {wf_model}, key={str_key_tuple}"
                )

        return True

    def _update_sync_info_fields(
        self, mapping, record_ids, wf_slip=None, slip_numbers=None
    ):
        """根據 sync_info_ids 設定自動更新 Odoo 欄位"""
        if not mapping.sync_info_ids and not slip_numbers:
            return
        model_name = mapping.odoo_model_model
        records = self.env[model_name].sudo().browse(record_ids)
        vals = {}
        for info in mapping.sync_info_ids:
            field_name = info.odoo_field_id.name
            if info.value_type == "today":
                vals[field_name] = fields.Date.context_today(self)
            elif info.value_type == "now":
                vals[field_name] = fields.Datetime.now()
            elif info.value_type == "user":
                vals[field_name] = self.env.uid
            elif info.value_type == "fixed_text":
                vals[field_name] = info.value_text
            elif info.value_type == "fixed_number":
                vals[field_name] = info.value_number
            elif info.value_type == "bool_true":
                vals[field_name] = True
            elif info.value_type == "bool_false":
                vals[field_name] = False

        # 回寫 wf_slip/new_slip_num
        if mapping.main_type == "3" and slip_numbers:
            for rec in records:
                vals2 = vals.copy()
                plus_fields = []
                if mapping.odoo_s_field and mapping.odoo_b_field:
                    vals2[mapping.odoo_s_field.name] = (
                        wf_slip if wf_slip else mapping.wf_slip
                    )
                    vals2[mapping.odoo_b_field.name] = slip_numbers.get(rec.id)
                for info in mapping.sync_info_ids:
                    if info.value_type == "plus":
                        plus_fields.append(info.odoo_field_id.name)
                table = self.env[model_name]._table
                set_clauses = [f"{k} = %s" for k in vals2.keys()] + [
                    f"{pf} = {pf} + 1" for pf in plus_fields
                ]
                params = list(vals2.values()) + [rec.id]
                sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = %s"
                self.env.cr.execute(sql, params)
        elif vals:
            for rec in records:
                vals2 = vals.copy()
                plus_fields = []
                for info in mapping.sync_info_ids:
                    if info.value_type == "plus":
                        plus_fields.append(info.odoo_field_id.name)
                table = self.env[model_name]._table
                set_clauses = [f"{k} = %s" for k in vals2.keys()] + [
                    f"{pf} = {pf} + 1" for pf in plus_fields
                ]
                params = list(vals2.values()) + [rec.id]
                sql = f"UPDATE {table} SET {', '.join(set_clauses)} WHERE id = %s"
                self.env.cr.execute(sql, params)

        # 回寫 wf_slip/new_slip_num
        # if mapping.main_type == '3' and slip_numbers:
        #     for rec in records:
        #         vals2 = vals.copy()
        #         if mapping.odoo_s_field and mapping.odoo_b_field:
        #             vals2[mapping.odoo_s_field.name] = mapping.wf_slip
        #             vals2[mapping.odoo_b_field.name] = slip_numbers.get(rec.id)
        #         for info in mapping.sync_info_ids:
        #             if info.value_type == 'plus':
        #                 field_name = info.odoo_field_id.name
        #                 vals2[field_name] = (getattr(rec, field_name, 0) or 0) + 1
        #         rec.write(vals2)
        # elif vals:
        #     for rec in records:
        #         vals2 = vals.copy()
        #         for info in mapping.sync_info_ids:
        #             if info.value_type == 'plus':
        #                 field_name = info.odoo_field_id.name
        #                 vals2[field_name] = (getattr(rec, field_name, 0) or 0) + 1
        #         rec.write(vals2)

    def _wf_to_odoo_sync(
        self,
        wf_model,
        wf_domain=" 1=1 ",
        wf_db=None,
        wf_main_domain=None,
        wf_line_domain=None,
    ):
        """
        連接WF的MSSQL，查詢指定表（where條件套用wf_domain），將資料取出後回寫Odoo。
        主表找不到INSERT找的到Update，副表做insert/update/delete。
        :param wf_model: WF資料表名
        :param wf_domain: list of tuple，MSSQL查詢條件
        :param wf_db: WF資料庫名
        :return: (success, error_message) 元組，success 為布林值，error_message 為錯誤訊息或 None
        """

        def _get_nested_attr(obj, attr_path):
            """依 attr_path 取多層關聯值"""
            for attr in attr_path.split("."):
                obj = getattr(obj, attr, False)
                if not obj:
                    return False
            if isinstance(obj, (datetime, date)):
                obj = obj.strftime("%Y%m%d")
            elif isinstance(obj, bool):
                obj = "Y" if obj else "N"

            return obj

        error_message = None  # 初始化錯誤訊息
        mapping = (
            self.env["wf.mapping"]
            .sudo()
            .search([("wf_model_id", "=", wf_model)], limit=1)
        )
        if not mapping:
            error_message = (
                f"WF檔案對照表中，查無此主表，請先通知IT建立主表對應資料: {wf_model}"
            )
            _logger.warning(error_message)
            return False, error_message

        # 主表 key 欄位
        key_lines = mapping.line_ids.filtered(lambda l: l.wf_key)
        key_fields = [line.wf_field_code for line in key_lines]
        odoo_key_fields = [line.odoo_field_name for line in key_lines]
        if not key_fields or not odoo_key_fields:
            error_message = (
                f"WF檔案對照表中，此主表未建立Key值，請先通知IT建立: {wf_model}"
            )
            _logger.warning(error_message)
            return False, error_message

        # 使用集合避免重複，並直接生成 unique_mapping_lines
        seen_field_ids = set()
        unique_mapping_lines = [
            line
            for line in mapping.line_ids.filtered(
                lambda l: l.snyc_type == "F" and not l.wf_key
            )
            if line.odoo_field_id.id not in seen_field_ids
            and not seen_field_ids.add(line.odoo_field_id.id)
        ]

        # 生成 return_fields
        return_fields = [
            line.wf_field_code
            for line in unique_mapping_lines
            if line.wf_field_code not in key_fields
        ]

        odoo_model = mapping.odoo_model_model
        Model = self.env[odoo_model].sudo()
        # 查詢WF主表資料
        connection_params = self._get_connection_parameters(wf_db)
        try:
            with pyodbc.connect(
                connection_params["connection_string"], timeout=3
            ) as connection, connection.cursor() as cursor:
                sql = f"SELECT {','.join(key_fields + return_fields)} FROM {wf_model} WHERE {wf_domain}"
                if wf_main_domain:
                    sql += f" AND {wf_main_domain}"
                cursor.execute(sql)
                rows = cursor.fetchall()
                wf_data = {
                    tuple(str(x).strip() for x in row[: len(key_fields)]): list(
                        row[len(key_fields) :]
                    )
                    for row in rows
                }
        except Exception as e:
            error_message = f"WF DB連線失敗: {str(e)}"
            _logger.warning(error_message)
            return False, error_message

        # 主表create or update
        all_main_rec_ids = set()
        main_recs = Model
        for key_tuple, values in wf_data.items():
            domain = [(k, "=", v) for k, v in zip(odoo_key_fields, key_tuple)]
            main_recs = Model.search(domain, limit=1)

            if not main_recs:
                # odoo不存在，要create
                vals = {}
                for idx, line in enumerate(key_lines):
                    converted_value, error_message = self._wf_value_to_odoo_value(
                        line, key_tuple[idx]
                    )
                    if error_message:
                        return False, error_message
                    vals[line.odoo_field_name] = converted_value
                if return_fields:
                    for idx, line in enumerate(unique_mapping_lines):
                        converted_value, error_message = self._wf_value_to_odoo_value(
                            line, values[idx]
                        )
                        if error_message:
                            return False, error_message
                        vals[line.odoo_field_name] = converted_value
                main_recs = Model.with_context(id_wf=True).create(vals)
                _logger.info(f"Creating new record in {odoo_model} with vals: {vals}")

            else:
                if return_fields:
                    # odoo有資料，要update
                    test_vals = {}
                    for idx, line in enumerate(unique_mapping_lines):
                        if idx < len(values) and line.wf_field_code in return_fields:
                            converted_value, error_message = (
                                self._wf_value_to_odoo_value(line, values[idx])
                            )
                            test_vals[line.odoo_field_name] = converted_value

                    vals = {}
                    for idx, line in enumerate(unique_mapping_lines):
                        if idx < len(values) and line.wf_field_code in return_fields:
                            converted_value, error_message = (
                                self._wf_value_to_odoo_value(
                                    line,
                                    values[idx],
                                    rec=main_recs,
                                    existing_vals=test_vals,
                                )
                            )
                            if error_message:
                                return False, error_message
                            vals[line.odoo_field_name] = converted_value
                    main_recs.with_context(id_wf=True).write(vals)
                    _logger.info(
                        f"Updating record id(s): {main_recs.ids} with vals: {vals}"
                    )
            if main_recs:
                all_main_rec_ids.update(main_recs.ids)
        # ====== 副表同步 ======
        for sub in mapping.sub_ids.filtered(lambda s: s.is_same_parent is False):
            sub_mapping = (
                self.env["wf.mapping"]
                .sudo()
                .search([("wf_model_id", "=", sub.wf_model_id)], limit=1)
            )
            if not sub_mapping:
                error_message = f"WF檔案對照表中，查無此副表，請先通知IT建立副表對應資料: {sub.wf_model_id}"
                _logger.warning(error_message)
                continue
            odoo_sub_model = sub_mapping.odoo_model_model
            odoo_sub_Model = self.env[odoo_sub_model].sudo()
            sub_key_lines = sub_mapping.line_ids.filtered(lambda l: l.wf_key)
            sub_key_fields = [line.wf_field_code for line in sub_key_lines]
            odoo_sub_key_fields = [
                (
                    line.odoo_field_name + "." + line.odoo_related_id.name
                    if line.odoo_related_id
                    else line.odoo_field_name
                )
                for line in sub_key_lines
            ]
            sub_seen_field_ids = set()
            sub_unique_mapping_lines = [
                line
                for line in sub_mapping.line_ids.filtered(lambda l: l.snyc_type == "F")  
                if (line.odoo_field_id.id not in sub_seen_field_ids 
                and not sub_seen_field_ids.add(line.odoo_field_id.id)) or line.wf_key
            ]
            sub_return_fields = [
                line.wf_field_code
                for line in sub_unique_mapping_lines
                if line.wf_field_code not in sub_key_fields
            ]

            # 查WF副表資料
            try:
                with pyodbc.connect(
                    connection_params["connection_string"], timeout=3
                ) as connection, connection.cursor() as cursor:
                    sub_where = wf_domain
                    if wf_line_domain and sub.wf_model_id in wf_line_domain:
                        sub_where = f"{sub_where} AND {wf_line_domain[sub.wf_model_id]}"
                    sql = f"SELECT {','.join(sub_key_fields + sub_return_fields)} FROM {sub.wf_model_id} WHERE {sub_where}"
                    cursor.execute(sql)
                    rows = cursor.fetchall()
                    wf_sub_data = [
                        tuple(
                            value.rstrip() if isinstance(value, str) else value
                            for value in row
                        )
                        for row in rows
                    ]
            except Exception as e:
                error_message = f"SM DB連線失敗: {str(e)}"
                _logger.warning(error_message)
                continue
            # 依主表key group by
            wf_body_fields = [
                f.strip() for f in (sub.wf_body_field or "").split(",") if f.strip()
            ]
            # 取得主表key在副表的index
            main_key_indexes = [
                sub_key_fields.index(f) for f in wf_body_fields if f in sub_key_fields
            ]
            # group by 主表key
            grouped = {}
            for row in wf_sub_data:
                main_key = tuple(row[i] for i in main_key_indexes)
                grouped.setdefault(main_key, []).append(row)
            for main_key, sub_rows in grouped.items():
                # 先檢查主表key在odoo有無資料
                main_domain = [(k, "=", v) for k, v in zip(odoo_key_fields, main_key)]
                main_rec = Model.search(main_domain, limit=1)
                if not main_rec:
                    continue
                # 取得該主表下所有odoo副表資料
                odoo_sub_records = getattr(
                    main_rec, sub.odoo_field_id.name, []
                ).filtered_domain(eval(sub_mapping.extra_domain or "[]"))

                odoo_sub_dict = (
                    {
                        tuple(
                            _get_nested_attr(sub_rec, k) for k in odoo_sub_key_fields
                        ): sub_rec
                        for sub_rec in odoo_sub_records
                    }
                    if odoo_sub_records
                    else {}
                )

                # 取得wf副表key
                wf_sub_dict = {
                    tuple(str(row[i]).strip() for i in range(len(sub_key_fields))): row
                    for row in sub_rows
                }
                wf_keys = set(wf_sub_dict.keys())
                odoo_keys = set(odoo_sub_dict.keys())
                # (1) insert
                to_insert = wf_keys - odoo_keys
                insert_vals = []
                for key in to_insert:
                    raw_row_tuple = wf_sub_dict[key]
                    row_dict = {
                        line.wf_field_code: raw_row_tuple[idx] 
                        for idx, line in enumerate(sub_unique_mapping_lines)
                        if idx < len(raw_row_tuple)
                    }
                    test_vals = {}
                    for idx, line in enumerate(sub_unique_mapping_lines):
                        converted_value, error_message = self._wf_value_to_odoo_value(
                            line, wf_sub_dict[key][idx]
                        )
                        test_vals[line.odoo_field_name] = converted_value

                    vals = {}
                    for idx, line in enumerate(sub_unique_mapping_lines):
                        converted_value, error_message = self._wf_value_to_odoo_value(
                            line, wf_sub_dict[key][idx], existing_vals=test_vals, raw_value=row_dict
                        )
                        if error_message:
                            return False, error_message
                        vals[line.odoo_field_name] = converted_value
                    vals[sub.odoo_sub_id.name] = main_rec.id  # 關聯主表id
                    insert_vals.append(vals)
                if insert_vals:
                    odoo_sub_Model.create(insert_vals)
                # (2) update
                to_update = wf_keys & odoo_keys
                for key in to_update:
                    rec = odoo_sub_dict[key]
                    wf_row = wf_sub_dict[key]
                    row_dict = {
                        line.wf_field_code: wf_row[idx] 
                        for idx, line in enumerate(sub_unique_mapping_lines)
                        if idx < len(wf_row)
                    }
                    test_vals = {}
                    for idx, line in enumerate(sub_unique_mapping_lines):
                        if line.wf_field_code in sub_return_fields:
                            converted_value, error_message = (
                                self._wf_value_to_odoo_value(line, wf_row[idx], rec=rec)
                            )
                            test_vals[line.odoo_field_name] = converted_value
                    vals = {}
                    for idx, line in enumerate(sub_unique_mapping_lines):
                        if line.wf_field_code in sub_return_fields:
                            converted_value, error_message = (
                                self._wf_value_to_odoo_value(
                                    line, wf_row[idx], rec=rec, existing_vals=test_vals, raw_value=row_dict
                                )
                            )
                            if error_message:
                                return False, error_message
                            vals[line.odoo_field_name] = converted_value
                    print(rec.wf_sequence)
                    _logger.info(f"Odoo副表更新: rec.id={rec.id}, vals={vals}")
                    rec.sudo().write(vals)

                # (3) delete
                to_delete = odoo_keys - wf_keys
                for key in to_delete:
                    rec = odoo_sub_dict[key]
                    rec.sudo().unlink()

        if all_main_rec_ids:
            self._update_sync_info_fields(
                mapping, list(all_main_rec_ids), slip_numbers=None
            )

        return True, None

    def _wf_value_to_odoo_value(self, line, value, rec=None, raw_value=None, existing_vals=None):
        """
        將 WF 資料依據 Odoo 欄位類型自動轉換為 Odoo 相容格式
        :param line: wf.mapping.line record
        :param value: WF 資料
        :param rec: 現有 Odoo 記錄 (用於 many2one lookup)
        :param raw_value: 原始 WF 資料字典 (用於 many2one lookup)
        :param existing_vals: 現有值字典 (用於 many2one lookup)
        :return: (Odoo 相容格式, 是否有錯誤)
        """
        ttype = line.odoo_field_ttype
        error_message = None

        type_handlers = {
            "date": lambda v: (
                (
                    f"{v[:4]}-{v[4:6]}-{v[6:8]}"
                    if v and isinstance(v, str) and len(v) == 8 and v.isdigit()
                    else False
                ),
                False,
            ),
            "datetime": lambda v: (
                (
                    f"{v[:4]}-{v[4:6]}-{v[6:8]} 08:00:00"
                    if v and isinstance(v, str) and len(v) == 8 and v.isdigit()
                    else False
                ),
                False,
            ),
            "boolean": lambda v: (v == "Y", False),
            "many2one": lambda v: self._handle_many2one(line, v, rec, raw_value=raw_value, existing_vals=existing_vals),
            "float": lambda v: (float(v) if v else 0.0, False),
            "monetary": lambda v: (float(v) if v else 0.0, False),
            "integer": lambda v: (int(v) if v else 0, False),
        }

        if ttype in type_handlers:
            return type_handlers[ttype](value)
        else:
            # 其他類型直接返回原值，字串去空白
            if isinstance(value, str):
                return value.strip(), error_message
            return value, error_message

    def _handle_many2one(self, line, value, rec=None, raw_value=None, existing_vals=None):
        """處理 many2one 欄位轉換"""
        error_message = None
        if not value:
            return False, error_message
        related_field = line.odoo_related_id
        if not related_field:
            return False, error_message
        model = self.env[related_field.model_id.model]
        domain = [(related_field.name, "=", value)]
        # 處理第二鍵：優先從 existing_vals 獲取，否則從 rec 獲取
        if line.odoo_lookup_id and line.odoo_lookup_main_id:
            lookup_value = (
                existing_vals.get(line.odoo_lookup_main_id.name)
                if existing_vals
                else getattr(rec, line.odoo_lookup_main_id.name, False)
            )
            if hasattr(lookup_value, "id"):
                lookup_value = lookup_value.id
            if line.x_reserved and raw_value:
                    lookup_value = raw_value.get(line.x_reserved)
            _logger.info(f"Domain is : {domain}")
            domain.append((line.odoo_lookup_id.name, "=", lookup_value))
        recs = model.sudo().search(domain, limit=1)
        if not recs:
            error_message = f"在關聯表 {model._description} ({model._name}) 查無此條件 {domain} 資料，請您先到對應的作業，建立好基本資料再重新執行"
            _logger.error(error_message)
        return recs.id if recs else False, error_message


class WFMappingLine(models.Model):
    _name = "wf.mapping.line"
    _description = "WF Mapping Line"
    _order = "wf_field_code"

    mapping_id = fields.Many2one(
        "wf.mapping", string="單身欄位對照", required=True, ondelete="cascade"
    )
    odoo_model_id = fields.Many2one(
        "ir.model", string="Odoo型號", related="mapping_id.odoo_model_id"
    )
    odoo_field_id = fields.Many2one(
        "ir.model.fields", string="Odoo欄位", index=True, ondelete="set null"
    )
    odoo_field_ttype = fields.Selection(
        related="odoo_field_id.ttype", string="Odoo欄位型態", index=True, store=True
    )
    odoo_field_relation = fields.Char(related="odoo_field_id.relation", index=True)
    odoo_field_name = fields.Char(
        string="Odoo欄位代號", related="odoo_field_id.name", index=True
    )
    odoo_related_id = fields.Many2one(
        "ir.model.fields", string="Odoo關聯最終欄位", ondelete="set null", index=True
    )
    odoo_related_name = fields.Char(
        string="Odoo關聯最終欄位代號", related="odoo_related_id.name", index=True
    )
    odoo_related_model_id = fields.Many2one(
        string="Odoo關聯最終欄位的model", related="odoo_related_id.model_id"
    )
    wf_field_code = fields.Char(string="WF欄位代號", required=True, index=True)
    wf_field_name = fields.Char(string="WF欄位名稱")
    snyc_type = fields.Selection(
        [
            ("F", "Odoo欄位"),
            ("C", "固定文字"),
            ("N", "固定數值"),
            ("W", "WF關聯表"),
            ("D", "執行當日"),
            ("B", "是否值"),
            ("A", "字串相加"),
            ("S", "空格"),
        ],
        string="同步方式",
        required=True,
        default="F",
    )
    wf_def_c = fields.Char(string="固定文字(含單別)")
    wf_def_n = fields.Float(string="固定數值")
    wf_key = fields.Boolean(
        string="WF KEY", default=False, help="是否為WF檔案的KEY欄位", index=True
    )
    wf_orign_field = fields.Char(string="WF來源欄位", index=True)
    wf_related_model = fields.Char(
        string="WF關聯檔案", help="WF關聯檔案的名稱", index=True
    )
    wf_related_key = fields.Char(
        string="WF關聯KEY欄位", help="WF關聯檔案之KEY欄位名稱", index=True
    )
    wf_related_field = fields.Char(
        string="WF關聯最終欄位", help="WF關聯檔案之欄位名稱", index=True
    )
    wf_def_b = fields.Selection([("Y", "Y"), ("N", "N")], string="是否值")
    wf_def_a = fields.Char(string="字串相加邏輯")
    wf_def_d = fields.Char(string="執行當日(日期格式)")
    x_reserved = fields.Char(string='預留欄位')
    odoo_lookup_id = fields.Many2one(
        "ir.model.fields",
        string="Odoo關聯第二Key欄位",
        ondelete="set null",
        help="many2one查詢時的第二key欄位（如product_temp_id）",
    )
    odoo_lookup_main_id = fields.Many2one(
        "ir.model.fields",
        string="Odoo第二Key來源欄位",
        ondelete="set null",
        help="many2one查詢時，第二key的來源欄位（如sale.order.line的product_temp_id）",
    )

    _sql_constraints = [
        (
            "wf_unique",
            "unique(mapping_id,wf_field_code)",
            "WF欄位在同一張表裡必須唯一！",
        )
    ]

    @api.constrains("wf_key")
    def _check_wf_key(self):
        for record in self:
            lines = self.search([("mapping_id", "=", record.mapping_id.id)])
            if not any(line.wf_key for line in lines):
                raise ValidationError(_("主欄位對照表，至少需要有一筆資料WF KEY!"))

    @api.onchange("odoo_field_id")
    def _onchange_odoo_field_id(self):
        if self.odoo_field_id:
            self.odoo_related_id = False

    @api.onchange("snyc_type")
    def _onchange_snyc_type(self):
        self.odoo_field_id = None
        self.odoo_related_id = None
        self.wf_def_c = None
        self.wf_def_n = None
        self.wf_orign_field = None
        self.wf_related_model = None
        self.wf_related_key = None
        self.wf_related_field = None
        self.wf_def_b = None
        self.wf_def_a = None
        self.wf_def_d = None
        self.odoo_lookup_id = None
        self.odoo_lookup_main_id = None

    def write(self, vals):
        if "snyc_type" in vals:
            sync_type = vals.get("snyc_type")
            fields_to_reset = {
                "B": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "C": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "N": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_c",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "W": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_def_d",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "D": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "A": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "S": [
                    "odoo_field_id",
                    "odoo_related_id",
                    "wf_def_b",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "wf_def_a",
                    "odoo_lookup_id",
                    "odoo_lookup_main_id",
                ],
                "F": [
                    "wf_def_b",
                    "wf_def_c",
                    "wf_def_n",
                    "wf_orign_field",
                    "wf_related_model",
                    "wf_related_key",
                    "wf_related_field",
                    "wf_def_d",
                    "wf_def_a",
                ],
            }
            for field in fields_to_reset.get(sync_type, []):
                vals[field] = False

        return super(WFMappingLine, self).write(vals)


class WFMappingSub(models.Model):
    _name = "wf.mapping.sub"
    _description = "副表對照"

    mapping_id = fields.Many2one(
        "wf.mapping", string="主表對照", required=True, ondelete="cascade"
    )
    mapping_model_id = fields.Many2one(
        "ir.model", related="mapping_id.odoo_model_id", store=True
    )
    wf_model_id = fields.Char(string="WF副表代號", required=True)
    odoo_field_id = fields.Many2one(
        "ir.model.fields", string="Odoo主表關聯欄位", ondelete="set null"
    )
    odoo_field_model = fields.Many2one(
        "ir.model",
        string="Odoo主表關聯模型",
        compute="_compute_odoo_field_model",
        store=True,
    )
    odoo_sub_id = fields.Many2one(
        "ir.model.fields", string="Odoo副表關聯欄位", ondelete="set null"
    )
    is_same_parent = fields.Boolean(string="沿用Odoo主表資料", default=False)
    wf_parent_field = fields.Char(
        string="WF主表關聯Key", help="WF主表關聯Key，若多欄位請用逗號分隔", index=True
    )
    wf_body_field = fields.Char(
        string="WF副表關聯Key", help="WF副表關聯Key，若多欄位請用逗號分隔", index=True
    )

    @api.depends("odoo_field_id")
    def _compute_odoo_field_model(self):
        for record in self:
            if record.odoo_field_id and record.odoo_field_id.relation:
                model = self.env["ir.model"].search(
                    [("model", "=", record.odoo_field_id.relation)], limit=1
                )
                record.odoo_field_model = model.id if model else False

    def _prepare_sub_batch(
        self,
        sub_mapping,
        record,
        connection_creator,
        connection_usr_group,
        company_name,
        main_mapping,
        sub,
        main_record,
        cursor,
        slip_num=None,
    ):
        s_field_id = None
        b_field_id = None
        # 主副表多key支援: 逗號分隔
        parent_fields = [
            k.strip() for k in (sub.wf_parent_field or "").split(",") if k.strip()
        ]
        key_fields = [
            k.strip() for k in (sub.wf_body_field or "").split(",") if k.strip()
        ]
        for parent_field, key_field in zip(parent_fields, key_fields):
            if main_mapping.wf_slip and main_mapping.wf_s_field == parent_field:
                s_field_id = key_field
            if main_mapping.wf_slip and main_mapping.wf_b_field == parent_field:
                b_field_id = key_field

        # 準備副表 key 值的判斷條件
        key_conditions = [
            f"({line.wf_field_code} = '{sub_mapping._get_wf_value(record, line, cursor, mapping_slip=main_mapping.wf_slip, slip_num=slip_num, s_field_id=s_field_id, b_field_id=b_field_id)}')"
            for line in sub_mapping.line_ids.filtered(lambda l: l.wf_key)
            if sub_mapping._get_wf_value(
                record,
                line,
                cursor,
                mapping_slip=main_mapping.wf_slip,
                slip_num=slip_num,
                s_field_id=s_field_id,
                b_field_id=b_field_id,
            )
            is not None
        ]
        condition_where = " AND ".join(key_conditions) if key_conditions else ""

        # 2. 主表關聯條件
        body_fields = [
            k.strip() for k in (sub.wf_body_field or "").split(",") if k.strip()
        ]
        main_conditions = []
        for parent_field, body_field in zip(parent_fields, body_fields):
            # 取主表line
            line = main_mapping.line_ids.filtered(
                lambda l: l.wf_field_code == parent_field
            )
            if line:
                value = main_mapping._get_wf_value(
                    main_record,
                    line[0],
                    cursor,
                    mapping_slip=main_mapping.wf_slip,
                    slip_num=slip_num,
                    s_field_id=s_field_id,
                    b_field_id=b_field_id,
                )
                if value is not None:
                    main_conditions.append(f"({body_field} = '{value}')")
        main_condition_where = " AND ".join(main_conditions) if main_conditions else ""

        ins_columns = [line.wf_field_code for line in sub_mapping.line_ids]
        ins_values = [
            sub_mapping._get_wf_value(
                record,
                line,
                cursor,
                mapping_slip=main_mapping.wf_slip,
                slip_num=slip_num,
                s_field_id=s_field_id,
                b_field_id=b_field_id,
            )
            for line in sub_mapping.line_ids
        ]
        ins_fixed_columns = ["COMPANY", "CREATOR", "USR_GROUP", "CREATE_DATE", "FLAG"]
        ins_fixed_values = [
            company_name,
            connection_creator,
            connection_usr_group,
            datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y%m%d"),
            1,
        ]

        upd_columns = [
            line.wf_field_code
            for line in sub_mapping.line_ids.filtered(
                lambda l: l.wf_key is False and l.snyc_type == "F"
            )
        ]
        upd_values = [
            sub_mapping._get_wf_value(
                record,
                line,
                cursor,
                mapping_slip=main_mapping.wf_slip,
                slip_num=slip_num,
                s_field_id=s_field_id,
                b_field_id=b_field_id,
            )
            for line in sub_mapping.line_ids.filtered(
                lambda l: l.wf_key is False and l.snyc_type == "F"
            )
        ]
        upd_fixed_columns = ["MODIFIER", "MODI_DATE", "FLAG"]
        upd_fixed_values = [
            connection_creator,
            datetime.now(pytz.timezone("Asia/Taipei")).strftime("%Y%m%d"),
            2,
        ]

        return {
            "ins_columns": ins_columns + ins_fixed_columns,
            "ins_values": ins_values + ins_fixed_values,
            "upd_columns": upd_columns + upd_fixed_columns,
            "upd_values": upd_values + upd_fixed_values,
            "wf_model_id": sub_mapping.wf_model_id,
            "condition_where": condition_where,
            "main_condition_where": main_condition_where,
        }


class WFMappingSyncInfo(models.Model):
    _name = "wf.mapping.sync.info"
    _description = "同步後資訊紀錄"

    mapping_id = fields.Many2one(
        "wf.mapping", string="主表對照", required=True, ondelete="cascade"
    )
    mapping_model_id = fields.Many2one(
        "ir.model", related="mapping_id.odoo_model_id", store=True
    )
    odoo_field_id = fields.Many2one(
        "ir.model.fields", string="Odoo欄位", ondelete="set null"
    )
    value_type = fields.Selection(
        [
            ("today", "當下日期"),
            ("now", "當下時間"),
            ("user", "執行帳號"),
            ("fixed_text", "固定文字"),
            ("fixed_number", "固定數值"),
            ("bool_true", "是"),
            ("bool_false", "否"),
            ("plus", "數值累加1"),
        ],
        string="值類型",
        required=True,
    )
    value_text = fields.Char(string="固定文字")
    value_number = fields.Float(string="固定數值")
