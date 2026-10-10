import pytest

from models import ErrorResponse, MetObject, RetiredEndpointResponse, SearchResponse

KEYWORDS = [
    "sunflowers", "Monet", "armor", "Egypt", "vase",
    "sword", "portrait", "Rembrandt", "cat", "dragon",
]


def search(client, q=None, **params) -> SearchResponse:
    response = client.search(q, **params)
    assert response.status_code == 200, response.text
    return SearchResponse.model_validate(response.json())


def load_objects(client, ids, count=3):
    objects = []
    for object_id in ids[:count]:
        response = client.get_object(object_id)
        assert response.status_code == 200
        objects.append(MetObject.model_validate(response.json()))
    return objects


def test_old_search_endpoint_is_retired(client):
    response = client.search_v1("sunflowers")

    assert response.status_code == 410
    body = RetiredEndpointResponse.model_validate(response.json())
    assert body.replacement == "/public/collection/v1.1/search"


@pytest.mark.smoke
@pytest.mark.parametrize("keyword", KEYWORDS)
def test_search_by_keyword(client, keyword):
    data = search(client, keyword)

    assert data.total > 0
    assert data.ids
    assert len(set(data.ids)) == len(data.ids)


@pytest.mark.parametrize("keyword", ["sunflowers", "armor", "Rembrandt"])
def test_search_results_are_real_objects(client, keyword):
    data = search(client, keyword)

    objects = load_objects(client, data.ids)

    assert [obj.objectID for obj in objects] == data.ids[: len(objects)]


def test_search_in_title(client):
    data = search(client, "sunflowers", title="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert "sunflower" in obj.title.lower()


def test_search_in_title_is_narrower_than_general(client):
    general = search(client, "sunflowers")
    in_title = search(client, "sunflowers", title="true")

    assert 0 < in_title.total <= general.total


@pytest.mark.parametrize("query", ["zxqvbnmasdfghjkl123456", "qqqqwwwweeeerrrr9999"])
def test_search_nonsense_query_returns_nothing(client, query):
    data = search(client, query)

    assert data.total == 0
    assert data.ids == []


@pytest.mark.parametrize("keyword", ["monet", "armor", "egypt"])
def test_search_is_case_insensitive(client, keyword):
    assert search(client, keyword).total == search(client, keyword.upper()).total


def test_search_multiple_words(client):
    one_word = search(client, "sunflowers")
    two_words = search(client, "sunflowers Van Gogh")

    assert two_words.total > 0
    assert two_words.total != one_word.total


@pytest.mark.parametrize("query", ["a&b=c", "'quote'", "кошка", "100%", "café"])
def test_search_with_special_characters(client, query):
    response = client.search(query)

    assert response.status_code == 200
    SearchResponse.model_validate(response.json())


def test_search_with_html_tags(client):
    response = client.search("<script>alert(1)</script>", retry_waf=False)

    assert response.status_code in (200, 400, 403)
    if response.status_code == 200:
        SearchResponse.model_validate(response.json())


def test_search_without_query_but_with_filters(client):
    data = search(client, None, hasImages="true", departmentId=11)

    assert data.total > 0
    assert data.ids


def test_default_page_size_is_100(client):
    data = search(client, "flower")

    assert data.total > 100
    assert len(data.ids) == 100


@pytest.mark.parametrize("limit", [1, 5, 50, 100, 500])
def test_limit_controls_page_size(client, limit):
    data = search(client, "flower", limit=limit)

    assert len(data.ids) == limit


def test_limit_above_maximum_is_capped_at_500(client):
    data = search(client, "flower", limit=1000)

    assert len(data.ids) == 500


def test_total_does_not_depend_on_page(client):
    first_page = search(client, "flower", limit=5)
    other_page = search(client, "flower", offset=50, limit=10)
    big_page = search(client, "flower", limit=200)

    assert first_page.total == other_page.total == big_page.total


def test_offset_skips_results(client):
    first_ten = search(client, "flower", limit=10).ids
    next_five = search(client, "flower", offset=5, limit=5).ids

    assert next_five == first_ten[5:10]


@pytest.mark.bulk
def test_paging_through_results_matches_single_request(client):
    pages = []
    for page in range(5):
        pages += search(client, "flower", offset=page * 10, limit=10).ids

    single_request = search(client, "flower", limit=50).ids

    assert pages == single_request
    assert len(set(pages)) == 50


def test_offset_beyond_total_returns_empty_page(client):
    first = search(client, "sunflowers", limit=1)
    response = client.search("sunflowers", offset=first.total + 100, limit=10)

    assert response.status_code in (200, 400)
    if response.status_code == 200:
        data = SearchResponse.model_validate(response.json())
        assert data.ids == []
        assert data.total == first.total


def test_offset_plus_limit_is_capped_at_10000(client):
    response = client.search("flower", offset=9990, limit=100)

    assert response.status_code in (200, 400)
    if response.status_code == 200:
        data = SearchResponse.model_validate(response.json())
        assert 9990 + len(data.ids) <= 10000


@pytest.mark.parametrize("param, value", [
    ("limit", 0), ("limit", -1), ("limit", "abc"), ("offset", -1), ("offset", "abc"),
])
def test_invalid_pagination_parameters(client, param, value):
    response = client.search("flower", **{param: value})

    assert response.status_code in (200, 400, 422)
    if response.status_code == 200:
        data = SearchResponse.model_validate(response.json())
        assert len(data.ids) <= 100


def test_filter_reduces_number_of_results(client):
    broad = search(client, "flower")
    narrow = search(client, "flower", isHighlight="true")

    assert 0 < narrow.total < broad.total


def test_combined_filters_narrow_results_further(client):
    highlight = search(client, "flower", isHighlight="true")
    images = search(client, "flower", hasImages="true")
    both = search(client, "flower", isHighlight="true", hasImages="true")

    assert both.total <= highlight.total
    assert both.total <= images.total


def test_filter_is_highlight(client):
    data = search(client, "flower", isHighlight="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert obj.isHighlight is True


def test_filter_has_images(client):
    data = search(client, "sunflowers", hasImages="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert obj.primaryImage or obj.primaryImageSmall or obj.additionalImages


def test_filter_is_on_view(client):
    data = search(client, "flower", isOnView="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert obj.GalleryNumber


def test_filter_by_tags(client):
    data = search(client, "flower", tags="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        terms = [tag.term.lower() for tag in (obj.tags or [])]
        assert any("flower" in term for term in terms)


def test_filter_by_geo_location(client):
    data = search(client, "vase", geoLocation="France")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        place = " ".join([obj.country, obj.region, obj.subregion, obj.city, obj.state, obj.county, obj.locale])
        assert "france" in place.lower() or "france" in obj.culture.lower()


def test_filter_by_department(client, departments):
    department = next(d for d in departments if d.displayName == "European Paintings")

    data = search(client, "flower", departmentId=department.departmentId)

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert obj.department == department.displayName


@pytest.mark.bulk
def test_filter_by_every_department(client, departments):
    total_without_filter = search(client, "art").total
    errors = []
    for department in departments:
        data = search(client, "art", departmentId=department.departmentId)
        if data.total > total_without_filter:
            errors.append(f"{department.displayName}: {data.total} > {total_without_filter}")

    assert not errors, "\n".join(errors)


def test_filter_by_artist_or_culture(client):
    data = search(client, "Van Gogh", artistOrCulture="true")

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert "gogh" in (obj.artistDisplayName + obj.culture).lower()


@pytest.mark.parametrize("date_begin, date_end", [(1800, 1900), (1500, 1600), (-500, 0)])
def test_filter_by_date_range(client, date_begin, date_end):
    data = search(client, "vase", dateBegin=date_begin, dateEnd=date_end)

    assert data.total > 0
    for obj in load_objects(client, data.ids, count=5):
        assert obj.objectEndDate >= date_begin
        assert obj.objectBeginDate <= date_end


def test_filter_by_medium_narrows_results(client):
    broad = search(client, "flower")
    narrow = search(client, "flower", medium="Paintings")

    assert 0 < narrow.total <= broad.total


@pytest.mark.parametrize("keyword", ["monet", "armor"])
def test_order_is_stable_between_requests(client, keyword):
    first = search(client, keyword)
    second = search(client, keyword)

    assert first.ids == second.ids


@pytest.mark.parametrize("sort_param", [{"sortBy": "title"}, {"sort": "date"}, {"orderBy": "id"}])
def test_sort_parameter_is_ignored(client, sort_param):
    default = search(client, "monet")
    with_sort = search(client, "monet", **sort_param)

    assert with_sort.ids == default.ids
