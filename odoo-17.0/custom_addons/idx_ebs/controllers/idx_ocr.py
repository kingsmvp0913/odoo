import logging
import requests
import base64
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from Crypto.Cipher import AES

from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from datetime import datetime

_logger = logging.getLogger(__name__)


class IdxOCRController(http.Controller):
    def _get_params(self, env):
        """
        取得OCR辨識服務的參數配置
        @param env: 環境變數
        """
        ICPSudo = env["ir.config_parameter"].sudo()
        group_value = ICPSudo.get_param("idx_ebs.enable_sync_ocr", default="")
        if not group_value:
            _logger.error("OCR 辨識未啟用")
            return {
                "url": "",
                "encryptData": "",
                "API_TOKEN": "",
                "key": "",
                "iv": "",
            }

        config = env["ir.config_parameter"].sudo()
        url = config.get_param("idx_ebs.ocr_url", default="")
        encrypt_data = config.get_param("idx_ebs.encrypt_data", default="")
        API_TOKEN = config.get_param("idx_ebs.ocr_api_token", default="")
        key = config.get_param("idx_ebs.ocr_key", default="")
        iv = config.get_param("idx_ebs.ocr_iv", default="")

        if not (encrypt_data and API_TOKEN and key and iv and url):
            _logger.error("OCR 參數配置不完整!")
            return {
                "url": "",
                "encryptData": "",
                "API_TOKEN": "",
                "key": "",
                "iv": "",
            }

        return {
            "url": url,
            "encryptData": encrypt_data,
            "API_TOKEN": API_TOKEN,
            "key": key,
            "iv": iv,
        }
    
    @http.route(
        "/idx_ocr/error_log",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def error_log(self, **kwargs):
        payload = {}
        raw_body = request.httprequest.get_data(cache=False, as_text=True)
        if raw_body:
            payload = json.loads(raw_body)

        message = payload.get("message", "")
        _logger.error(message)
        return request.make_json_response({"success": True})

    @http.route(
        "/idx_ocr/submit",
        type="http",
        auth="user",
        methods=["POST"],
        csrf=False,
    )
    def submit_ocr(self, **kwargs):
        """
        處理OCR辨識的HTTP請求，接收上傳的圖片檔案，呼叫外部OCR API進行辨識，並將結果解析後寫入對應的模型中。
        @return: JSON格式的辨識結果，包括成功與否、訊息、建立的資料筆數以及錯誤詳情。
        """
        files = request.httprequest.files.getlist("files")
        page = request.params.get("page")
        if page == "page1":
            desc = "人類醫學"
        else:
            desc = "小動物"

        # 二次防呆
        if not files:
            return json.dumps(
                {
                    "success": False,
                    "message": "沒有上傳任何檔案!",
                }
            )

        created_total = 0
        errors = []
        ocr_data_list = []
        params = self._get_params(request.env)
        if not (
            params.get("encryptData")
            and params.get("url")
            and params.get("API_TOKEN")
            and params.get("key")
            and params.get("iv")
        ):
            return json.dumps(
                {
                    "success": False,
                    "message": "OCR辨識參數不完整，請確認配置!",
                }
            )

        file_payloads = []
        for index, f in enumerate(files):
            file_payloads.append(
                {
                    "index": index,
                    "filename": f.filename,
                    "content": f.read(),
                    "mimetype": f.mimetype,
                }
            )

        max_workers = min(len(file_payloads), 5)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_map = {
                executor.submit(self._call_external_ocr, payload, params): payload
                for payload in file_payloads
            }

            ocr_results = []
            for future in as_completed(future_map):
                payload = future_map[future]
                try:
                    decrypt_data = future.result()
                    ocr_results.append(
                        {
                            "index": payload["index"],
                            "file": payload["filename"],
                            "image_file": base64.b64encode(payload["content"]).decode("ascii"),
                            "image_file_name": payload["filename"],
                            "data": decrypt_data,
                        }
                    )
                except Exception as e:
                    errors.append(
                        {
                            "file": payload["filename"],
                            "error": f"系統錯誤：{str(e)}",
                        }
                    )

        for ocr_result in sorted(ocr_results, key=lambda result: result["index"]):
            file_name = ocr_result["file"]
            decrypt_data = ocr_result["data"]
            try:
                ocr_data_list.append({"file": file_name, "data": decrypt_data})
                if page == "page1":  # 人類醫學新增資料
                    created_count, errors_row = self._create_ocr1_records(
                        decrypt_data,
                        ocr_result.get("image_file"),
                        ocr_result.get("image_file_name"),
                    )
                else:  # 小動物新增資料
                    created_count, errors_row = self._create_ocr2_records(
                        decrypt_data,
                        ocr_result.get("image_file"),
                        ocr_result.get("image_file_name"),
                    )
                created_total += created_count  # 筆數增加
                if errors_row:
                    errors.append(
                        {
                            "file": file_name,
                            "error": "\n".join(str(e) for e in errors_row),
                        }
                    )
            except Exception as e:
                errors.append({"file": file_name, "error": f"系統錯誤：{str(e)}"})

        # 組合回傳訊息
        if errors:
            message = f"辨識完成，已建立{created_total}筆{desc}資料，共有{len(errors)}張圖片出現辨識異常狀況!"
        else:
            message = f"辨識完成，已建立{created_total}筆{desc}資料"

        return json.dumps(
            {
                "success": True,
                "message": message,
                "created_count": created_total,
                "errors": errors,
                "ocr_data": ocr_data_list,
            }
        )

    def _call_external_ocr(self, file_storage, params=None):
        """
        呼叫外部OCR API進行辨識，並返回辨識結果的解密資料
        @param file_storage: 上傳的圖片檔案
        @param params: OCR API參數，平行呼叫時由主thread先取得後傳入
        @return: 解密後的OCR辨識結果
        """
        if params is None:
            params = self._get_params(request.env)
        url = params.get("url")
        encrypt_data = params.get("encryptData")
        key = params.get("key")
        iv = params.get("iv")
        API_TOKEN = params.get("API_TOKEN")
        if not (encrypt_data and url and API_TOKEN and key and iv):
            raise ValidationError("OCR辨識參數不完整，請確認配置!")

        if isinstance(file_storage, dict):
            filename = file_storage.get("filename")
            content = file_storage.get("content")
            mimetype = file_storage.get("mimetype")
        else:
            filename = file_storage.filename
            file_storage.stream.seek(0)
            content = file_storage.stream.read()
            mimetype = file_storage.mimetype

        headers = {"API_TOKEN": API_TOKEN}
        data = {"encryptData": encrypt_data}

        # 增加超時時間至 90 秒，並添加重試機制
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                files = {"file": (filename, BytesIO(content), mimetype)}
                resp = requests.post(
                    url, headers=headers, files=files, data=data, timeout=300
                )
                resp.raise_for_status()
                get_encrypt_data = resp.text.strip()
                _logger.info(f"OCR API 回傳的加密資料: {get_encrypt_data}")
                decrypt_data = self._decrypt_response(get_encrypt_data, key, iv)
                return decrypt_data
            except requests.exceptions.Timeout:
                retry_count += 1
                if retry_count > max_retries:
                    raise ValidationError(
                        f"OCR API 連線超時（已嘗試 {max_retries + 1} 次），請確認：1.網路連線是否正常 2.圖片檔案是否過大"
                    )
            except requests.exceptions.RequestException as e:
                raise ValidationError(f"OCR API 連線錯誤：{str(e)}")

    def _decrypt_response(self, decrypt_data, key, iv):
        """
        解密OCR API回傳的加密資料
        @param decrypt_data: 從OCR API回傳的加密資料
        @param key: 解密金鑰
        @param iv: 解密向量
        @return: 解密後的資料，通常為OCR辨識的結果
        """
        encrypted_bytes = base64.b64decode(decrypt_data)
        cipher = AES.new(key.encode("utf-8"), AES.MODE_CBC, iv.encode("utf-8"))
        decrypted = cipher.decrypt(encrypted_bytes)
        pad_len = decrypted[-1]
        decrypted = decrypted[:-pad_len]
        return json.loads(decrypted.decode("utf-8"))

    def _create_ocr1_records(self, decrypt_data, image_file=None, image_file_name=None):
        raw_result = decrypt_data.get("result")
        if not raw_result:
            raise ValidationError("OCR辨識結果沒有任何內容!")
        created_count = 0
        errors = []
        blocks = json.loads(raw_result)
        _logger.info(f"[OCR1] 解密後完整內容: {decrypt_data}")
        _logger.info(f"[OCR1] blocks 數量: {len(blocks)}，內容: {blocks}")
        for block in blocks:
            detect_list = block.get("檢測列表", [])
            errors_row_count = 0
            for item in detect_list:
                try:
                    partner_name = (item.get("送檢單位") or "ERROR").strip()  # 聯絡人(送檢單位)
                    patient_name = (item.get("姓名") or "ERROR").strip()  # 姓名
                    birth_date = item.get("生日", "").strip()  # 出生年月日
                    inspection_date = item.get("檢測日期", "").strip()  # 檢測日期
                    medical_no = item.get("流水號", "").strip()  # 病歷號碼
                    inspect_number = item.get("流水號", "").strip()  # 送檢流水編號
                    gender_name = (item.get("性別") or "").strip()  # 性別
                    sample_name = item.get("樣本種類/檢體種類", "").strip()  # 樣本種類
                    product_template_name = (item.get("檢測項目代碼") or "ERROR").strip()  # 檢測項目
                    note = item.get("備註", "").strip()  # 備註
                    detect_error = None
                    errors_row_count += 1

                    # 資料處理與驗證
                    # 姓名（必填）
                    if not patient_name:
                        errors.append(f"第{errors_row_count}列資料，缺少姓名!")
                        continue

                    # 聯絡人(送檢單位)（必填）
                    if not partner_name:
                        errors.append(
                            f"第{errors_row_count}列資料，缺少聯絡人(送檢單位)!"
                        )
                        continue

                    partner_id, partner_name = self._find_partner(partner_name)
                    if not partner_id:
                        errors.append(
                            f"第{errors_row_count}列資料，找不到聯絡人(送檢單位)：{partner_name}"
                        )
                        continue

                    # 檢測項目（必填）
                    if not product_template_name:
                        errors.append(f"第{errors_row_count}列資料，缺少檢測項目!")
                        continue

                    if product_template_name == "GE224":
                        product_template_name = "GE224項血清特定抗體量測服務"
                    elif product_template_name == "G101":
                        product_template_name = "G101項血清特定抗體量測服務"
                    elif product_template_name == "GE110":
                        product_template_name = "GE110項血清特定抗體量測服務"
                    elif product_template_name == "E66":
                        product_template_name = "E66項血清特定抗體量測服務"
                    else:
                        product_template_name = "ERROR"
                    
                    if not product_template_name:
                        errors.append(
                            f"第{errors_row_count}列資料，檢測項目代碼：{item.get('檢測項目代碼', '').strip()}無法對應到有效的檢測項目名稱!"
                        )
                        continue

                    product_template_id = self._find_product_template(
                        product_template_name
                    )
                    if not product_template_id:
                        errors.append(
                            f"第{errors_row_count}列資料，找不到檢測項目：{product_template_name}"
                        )
                        continue

                    # 性別（必填）
                    if not gender_name:
                        errors.append(f"第{errors_row_count}列資料，缺少性別!")
                        continue

                    gender = self._check_gender(gender_name)

                    # 不為require => 允許為空，但標記為異常
                    # 樣本種類
                    sample_type = (
                        self._check_sample(sample_name) if sample_name else None
                    )
                    if sample_name and not sample_type:
                        detect_error = (
                            f"{detect_error}[樣本種類]欄位異常；"
                            if detect_error
                            else "[樣本種類]欄位異常；"
                        )

                    # 出生年月日
                    birth_date_f = (
                        self._check_birth_date(birth_date) if birth_date else None
                    )
                    if birth_date and not birth_date_f:
                        detect_error = (
                            f"{detect_error}[出生年月日]欄位異常；"
                            if detect_error
                            else "[出生年月日]欄位異常；"
                        )

                    # 檢測日期
                    inspection_date_f = (
                        self._check_date(inspection_date) if inspection_date else None
                    )
                    if inspection_date and not inspection_date_f:
                        detect_error = (
                            f"{detect_error}[檢測日期]欄位異常；"
                            if detect_error
                            else "[檢測日期]欄位異常；"
                        )
                    
                    error_fields = []
                    if "error" in patient_name.lower():
                        error_fields.append("姓名")
                    if "error" in partner_name.lower():
                        error_fields.append("客戶")
                    if "error" in product_template_name.lower():
                        error_fields.append("檢測項目")
                    if error_fields:
                        error_message = "錯誤欄位：" + "、".join(error_fields) + "；"
                        detect_error = (
                            f"{detect_error}{error_message}"
                            if detect_error
                            else error_message
                        )

                    # 寫入idx.sale.order.ocr1
                    vals = {
                        "partner_id": partner_id,
                        "patient_name": patient_name,
                        "gender": gender,
                        "medical_no": medical_no,
                        "inspect_number": inspect_number,
                        "inspection_date": inspection_date_f,
                        "birth_date": birth_date_f,
                        "sample_type": sample_type,
                        "product_template_id": product_template_id,
                        "note": note,
                        "detect_error": detect_error,
                        "order_source": "ocr",
                    }
                    if image_file:
                        vals["image_file"] = image_file
                        vals["image_file_name"] = image_file_name
                    request.env["idx.sale.order.ocr1"].sudo().create(vals)
                    created_count += 1
                except ValidationError as e:
                    errors.append(
                        f"第{errors_row_count}列資料-產品【{product_template_name}】，{str(e)}。"
                    )
                    continue
                except Exception as e:
                    error_detail = traceback.format_exc()
                    _logger.error(
                        f"第{errors_row_count}列資料，處理失敗\n錯誤類型：{type(e).__name__}\n錯誤信息：{str(e)}\n詳細堆疊：\n{error_detail}"
                    )
                    raise ValidationError(f"OCR辨識後，解析格式的過程中出現異常!")

        return created_count, errors

    def _create_ocr2_records(self, decrypt_data, image_file=None, image_file_name=None):
        raw_result = decrypt_data.get("result")
        if not raw_result:
            raise ValidationError("OCR辨識結果沒有任何內容!")
        created_count = 0
        errors = []
        blocks = json.loads(raw_result)
        _logger.info(f"[OCR2] 解密後完整內容: {decrypt_data}")
        _logger.info(f"[OCR2] blocks 數量: {len(blocks)}，內容: {blocks}")
        for block in blocks:
            errors_row_count = 0
            try:
                partner_name = (block.get("送檢醫院") or "ERROR").strip()  # 送檢醫院
                patient_name = (block.get("寵物姓名") or "ERROR").strip()  # 寵物姓名
                animal_type_name = block.get("送檢種類", "犬").strip()  # 送檢種類
                breed = block.get("品系", "").strip()  # 品系
                medical_record_number = block.get("病歷號", "").strip()  # 病歷號
                detect_error = None
                errors_row_count += 1

                # 資料處理與驗證
                # 寵物姓名（必填）
                if not patient_name:
                    errors.append(f"第{errors_row_count}列資料，缺少寵物姓名!")
                    continue

                # 送檢醫院（必填）
                if not partner_name:
                    errors.append(f"第{errors_row_count}列資料，缺少送檢醫院!")
                    continue

                partner_id, partner_name = self._find_partner(partner_name)
                if not partner_id:
                    errors.append(
                        f"第{errors_row_count}列資料，找不到送檢醫院：{partner_name}"
                    )
                    continue

                # 送檢種類（必填）
                if not animal_type_name:
                    errors.append(f"第{errors_row_count}列資料，缺少送檢種類!")
                    continue

                animal_type = self._check_animal_type(animal_type_name)
                if not animal_type:
                    errors.append(
                        f"第{errors_row_count}列資料，物種：{animal_type_name}在資料轉換過程中出現異常!"
                    )
                    continue

                # 送檢種類自動帶出檢測項目
                product_template_name = "DOG72項血清特定抗體量測服務" if animal_type == "dog" else "CAT72項血清特定抗體量測服務"

                product_template_id = self._find_product_template(product_template_name)
                if not product_template_id:
                    errors.append(
                        f"第{errors_row_count}列資料，找不到檢測項目：{product_template_name}"
                    )
                    continue
                
                error_fields = []
                if "error" in patient_name.lower():
                    error_fields.append("病患名稱")
                if "error" in partner_name.lower():
                    error_fields.append("送檢醫院")
                if error_fields:
                    error_message = "錯誤欄位：" + "、".join(error_fields) + "；"
                    detect_error = (
                        f"{detect_error}{error_message}"
                        if detect_error
                        else error_message
                    )

                # 寫入idx.sale.order.ocr2
                vals = {
                    "product_template_id": product_template_id,
                    "partner_id": partner_id,
                    "patient_name": patient_name,
                    "animal_type": animal_type,
                    "detect_error": detect_error,
                    "order_source": "ocr",
                    "medical_record_number": medical_record_number,
                    "breed": breed,
                }
                if image_file:
                    vals["image_file"] = image_file
                    vals["image_file_name"] = image_file_name
                request.env["idx.sale.order.ocr2"].sudo().create(vals)
                created_count += 1
            except ValidationError as e:
                errors.append(
                    f"第{errors_row_count}列資料-產品【{product_template_name}】，{str(e)}。"
                )
                continue
            except Exception as e:
                error_detail = traceback.format_exc()
                _logger.error(
                    f"第{errors_row_count}列資料處理失敗\n錯誤類型：{type(e).__name__}\n錯誤信息：{str(e)}\n詳細堆疊：\n{error_detail}"
                )
                raise ValidationError(f"OCR辨識後，解析格式的過程中出現異常!")

        return created_count, errors

    # 聯絡人(送檢單位)/醫院
    def _find_partner(self, partner_name):
        partner_model = request.env["res.partner"].sudo()
        search_domains = [
            [("name", "=", partner_name)],
            [("name", "ilike", partner_name)],
            [("name", "=", "ERROR")],
        ]

        for domain in search_domains:
            rec = partner_model.search(domain, limit=1)
            if rec:
                return rec.id, rec.name

        error_partner = partner_model.create({"name": "ERROR","full_name": "ERROR"})
        return error_partner.id, error_partner.name

    # 檢測項目
    def _find_product_template(self, product_template_name):
        rec = (
            request.env["product.template"]
            .sudo()
            .search([("name", "=", product_template_name)], limit=1)
        )
        if rec:
            return rec.id

        return False

    # 性別
    def _check_gender(self, gender_name):
        has_male = "男" in gender_name or "公" in gender_name
        has_female = "女" in gender_name or "母" in gender_name
        if has_male and not has_female:
            return "male"
        elif has_female and not has_male:
            return "female"
        else:
            return None

    # 樣本種類
    def _check_sample(self, sample_name):
        has_serum = "血清" in sample_name
        has_plasma = "血漿" in sample_name
        has_whole_blood = "全血" in sample_name
        if has_serum and not has_plasma and not has_whole_blood:
            return "serum"
        elif has_plasma and not has_serum and not has_whole_blood:
            return "plasma"
        elif has_whole_blood and not has_serum and not has_plasma:
            return "whole_blood"
        else:
            return False

    # 出生年月日
    def _check_birth_date(self, birth_date):
        return self._check_date(birth_date)

    def _check_date(self, date_value):
        for date_format in ("%Y/%m/%d", "%Y-%m-%d", "%Y:%m:%d", "%Y%m%d"):
            try:
                return datetime.strptime(date_value, date_format).date()
            except Exception:
                continue
        return None

    # 物種
    def _check_animal_type(self, animal_type_name):
        has_dog = "犬" in animal_type_name
        has_cat = "貓" in animal_type_name
        if has_dog and not has_cat:
            return "dog"
        elif has_cat and not has_dog:
            return "cat"
        else:
            return False

    # 採血日期/西元採檢日期
    def _check_collect_date(self, collect_date):
        try:
            return datetime.strptime(collect_date, "%Y/%m/%d").date()
        except Exception:
            try:
                return datetime.strptime(collect_date, "%Y%m%d").date()
            except Exception:
                return False
