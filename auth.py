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

    _LOGIN_PAGE_URLS = (
        "https://www.dhlottery.co.kr/login",
        "https://www.dhlottery.co.kr/user.do?method=login",
    )
    _RSA_KEY_URLS = (
        "https://www.dhlottery.co.kr/login/selectRsaModulus.do",
        "https://www.dhlottery.co.kr/user.do?method=selectRsaModulus",
    )
    _LOGIN_ENDPOINTS = (
        "https://www.dhlottery.co.kr/login/securityLoginCheck.do",
        "https://www.dhlottery.co.kr/user.do?method=login",
    )

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

        last_error = None
        for login_url in self._LOGIN_ENDPOINTS:
            try:
                res = self._try_login(headers, data, login_url)
                self._update_auth_cred(res)
                return
            except Exception as exc:
                last_error = exc

        if last_error:
            raise last_error

    def add_auth_cred_to_headers(self, headers: dict) -> str:
        assert type(headers) == dict

        copied_headers = copy.deepcopy(headers)
        cookie_header = self._cached_cookie_header or f"JSESSIONID={self._AUTH_CRED}"
        copied_headers["Cookie"] = cookie_header
        return copied_headers

    def _prepare_session(self):
        for url in self._LOGIN_PAGE_URLS:
            try:
                self.http_client.get(
                    url,
                    headers=self._generate_login_headers(
                        include_content_type=False,
                        referer=url,
                    ),
                )
                return
            except Exception:
                continue

    def _fetch_rsa_key(self):
        last_payload = None
        for url in self._RSA_KEY_URLS:
            try:
                res = self.http_client.get(
                    url,
                    headers=self._generate_login_headers(
                        include_content_type=False,
                        referer=url,
                    ),
                )
                payload = json.loads(res.text)
                last_payload = payload
                data = payload.get("data", {})
                modulus = data.get("rsaModulus")
                exponent = data.get("publicExponent")
                if modulus and exponent:
                    return modulus, exponent
            except Exception:
                continue

        raise KeyError(
            f"RSA modulus or exponent missing in response: {last_payload!r}"
        )

    def _encrypt_credential(self, credential: str, modulus_hex: str, exponent_hex: str) -> str:
        assert type(credential) == str
        pub_key = rsa.PublicKey(int(modulus_hex, 16), int(exponent_hex, 16))
        encrypted_bytes = rsa.encrypt(credential.encode("utf-8"), pub_key)
        return encrypted_bytes.hex()

    def _generate_login_headers(self, include_content_type: bool = True, referer: str | None = None):
        copied_headers = copy.deepcopy(self._REQ_HEADERS)
        copied_headers.update(
            {
                "Referer": referer or "https://www.dhlottery.co.kr/login",
                "Origin": "https://www.dhlottery.co.kr",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )
        if not include_content_type:
            copied_headers.pop("Content-Type", None)
        return copied_headers

    def _try_login(self, headers: dict, data: dict, url: str) -> requests.Response:
        assert type(headers) == dict
        assert type(data) == dict

        req_headers = copy.deepcopy(headers)
        req_headers["Referer"] = url
        res = self.http_client.post(
            url,
            headers=req_headers,
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
        """Refresh the cached session cookies after login.

        Some environments report merge conflicts when the session cookie is set
        on a redirect response or under a different cookie name. To avoid
        brittle parsing, collect cookies from the session jar, the login
        response, and any intermediate responses, then build a unified cookie
        header and extract the JSESSIONID-equivalent value from that set.
        """

        cookies = self._collect_cookies(login_response)
        self._AUTH_CRED = self._extract_j_session_id(cookies)
        self._cached_cookie_header = self._build_cookie_header_from_list(cookies)

    def _extract_j_session_id(self, cookies: list[tuple[str, str]]) -> str:
        for name, value in cookies:
            if value and name.upper().startswith("JSESSIONID"):
                return value

        raise KeyError("로그인 후 JSESSIONID 쿠키를 찾을 수 없습니다")

    def _generate_req_headers(self, j_session_id: str):
        assert type(j_session_id) == str

        copied_headers = copy.deepcopy(self._REQ_HEADERS)
        copied_headers["Cookie"] = f"JSESSIONID={j_session_id}"
        return copied_headers

    def _build_cookie_header_from_list(self, cookies: list[tuple[str, str]]) -> str:
        """Assemble the Cookie header from known cookies.

        Some endpoints depend on cookies other than JSESSIONID. Build a
        semicolon-separated header from the aggregated cookie list so callers
        can reuse the full set.
        """

        cookie_pairs = [f"{name}={value}" for name, value in cookies if value]

        # Ensure JSESSIONID is always present if we already discovered it
        if self._AUTH_CRED and not any(
            pair.upper().startswith("JSESSIONID=") for pair in cookie_pairs
        ):
            cookie_pairs.append(f"JSESSIONID={self._AUTH_CRED}")

        return "; ".join(dict.fromkeys(cookie_pairs))

    def _collect_cookies(self, res: requests.Response) -> list[tuple[str, str]]:
        cookies: list[tuple[str, str]] = []

        def _append_cookie(name: str, value: str):
            if value:
                cookies.append((name, value))

        def _parse_set_cookie(header_value: str):
            for part in header_value.split(","):
                if "=" in part:
                    name, value = part.split("=", 1)
                    value = value.split(";", 1)[0].strip()
                    name = name.strip()
                    _append_cookie(name, value)

        _parse_set_cookie(self.http_client.session.headers.get("Cookie", ""))
        for cookie in self.http_client.session.cookies:
            _append_cookie(cookie.name, cookie.value)

        if res is not None:
            for cookie in res.cookies:
                _append_cookie(cookie.name, cookie.value)
            _parse_set_cookie(res.headers.get("Set-Cookie", ""))
            for history_res in res.history:
                _parse_set_cookie(history_res.headers.get("Set-Cookie", ""))
                for cookie in history_res.cookies:
                    _append_cookie(cookie.name, cookie.value)

        # Deduplicate while preserving order
        seen = set()
        unique = []
        for name, value in cookies:
            key = (name.upper(), value)
            if key not in seen:
                seen.add(key)
                unique.append((name, value))

        return unique
