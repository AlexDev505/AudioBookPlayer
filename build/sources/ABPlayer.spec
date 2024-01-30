# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['E:\\PycharmProjects\\AudioBookPlayer\\build\\..\\ABPlayer\\run.py'],
    pathex=[],
    binaries=[],
    datas=[('E:\\PycharmProjects\\AudioBookPlayer\\build\\..\\ABPlayer\\web\\static', 'static'), ('E:\\PycharmProjects\\AudioBookPlayer\\build\\..\\ABPlayer\\web\\templates', 'templates')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
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
    console=True,
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
