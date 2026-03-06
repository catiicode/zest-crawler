# zest-crawler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a Python CLI tool that automatically discovers and downloads GeoGebra resources (.ggb files + CSV metadata) from Book pages, User pages, and single resource pages.

**Architecture:** Playwright opens GeoGebra SPA pages and intercepts XHR/Fetch requests to discover internal API endpoints and extract resource lists. httpx async client then downloads .ggb files with concurrency control. click provides the CLI interface. Output is organized into directories with numbered .ggb files and a metadata.csv.

**Tech Stack:** Python 3.12+, Playwright, httpx, click, uv + pyproject.toml, dataclasses

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/zest_crawler/__init__.py`
- Create: `src/zest_crawler/models.py`
- Create: `tests/__init__.py`
- Create: `tests/test_models.py`

**Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "zest-crawler"
version = "0.1.0"
description = "GeoGebra resource crawler and downloader"
requires-python = ">=3.12"
dependencies = [
    "click>=8.1",
    "httpx>=0.27",
    "playwright>=1.40",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
]

[project.scripts]
zest-crawler = "zest_crawler.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/zest_crawler"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create `src/zest_crawler/__init__.py`**

```python
"""zest-crawler: GeoGebra resource crawler and downloader."""
```

**Step 3: Create `tests/__init__.py`**

Empty file.

**Step 4: Write the failing test for models**

Create `tests/test_models.py`:

```python
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
```

**Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.models'`

**Step 6: Write minimal implementation**

Create `src/zest_crawler/models.py`:

```python
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
```

**Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -v`
Expected: All 4 tests PASS

**Step 8: Install dependencies and Playwright browsers**

Run:
```bash
uv sync
uv run playwright install chromium
```

**Step 9: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat: project scaffolding with models and pyproject.toml"
```

---

### Task 2: URL Router

**Files:**
- Create: `src/zest_crawler/router.py`
- Create: `tests/test_router.py`

**Step 1: Write the failing test**

Create `tests/test_router.py`:

```python
import pytest
from zest_crawler.router import parse_url
from zest_crawler.models import UrlType


def test_parse_book_url():
    result = parse_url("https://www.geogebra.org/m/urufsydt")
    assert result.url_type == UrlType.BOOK  # initially parsed as SINGLE, refined later
    assert result.identifier == "urufsydt"


def test_parse_material_url():
    """Material URLs /m/<id> are initially classified as SINGLE."""
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
```

**Note:** The `/m/<id>` URL can be either a Book or a Single resource. At the router level, we parse it as SINGLE by default. The analyzer will later determine the actual type by inspecting the page. The `test_parse_book_url` test above uses BOOK — but this requires the router to NOT distinguish Book vs Single at URL level alone. Let me revise: router should parse ALL `/m/<id>` as `UrlType.SINGLE`, and the analyzer determines if it's actually a Book. Update the test:

Revised `tests/test_router.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.router'`

**Step 3: Write minimal implementation**

Create `src/zest_crawler/router.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_router.py -v`
Expected: All 7 tests PASS

**Step 5: Commit**

```bash
git add src/zest_crawler/router.py tests/test_router.py
git commit -m "feat: URL router with pattern matching for GeoGebra URLs"
```

---

### Task 3: Storage Module

**Files:**
- Create: `src/zest_crawler/storage.py`
- Create: `tests/test_storage.py`

**Step 1: Write the failing test**

Create `tests/test_storage.py`:

```python
import csv
from pathlib import Path

from zest_crawler.models import GeoGebraResource, ResourceType
from zest_crawler.storage import Storage


def test_storage_creates_output_dir(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out" / "test-book")
    storage.ensure_dir()
    assert (tmp_path / "out" / "test-book").is_dir()


def test_storage_save_file(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out")
    storage.ensure_dir()
    storage.save_file("01-hello.ggb", b"fake-ggb-content")
    saved = tmp_path / "out" / "01-hello.ggb"
    assert saved.exists()
    assert saved.read_bytes() == b"fake-ggb-content"


def test_storage_write_metadata_csv(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out")
    storage.ensure_dir()

    resources = [
        GeoGebraResource(
            material_id="abc123",
            title="Demo 1",
            author="user1",
            resource_type=ResourceType.ACTIVITY,
            url="https://www.geogebra.org/m/abc123",
            filename="01-Demo 1.ggb",
            download_time="2026-03-06T10:00:00",
        ),
        GeoGebraResource(
            material_id="def456",
            title="Demo 2",
            author="user2",
            resource_type=ResourceType.WORKSHEET,
            url="https://www.geogebra.org/m/def456",
            filename="02-Demo 2.ggb",
            download_time="2026-03-06T10:01:00",
        ),
    ]

    storage.write_metadata(resources)

    csv_path = tmp_path / "out" / "metadata.csv"
    assert csv_path.exists()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["material_id"] == "abc123"
    assert rows[0]["title"] == "Demo 1"
    assert rows[1]["resource_type"] == "worksheet"


def test_storage_make_filename():
    storage = Storage(output_dir=Path("out"))
    assert storage.make_filename(1, "三角函数") == "01-三角函数.ggb"
    assert storage.make_filename(12, "Demo / Test") == "12-Demo _ Test.ggb"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.storage'`

**Step 3: Write minimal implementation**

Create `src/zest_crawler/storage.py`:

```python
"""File storage and CSV metadata writer."""

import csv
import re
from pathlib import Path

from zest_crawler.models import GeoGebraResource

_CSV_FIELDS = [
    "material_id",
    "title",
    "author",
    "resource_type",
    "url",
    "filename",
    "download_time",
]


class Storage:
    """Manages output directory and file saving."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def ensure_dir(self) -> None:
        """Create the output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename: str, content: bytes) -> Path:
        """Save a file to the output directory."""
        path = self.output_dir / filename
        path.write_bytes(content)
        return path

    def write_metadata(self, resources: list[GeoGebraResource]) -> Path:
        """Write resource metadata to a CSV file."""
        csv_path = self.output_dir / "metadata.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            for r in resources:
                writer.writerow({
                    "material_id": r.material_id,
                    "title": r.title,
                    "author": r.author,
                    "resource_type": r.resource_type.value,
                    "url": r.url,
                    "filename": r.filename,
                    "download_time": r.download_time,
                })
        return csv_path

    @staticmethod
    def make_filename(index: int, title: str) -> str:
        """Generate a numbered filename from a title.

        Replaces filesystem-unsafe characters with underscores.
        """
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
        return f"{index:02d}-{safe_title}.ggb"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_storage.py -v`
Expected: All 4 tests PASS

**Step 5: Commit**

```bash
git add src/zest_crawler/storage.py tests/test_storage.py
git commit -m "feat: storage module with file saving and CSV metadata export"
```

---

### Task 4: Async Downloader

**Files:**
- Create: `src/zest_crawler/downloader.py`
- Create: `tests/test_downloader.py`

**Step 1: Write the failing test**

Create `tests/test_downloader.py`:

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from zest_crawler.downloader import Downloader, DownloadResult


@pytest.mark.asyncio
async def test_download_single_file():
    """Test downloading a single file with a mocked HTTP response."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.content = b"fake-ggb-data"
    mock_response.raise_for_status = lambda: None

    with patch("zest_crawler.downloader.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(return_value=mock_response)
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        downloader = Downloader(concurrency=2)
        result = await downloader.download_file(
            url="https://www.geogebra.org/material/download/format/file/id/12345",
            material_id="abc123",
        )

    assert isinstance(result, DownloadResult)
    assert result.material_id == "abc123"
    assert result.content == b"fake-ggb-data"
    assert result.success is True


@pytest.mark.asyncio
async def test_download_file_failure():
    """Test download failure returns error result."""
    with patch("zest_crawler.downloader.httpx.AsyncClient") as MockClient:
        client_instance = AsyncMock()
        client_instance.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Not Found",
                request=httpx.Request("GET", "https://example.com"),
                response=httpx.Response(404),
            )
        )
        client_instance.__aenter__ = AsyncMock(return_value=client_instance)
        client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = client_instance

        downloader = Downloader(concurrency=2, max_retries=1)
        result = await downloader.download_file(
            url="https://example.com/notfound",
            material_id="bad123",
        )

    assert result.success is False
    assert result.material_id == "bad123"
    assert result.content is None
    assert "Not Found" in result.error


def test_build_download_url():
    """Test constructing download URL from material numeric ID."""
    url = Downloader.build_download_url(12345)
    assert url == "https://www.geogebra.org/material/download/format/file/id/12345"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.downloader'`

**Step 3: Write minimal implementation**

Create `src/zest_crawler/downloader.py`:

```python
"""Async file downloader with concurrency control."""

import asyncio
from dataclasses import dataclass

import httpx

_BASE_DOWNLOAD_URL = "https://www.geogebra.org/material/download/format/file/id"


@dataclass
class DownloadResult:
    """Result of a single file download."""
    material_id: str
    success: bool
    content: bytes | None = None
    error: str = ""


class Downloader:
    """Async downloader with semaphore-based concurrency control."""

    def __init__(
        self,
        concurrency: int = 5,
        max_retries: int = 3,
        timeout: float = 30.0,
    ) -> None:
        self.semaphore = asyncio.Semaphore(concurrency)
        self.max_retries = max_retries
        self.timeout = timeout

    async def download_file(
        self,
        url: str,
        material_id: str,
    ) -> DownloadResult:
        """Download a single file with retry logic.

        Args:
            url: The download URL.
            material_id: The material identifier for tracking.

        Returns:
            DownloadResult with content on success, error on failure.
        """
        async with self.semaphore:
            last_error = ""
            for attempt in range(self.max_retries):
                try:
                    async with httpx.AsyncClient(
                        timeout=self.timeout,
                        follow_redirects=True,
                    ) as client:
                        response = await client.get(url)
                        response.raise_for_status()
                        return DownloadResult(
                            material_id=material_id,
                            success=True,
                            content=response.content,
                        )
                except (httpx.HTTPError, httpx.HTTPStatusError) as e:
                    last_error = str(e)
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(2 ** attempt)

            return DownloadResult(
                material_id=material_id,
                success=False,
                error=last_error,
            )

    async def download_many(
        self,
        tasks: list[tuple[str, str]],
    ) -> list[DownloadResult]:
        """Download multiple files concurrently.

        Args:
            tasks: List of (url, material_id) tuples.

        Returns:
            List of DownloadResult objects.
        """
        coros = [self.download_file(url, mid) for url, mid in tasks]
        return await asyncio.gather(*coros)

    @staticmethod
    def build_download_url(numeric_id: int) -> str:
        """Build a download URL from a numeric material ID."""
        return f"{_BASE_DOWNLOAD_URL}/{numeric_id}"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_downloader.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/zest_crawler/downloader.py tests/test_downloader.py
git commit -m "feat: async downloader with concurrency control and retry logic"
```

---

### Task 5: Playwright Page Analyzer

**Files:**
- Create: `src/zest_crawler/analyzer.py`
- Create: `tests/test_analyzer.py`

This is the most complex module. It uses Playwright to open GeoGebra pages, intercept network requests, and extract resource lists. Since we cannot predict the exact API structure without live testing, we build the analyzer with request interception and provide a framework that captures API responses for analysis.

**Step 1: Write the failing test**

Create `tests/test_analyzer.py`:

```python
import pytest
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
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.analyzer'`

**Step 3: Write minimal implementation**

Create `src/zest_crawler/analyzer.py`:

```python
"""Playwright-based page analyzer for GeoGebra resources.

Opens GeoGebra pages in a headless browser, intercepts network requests
to discover API endpoints, and extracts resource lists.
"""

import json
import logging
from typing import Any

from playwright.async_api import async_playwright, Page, Response

from zest_crawler.models import GeoGebraResource, ParsedUrl, ResourceType, UrlType

logger = logging.getLogger(__name__)


class GeoGebraAnalyzer:
    """Analyzes GeoGebra pages using Playwright to extract resource info."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self._captured_responses: list[dict[str, Any]] = []

    @staticmethod
    def build_full_url(parsed: ParsedUrl) -> str:
        """Build a full GeoGebra URL from a ParsedUrl."""
        if parsed.url_type == UrlType.USER:
            return f"https://www.geogebra.org/u/{parsed.identifier}"
        return f"https://www.geogebra.org/m/{parsed.identifier}"

    async def analyze(self, parsed: ParsedUrl) -> list[GeoGebraResource]:
        """Analyze a GeoGebra page and extract resources.

        Opens the page in Playwright, intercepts API responses,
        and parses them to build a list of GeoGebraResource objects.

        Args:
            parsed: The parsed URL to analyze.

        Returns:
            List of discovered GeoGebraResource objects.
        """
        url = self.build_full_url(parsed)
        self._captured_responses.clear()

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()

            # Intercept API responses
            page.on("response", self._on_response)

            logger.info("Navigating to %s", url)
            await page.goto(url, wait_until="networkidle")

            # Give extra time for dynamic content
            await page.wait_for_timeout(2000)

            # For user pages, try scrolling to load more
            if parsed.url_type == UrlType.USER:
                await self._scroll_to_load_all(page)

            await browser.close()

        return self._parse_captured_responses(parsed)

    async def _on_response(self, response: Response) -> None:
        """Capture API responses from the page."""
        url = response.url
        # Capture JSON API responses from GeoGebra
        if "api" in url or "materials" in url or "json" in url:
            try:
                content_type = response.headers.get("content-type", "")
                if "json" in content_type or "javascript" in content_type:
                    body = await response.json()
                    self._captured_responses.append({
                        "url": url,
                        "status": response.status,
                        "body": body,
                    })
                    logger.debug("Captured API response: %s", url)
            except Exception:
                pass

    async def _scroll_to_load_all(self, page: Page) -> None:
        """Scroll to the bottom of the page to trigger lazy loading."""
        previous_height = 0
        for _ in range(20):  # max 20 scrolls to prevent infinite loop
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)

    def _parse_captured_responses(
        self, parsed: ParsedUrl
    ) -> list[GeoGebraResource]:
        """Parse captured API responses into GeoGebraResource objects.

        This method inspects the captured responses and attempts to extract
        material information. The exact parsing logic may need adjustment
        based on the actual API response format discovered during runtime.
        """
        resources: list[GeoGebraResource] = []
        seen_ids: set[str] = set()

        for resp in self._captured_responses:
            body = resp["body"]
            materials = self._extract_materials_from_response(body)
            for mat in materials:
                mid = str(mat.get("id", ""))
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                resources.append(
                    GeoGebraResource(
                        material_id=mid,
                        title=mat.get("title", "Untitled"),
                        author=mat.get("creator", {}).get("displayname", "")
                            if isinstance(mat.get("creator"), dict)
                            else str(mat.get("creator", "")),
                        resource_type=self._map_resource_type(
                            mat.get("type", "")
                        ),
                        url=f"https://www.geogebra.org/m/{mid}",
                    )
                )

        logger.info("Found %d resources from API responses", len(resources))

        # If no resources found via API interception, try page scraping
        if not resources:
            logger.warning(
                "No resources found via API interception. "
                "Page structure may have changed."
            )

        return resources

    def _extract_materials_from_response(
        self, body: Any
    ) -> list[dict[str, Any]]:
        """Extract material items from various API response formats."""
        materials: list[dict[str, Any]] = []

        if isinstance(body, dict):
            # Check common response structures
            for key in ("materials", "items", "results", "chapters", "children", "elements"):
                if key in body and isinstance(body[key], list):
                    for item in body[key]:
                        if isinstance(item, dict):
                            materials.append(item)
                            # Recursively check for nested materials
                            nested = self._extract_materials_from_response(item)
                            materials.extend(nested)

            # Check if the body itself looks like a material
            if "id" in body and "title" in body:
                materials.append(body)

        elif isinstance(body, list):
            for item in body:
                if isinstance(item, dict):
                    materials.append(item)

        return materials

    @staticmethod
    def _map_resource_type(type_str: str) -> ResourceType:
        """Map API type string to ResourceType enum."""
        type_lower = str(type_str).lower()
        if "book" in type_lower:
            return ResourceType.BOOK
        if "worksheet" in type_lower:
            return ResourceType.WORKSHEET
        if "activity" in type_lower:
            return ResourceType.ACTIVITY
        return ResourceType.UNKNOWN
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_analyzer.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/zest_crawler/analyzer.py tests/test_analyzer.py
git commit -m "feat: Playwright page analyzer with API request interception"
```

---

### Task 6: CLI Entry Point

**Files:**
- Create: `src/zest_crawler/cli.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
from click.testing import CliRunner
from zest_crawler.cli import main


def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "GeoGebra resource crawler" in result.output


def test_cli_download_help():
    runner = CliRunner()
    result = runner.invoke(main, ["download", "--help"])
    assert result.exit_code == 0
    assert "--output" in result.output
    assert "--concurrency" in result.output


def test_cli_download_invalid_url():
    runner = CliRunner()
    result = runner.invoke(main, ["download", "https://www.google.com"])
    assert result.exit_code != 0
    assert "Unsupported URL" in result.output
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'zest_crawler.cli'`

**Step 3: Write minimal implementation**

Create `src/zest_crawler/cli.py`:

```python
"""CLI entry point for zest-crawler."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from zest_crawler.analyzer import GeoGebraAnalyzer
from zest_crawler.downloader import Downloader
from zest_crawler.models import UrlType
from zest_crawler.router import parse_url
from zest_crawler.storage import Storage


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
def main(verbose: bool) -> None:
    """GeoGebra resource crawler and downloader."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )


@main.command()
@click.argument("url")
@click.option(
    "--output", "-o",
    default="./output",
    type=click.Path(),
    help="Output directory (default: ./output).",
)
@click.option(
    "--concurrency", "-c",
    default=5,
    type=int,
    help="Max concurrent downloads (default: 5).",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: headless).",
)
def download(url: str, output: str, concurrency: int, headless: bool) -> None:
    """Download GeoGebra resources from a URL.

    URL can be a material page (/m/<id>), user page (/u/<username>),
    or a short URL (ggbm.at/<id>).
    """
    try:
        parsed = parse_url(url)
    except ValueError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    click.echo(f"Parsed URL: type={parsed.url_type.value}, id={parsed.identifier}")
    asyncio.run(_download_async(parsed, output, concurrency, headless))


async def _download_async(
    parsed_url: "ParsedUrl",
    output_dir: str,
    concurrency: int,
    headless: bool,
) -> None:
    """Async download workflow."""
    from zest_crawler.models import ParsedUrl

    # Step 1: Analyze the page
    click.echo("Analyzing page with Playwright...")
    analyzer = GeoGebraAnalyzer(headless=headless)
    resources = await analyzer.analyze(parsed_url)

    if not resources:
        click.echo("No resources found on this page.")
        return

    click.echo(f"Found {len(resources)} resource(s).")

    # Determine output subdirectory name
    subdir_name = parsed_url.identifier
    storage = Storage(output_dir=Path(output_dir) / subdir_name)
    storage.ensure_dir()

    # Step 2: Download files
    click.echo(f"Downloading with concurrency={concurrency}...")
    downloader = Downloader(concurrency=concurrency)

    # Build download tasks — use material_id-based URL pattern
    download_tasks: list[tuple[str, str]] = []
    for r in resources:
        download_url = (
            f"https://www.geogebra.org/material/download"
            f"/format/file/id/{r.material_id}"
        )
        download_tasks.append((download_url, r.material_id))

    results = await downloader.download_many(download_tasks)

    # Step 3: Save files and update metadata
    now = datetime.now(timezone.utc).isoformat()
    success_count = 0
    for i, (resource, result) in enumerate(zip(resources, results), start=1):
        if result.success and result.content:
            filename = storage.make_filename(i, resource.title)
            storage.save_file(filename, result.content)
            resource.filename = filename
            resource.download_time = now
            success_count += 1
            click.echo(f"  [{i}/{len(resources)}] Downloaded: {filename}")
        else:
            click.echo(
                f"  [{i}/{len(resources)}] Failed: {resource.title} "
                f"({result.error})",
                err=True,
            )

    # Step 4: Write metadata CSV
    storage.write_metadata(resources)
    click.echo(
        f"\nDone! {success_count}/{len(resources)} files saved to "
        f"{storage.output_dir}"
    )
    click.echo(f"Metadata written to {storage.output_dir / 'metadata.csv'}")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 3 tests PASS

**Step 5: Commit**

```bash
git add src/zest_crawler/cli.py tests/test_cli.py
git commit -m "feat: CLI entry point with download command"
```

---

### Task 7: Integration Test and End-to-End Validation

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write a basic integration test**

This test validates the full pipeline wiring without making real network calls. It mocks the Playwright analyzer and httpx downloader.

Create `tests/test_integration.py`:

```python
"""Integration test: validates the full pipeline wiring."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from click.testing import CliRunner

from zest_crawler.cli import main
from zest_crawler.models import GeoGebraResource, ResourceType


@pytest.fixture
def mock_resources():
    return [
        GeoGebraResource(
            material_id="res1",
            title="Test Resource 1",
            author="test_author",
            resource_type=ResourceType.ACTIVITY,
            url="https://www.geogebra.org/m/res1",
        ),
        GeoGebraResource(
            material_id="res2",
            title="Test Resource 2",
            author="test_author",
            resource_type=ResourceType.WORKSHEET,
            url="https://www.geogebra.org/m/res2",
        ),
    ]


def test_full_pipeline_with_mocks(tmp_path: Path, mock_resources):
    """Test the full download pipeline with mocked analyzer and downloader."""
    from zest_crawler.downloader import DownloadResult

    mock_results = [
        DownloadResult(material_id="res1", success=True, content=b"ggb-data-1"),
        DownloadResult(material_id="res2", success=True, content=b"ggb-data-2"),
    ]

    with (
        patch("zest_crawler.cli.GeoGebraAnalyzer") as MockAnalyzer,
        patch("zest_crawler.cli.Downloader") as MockDownloader,
    ):
        analyzer_instance = MagicMock()
        analyzer_instance.analyze = AsyncMock(return_value=mock_resources)
        MockAnalyzer.return_value = analyzer_instance

        downloader_instance = MagicMock()
        downloader_instance.download_many = AsyncMock(return_value=mock_results)
        MockDownloader.return_value = downloader_instance

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["download", "https://www.geogebra.org/m/testbook", "-o", str(tmp_path)],
        )

    assert result.exit_code == 0
    assert "Found 2 resource(s)" in result.output
    assert "Done! 2/2 files saved" in result.output

    # Check files were created
    output_dir = tmp_path / "testbook"
    assert output_dir.exists()
    assert (output_dir / "metadata.csv").exists()
    assert (output_dir / "01-Test Resource 1.ggb").exists()
    assert (output_dir / "02-Test Resource 2.ggb").exists()
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_integration.py -v`
Expected: PASS

**Step 3: Run all tests**

Run: `uv run pytest -v`
Expected: All tests PASS (models, router, storage, downloader, cli, integration)

**Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add integration test for full download pipeline"
```

---

### Task 8: Live Testing and Analyzer Tuning

**Files:**
- Modify: `src/zest_crawler/analyzer.py` (likely adjustments based on real API responses)

This task requires running the tool against real GeoGebra pages to discover the actual API endpoints and response formats. This is an exploratory task.

**Step 1: Run against a real material page in non-headless mode**

```bash
uv run zest-crawler -v download https://www.geogebra.org/m/urufsydt --no-headless
```

Observe:
- What API requests are made (check verbose logs)
- Whether resources are discovered
- What the actual API response format looks like

**Step 2: Run against a real user page**

```bash
uv run zest-crawler -v download https://www.geogebra.org/u/mengbaoxing --no-headless
```

**Step 3: Adjust analyzer.py based on findings**

Based on the actual API responses discovered in Steps 1-2, update:
- The `_on_response` URL matching patterns
- The `_extract_materials_from_response` parsing logic
- The `_map_resource_type` mapping

The analyzer is designed to be flexible with its response parsing, checking multiple common key names (`materials`, `items`, `results`, `chapters`, `children`, `elements`). It may need additional keys or different nesting based on actual responses.

**Step 4: Run tests to verify nothing broke**

Run: `uv run pytest -v`
Expected: All tests still PASS

**Step 5: Commit adjustments**

```bash
git add src/zest_crawler/analyzer.py
git commit -m "fix: tune analyzer based on live GeoGebra API response format"
```

---

## Summary

| Task | Module | Purpose |
|------|--------|---------|
| 1 | Scaffolding + models | Project setup, data models |
| 2 | router.py | URL pattern matching |
| 3 | storage.py | File saving + CSV export |
| 4 | downloader.py | Async file download with retry |
| 5 | analyzer.py | Playwright page analysis |
| 6 | cli.py | Click CLI entry point |
| 7 | Integration test | End-to-end pipeline validation |
| 8 | Live tuning | Real-world API discovery and tuning |

**Dependencies:** Tasks 1-5 can be implemented independently. Task 6 depends on all prior modules. Task 7 depends on Task 6. Task 8 depends on everything.
