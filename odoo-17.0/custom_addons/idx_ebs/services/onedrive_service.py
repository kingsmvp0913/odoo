import requests
import logging
import threading
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import base64

from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class OnedriveService:
    _instance = None
    _lock = threading.RLock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._token = None
                    cls._instance._token_expire_time = None
        return cls._instance

    def _get_params(self, env) -> dict:
        """
        取得 OneDrive 服務的參數配置
        @param env: 環境變數
        @return: dict
        """
        ICPSudo = env["ir.config_parameter"].sudo()
        group_value = ICPSudo.get_param("idx_ebs.enable_sync_onedrive", default="")
        if not group_value:
            _logger.error("OneDrive 同步未啟用")
            return {
                "onedrive_email": "",
                "tenant_id": "",
                "client_id": "",
                "client_secret": "",
            }

        config = env["ir.config_parameter"].sudo()
        onedrive_email = config.get_param("idx_ebs.onedrive_email", default="")
        tenant_id = config.get_param("idx_ebs.tenant_id", default="")
        client_id = config.get_param("idx_ebs.client_id", default="")
        client_secret = config.get_param("idx_ebs.client_secret", default="")
        if not (onedrive_email and tenant_id and client_id and client_secret):
            _logger.error("OneDrive 參數配置不完整!")
            return {
                "onedrive_email": "",
                "tenant_id": "",
                "client_id": "",
                "client_secret": "",
            }

        return {
            "onedrive_email": onedrive_email,
            "tenant_id": tenant_id,
            "client_id": client_id,
            "client_secret": client_secret,
        }

    def _get_token(self, env, force_refresh=False) -> str:
        """
        獲取 OneDrive 存取令牌
        @param env: 環境變數
        @param force_refresh: 是否強制刷新令牌
        @return: str
        """
        if not env:
            raise ValidationError("env 參數不可為空")

        with self._lock:
            now = datetime.now(timezone.utc)

            needs_refresh = (
                force_refresh
                or not self._token
                or not self._token_expire_time
                or now >= self._token_expire_time
            )

            if needs_refresh:
                try:
                    token = self._fetch_token_from_api(env)
                    if not token:
                        raise ValidationError("取得 OneDrive token 失敗")

                    self._token = token
                    self._token_expire_time = now + timedelta(minutes=50)
                except Exception as e:
                    _logger.error(f"取得 token 失敗: {str(e)}")
                    raise ValidationError("取得 OneDrive token 失敗")

            return self._token

    def _fetch_token_from_api(self, env) -> str:
        """
        從 OneDrive API 獲取存取令牌
        @param env: 環境變數
        @return: str
        """
        params = self._get_params(env)
        if not all(params.values()):
            return ""

        url = (
            f"https://login.microsoftonline.com/{params['tenant_id']}/oauth2/v2.0/token"
        )
        data = {
            "grant_type": "client_credentials",
            "client_id": params["client_id"],
            "client_secret": params["client_secret"],
            "scope": "https://graph.microsoft.com/.default",
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            response = requests.post(url, data=data, headers=headers, timeout=10)
            token_info = response.json()
            token = token_info.get("access_token", "")
            if not token:
                _logger.error("未能從 OneDrive 獲取存取令牌")
                raise ValidationError("未能從 OneDrive 獲取存取令牌")

            return token
        except requests.RequestException as e:
            _logger.exception("獲取 OneDrive 存取令牌時出錯: %s", e)
            raise ValidationError("獲取 OneDrive 存取令牌時出錯")

    def _get_user(self, env) -> str:
        """
        獲取 OneDrive 使用者
        @return: str
        """
        try:
            params = self._get_params(env)
            onedrive_email = params.get("onedrive_email")
            if not onedrive_email:
                _logger.error("OneDrive 帳號(Email) 參數未配置")
                raise ValidationError("OneDrive 帳號(Email) 參數未配置")

            return onedrive_email

        except requests.RequestException as e:
            _logger.exception("獲取 OneDrive 使用者時出錯: %s", e)
            raise ValidationError("獲取 OneDrive 使用者時出錯")

    def get_file_content(self, env, dir_path="", file_name="") -> bytes:
        """
        依照絕對路徑("文件/##對帳單專區##/2025年/202511")和檔案名稱("abc.pdf")取得檔案內容
        @param env: 環境參數
        @param dir_path: 目錄路徑
        @param file_name: 檔案名稱
        @return: base64 編碼的檔案內容
        """
        if not dir_path or not file_name:
            raise ValidationError("目錄路徑或檔案名稱參數不可為空")

        token = self._get_token(env)
        root_user = self._get_user(env)

        full_path = f"{dir_path}/{file_name}".strip("/")
        encode_path = quote(full_path)

        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/users/{root_user}/drive/root:/{encode_path}:/content"

        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 404:
                self._get_token(env, force_refresh=True)
                _logger.error(f"Onedrive 檔案不存在: {full_path}")
                return b""

            return base64.b64encode(response.content).decode("utf-8")

        except requests.RequestException as e:
            self._get_token(env, force_refresh=True)
            _logger.exception("取得檔案內容時出錯: %s", e)
            raise ValidationError(f"取得檔案內容時出錯: {str(e)}")

    def get_file_contents(self, env, dir_path, target_files) -> dict:
        """
        批量取得多個檔案內容，此方式適用於檔案在同個目錄下
        @param env: 環境參數
        @param dir_path: 目錄路徑
        @param target_files: 目標檔案名稱的集合，例如 {"abc.pdf", "def.xlsx"}
        @return: dict {檔案類型: base64 編碼內容}，目前只有回傳pdf和excel各一個檔案
        """
        token = self._get_token(env)
        root_user = self._get_user(env)

        encode_path = quote(dir_path)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/users/{root_user}/drive/root:/{encode_path}:/children"

        try:
            results = {}
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 404:
                self._get_token(env, force_refresh=True)
                _logger.error(f"Onedrive 目錄不存在: {dir_path}")
                return results

            files = resp.json().get("value", [])

            for f in files:
                name = f.get("name")
                if name not in target_files:
                    continue

                download_url = f.get("@microsoft.graph.downloadUrl")
                if not download_url:
                    continue

                file_resp = requests.get(download_url, timeout=30)

                results["pdf" if name.endswith(".pdf") else "excel"] = base64.b64encode(
                    file_resp.content
                ).decode("utf-8")
        except requests.RequestException as e:
            self._get_token(env, force_refresh=True)
            _logger.exception("批量取得檔案內容時出錯: %s", e)
            raise ValidationError(f"批量取得檔案內容時出錯: {str(e)}")

        return results

    def get_files(self, env, dir_path) -> dict:
        """
        取得指定目錄下的所有檔案資訊
        @param env: 環境參數
        @param dir_path: 目錄路徑
        @return: dict 檔案資訊
        """
        token = self._get_token(env)
        root_user = self._get_user(env)

        encode_path = quote(dir_path)
        headers = {"Authorization": f"Bearer {token}"}
        url = f"https://graph.microsoft.com/v1.0/users/{root_user}/drive/root:/{encode_path}:/children"

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 404:
                self._get_token(env, force_refresh=True)
                _logger.error(f"Onedrive 目錄不存在: {dir_path}")
                return {}

            files = resp.json().get("value", [])
            return {f.get("name"): f for f in files}

        except requests.RequestException as e:
            self._get_token(env, force_refresh=True)
            _logger.exception("取得目錄檔案列表時出錯: %s", e)
            raise ValidationError(f"取得目錄檔案列表時出錯: {str(e)}")