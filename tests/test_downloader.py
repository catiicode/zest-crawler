from zest_crawler.downloader import Downloader, DownloadResult


def test_download_result_success():
    r = DownloadResult(material_id="abc", success=True, content=b"data")
    assert r.success is True
    assert r.content == b"data"


def test_download_result_failure():
    r = DownloadResult(material_id="abc", success=False, error="timeout")
    assert r.success is False
    assert r.content is None
    assert r.error == "timeout"


def test_build_classic_url():
    url = Downloader.build_classic_url("gvu6wrmv")
    assert url == "https://www.geogebra.org/classic/gvu6wrmv"
