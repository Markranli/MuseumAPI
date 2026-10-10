import pytest
from pydantic import ValidationError

from helpers import fetch_objects_parallel
from models import ErrorResponse, MetObject, ObjectsListResponse

KNOWN_ID = 436535


@pytest.mark.smoke
def test_get_known_object(client):
    response = client.get_object(KNOWN_ID)

    assert response.status_code == 200
    assert "application/json" in response.headers["Content-Type"]
    obj = MetObject.model_validate(response.json())
    assert obj.objectID == KNOWN_ID
    assert obj.objectURL.endswith(str(KNOWN_ID))


def test_objects_found_by_search_match_model(client, sample_object_ids):
    for object_id in sample_object_ids:
        response = client.get_object(object_id)

        assert response.status_code == 200
        obj = MetObject.model_validate(response.json())
        assert obj.objectID == object_id


@pytest.mark.bulk
def test_many_objects_match_model(client, many_object_ids):
    results = fetch_objects_parallel(client, many_object_ids)

    errors = []
    for object_id, response in results:
        if response.status_code != 200:
            errors.append(f"{object_id}: HTTP {response.status_code}")
            continue
        try:
            obj = MetObject.model_validate(response.json())
        except ValidationError as error:
            errors.append(f"{object_id}: {error.errors()[0]}")
            continue
        if obj.objectID != object_id:
            errors.append(f"{object_id}: в ответе objectID={obj.objectID}")

    assert len(results) == len(many_object_ids)
    assert not errors, "\n".join(errors)


@pytest.mark.bulk
def test_many_objects_dates_and_images(client, many_object_ids):
    results = fetch_objects_parallel(client, many_object_ids)

    errors = []
    for object_id, response in results:
        obj = MetObject.model_validate(response.json())
        if obj.objectBeginDate > obj.objectEndDate:
            errors.append(f"{object_id}: начало {obj.objectBeginDate} позже конца {obj.objectEndDate}")
        if obj.primaryImage and not obj.primaryImage.startswith("https://"):
            errors.append(f"{object_id}: primaryImage не https")
        if obj.isPublicDomain is False and obj.primaryImage:
            errors.append(f"{object_id}: есть изображение, но объект не в public domain")

    assert not errors, "\n".join(errors)


def test_object_response_is_stable(client):
    first = client.get_object(KNOWN_ID).json()
    second = client.get_object(KNOWN_ID).json()

    assert first["objectID"] == second["objectID"]
    assert first["title"] == second["title"]


@pytest.mark.parametrize("object_id", [999999999, 2147483647])
def test_nonexistent_id_returns_404(client, object_id):
    response = client.get_object(object_id)

    assert response.status_code == 404
    error = ErrorResponse.model_validate(response.json())
    assert "not found" in error.message.lower()


@pytest.mark.parametrize("bad_id", ["abc", "1.5"])
def test_non_numeric_id_returns_400(client, bad_id):
    response = client.get_object(bad_id)

    assert response.status_code == 400
    error = ErrorResponse.model_validate(response.json())
    assert "parse" in error.message.lower()


@pytest.mark.parametrize("bad_id", ["-1", "0"])
def test_non_positive_id_returns_404(client, bad_id):
    response = client.get_object(bad_id)

    assert response.status_code == 404
    ErrorResponse.model_validate(response.json())


def test_model_rejects_invalid_data():
    with pytest.raises(ValidationError):
        MetObject.model_validate({"objectID": "не число", "title": ""})


def test_model_rejects_foreign_url():
    data = {
        "objectID": 1, "isHighlight": False, "isPublicDomain": True, "title": "x",
        "department": "y", "objectURL": "https://example.com/1",
        "objectBeginDate": 1900, "objectEndDate": 1901,
    }
    with pytest.raises(ValidationError):
        MetObject.model_validate(data)


def test_objects_list_schema(all_objects):
    assert all_objects.total > 1000
    assert len(set(all_objects.objectIDs)) == all_objects.total


@pytest.mark.bulk
def test_objects_list_filter_by_each_department(client, departments, all_objects):
    errors = []
    for department in departments:
        response = client.get_objects(departmentIds=department.departmentId)
        if response.status_code != 200:
            errors.append(f"{department.displayName}: HTTP {response.status_code}")
            continue
        filtered = ObjectsListResponse.model_validate(response.json())
        if not 0 < filtered.total < all_objects.total:
            errors.append(f"{department.displayName}: total={filtered.total}")

    assert not errors, "\n".join(errors)


def test_objects_list_filter_by_two_departments(client, departments):
    first, second = departments[0], departments[1]

    only_first = ObjectsListResponse.model_validate(client.get_objects(departmentIds=first.departmentId).json())
    both = ObjectsListResponse.model_validate(
        client.get_objects(departmentIds=f"{first.departmentId}|{second.departmentId}").json()
    )

    assert both.total > only_first.total


def test_objects_list_filter_by_metadata_date(client, all_objects):
    response = client.get_objects(metadataDate="2024-01-01")

    assert response.status_code == 200
    filtered = ObjectsListResponse.model_validate(response.json())
    assert filtered.total <= all_objects.total
