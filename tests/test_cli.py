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
