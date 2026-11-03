# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['smoothstep.py'],
    pathex=[],
    binaries=[],
    datas=[('gcodezaa', 'gcodezaa'), ('smoothstep_icon.png', '.'), ('Fromel3DLogo-8.1.png', '.')],
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
    name='SmoothStep',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='SmoothStep',
)
app = BUNDLE(
    coll,
    name='SmoothStep.app',
    icon=None,
    bundle_identifier=None,
)
