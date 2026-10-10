import statistics
import time

import pytest

from helpers import fetch_objects_parallel
from models import DepartmentsResponse

KNOWN_ID = 436535


def test_object_response_time(client):
    times = []
    for _ in range(5):
        started = time.perf_counter()
        response = client.get_object(KNOWN_ID)
        times.append(time.perf_counter() - started)
        assert response.status_code == 200

    assert statistics.median(times) < 10


@pytest.mark.bulk
def test_series_of_requests_is_stable(client):
    responses = [client.get_departments() for _ in range(20)]

    assert all(r.status_code == 200 for r in responses)
    first = DepartmentsResponse.model_validate(responses[0].json())
    for response in responses[1:]:
        assert DepartmentsResponse.model_validate(response.json()) == first


@pytest.mark.bulk
def test_parallel_requests_do_not_fail(client):
    results = fetch_objects_parallel(client, [KNOWN_ID] * 30, workers=5)

    statuses = [response.status_code for _, response in results]
    assert statuses.count(200) == len(statuses), statuses
