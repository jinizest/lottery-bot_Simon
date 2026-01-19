import requests
import time
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
        return self._request_with_retry(
            self.session.post,
            url,
            headers=session_headers,
            data=data,
            timeout=30,
            allow_redirects=True,
        )

    def get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        return self._request_with_retry(
            self.session.get,
            url,
            headers=session_headers,
            params=params,
            timeout=30,
        )

    def _request_with_retry(self, request_func, url: str, retries: int = 2, backoff: float = 1.0, **kwargs) -> requests.Response:
        last_error = None
        for attempt in range(retries + 1):
            try:
                res = request_func(url, **kwargs)
                res.raise_for_status()
                return res
            except RequestException as exc:
                last_error = exc
                if attempt >= retries:
                    raise
                time.sleep(backoff * (2 ** attempt))
        raise last_error

class HttpClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if HttpClientSingleton._instance is None:
            HttpClientSingleton._instance = HttpClient()
        return HttpClientSingleton._instance
