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
    parsed_url: ParsedUrl,
    output_dir: str,
    concurrency: int,
    headless: bool,
) -> None:
    """Async download workflow."""
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
