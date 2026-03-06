import csv
from pathlib import Path

from zest_crawler.models import GeoGebraResource, ResourceType
from zest_crawler.storage import Storage


def test_storage_creates_output_dir(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out" / "test-book")
    storage.ensure_dir()
    assert (tmp_path / "out" / "test-book").is_dir()


def test_storage_save_file(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out")
    storage.ensure_dir()
    storage.save_file("01-hello.ggb", b"fake-ggb-content")
    saved = tmp_path / "out" / "01-hello.ggb"
    assert saved.exists()
    assert saved.read_bytes() == b"fake-ggb-content"


def test_storage_write_metadata_csv(tmp_path: Path):
    storage = Storage(output_dir=tmp_path / "out")
    storage.ensure_dir()

    resources = [
        GeoGebraResource(
            material_id="abc123",
            title="Demo 1",
            author="user1",
            resource_type=ResourceType.ACTIVITY,
            url="https://www.geogebra.org/m/abc123",
            filename="01-Demo 1.ggb",
            download_time="2026-03-06T10:00:00",
        ),
        GeoGebraResource(
            material_id="def456",
            title="Demo 2",
            author="user2",
            resource_type=ResourceType.WORKSHEET,
            url="https://www.geogebra.org/m/def456",
            filename="02-Demo 2.ggb",
            download_time="2026-03-06T10:01:00",
        ),
    ]

    storage.write_metadata(resources)

    csv_path = tmp_path / "out" / "metadata.csv"
    assert csv_path.exists()

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["material_id"] == "abc123"
    assert rows[0]["title"] == "Demo 1"
    assert rows[1]["resource_type"] == "worksheet"


def test_storage_make_filename():
    storage = Storage(output_dir=Path("out"))
    assert storage.make_filename(1, "三角函数") == "01-三角函数.ggb"
    assert storage.make_filename(12, "Demo / Test") == "12-Demo _ Test.ggb"
