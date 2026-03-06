"""Data models for zest-crawler."""

from dataclasses import dataclass, field
from enum import Enum


class ResourceType(Enum):
    """Type of GeoGebra resource."""
    ACTIVITY = "activity"
    BOOK = "book"
    WORKSHEET = "worksheet"
    UNKNOWN = "unknown"


class UrlType(Enum):
    """Type of input URL."""
    BOOK = "book"
    USER = "user"
    SINGLE = "single"


@dataclass
class ParsedUrl:
    """Result of parsing a GeoGebra URL."""
    url_type: UrlType
    identifier: str  # material_id or username


@dataclass
class GeoGebraResource:
    """A single GeoGebra resource with metadata."""
    material_id: str
    title: str
    author: str
    resource_type: ResourceType
    url: str
    filename: str = ""
    download_time: str = ""
