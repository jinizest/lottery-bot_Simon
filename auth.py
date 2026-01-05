import copy
import json
import requests
import rsa
from HttpClient import HttpClientSingleton


class AuthController:
    _REQ_HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36",
        "Connection": "keep-alive",
        "Cache-Control": "max-age=0",
        "sec-ch-ua": '" Not;A Brand";v="99", "Google Chrome";v="91", "Chromium";v="91"',
        "sec-ch-ua-mobile": "?0",
        "Upgrade-Insecure-Requests": "1",
        "Origin": "https://www.dhlottery.co.kr",
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
        "Referer": "https://www.dhlottery.co.kr/",
        "Sec-Fetch-Site": "same-site",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-User": "?1",
        "Sec-Fetch-Dest": "document",
        "Accept-Language": "ko,en-US;q=0.9,en;q=0.8,ko-KR;q=0.7",
    }

    _AUTH_CRED = ""

    def __init__(self):
        self.http_client = HttpClientSingleton.get_instance()
        # Cache the complete Cookie header issued during login so we can reuse
        # auxiliary cookies (e.g., WMONID) that some endpoints expect.
        self._cached_cookie_header = ""

    def login(self, user_id: str, password: str):
        assert type(user_id) == str
        assert type(password) == str

        self._prepare_session()
        modulus, exponent = self._fetch_rsa_key()

        encrypted_user_id = self._encrypt_credential(user_id, modulus, exponent)
        encrypted_password = self._encrypt_credential(password, modulus, exponent)

        headers = self._generate_login_headers()
        data = {
            "userId": encrypted_user_id,
            "userPswdEncn": encrypted_password,
        }

        res = self._try_login(headers, data)
        self._update_auth_cred(res)

    def add_auth_cred_to_headers(self, headers: dict) -> str:
        assert type(headers) == dict

        copied_headers = copy.deepcopy(headers)
        cookie_header = self._cached_cookie_header or f"JSESSIONID={self._AUTH_CRED}"
        copied_headers["Cookie"] = cookie_header
        return copied_headers

    def _prepare_session(self):
        self.http_client.get(
            "https://www.dhlottery.co.kr/login",
            headers=self._generate_login_headers(include_content_type=False),
        )

    def _fetch_rsa_key(self):
        res = self.http_client.get(
            "https://www.dhlottery.co.kr/login/selectRsaModulus.do",
            headers=self._generate_login_headers(include_content_type=False),
        )

        payload = json.loads(res.text)
        data = payload.get("data", {})
        modulus = data.get("rsaModulus")
        exponent = data.get("publicExponent")

        if not modulus or not exponent:
            raise KeyError(
                f"RSA modulus or exponent missing in response: {payload!r}"
            )

        return modulus, exponent

    def _encrypt_credential(self, credential: str, modulus_hex: str, exponent_hex: str) -> str:
        assert type(credential) == str
        pub_key = rsa.PublicKey(int(modulus_hex, 16), int(exponent_hex, 16))
        encrypted_bytes = rsa.encrypt(credential.encode("utf-8"), pub_key)
        return encrypted_bytes.hex()

    def _generate_login_headers(self, include_content_type: bool = True):
        copied_headers = copy.deepcopy(self._REQ_HEADERS)
        copied_headers.update(
            {
                "Referer": "https://www.dhlottery.co.kr/login",
                "Origin": "https://www.dhlottery.co.kr",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        if not include_content_type:
            copied_headers.pop("Content-Type", None)
        return copied_headers

    def _try_login(self, headers: dict, data: dict) -> requests.Response:
        assert type(headers) == dict
        assert type(data) == dict

        res = self.http_client.post(
            "https://www.dhlottery.co.kr/login/securityLoginCheck.do",
            headers=headers,
            data=data,
        )

        body = res.text
        if any(
            msg in body
            for msg in [
                "아이디 또는 비밀번호를 확인해주세요",
                "로그인에 실패",
                "loginFail",
            ]
        ):
            raise PermissionError("로그인 실패: 아이디 또는 비밀번호가 올바르지 않습니다")

        return res

    def _update_auth_cred(self, login_response: requests.Response) -> None:
        """Refresh the cached JSESSIONID after login.

        Prefer the session's cookie jar because redirects may set the cookie
        on subsequent requests. Fall back to the login response headers if the
        cookie jar does not yet contain it so we do not fail when requests
        misses a Set-Cookie during redirect handling.
        """

        try:
            self._AUTH_CRED = self._get_j_session_id_from_session()
            self._cached_cookie_header = self._build_cookie_header()
            return
        except KeyError:
            pass

        self._AUTH_CRED = self._get_j_session_id_from_response(login_response)
        self._cached_cookie_header = self._build_cookie_header(login_response)

    def _get_j_session_id_from_session(self) -> str:
        for cookie in self.http_client.session.cookies:
            if cookie.value and cookie.name.upper().startswith("JSESSIONID"):
                return cookie.value

        raise KeyError("로그인 후 JSESSIONID 쿠키를 찾을 수 없습니다")

    def _get_j_session_id_from_response(self, res: requests.Response):
        assert type(res) == requests.Response
        # First try: requests' cookie jar
        for cookie in res.cookies:
            if cookie.name.upper().startswith("JSESSIONID"):
                return cookie.value

        # Second try: parse Set-Cookie header if present
        set_cookie = res.headers.get("Set-Cookie", "")
        if set_cookie:
            import re

            m = re.search(r"JSESSIONID[^=]*=([^;\s]+)", set_cookie, re.IGNORECASE)
            if m:
                return m.group(1)

        # If still not found, raise a more informative error to help debugging
        snippet = ""
        try:
            snippet = res.text[:500]
        except Exception:
            snippet = "<could not read response body>"

        raise KeyError(
            f"JSESSIONID cookie is not set in response (status={res.status_code}). "
            f"Set-Cookie: {set_cookie!r}. Response body snippet: {snippet!r}"
        )

    def _generate_req_headers(self, j_session_id: str):
        assert type(j_session_id) == str

        copied_headers = copy.deepcopy(self._REQ_HEADERS)
        copied_headers["Cookie"] = f"JSESSIONID={j_session_id}"
        return copied_headers

    def _build_cookie_header(self, res: requests.Response = None) -> str:
        """Assemble the Cookie header from known cookies.

        Some endpoints depend on cookies other than JSESSIONID. Build a
        semicolon-separated header from the session jar (and optionally a
        single response) so callers can reuse the full set.
        """

        cookies = []

        def _append_from_jar(jar):
            for cookie in jar:
                if cookie.value:
                    cookies.append(f"{cookie.name}={cookie.value}")

        _append_from_jar(self.http_client.session.cookies)

        if res is not None:
            _append_from_jar(res.cookies)
            set_cookie = res.headers.get("Set-Cookie", "")
            if set_cookie:
                for part in set_cookie.split(","):
                    if "=" in part:
                        name, value = part.split("=", 1)
                        value = value.split(";", 1)[0].strip()
                        name = name.strip()
                        if value:
                            cookies.append(f"{name}={value}")

        # Ensure JSESSIONID is always present if we already discovered it
        if self._AUTH_CRED and not any(
            c.upper().startswith("JSESSIONID=") for c in cookies
        ):
            cookies.append(f"JSESSIONID={self._AUTH_CRED}")

        return "; ".join(dict.fromkeys(cookies))
