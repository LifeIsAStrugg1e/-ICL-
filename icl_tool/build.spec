# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None
base = os.path.dirname(os.path.abspath('icl_tool.py'))

a = Analysis(
    ['icl_tool.py'],
    pathex=[base],
    binaries=[
        (os.path.join(base, 'lzo.dll'), '.'),
        (os.path.join(base, 'tjpgd.dll'), '.'),
    ],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ICL_ICO_Tool',
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
    icon=os.path.join(os.path.dirname(base), 'icon', 'icon.ico'),
)
