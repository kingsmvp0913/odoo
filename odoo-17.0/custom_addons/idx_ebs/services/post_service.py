import requests
import logging
import time

_logger = logging.getLogger(__name__)


class PostService:
    def _get_params(self, env) -> bool:
        """
        取得 POST 服務的參數配置
        @param env: 環境變數
        @return: bool
        """
        ICPSudo = env["ir.config_parameter"].sudo()
        group_value = ICPSudo.get_param("idx_ebs.enable_post", default=False)
        if not group_value:
            _logger.error("中華郵政同步未啟用")

        return group_value

    def _fetch_carrier_type(self, env, carrier_number) -> dict:
        """
        從中華郵政 API 獲取物流狀態
        @param env: 環境變數
        @param carrier: 物流方式
        @param carrier_number: 物流編號
        @return: dict {"success": bool, "carrier_type": str, "message": str}
        """
        if not (carrier_number):
            return {
                "success": False,
                "carrier_type": "",
                "message": "缺少物流或物流編號，無法查詢物流狀態。",
            }

        enable_post = self._get_params(env)
        if not enable_post:
            return {
                "success": False,
                "carrier_type": "",
                "message": "中華郵政串接未啟用，無法查詢物流狀態。",
            }

        url = "https://postserv.post.gov.tw/pstmail/EsoafDispatcher"
        payload = {
            "header": {
                "InputVOClass": "com.systex.jbranch.app.server.post.vo.EB500100InputVO",
                "TxnCode": "EB500100",
                "BizCode": "query2",
                "StampTime": True,
                "SupvPwd": "",
                "TXN_DATA": {},
                "SupvID": "",
                "CustID": "",
                "REQUEST_ID": "",
                "ClientTransaction": True,
                "DevMode": False,
                "SectionID": "esoaf",
            },
            "body": {
                "MAILNO": carrier_number,
                "pageCount": 10,
            },
        }
        headers = {
            "Content-Type": "application/json",
        }

        try:
            time.sleep(1)  # 避免過快請求
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            data = response.json()
            logistic_datas = data[0]["body"]["host_rs"]

            items = (
                logistic_datas.get("ITEM", [])
                if logistic_datas and isinstance(logistic_datas, dict)
                else []
            )
            message = "此物流編號查無資料" if not items else "串接後回傳訊息異常。"

            if items:
                message = ""
                events = [
                    {
                        "datetime": i.get("DATIME", "").strip(),
                        "status": i.get("STATUS", "").strip(),
                        "station": i.get("BRHNC", "").strip(),
                        "evcode": i.get("EVCODE", ""),
                    }
                    for i in items
                ]
                _logger.info(events)
                latest_event = events[0] if events else {}

                return {
                    "success": True,
                    "carrier_type": latest_event.get("status", ""),
                    "message": latest_event.get("status", "串接後回傳訊息異常。"),
                }

            return {
                "success": False,
                "carrier_type": "",
                "message": message,
            }
        except Exception as e:
            _logger.error(f"串接時發生錯誤: {str(e)}")
            return {
                "success": False,
                "carrier_type": "",
                "message": f"串接時發生錯誤!",
            }
