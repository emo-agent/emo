# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for emo
# Build with: pyinstaller emo.spec

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    # Entry point — same module that pyproject.toml [project.scripts] points at
    ['emo/cli.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # Bundle the example config so first-run setup wizard can reference it
        ('config.yaml.example', '.'),
    ],
    hiddenimports=[
        # litellm uses lazy provider imports; name them explicitly so PyInstaller
        # includes them even though they are not statically reachable
        'litellm',
        'litellm.utils',
        'litellm.main',
        'litellm.integrations',
        'litellm.llms',
        'litellm.llms.openai',
        'litellm.llms.anthropic',
        'litellm.llms.ollama',
        'litellm.llms.cohere',
        'litellm.llms.gemini',
        'litellm.llms.huggingface_restapi',
        # httpx transports used at runtime
        'httpx._transports.default',
        'httpx._transports.asgi',
        # pyyaml C extension fallback
        '_yaml',
        # rich internals
        'rich.markup',
        'rich.syntax',
        'rich.traceback',
        # prompt_toolkit
        'prompt_toolkit.shortcuts',
        'prompt_toolkit.lexers',
        # sqlite3 is stdlib but sometimes missed on Linux builds
        'sqlite3',
        '_sqlite3',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim test frameworks from the binary
        'pytest',
        'pytest_mock',
        '_pytest',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    # Single-file binary — no directory bundle
    name='emo',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,          # compress if UPX is available; silently skipped if not
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,      # emo is a CLI tool
    disable_windowed_traceback=False,
    target_arch=None,  # use host arch; cross-compilation is done via native runners
    codesign_identity=None,
    entitlements_file=None,
)
