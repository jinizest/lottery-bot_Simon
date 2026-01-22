import os
import time
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util import Retry

class HttpClient:
    def __init__(
        self,
        timeout: int = 90,
        max_retries: int = 3,
        connect_timeout: int = None,
        read_timeout: int = None,
        request_delay: float = None,
    ):
        self.session = requests.Session()
        connect = connect_timeout or int(os.getenv("CONNECT_TIMEOUT", "30"))
        read = read_timeout or int(os.getenv("READ_TIMEOUT", str(timeout)))
        self.timeout = (connect, read)
        self.request_delay = request_delay if request_delay is not None else float(
            os.getenv("REQUEST_DELAY", "0.6")
        )
        retry_strategy = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def __del__(self):
        self.session.close()

    def post(self, url: str, headers: dict = None, data: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        try:
            if self.request_delay > 0:
                time.sleep(self.request_delay)
            print(f"[http] POST url={url}")
            res = self.session.post(
                url,
                headers=session_headers,
                data=data,
                timeout=self.timeout,
                allow_redirects=True,
            )
            res.raise_for_status()
            print(f"[http] POST success url={url} status={res.status_code}")
            return res
        except RequestException as exc:
            print(f"[http] POST failed url={url} error={exc}")
            raise

    def get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        try:
            if self.request_delay > 0:
                time.sleep(self.request_delay)
            print(f"[http] GET url={url}")
            res = self.session.get(
                url,
                headers=session_headers,
                params=params,
                timeout=self.timeout,
            )
            res.raise_for_status()
            print(f"[http] GET success url={url} status={res.status_code}")
            return res
        except RequestException as exc:
            print(f"[http] GET failed url={url} error={exc}")
            raise

class HttpClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if HttpClientSingleton._instance is None:
            HttpClientSingleton._instance = HttpClient()
        return HttpClientSingleton._instance
