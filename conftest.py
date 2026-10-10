import logging

import pytest

from client import MetClient
from models import DepartmentsResponse, ObjectsListResponse, SearchResponse

logger = logging.getLogger("met_api")

logging.getLogger("urllib3").setLevel(logging.WARNING)

SEED_KEYWORDS = ["sunflowers", "monet", "armor", "vase", "sword", "portrait"]


@pytest.fixture(scope="session")
def client() -> MetClient:
    return MetClient()


@pytest.fixture(scope="session")
def departments(client):
    response = client.get_departments()
    assert response.status_code == 200
    return DepartmentsResponse.model_validate(response.json()).departments


@pytest.fixture(scope="session")
def all_objects(client) -> ObjectsListResponse:
    response = client.get_objects()
    assert response.status_code == 200
    return ObjectsListResponse.model_validate(response.json())


@pytest.fixture(scope="session")
def sample_object_ids(client):
    response = client.search("sunflowers", hasImages="true")
    assert response.status_code == 200
    ids = SearchResponse.model_validate(response.json()).ids
    assert ids, "поиск по 'sunflowers' ничего не вернул"
    return ids[:3]


@pytest.fixture(scope="session")
def many_object_ids(client):
    ids = []
    for keyword in SEED_KEYWORDS:
        response = client.search(keyword, limit=5)
        assert response.status_code == 200
        found = SearchResponse.model_validate(response.json()).ids
        ids.extend(i for i in found if i not in ids)
    assert len(ids) >= 20
    return ids


@pytest.fixture(autouse=True)
def log_test_boundaries(request):
    logger.info("=== START %s ===", request.node.nodeid)
    yield
    logger.info("=== END   %s ===", request.node.nodeid)
