# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for CodeGuard Harness — bundles WebUI templates/static."""

block_cipher = None

a = Analysis(
    ['codeguard/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=['jinja2', 'uvicorn', 'fastapi', 'httpx'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Bundle WebUI templates and static assets (frozen path resolved in app.py)
_web_assets = [
    'codeguard/web/templates/base.html',
    'codeguard/web/templates/scenarios.html',
    'codeguard/web/templates/dashboard.html',
    'codeguard/web/templates/approval.html',
    'codeguard/web/templates/results.html',
    'codeguard/web/static/style.css',
    'codeguard/web/static/main.js',
    'codeguard/web/static/approval.js',
]
a.datas += [(f, f, 'DATA') for f in _web_assets]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
    name='codeguard', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=True, upx_exclude=[], runtime_tmpdir=None,
    console=True, disable_windowed_traceback=False, argv_emulation=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
)
