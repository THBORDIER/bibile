# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Bibile Desktop.
Build: pyinstaller bibile.spec --clean
"""

import os

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('bibile/templates', 'bibile/templates'),
        ('bibile/static', 'bibile/static'),
    ],
    hiddenimports=[
        'pandas',
        'openpyxl',
        'webview',
        'flask',
        'jinja2',
        'jinja2.ext',
        'fitz',
        'pymupdf',
        'pymssql',
        'pyodbc',
    ],
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
    name='Bibile',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Bibile',
)
