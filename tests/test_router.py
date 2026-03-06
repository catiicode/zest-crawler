import pytest
from zest_crawler.router import parse_url
from zest_crawler.models import UrlType


def test_parse_material_url():
    """Material URLs /m/<id> are parsed as SINGLE (analyzer determines Book vs Single)."""
    result = parse_url("https://www.geogebra.org/m/urufsydt")
    assert result.url_type == UrlType.SINGLE
    assert result.identifier == "urufsydt"


def test_parse_material_url_2():
    result = parse_url("https://www.geogebra.org/m/abc123")
    assert result.url_type == UrlType.SINGLE
    assert result.identifier == "abc123"


def test_parse_user_url():
    result = parse_url("https://www.geogebra.org/u/mengbaoxing")
    assert result.url_type == UrlType.USER
    assert result.identifier == "mengbaoxing"


def test_parse_user_url_with_trailing_slash():
    result = parse_url("https://www.geogebra.org/u/mengbaoxing/")
    assert result.url_type == UrlType.USER
    assert result.identifier == "mengbaoxing"


def test_parse_invalid_url():
    with pytest.raises(ValueError, match="Unsupported URL"):
        parse_url("https://www.google.com")


def test_parse_short_url():
    result = parse_url("https://ggbm.at/abc123")
    assert result.url_type == UrlType.SINGLE
    assert result.identifier == "abc123"


def test_parse_http_url():
    """HTTP URLs should work too."""
    result = parse_url("http://www.geogebra.org/m/xyz789")
    assert result.url_type == UrlType.SINGLE
    assert result.identifier == "xyz789"
