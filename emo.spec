# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for emo
# Build with: pyinstaller emo.spec

from PyInstaller.utils.hooks import collect_all

# collect_all bundles litellm's Python modules, binaries, AND data files,
# preserving the exact package-relative paths that importlib.resources expects.
_litellm_datas, _litellm_binaries, _litellm_hiddenimports = collect_all("litellm")
_tiktoken_datas, _tiktoken_binaries, _tiktoken_hiddenimports = collect_all("tiktoken")
# tiktoken_ext is a namespace package containing the actual encoding constructors
# (e.g. cl100k_base). Without it tiktoken.get_encoding() raises "Unknown encoding".
_tiktoken_ext_datas, _tiktoken_ext_binaries, _tiktoken_ext_hiddenimports = collect_all(
    "tiktoken_ext"
)

block_cipher = None

a = Analysis(
    ["emo/cli.py"],
    pathex=["."],
    binaries=[
        *_litellm_binaries,
        *_tiktoken_binaries,
        *_tiktoken_ext_binaries,
    ],
    datas=[
        ("config.yaml.example", "."),
        # Web UI static build — produced by `pnpm build` in web/
        # The entire web/build directory is embedded under _emo_web/ in the binary.
        ("web/build", "_emo_web"),
        *_litellm_datas,
        *_tiktoken_datas,
        *_tiktoken_ext_datas,
    ],
    hiddenimports=[
        *_litellm_hiddenimports,
        *_tiktoken_hiddenimports,
        *_tiktoken_ext_hiddenimports,
        # litellm lazy provider imports
        "litellm",
        "litellm.utils",
        "litellm.main",
        "litellm.integrations",
        "litellm.llms",
        "litellm.llms.openai",
        "litellm.llms.anthropic",
        "litellm.llms.ollama",
        "litellm.llms.cohere",
        "litellm.llms.gemini",
        # httpx transports used at runtime
        "httpx._transports.default",
        "httpx._transports.asgi",
        # pyyaml C extension fallback
        "_yaml",
        # rich internals
        "rich.markup",
        "rich.syntax",
        "rich.traceback",
        # prompt_toolkit
        "prompt_toolkit.shortcuts",
        "prompt_toolkit.lexers",
        # sqlite3
        "sqlite3",
        "_sqlite3",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim test frameworks from the binary
        "pytest",
        "pytest_mock",
        "_pytest",
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
    name="emo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,  # compress if UPX is available; silently skipped if not
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # emo is a CLI tool
    disable_windowed_traceback=False,
    target_arch=None,  # use host arch; cross-compilation is done via native runners
    codesign_identity=None,
    entitlements_file=None,
)
