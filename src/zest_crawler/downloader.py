"""GeoGebra file downloader using Playwright.

Downloads .ggb files by opening each resource in GeoGebra Classic,
then calling the applet's getBase64() JavaScript API to export the file.
"""

import asyncio
import base64
import logging
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

from playwright.async_api import async_playwright, Browser, BrowserContext

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """Result of a single file download."""
    material_id: str
    success: bool
    content: bytes | None = None
    error: str = ""


# JS to find the GeoGebra applet object on a /classic/<id> page.
# Returns true if applet is found and has getBase64 method.
_FIND_APPLET_JS = """
() => {
    if (typeof window.ggbApplet !== 'undefined' && window.ggbApplet.getBase64) return true;
    for (const key of Object.keys(window)) {
        if (key.startsWith('ggbApplet') && window[key] && window[key].getBase64) return true;
    }
    const el = document.querySelector('[data-param-id]');
    if (el) {
        const applet = window[el.getAttribute('data-param-id')];
        if (applet && applet.getBase64) return true;
    }
    return false;
}
"""

# JS to extract base64 from the GeoGebra applet.
# Must be called only after _FIND_APPLET_JS returns true.
_GET_BASE64_JS = """
async () => {
    // Strategy 1: Try window.ggbApplet directly
    if (typeof window.ggbApplet !== 'undefined' && window.ggbApplet.getBase64) {
        return new Promise((resolve) => {
            window.ggbApplet.getBase64((b64) => resolve(b64));
        });
    }

    // Strategy 2: Search for ggbApplet-like variables on window
    for (const key of Object.keys(window)) {
        if (key.startsWith('ggbApplet') && window[key] && window[key].getBase64) {
            return new Promise((resolve) => {
                window[key].getBase64((b64) => resolve(b64));
            });
        }
    }

    // Strategy 3: Look for the applet via document querySelector
    const appletEl = document.querySelector('[data-param-id]');
    if (appletEl) {
        const appId = appletEl.getAttribute('data-param-id');
        const applet = window[appId];
        if (applet && applet.getBase64) {
            return new Promise((resolve) => {
                applet.getBase64((b64) => resolve(b64));
            });
        }
    }

    throw new Error('GeoGebra applet not found on page');
}
"""


class Downloader:
    """Downloads .ggb files via Playwright by calling getBase64() on Classic pages."""

    def __init__(
        self,
        concurrency: int = 2,
        headless: bool = True,
        proxy: str | None = None,
        timeout: float = 60000,
        max_retries: int = 3,
    ) -> None:
        self.concurrency = concurrency
        self.headless = headless
        self.proxy = proxy
        self.timeout = timeout
        self.max_retries = max_retries

    async def download_many(
        self,
        material_ids: list[str],
    ) -> list[DownloadResult]:
        """Download multiple .ggb files and return all results at once.

        For streaming results (one at a time), use download_iter() instead.
        """
        results = []
        async for result in self.download_iter(material_ids):
            results.append(result)
        return results

    async def download_iter(
        self,
        material_ids: list[str],
    ) -> AsyncIterator[DownloadResult]:
        """Download .ggb files one at a time, yielding each result immediately.

        This allows the caller to save files and update UI progressively
        instead of waiting for all downloads to finish.

        Args:
            material_ids: List of material IDs to download.

        Yields:
            DownloadResult for each material, in order.
        """
        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}
        else:
            proxy_url = (
                os.environ.get("HTTPS_PROXY")
                or os.environ.get("https_proxy")
                or os.environ.get("HTTP_PROXY")
                or os.environ.get("http_proxy")
            )
            if proxy_url:
                proxy_config = {"server": proxy_url}

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                proxy=proxy_config,
            )
            context = await browser.new_context()

            for mid in material_ids:
                result = await self._download_one(context, mid)
                yield result

            await context.close()
            await browser.close()

    async def _download_one(
        self,
        context: BrowserContext,
        material_id: str,
    ) -> DownloadResult:
        """Download a single .ggb file from GeoGebra Classic.

        Opens https://www.geogebra.org/classic/<material_id>, polls until
        the applet is ready, then calls getBase64() to export the file.
        """
        classic_url = f"https://www.geogebra.org/classic/{material_id}"
        last_error = ""

        for attempt in range(self.max_retries):
            page = await context.new_page()
            try:
                logger.info(
                    "Opening Classic page: %s (attempt %d/%d)",
                    classic_url, attempt + 1, self.max_retries,
                )

                await page.goto(
                    classic_url,
                    wait_until="networkidle",
                    timeout=self.timeout,
                )

                # Poll until the applet object appears on the page.
                # GeoGebra Classic loads the applet asynchronously after
                # the page HTML is ready; a fixed delay is unreliable.
                applet_ready = False
                for poll in range(30):  # up to ~30 seconds
                    found = await page.evaluate(_FIND_APPLET_JS)
                    if found:
                        applet_ready = True
                        logger.debug(
                            "Applet ready for %s after ~%ds",
                            material_id, poll,
                        )
                        break
                    await page.wait_for_timeout(1000)

                if not applet_ready:
                    raise RuntimeError(
                        "Applet did not become ready within 30s"
                    )

                # Extra settle time — let the applet finish rendering
                # so getBase64() captures the full construction.
                await page.wait_for_timeout(2000)

                # Export
                logger.debug("Calling getBase64() for %s", material_id)
                b64_str = await page.evaluate(_GET_BASE64_JS)

                if not b64_str:
                    raise RuntimeError("getBase64() returned empty result")

                content = base64.b64decode(b64_str)
                logger.info(
                    "Successfully exported %s (%d bytes)",
                    material_id, len(content),
                )

                return DownloadResult(
                    material_id=material_id,
                    success=True,
                    content=content,
                )

            except Exception as e:
                last_error = str(e)
                logger.warning(
                    "Failed to download %s (attempt %d): %s",
                    material_id, attempt + 1, last_error,
                )
                if attempt < self.max_retries - 1:
                    # Exponential backoff: 3s, 6s, ...
                    await asyncio.sleep(3 * (2 ** attempt))
            finally:
                await page.close()

        return DownloadResult(
            material_id=material_id,
            success=False,
            error=last_error,
        )

    @staticmethod
    def build_classic_url(material_id: str) -> str:
        """Build a GeoGebra Classic URL from a material ID."""
        return f"https://www.geogebra.org/classic/{material_id}"
