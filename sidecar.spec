# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — 仅打包 Python API sidecar（无托盘、无窗口、无前端）。"""

import sys
from pathlib import Path

_root = Path(SPECPATH)

a = Analysis(
    ['sidecar.py'],
    pathex=[str(_root)],
    binaries=[],
    datas=[
        (str(_root / 'config.example.yaml'), '.'),
        (str(_root / 'dist'), 'dist'),
    ],
    hiddenimports=[
        'uvicorn', 'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http', 'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets', 'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan', 'uvicorn.lifespan.on',
        'fastapi', 'fastapi.middleware',
        'starlette', 'starlette.staticfiles',
        'yaml',
        'paramiko',
        'sqlite3',
        'asyncio', 'asyncio.windows_events',
        'requests',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pystray', 'webview', 'PIL', 'PIL.Image', 'PIL.ImageDraw', 'numpy'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='python-sidecar',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
