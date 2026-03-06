# GUI + Portable Packaging Design

**Date:** 2026-03-06
**Status:** Approved

## Goal

Add a tkinter GUI to zest-crawler and produce a portable Windows .zip package that runs without Python installed.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| GUI framework | tkinter + async-tkinter-loop | Stdlib, zero size overhead, adequate for simple form |
| Packager | PyInstaller --onedir | Official Playwright hook, fast builds, mature |
| Chromium | Bundle in .zip | Extract-and-run, no first-launch download needed |
| Language | Chinese UI | Target users are Chinese educators |
| Platform | Windows only | User requirement |

## GUI Layout

```
┌─────────────────────────────────────────────┐
│  GeoGebra 资源下载器                         │
├─────────────────────────────────────────────┤
│  资源地址: [________________________] [浏览..] │
│  保存目录: [________________________] [选择..] │
│  代理地址: [________________________]        │
│  并发数:   [2 ▾]    ☐ 显示浏览器窗口         │
│         [ 开始下载 ]    [ 停止 ]             │
├─────────────────────────────────────────────┤
│  ████████████████░░░░░░░░  7/10  70%        │
├─────────────────────────────────────────────┤
│  [scrolling log area]                       │
└─────────────────────────────────────────────┘
```

## Architecture

- **Only one new file**: `src/zest_crawler/gui.py` (~200 lines)
- All existing modules (analyzer, downloader, storage, router, models) reused unchanged
- CLI entry point preserved alongside GUI entry point
- `async-tkinter-loop` integrates tkinter mainloop with asyncio

## Packaging

- PyInstaller `--onedir --windowed` (no console window)
- Playwright official hook includes driver + chromium automatically
- Output zipped as `zest-crawler-portable.zip` (~150-180MB compressed)
- User extracts and double-clicks `zest-crawler.exe`

## Dependency Changes

```toml
# New runtime dependency
"async-tkinter-loop>=0.10"

# New optional build dependency
[project.optional-dependencies]
build = ["pyinstaller>=6.0"]

# New entry point
[project.gui-scripts]
zest-crawler-gui = "zest_crawler.gui:main"
```

## Out of Scope

- No changes to existing CLI code
- No multi-language support (Chinese only)
- No system tray / minimize-to-tray
- No auto-update mechanism
- No installer (.msi / .exe) — .zip only
