# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for zest-crawler portable build."""

block_cipher = None

a = Analysis(
    ['src/zest_crawler/gui.py'],
    pathex=['src'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'zest_crawler',
        'zest_crawler.cli',
        'zest_crawler.gui',
        'zest_crawler.analyzer',
        'zest_crawler.downloader',
        'zest_crawler.models',
        'zest_crawler.router',
        'zest_crawler.storage',
        'async_tkinter_loop',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='zest-crawler',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='zest-crawler',
)
