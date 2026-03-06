"""CLI entry point for zest-crawler."""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import click

from zest_crawler.analyzer import GeoGebraAnalyzer
from zest_crawler.downloader import Downloader
from zest_crawler.models import ParsedUrl
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
    default=2,
    type=int,
    help="Max concurrent downloads (default: 2).",
)
@click.option(
    "--headless/--no-headless",
    default=True,
    help="Run browser in headless mode (default: headless).",
)
@click.option(
    "--proxy", "-p",
    default=None,
    type=str,
    help="Proxy server URL (e.g. http://127.0.0.1:7890). Auto-detects from HTTPS_PROXY/HTTP_PROXY env vars if not set.",
)
@click.option(
    "--timeout", "-t",
    default=60000,
    type=int,
    help="Page load timeout in ms (default: 60000).",
)
def download(url: str, output: str, concurrency: int, headless: bool, proxy: str | None, timeout: int) -> None:
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
    asyncio.run(_download_async(parsed, output, concurrency, headless, proxy, timeout))


async def _download_async(
    parsed_url: ParsedUrl,
    output_dir: str,
    concurrency: int,
    headless: bool,
    proxy: str | None,
    timeout: int,
) -> None:
    """Async download workflow."""
    # Step 1: Analyze the page to discover resources
    click.echo("Analyzing page with Playwright...")
    analyzer = GeoGebraAnalyzer(headless=headless, proxy=proxy, timeout=timeout)
    resources = await analyzer.analyze(parsed_url)

    if not resources:
        click.echo("No resources found on this page.")
        return

    click.echo(f"Found {len(resources)} resource(s).")

    # Determine output subdirectory name
    subdir_name = parsed_url.identifier
    storage = Storage(output_dir=Path(output_dir) / subdir_name)
    storage.ensure_dir()

    # Step 2: Download .ggb files one at a time, saving each immediately
    click.echo(f"Downloading .ggb files (one at a time)...")
    click.echo("  Each file is exported via GeoGebra Classic's getBase64() API.")

    downloader = Downloader(
        concurrency=concurrency,
        headless=headless,
        proxy=proxy,
        timeout=timeout,
    )

    material_ids = [r.material_id for r in resources]
    now = datetime.now(timezone.utc).isoformat()
    success_count = 0
    i = 0

    async for result in downloader.download_iter(material_ids):
        i += 1
        resource = resources[i - 1]
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
