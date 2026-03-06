"""File storage and CSV metadata writer."""

import csv
import re
from pathlib import Path

from zest_crawler.models import GeoGebraResource

_CSV_FIELDS = [
    "material_id",
    "title",
    "author",
    "resource_type",
    "url",
    "filename",
    "download_time",
]


class Storage:
    """Manages output directory and file saving."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir

    def ensure_dir(self) -> None:
        """Create the output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, filename: str, content: bytes) -> Path:
        """Save a file to the output directory."""
        path = self.output_dir / filename
        path.write_bytes(content)
        return path

    def write_metadata(self, resources: list[GeoGebraResource]) -> Path:
        """Write resource metadata to a CSV file."""
        csv_path = self.output_dir / "metadata.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
            writer.writeheader()
            for r in resources:
                writer.writerow({
                    "material_id": r.material_id,
                    "title": r.title,
                    "author": r.author,
                    "resource_type": r.resource_type.value,
                    "url": r.url,
                    "filename": r.filename,
                    "download_time": r.download_time,
                })
        return csv_path

    @staticmethod
    def make_filename(index: int, title: str) -> str:
        """Generate a numbered filename from a title.

        Replaces filesystem-unsafe characters with underscores.
        """
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title)
        return f"{index:02d}-{safe_title}.ggb"
