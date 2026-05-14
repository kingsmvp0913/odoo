import requests
import logging
import time

_logger = logging.getLogger(__name__)


class TcatService:
    def _get_params(self, env) -> dict:
        """
        取得 TCAT 服務的參數配置
        @param env: 環境變數
        @return: dict
        """
        ICPSudo = env["ir.config_parameter"].sudo()
        group_value = ICPSudo.get_param("idx_ebs.enable_tcat", default="")
        if not group_value:
            _logger.error("黑貓同步未啟用")
            return {
                "tcat_endpoint": "",
                "customer_id": "",
                "customer_token": "",
            }

        config = env["ir.config_parameter"].sudo()
        tcat_endpoint = config.get_param("idx_ebs.tcat_endpoint", default="")
        customer_id = config.get_param("idx_ebs.customer_id", default="")
        customer_token = config.get_param("idx_ebs.customer_token", default="")
        if not (tcat_endpoint and customer_id and customer_token):
            _logger.error("黑貓參數配置不完整!")
            return {
                "tcat_endpoint": "",
                "customer_id": "",
                "customer_token": "",
            }

        return {
            "tcat_endpoint": tcat_endpoint,
            "customer_id": customer_id,
            "customer_token": customer_token,
        }

    def _fetch_carrier_type(self, env, carrier_number) -> dict:
        """
        從黑貓 API 獲取物流狀態
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

        params = self._get_params(env)
        if not all(params.values()):
            return {
                "success": False,
                "carrier_type": "",
                "message": "黑貓參數配置不完整，無法查詢物流狀態。",
            }

        url = f"{params['tcat_endpoint'].rstrip('/')}/api/Egs/OBTStatus"
        data = {
            "CustomerId": params["customer_id"],
            "CustomerToken": params["customer_token"],
            "OBTNumbers": [carrier_number],
        }
        headers = {"Content-Type": "application/json"}

        try:
            time.sleep(1)  # 避免過快請求
            response = requests.post(url, json=data, headers=headers, timeout=65)
            result = response.json()

            _logger.info(result)
            status = result.get("IsOK", "N")
            message = result.get("Message", "串接後回傳訊息異常。")

            if status == "Y":
                data = result.get("Data", {}).get("OBTs", [])[0]
                return {
                    "success": True,
                    "carrier_type": data.get("StatusName", ""),
                    "message": message,
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
