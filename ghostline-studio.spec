# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Ghostline Studio
Creates a standalone Linux executable with all dependencies bundled
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all ghostline submodules
ghostline_modules = collect_submodules('ghostline')

# Collect data files from ghostline package
ghostline_datas = collect_data_files('ghostline', include_py_files=True)

# Add resources directory explicitly
resources_path = Path('ghostline/resources')
if resources_path.exists():
    ghostline_datas.append(('ghostline/resources', 'ghostline/resources'))

# Add settings directory
settings_path = Path('ghostline/settings')
if settings_path.exists():
    ghostline_datas.append(('ghostline/settings', 'ghostline/settings'))

# Add docs if they exist
docs_path = Path('docs')
if docs_path.exists():
    ghostline_datas.append(('docs', 'docs'))

a = Analysis(
    ['ghostline/main.py'],
    pathex=[],
    binaries=[],
    datas=ghostline_datas,
    hiddenimports=[
        # Core ghostline modules
        'ghostline',
        'ghostline.main',
        'ghostline.app',

        # PySide6 modules
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'PySide6.QtPrintSupport',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',

        # Shiboken
        'shiboken6',

        # AI and HTTP libraries
        'openai',
        'httpx',
        'httpx._transports.default',
        'httpx._transports.asgi',
        'httpx._models',
        'httpcore',
        'h11',
        'h2',
        'hpack',
        'hyperframe',
        'certifi',

        # YAML
        'yaml',

        # Token counting
        'tiktoken',
        'tiktoken_ext',
        'tiktoken_ext.openai_public',

        # Platform directories
        'platformdirs',

        # Process utilities
        'psutil',

        # Terminal modules (platform-specific)
        'ghostline.terminal.pty_terminal',
        'ghostline.terminal.windows_terminal',
        'ghostline.terminal.windsurf_terminal',

        # All ghostline submodules
        *ghostline_modules,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude test modules
        'tests',
        'pytest',
        'test',

        # Exclude development tools
        'black',
        'ruff',
        'mypy',

        # Exclude unnecessary Qt modules
        'PySide6.QtQuick',
        'PySide6.QtQml',
        'PySide6.QtWebEngine',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.Qt3D',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ghostline-studio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # GUI application, no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # TODO: Add application icon
)
