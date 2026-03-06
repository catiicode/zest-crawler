"""Playwright-based page analyzer for GeoGebra resources.

Opens GeoGebra pages in a headless browser and extracts resource lists
from the DOM (links, cards, etc.).
"""

import logging
import os
import re
from typing import Any

from playwright.async_api import async_playwright, Page

from zest_crawler.models import GeoGebraResource, ParsedUrl, ResourceType, UrlType

logger = logging.getLogger(__name__)

# Pattern to extract material ID from hash fragments like #material/gvu6wrmv
_HASH_MATERIAL_RE = re.compile(r"#material/([a-zA-Z0-9]+)")

# Pattern to extract material ID from /m/<id> URLs
_PATH_MATERIAL_RE = re.compile(r"/m/([a-zA-Z0-9]+)$")


def _detect_proxy() -> dict[str, str] | None:
    """Detect system proxy from environment variables."""
    proxy_url = (
        os.environ.get("HTTPS_PROXY")
        or os.environ.get("https_proxy")
        or os.environ.get("HTTP_PROXY")
        or os.environ.get("http_proxy")
    )
    if proxy_url:
        return {"server": proxy_url}
    return None


class GeoGebraAnalyzer:
    """Analyzes GeoGebra pages using Playwright to extract resource info."""

    def __init__(
        self,
        headless: bool = True,
        proxy: str | None = None,
        timeout: float = 60000,
    ) -> None:
        self.headless = headless
        self.proxy = proxy
        self.timeout = timeout

    @staticmethod
    def build_full_url(parsed: ParsedUrl) -> str:
        """Build a full GeoGebra URL from a ParsedUrl."""
        if parsed.url_type == UrlType.USER:
            return f"https://www.geogebra.org/u/{parsed.identifier}"
        return f"https://www.geogebra.org/m/{parsed.identifier}"

    async def analyze(self, parsed: ParsedUrl) -> list[GeoGebraResource]:
        """Analyze a GeoGebra page and extract resources.

        Args:
            parsed: The parsed URL to analyze.

        Returns:
            List of discovered GeoGebraResource objects.
        """
        url = self.build_full_url(parsed)

        proxy_config = None
        if self.proxy:
            proxy_config = {"server": self.proxy}
        else:
            proxy_config = _detect_proxy()

        if proxy_config:
            logger.info("Using proxy: %s", proxy_config["server"])

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                proxy=proxy_config,
            )
            context = await browser.new_context()
            page = await context.new_page()

            logger.info("Navigating to %s", url)
            await page.goto(url, wait_until="networkidle", timeout=self.timeout)
            await page.wait_for_timeout(2000)

            # For user pages, scroll to load all content
            if parsed.url_type == UrlType.USER:
                await self._scroll_to_load_all(page)

            # Extract resources from DOM
            resources = await self._extract_from_dom(page, parsed)

            await browser.close()

        return resources

    async def _extract_from_dom(
        self, page: Page, parsed: ParsedUrl
    ) -> list[GeoGebraResource]:
        """Extract resource information directly from the page DOM."""
        # Strategy 1: Extract from <a> links with #material/<id> hash
        resources = await self._extract_from_hash_links(page)

        # Strategy 2: If no hash links found, try /m/<id> links
        if not resources:
            resources = await self._extract_from_path_links(page)

        # Strategy 3: If this is a single resource (not a book/collection),
        # treat the page itself as the resource
        if not resources and parsed.url_type == UrlType.SINGLE:
            title = await page.title()
            # Clean up title: "XXX – GeoGebra" -> "XXX"
            title = re.sub(r"\s*[–-]\s*GeoGebra\s*$", "", title).strip()
            if title:
                resources = [
                    GeoGebraResource(
                        material_id=parsed.identifier,
                        title=title,
                        author="",
                        resource_type=ResourceType.UNKNOWN,
                        url=f"https://www.geogebra.org/m/{parsed.identifier}",
                    )
                ]

        logger.info("Found %d resources from page DOM", len(resources))
        return resources

    async def _extract_from_hash_links(
        self, page: Page
    ) -> list[GeoGebraResource]:
        """Extract resources from links like /m/<book>#material/<id>."""
        links = await page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a[href*="#material/"]').forEach(a => {
                    const href = a.href;
                    const match = href.match(/#material\\/([a-zA-Z0-9]+)/);
                    if (match && !seen.has(match[1])) {
                        seen.add(match[1]);
                        results.push({
                            id: match[1],
                            title: a.textContent.trim(),
                            href: href,
                        });
                    }
                });
                return results;
            }
        """)

        resources: list[GeoGebraResource] = []
        for link in links:
            mid = link["id"]
            title = link["title"] or "Untitled"
            resources.append(
                GeoGebraResource(
                    material_id=mid,
                    title=title,
                    author="",
                    resource_type=ResourceType.ACTIVITY,
                    url=f"https://www.geogebra.org/m/{mid}",
                )
            )
            logger.debug("Found resource: %s (%s)", title, mid)

        return resources

    async def _extract_from_path_links(
        self, page: Page
    ) -> list[GeoGebraResource]:
        """Extract resources from links like /m/<id> (user pages, recommendations)."""
        links = await page.evaluate("""
            () => {
                const seen = new Set();
                const results = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href;
                    const match = href.match(/geogebra\\.org\\/m\\/([a-zA-Z0-9]+)$/);
                    if (match && !seen.has(match[1])) {
                        seen.add(match[1]);
                        results.push({
                            id: match[1],
                            title: a.textContent.trim(),
                            href: href,
                        });
                    }
                });
                return results;
            }
        """)

        resources: list[GeoGebraResource] = []
        for link in links:
            mid = link["id"]
            title = link["title"] or "Untitled"
            if not title or len(title) > 200:
                continue
            resources.append(
                GeoGebraResource(
                    material_id=mid,
                    title=title,
                    author="",
                    resource_type=ResourceType.ACTIVITY,
                    url=f"https://www.geogebra.org/m/{mid}",
                )
            )
            logger.debug("Found resource: %s (%s)", title, mid)

        return resources

    async def _scroll_to_load_all(self, page: Page) -> None:
        """Scroll to the bottom of the page to trigger lazy loading."""
        previous_height = 0
        for _ in range(20):
            current_height = await page.evaluate("document.body.scrollHeight")
            if current_height == previous_height:
                break
            previous_height = current_height
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1500)
