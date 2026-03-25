# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Clawdbot Monitor GUI
"""

block_cipher = None

a = Analysis(
    ['clawdbot-monitor-gui.py'],
    pathex=[],
    binaries=[
        # WSL相关
    ],
    datas=[
        # 不需要打包额外文件
    ],
    hiddenimports=[
        'customtkinter',
        'PIL',
        'darkdetect',
        'packaging',
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
    name='ClawdbotMonitor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # 无控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标: icon='icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    target_arch=None,
    name='ClawdbotMonitor',
)
