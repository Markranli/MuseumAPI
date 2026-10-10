import logging
import threading
import time
from typing import Any, Dict, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT_URL = "https://collectionapi.metmuseum.org/public/collection"

MIN_INTERVAL = 0.05
WAF_RETRIES = 3

logger = logging.getLogger("met_api")


class MetClient:
    def __init__(self, root_url: str = ROOT_URL, timeout: float = 30.0):
        self.root_url = root_url.rstrip("/")
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last_request = 0.0

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        })
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retry))

    def _throttle(self) -> None:
        with self._lock:
            wait = self._last_request + MIN_INTERVAL - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last_request = time.monotonic()

    @staticmethod
    def is_waf_block(response: requests.Response) -> bool:
        return response.status_code == 403 and "Incapsula" in response.text

    def get(self, path: str, params: Optional[Dict[str, Any]] = None,
            version: str = "v1", retry_waf: bool = True) -> requests.Response:
        url = f"{self.root_url}/{version}/{path.lstrip('/')}"
        attempt = 0
        while True:
            attempt += 1
            self._throttle()
            logger.info("REQUEST  GET %s params=%s", url, params)
            started = time.perf_counter()
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException:
                logger.exception("ERROR    GET %s params=%s", url, params)
                raise
            elapsed = time.perf_counter() - started
            logger.info("RESPONSE %s status=%s time=%.3fs", response.url, response.status_code, elapsed)
            logger.debug("BODY     %s", response.text[:500])

            if self.is_waf_block(response) and retry_waf and attempt <= WAF_RETRIES:
                pause = 2 ** attempt
                logger.warning("WAF заблокировал запрос (403), повтор %s/%s через %s с",
                               attempt, WAF_RETRIES, pause)
                time.sleep(pause)
                continue

            if response.status_code >= 400:
                logger.warning("HTTP %s: %s", response.status_code, response.text[:300])
            return response

    def get_object(self, object_id: Any) -> requests.Response:
        return self.get(f"objects/{object_id}")

    def get_objects(self, **params) -> requests.Response:
        return self.get("objects", params=params or None)

    def search(self, q: Optional[str] = None, retry_waf: bool = True, **params) -> requests.Response:
        if q is not None:
            params["q"] = q
        return self.get("search", params=params or None, version="v1.1", retry_waf=retry_waf)

    def search_v1(self, q: Optional[str] = None, **params) -> requests.Response:
        if q is not None:
            params["q"] = q
        return self.get("search", params=params or None, version="v1")

    def get_departments(self) -> requests.Response:
        return self.get("departments")
