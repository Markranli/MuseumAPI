from concurrent.futures import ThreadPoolExecutor
from typing import Any, List, Tuple

import requests


def fetch_objects_parallel(client, ids: List[int], workers: int = 5) -> List[Tuple[Any, requests.Response]]:

    def fetch(object_id):
        return object_id, client.get_object(object_id)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(fetch, ids))
