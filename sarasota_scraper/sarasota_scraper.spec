# -*- mode: python ; coding: utf-8 -*-
import sys
import os

block_cipher = None

# Base project directory
project_dir = os.path.abspath(SPECPATH)

# Required hidden imports for scraping and GUI dependencies
hidden_imports = [
    'requests',
    'bs4',
    'soupsieve',
    'urllib3',
    'charset_normalizer',
    'idna',
    'certifi',
    'tkinter',
    'tkinter.ttk',
    'tkinter.font',
    'tkinter.scrolledtext',
]

# Windows-specific printing modules
if sys.platform == 'win32' or os.getenv('TARGET_OS') == 'windows':
    hidden_imports.extend([
        'win32print',
        'win32api',
        'win32con',
        'pywintypes',
    ])

# Exclude heavy or experimental libraries that are not part of the GUI app
excluded_modules = [
    'playwright',
    'pytest',
    'unittest',
    'pdb',
    'pydoc',
    'doctest',
    'accela_test',
    'scrapersave',
]

a = Analysis(
    [os.path.join(project_dir, 'gui.py')],
    pathex=[project_dir],
    binaries=[],
    datas=[],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excluded_modules,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='SarasotaScraper',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # Windowed GUI app (hides Windows CMD prompt)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=os.path.join(project_dir, 'app_icon.ico')  # Uncomment if .ico asset is added
)
