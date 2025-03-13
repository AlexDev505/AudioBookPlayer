# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\learn\\open_source_github\\audiobookplayer\\build\\..\\ABPlayer\\run.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\learn\\open_source_github\\audiobookplayer\\build\\..\\ABPlayer\\web\\static', 'static'), ('C:\\Users\\learn\\open_source_github\\audiobookplayer\\build\\..\\ABPlayer\\web\\templates', 'templates'), ('C:\\Users\\learn\\open_source_github\\audiobookplayer\\build\\..\\ABPlayer\\drivers\\bin', 'bin')],
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
    [],
    exclude_binaries=True,
    name='ABPlayer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_file',
    icon=['icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ABPlayer',
)
