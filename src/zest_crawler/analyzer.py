"""Playwright-based page analyzer for GeoGebra resources.

Opens GeoGebra pages in a headless browser, intercepts network requests
to discover API endpoints, and extracts resource lists.
"""

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
