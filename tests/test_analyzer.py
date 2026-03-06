from zest_crawler.analyzer import GeoGebraAnalyzer
from zest_crawler.models import UrlType, ParsedUrl


def test_analyzer_init():
    """Test analyzer can be instantiated."""
    analyzer = GeoGebraAnalyzer(headless=True)
    assert analyzer.headless is True


def test_build_full_url_material():
    parsed = ParsedUrl(url_type=UrlType.SINGLE, identifier="abc123")
    url = GeoGebraAnalyzer.build_full_url(parsed)
    assert url == "https://www.geogebra.org/m/abc123"


def test_build_full_url_user():
    parsed = ParsedUrl(url_type=UrlType.USER, identifier="mengbaoxing")
    url = GeoGebraAnalyzer.build_full_url(parsed)
    assert url == "https://www.geogebra.org/u/mengbaoxing"
