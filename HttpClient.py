import requests
from requests.exceptions import RequestException

class HttpClient:
    def __init__(self):
        self.session = requests.Session()

    def __del__(self):
        self.session.close()

    def post(self, url: str, headers: dict = None, data: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        try:
            print(f"[http] POST url={url}")
            res = self.session.post(url, headers=session_headers, data=data, timeout=30, allow_redirects=True)
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
            print(f"[http] GET url={url}")
            res = self.session.get(url, headers=session_headers, params=params, timeout=30)
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
