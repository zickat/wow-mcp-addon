# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['/sessions/compassionate-happy-cori/mnt/wow tbc/wow-mcp/server.py'],
    pathex=[],
    binaries=[],
    datas=[('/sessions/compassionate-happy-cori/mnt/wow tbc/data/items_db.json', 'data'), ('/sessions/compassionate-happy-cori/mnt/wow tbc/data/stat_weights.json', 'data'), ('/sessions/compassionate-happy-cori/mnt/wow tbc/data/loot.json', 'data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='wow-mcp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
