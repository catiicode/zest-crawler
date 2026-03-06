from zest_crawler.models import GeoGebraResource, ResourceType, UrlType, ParsedUrl


def test_resource_type_enum():
    assert ResourceType.ACTIVITY.value == "activity"
    assert ResourceType.BOOK.value == "book"


def test_url_type_enum():
    assert UrlType.BOOK.value == "book"
    assert UrlType.USER.value == "user"
    assert UrlType.SINGLE.value == "single"


def test_geogebra_resource_creation():
    r = GeoGebraResource(
        material_id="abc123",
        title="三角函数演示",
        author="mengbaoxing",
        resource_type=ResourceType.ACTIVITY,
        url="https://www.geogebra.org/m/abc123",
    )
    assert r.material_id == "abc123"
    assert r.title == "三角函数演示"
    assert r.filename == ""
    assert r.download_time == ""


def test_parsed_url():
    p = ParsedUrl(url_type=UrlType.BOOK, identifier="urufsydt")
    assert p.url_type == UrlType.BOOK
    assert p.identifier == "urufsydt"
