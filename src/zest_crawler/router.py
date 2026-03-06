"""URL parser and router for GeoGebra URLs."""

import re
from urllib.parse import urlparse

from zest_crawler.models import ParsedUrl, UrlType

# Pattern: https://www.geogebra.org/m/<id>
_MATERIAL_PATTERN = re.compile(r"^/m/([a-zA-Z0-9]+)/?$")

# Pattern: https://www.geogebra.org/u/<username>
_USER_PATTERN = re.compile(r"^/u/([a-zA-Z0-9_+.-]+)/?$")

# Short URL: https://ggbm.at/<id>
_SHORT_HOSTS = {"ggbm.at"}

_GEOGEBRA_HOSTS = {"www.geogebra.org", "geogebra.org"}


def parse_url(url: str) -> ParsedUrl:
    """Parse a GeoGebra URL and determine its type.

    /m/<id> URLs are classified as SINGLE. The analyzer will later
    determine if the resource is actually a Book (collection).
    /u/<username> URLs are classified as USER.

    Args:
        url: A GeoGebra URL.

    Returns:
        ParsedUrl with url_type and identifier.

    Raises:
        ValueError: If the URL is not a supported GeoGebra URL.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""

    # Short URL (ggbm.at/<id>)
    if host in _SHORT_HOSTS:
        identifier = parsed.path.strip("/")
        if identifier:
            return ParsedUrl(url_type=UrlType.SINGLE, identifier=identifier)

    # Standard GeoGebra URLs
    if host not in _GEOGEBRA_HOSTS:
        raise ValueError(f"Unsupported URL: {url}")

    # Try /u/<username>
    user_match = _USER_PATTERN.match(parsed.path)
    if user_match:
        return ParsedUrl(url_type=UrlType.USER, identifier=user_match.group(1))

    # Try /m/<id>
    material_match = _MATERIAL_PATTERN.match(parsed.path)
    if material_match:
        return ParsedUrl(url_type=UrlType.SINGLE, identifier=material_match.group(1))

    raise ValueError(f"Unsupported URL: {url}")
