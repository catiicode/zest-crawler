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
