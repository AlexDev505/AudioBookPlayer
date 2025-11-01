# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\projects\\AudioBookPlayer\\build\\..\\updater\\run.py'],
    pathex=[],
    binaries=[],
    datas=[('E:\\projects\\AudioBookPlayer\\build\\..\\updater\\web\\static', 'static'), ('E:\\projects\\AudioBookPlayer\\build\\..\\updater\\web\\templates', 'templates')],
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
    name='ABPlayerUpdater',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='updater_version_file',
    icon=['icon.ico'],
)
