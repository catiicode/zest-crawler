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
