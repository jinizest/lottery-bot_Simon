import os
import time
import logging
import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException
from urllib3.util import Retry

import common

common.setup_logging()
logger = logging.getLogger(__name__)


class HttpClient:
    def __init__(
        self,
        timeout: int = 20,
        max_retries: int = None,
        connect_timeout: int = None,
        read_timeout: int = None,
        request_delay: float = None,
    ):
        self.session = requests.Session()
        connect = connect_timeout or int(os.getenv("CONNECT_TIMEOUT", "6"))
        read = read_timeout or int(os.getenv("READ_TIMEOUT", "10"))
        self.timeout = (connect, read)
        self.request_delay = request_delay if request_delay is not None else float(
            os.getenv("REQUEST_DELAY", "0.2")
        )
        self.max_retries = max_retries if max_retries is not None else int(
            os.getenv("HTTP_MAX_RETRIES", "4")
        )
        self._mount_retry_adapters()

    def _mount_retry_adapters(self) -> None:
        retry_strategy = Retry(
            total=self.max_retries,
            connect=self.max_retries,
            read=self.max_retries,
            status=self.max_retries,
            backoff_factor=float(os.getenv("HTTP_BACKOFF_FACTOR", "0.3")),
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=None,
            raise_on_status=False,
        )
        pool_connections = int(os.getenv("HTTP_POOL_CONNECTIONS", "10"))
        pool_maxsize = int(os.getenv("HTTP_POOL_MAXSIZE", "10"))
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
        )
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    def reset_connection_pool(self) -> None:
        """Drop stale keep-alive connections while preserving login cookies."""
        logger.info("[http] Resetting connection pool")
        for adapter in self.session.adapters.values():
            adapter.close()
        self._mount_retry_adapters()

    def __del__(self):
        self.session.close()

    def post(self, url: str, headers: dict = None, data: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        try:
            if self.request_delay > 0:
                time.sleep(self.request_delay)
            logger.info("[http] POST url=%s timeout=%s", url, self.timeout)
            res = self.session.post(
                url,
                headers=session_headers,
                data=data,
                timeout=self.timeout,
                allow_redirects=True,
            )
            res.raise_for_status()
            logger.info("[http] POST success url=%s status=%s", url, res.status_code)
            return res
        except RequestException as exc:
            logger.error("[http] POST failed url=%s error=%s", url, exc)
            raise

    def get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        session_headers = self.session.headers.copy()
        if headers:
            session_headers.update(headers)
        try:
            if self.request_delay > 0:
                time.sleep(self.request_delay)
            logger.info("[http] GET url=%s timeout=%s", url, self.timeout)
            res = self.session.get(
                url,
                headers=session_headers,
                params=params,
                timeout=self.timeout,
            )
            res.raise_for_status()
            logger.info("[http] GET success url=%s status=%s", url, res.status_code)
            return res
        except RequestException as exc:
            logger.error("[http] GET failed url=%s error=%s", url, exc)
            raise


class HttpClientSingleton:
    _instance = None

    @staticmethod
    def get_instance():
        if HttpClientSingleton._instance is None:
            HttpClientSingleton._instance = HttpClient()
        return HttpClientSingleton._instance
