"""Debug script: capture all network requests and page structure from a GeoGebra page."""

import asyncio
import json
import logging
import os
import sys

from playwright.async_api import async_playwright, Response

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Collect ALL responses
all_responses: list[dict] = []


async def on_response(response: Response) -> None:
    url = response.url
    content_type = response.headers.get("content-type", "")

    # Log every response
    logger.info("RESPONSE: [%d] %s  (type: %s)", response.status, url[:120], content_type[:50])

    # Capture JSON responses from geogebra.org
    if "geogebra.org" in url and ("json" in content_type or "javascript" in content_type):
        try:
            body = await response.json()
            all_responses.append({
                "url": url,
                "status": response.status,
                "content_type": content_type,
                "body": body,
            })
            logger.debug("  -> Captured JSON body (keys: %s)", list(body.keys()) if isinstance(body, dict) else type(body).__name__)
        except Exception as e:
            logger.debug("  -> Failed to parse JSON: %s", e)


async def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.geogebra.org/m/wy53ufy2"

    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    proxy_config = {"server": proxy_url} if proxy_url else None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, proxy=proxy_config)
        page = await browser.new_page()

        page.on("response", on_response)

        logger.info("=== Navigating to %s ===", url)
        await page.goto(url, wait_until="networkidle", timeout=90000)
        await page.wait_for_timeout(3000)

        # Dump page title
        title = await page.title()
        logger.info("=== Page title: %s ===", title)

        # Dump page URL (in case of redirects)
        logger.info("=== Final URL: %s ===", page.url)

        # Try to extract resource links from the page DOM
        logger.info("=== Extracting links from page DOM ===")
        links = await page.evaluate("""
            () => {
                const results = [];
                // Find all links that look like GeoGebra material links
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href;
                    if (href.includes('/m/') || href.includes('/classic/')) {
                        results.push({
                            href: href,
                            text: a.textContent.trim().substring(0, 100),
                        });
                    }
                });
                return results;
            }
        """)
        for link in links:
            logger.info("  LINK: %s  ->  %s", link["text"][:60], link["href"])

        # Try to find material cards or items
        logger.info("=== Looking for material cards/items ===")
        cards = await page.evaluate("""
            () => {
                const results = [];
                // Try various selectors that might contain material info
                const selectors = [
                    '[class*="material"]', '[class*="card"]', '[class*="item"]',
                    '[class*="resource"]', '[class*="activity"]', '[class*="chapter"]',
                    '[data-id]', '[data-material]',
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        results.push({
                            selector: sel,
                            count: els.length,
                            sample: els[0].outerHTML.substring(0, 300),
                        });
                    }
                }
                return results;
            }
        """)
        for card in cards:
            logger.info("  SELECTOR: %s (count: %d)", card["selector"], card["count"])
            logger.info("    SAMPLE: %s", card["sample"][:200])

        # Dump the page's main content HTML structure (first 3000 chars)
        logger.info("=== Page body structure (abbreviated) ===")
        body_html = await page.evaluate("() => document.body.innerHTML.substring(0, 5000)")
        logger.info(body_html[:3000])

        await browser.close()

    # Save captured JSON responses
    logger.info("=== Total JSON responses captured: %d ===", len(all_responses))
    if all_responses:
        with open("debug_responses.json", "w", encoding="utf-8") as f:
            json.dump(all_responses, f, ensure_ascii=False, indent=2, default=str)
        logger.info("Saved to debug_responses.json")


if __name__ == "__main__":
    asyncio.run(main())
