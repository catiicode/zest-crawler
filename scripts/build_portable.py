"""Build a portable .zip distribution of zest-crawler.

Usage:
    uv sync --extra build
    uv run python scripts/build_portable.py [--proxy http://127.0.0.1:7890]

Options:
    --proxy URL   Proxy for downloading Playwright browsers.
                  Also reads from HTTPS_PROXY / HTTP_PROXY env vars.
    --skip-browser  Skip browser download (use if already installed).

This script:
1. Ensures Playwright Chromium is installed locally
2. Runs PyInstaller to create the onedir distribution
3. Zips the output into zest-crawler-portable.zip
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist"
BUILD_NAME = "zest-crawler"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build zest-crawler portable package")
    parser.add_argument("--proxy", help="Proxy URL for downloading Playwright browsers")
    parser.add_argument("--skip-browser", action="store_true",
                        help="Skip browser download step")
    args = parser.parse_args()

    print("=== Building zest-crawler portable package ===\n")

    env = os.environ.copy()
    env["PLAYWRIGHT_BROWSERS_PATH"] = "0"

    # Ensure proxy is set for Playwright's Node.js download process
    if args.proxy:
        env["HTTPS_PROXY"] = args.proxy
        env["HTTP_PROXY"] = args.proxy

    # Step 1: Ensure Playwright browsers are installed
    if not args.skip_browser:
        proxy_url = env.get("HTTPS_PROXY") or env.get("HTTP_PROXY")
        if proxy_url:
            print(f"[1/3] Downloading Playwright Chromium (proxy: {proxy_url})...")
        else:
            print("[1/3] Downloading Playwright Chromium...")
            print("      (If download fails, try: --proxy http://127.0.0.1:7890)")

        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            check=True,
            env=env,
        )
    else:
        print("[1/3] Skipping browser download (--skip-browser)")

    # Step 2: Run PyInstaller
    print("\n[2/3] Running PyInstaller...")
    spec_file = ROOT / "zest-crawler.spec"
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", str(spec_file), "--noconfirm"],
        check=True,
        cwd=str(ROOT),
        env=env,
    )

    # Step 3: Zip the output
    print("\n[3/3] Creating zip archive...")
    dist_folder = DIST_DIR / BUILD_NAME
    if not dist_folder.exists():
        print(f"ERROR: {dist_folder} not found. Build may have failed.")
        sys.exit(1)

    zip_path = DIST_DIR / f"{BUILD_NAME}-portable"
    shutil.make_archive(str(zip_path), "zip", str(DIST_DIR), BUILD_NAME)
    final_zip = zip_path.with_suffix(".zip")
    size_mb = final_zip.stat().st_size / 1024 / 1024
    print(f"\nDone! Portable package: {final_zip}")
    print(f"Size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
