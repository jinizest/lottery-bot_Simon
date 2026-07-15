import copy
import datetime
import logging
import os
import time
import requests
import json
import base64
import binascii
import re
from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5
from HttpClient import HttpClientSingleton

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
logger = logging.getLogger(__name__)


class SessionValidationError(RuntimeError):
    pass


class LoginValidationError(RuntimeError):
    pass


class AuthController:
    _REQ_HEADERS = {
        "User-Agent": USER_AGENT,
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://dhlottery.co.kr/",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    _AUTH_CRED = ""

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()
        self._last_balance = None

    def login(self, user_id: str, password: str):
        assert isinstance(user_id, str)
        assert isinstance(password, str)

        login_headers = copy.deepcopy(self._REQ_HEADERS)
        login_headers.update({
            "Origin": "https://www.dhlottery.co.kr",
            "Referer": "https://www.dhlottery.co.kr/",
        })
        self.http_client.get("https://www.dhlottery.co.kr/user.do?method=login", headers=login_headers)

        modulus, exponent = self._get_rsa_key()

        enc_user_id = self._rsa_encrypt(user_id, modulus, exponent)
        enc_password = self._rsa_encrypt(password, modulus, exponent)

        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.dhlottery.co.kr",
            "Referer": "https://www.dhlottery.co.kr/user.do?method=login"
        })
        
        data = {
            "userId": enc_user_id,
            "userPswdEncn": enc_password, 
            "inpUserId": user_id
        }

        self._try_login(headers, data)
        
    def add_auth_cred_to_headers(self, headers: dict) -> str:
        assert isinstance(headers, dict)

        copied_headers = copy.deepcopy(headers)
        return copied_headers

    def _get_default_auth_cred(self):
        res = self.http_client.get(
            "https://www.dhlottery.co.kr/common.do?method=main"
        )
        return self._get_j_session_id_from_response(res)

    def _get_rsa_key(self):
        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.dhlottery.co.kr/user.do?method=login"
        })
        headers.pop("Upgrade-Insecure-Requests", None)

        res = self.http_client.get(
            "https://www.dhlottery.co.kr/login/selectRsaModulus.do",
            headers=headers
        )
        
        try:
            data = res.json()
        except ValueError:
             raise ValueError(f"Failed to parse JSON. St: {res.status_code}")
        
        if "data" in data and "rsaModulus" in data["data"]:
            modulus = data["data"]["rsaModulus"]
            exponent = data["data"]["publicExponent"]
            return modulus, exponent
        
        if "rsaModulus" in data:
            return data["rsaModulus"], data["publicExponent"]
            
        raise KeyError("rsaModulus not found")

    def _rsa_encrypt(self, text, modulus, exponent):
        key_spec = RSA.construct((int(modulus, 16), int(exponent, 16)))
        cipher = PKCS1_v1_5.new(key_spec)
        ciphertext = cipher.encrypt(text.encode('utf-8'))
        return binascii.hexlify(ciphertext).decode('utf-8')

    def _get_j_session_id_from_response(self, res: requests.Response):
        assert isinstance(res, requests.Response)

        for cookie in res.cookies:
            if cookie.name == "JSESSIONID":
                return cookie.value

        return ""

    def _generate_req_headers(self):
        return copy.deepcopy(self._REQ_HEADERS)

    def _try_login(self, headers: dict, data: dict):
        assert isinstance(headers, dict)
        assert isinstance(data, dict)

        url = "https://www.dhlottery.co.kr/login/securityLoginCheck.do"
        logger.info("[auth] Login request url=%s", url)
        res = self.http_client.post(
            url,
            headers=headers,
            data=data,
        )

        self._log_login_response_summary(res)
        self._validate_login_response(res)

        new_jsessionid = self._get_j_session_id_from_response(res)
        if new_jsessionid:
             self._update_auth_cred(new_jsessionid)
             logger.info(
                 "[auth] Login JSESSIONID cookie updated cookie_names=%s",
                 self._get_safe_cookie_names(),
             )
        else:
             logger.info(
                 "[auth] Login response did not include JSESSIONID; preserving server-issued cookies cookie_names=%s",
                 self._get_safe_cookie_names(),
             )

        if not self.validate_session():
            raise LoginValidationError(
                "Login HTTP request completed, but authenticated session validation failed."
            )

        return res

    def _log_login_response_summary(self, res: requests.Response) -> None:
        content_type = res.headers.get("Content-Type", "")
        logger.info(
            "[auth] Login response received url=%s status=%s content_type=%s final_url=%s",
            res.request.url if res.request else "unknown",
            res.status_code,
            content_type,
            res.url,
        )
        logger.info("[auth] Login response cookie_names=%s", self._get_safe_cookie_names())

        parsed = self._parse_json_safely(res)
        if isinstance(parsed, dict):
            logger.info(
                "[auth] Login response json_summary=%s",
                self._summarize_json(parsed),
            )
            return

        logger.info(
            "[auth] Login response body_preview=%s",
            self._safe_text_preview(res.text),
        )

    def _validate_login_response(self, res: requests.Response) -> None:
        parsed = self._parse_json_safely(res)
        if isinstance(parsed, dict):
            result_code = self._find_first_value(
                parsed,
                ("resultCode", "resultCd", "returnCode", "code", "status"),
            )
            result_message = self._find_first_value(
                parsed,
                ("resultMsg", "message", "msg", "returnMsg", "errorMessage"),
            )
            if result_code and str(result_code).strip() not in ("0", "00", "000", "SUCCESS", "success", "OK", "ok", "Y"):
                raise LoginValidationError(
                    "Login response indicates failure "
                    f"result_code={result_code} result_message={self._sanitize_log_text(result_message)}"
                )
            if result_message and self._contains_login_failure_keyword(str(result_message)):
                raise LoginValidationError(
                    "Login response contains failure message "
                    f"result_message={self._sanitize_log_text(result_message)}"
                )
            return

        text = res.text or ""
        if self._contains_login_failure_keyword(text):
            raise LoginValidationError(
                "Login response body contains failure keywords "
                f"body_preview={self._safe_text_preview(text)}"
            )

    def _parse_json_safely(self, res: requests.Response):
        content_type = res.headers.get("Content-Type", "")
        text = (res.text or "").strip()
        if "json" not in content_type.lower() and not text.startswith(("{", "[")):
            return None
        try:
            return res.json()
        except ValueError:
            return None

    def _summarize_json(self, value) -> dict:
        if not isinstance(value, dict):
            return {"type": type(value).__name__}
        summary = {"keys": sorted(value.keys())}
        for key in ("resultCode", "resultCd", "returnCode", "code", "status", "resultMsg", "message", "msg", "returnMsg", "errorMessage"):
            found = self._find_first_value(value, (key,))
            if found is not None:
                summary[key] = self._sanitize_log_text(found)
        return summary

    def _find_first_value(self, value, keys: tuple):
        if isinstance(value, dict):
            for key, child in value.items():
                if key in keys:
                    return child
                found = self._find_first_value(child, keys)
                if found is not None:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = self._find_first_value(child, keys)
                if found is not None:
                    return found
        return None

    def _contains_login_failure_keyword(self, text: str) -> bool:
        lowered = text.lower()
        failure_keywords = (
            "로그인 실패",
            "비밀번호",
            "아이디",
            "인증",
            "본인확인",
            "휴면",
            "차단",
            "captcha",
            "login failed",
            "unauthorized",
            "error",
        )
        success_keywords = ("로그아웃", "logout")
        return any(keyword in lowered for keyword in failure_keywords) and not any(
            keyword in lowered for keyword in success_keywords
        )

    def _safe_text_preview(self, text: str, limit: int = 500) -> str:
        sanitized = self._sanitize_log_text(text)
        return sanitized[:limit]

    def _sanitize_log_text(self, value) -> str:
        if value is None:
            return ""
        text = str(value)
        text = re.sub(r"[0-9a-fA-F]{64,}", "[REDACTED_HEX]", text)
        text = re.sub(r"(?i)(password|passwd|pswd|userPswdEncn|userId|inpUserId)=[^&\s]+", r"\1=[REDACTED]", text)
        text = re.sub(
            r"(?i)(['\"]?(?:password|passwd|pswd|userPswdEncn|userId|inpUserId)['\"]?\s*:\s*)['\"]?[^,'\"}]+['\"]?",
            r"\1[REDACTED]",
            text,
        )
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _get_safe_cookie_names(self) -> list:
        return sorted({cookie.name for cookie in self.http_client.session.cookies})

    def _update_auth_cred(self, j_session_id: str) -> None:
        assert isinstance(j_session_id, str)
        self._AUTH_CRED = j_session_id

        if j_session_id:
             self.http_client.session.cookies.set("JSESSIONID", j_session_id, domain=".dhlottery.co.kr")

        wmonid = None
        for cookie in self.http_client.session.cookies:
             if cookie.name == "WMONID":
                 wmonid = cookie.value
                 break

        if wmonid:
             self.http_client.session.cookies.set("WMONID", wmonid, domain=".dhlottery.co.kr")

    def get_current_session_id(self) -> str:
        for cookie_name in ("JSESSIONID", "DHJSESSIONID", "WMONID"):
            for cookie in self.http_client.session.cookies:
                if cookie.name == cookie_name:
                    return cookie.value

        if self._AUTH_CRED:
            return self._AUTH_CRED

        return ""
            
    def get_user_balance(self) -> str:
        try:
             connect_timeout = int(os.getenv("BALANCE_CONNECT_TIMEOUT", "7"))
             read_timeout = int(os.getenv("BALANCE_READ_TIMEOUT", "15"))
             timeout = (connect_timeout, read_timeout)
             max_attempts = int(os.getenv("BALANCE_MAX_ATTEMPTS", "6"))

             def _refresh_mypage():
                 try:
                     self.http_client.get("https://dhlottery.co.kr/mypage/home")
                 except requests.RequestException as exc:
                     logger.warning("[auth] Balance preflight failed: %s", exc)

             def _get_with_retry(headers: dict = None) -> requests.Response:
                 last_exc = None
                 for attempt in range(1, max_attempts + 1):
                     timestamp = int(datetime.datetime.now().timestamp() * 1000)
                     url = f"https://dhlottery.co.kr/mypage/selectUserMndp.do?_={timestamp}"
                     try:
                         if attempt > 1:
                             _refresh_mypage()
                         logger.info(
                             "[auth] Balance request url=%s attempt=%s/%s",
                             url,
                             attempt,
                             max_attempts,
                         )
                         res = self.http_client.session.get(
                             url,
                             headers=headers,
                             timeout=timeout,
                         )
                         res.raise_for_status()
                         return res
                     except requests.RequestException as exc:
                         last_exc = exc
                         logger.warning(
                             "[auth] Balance request failed url=%s attempt=%s/%s error=%s",
                             url,
                             attempt,
                             max_attempts,
                             exc,
                         )
                         if attempt < max_attempts:
                             time.sleep(0.75 * attempt)
                 raise last_exc

             _refresh_mypage()

             headers = copy.deepcopy(self._REQ_HEADERS)
             headers.update({
                "Referer": "https://dhlottery.co.kr/mypage/home",
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json;charset=UTF-8",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "requestMenuUri": "/mypage/home",
                "AJAX": "true",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": "same-origin",
                "Sec-Fetch-Dest": "empty"
             })
             
             res = _get_with_retry(headers=headers)
             
             txt = res.text.strip()
             if txt.startswith("<"):
                  return "확인 불가 (로그인/설정)"

             data = json.loads(txt)
             
             if 'data' in data and isinstance(data['data'], dict):
                 data = data['data']

             if 'userMndp' in data:
                 data = data['userMndp']
                 
             if 'totalAmt' in data:
                 val = str(data['totalAmt']).replace(',', '')
                 balance = f"{int(val):,}원"
                 self._last_balance = balance
                 return balance
             
             return "0원"

        except Exception as e:
             if self._last_balance:
                 logger.warning("[auth] Balance fallback to cached value due to error: %s", e)
                 return self._last_balance
             logger.error("[auth] Balance request ultimately failed: %s", e)
             return "확인 불가"

    def validate_session(self) -> bool:
        url = "https://www.dhlottery.co.kr/mypage/home"
        headers = copy.deepcopy(self._REQ_HEADERS)
        headers.update({
            "Origin": "https://www.dhlottery.co.kr",
            "Referer": "https://www.dhlottery.co.kr/common.do?method=main",
        })
        try:
            res = self.http_client.session.get(url, headers=headers, timeout=self.http_client.timeout)
        except requests.RequestException as exc:
            logger.warning(
                "[auth] Session validation request failed url=%s error=%s",
                url,
                exc,
            )
            return False

        logger.info(
            "[auth] Session validation response status=%s final_url=%s cookie_names=%s",
            res.status_code,
            res.url,
            self._get_safe_cookie_names(),
        )

        if res.status_code in (401, 403):
            logger.warning(
                "[auth] Session validation unauthorized status=%s body_preview=%s",
                res.status_code,
                self._safe_text_preview(res.text),
            )
            return False

        if res.status_code >= 400:
            logger.warning(
                "[auth] Session validation failed status=%s body_preview=%s",
                res.status_code,
                self._safe_text_preview(res.text),
            )
            return False

        if "user.do?method=login" in res.url:
            logger.info("[auth] Session validation detected login redirect.")
            return False

        text = res.text.lower()
        if "로그인" in res.text and "로그아웃" not in res.text:
            logger.info("[auth] Session validation detected login page content.")
            return False

        if "login" in text and "logout" not in text and "securitylogincheck" not in text:
            logger.info("[auth] Session validation detected login page keywords.")
            return False

        return True

    def ensure_session(self) -> None:
        if not self.validate_session():
            raise SessionValidationError("Session validation failed.")
