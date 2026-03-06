"""Integration test: validates the full pipeline wiring."""

from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from click.testing import CliRunner

from zest_crawler.cli import main
from zest_crawler.models import GeoGebraResource, ResourceType


def _make_mock_resources():
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


def test_full_pipeline_with_mocks(tmp_path: Path):
    """Test the full download pipeline with mocked analyzer and downloader."""
    from zest_crawler.downloader import DownloadResult

    mock_resources = _make_mock_resources()

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
