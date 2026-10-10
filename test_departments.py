from models import DepartmentsResponse


def test_departments_schema(client):
    response = client.get_departments()

    assert response.status_code == 200
    data = DepartmentsResponse.model_validate(response.json())
    assert len(data.departments) > 5


def test_departments_are_unique(departments):
    ids = [d.departmentId for d in departments]
    names = [d.displayName for d in departments]

    assert len(ids) == len(set(ids))
    assert len(names) == len(set(names))


def test_known_department_exists(departments):
    assert "European Paintings" in [d.displayName for d in departments]
