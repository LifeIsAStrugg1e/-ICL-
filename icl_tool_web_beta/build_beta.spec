# -*- mode: python ; coding: utf-8 -*-
# pywebview 测试版打包配置
import os

block_cipher = None
base = os.path.dirname(os.path.abspath('icl_tool_web_beta.py'))
core = os.path.join(os.path.dirname(base), 'icl_tool')

a = Analysis(
    ['icl_tool_web_beta.py'],
    pathex=[base, core],
    binaries=[
        (os.path.join(base, 'lzo.dll'), '.'),
        (os.path.join(base, 'tjpgd.dll'), '.'),
    ],
    datas=[
        (os.path.join(base, 'web'), 'web'),
    ],
    hiddenimports=[
        'webview',
        'webview.platforms.winforms',
        'clr',
        'pythonnet',
    ],
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
    name='ICL_ICO_Tool_Web_Beta',
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
