# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for claude-note
# Build: pyinstaller cn.spec  (or run build.ps1)

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Bundle static web UI files
        ('src/claude_note/static', 'claude_note/static'),
    ],
    hiddenimports=[
        # uvicorn dynamic imports
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.protocols.websockets.websockets_impl',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'uvicorn.lifespan.off',
        # fastapi / pydantic
        'fastapi',
        'fastapi.responses',
        'fastapi.staticfiles',
        'pydantic',
        # tray
        'pystray._win32',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        'PIL.ImageFont',
        # claude_note modules
        'claude_note.cli',
        'claude_note.tray',
        'claude_note.worker',
        'claude_note.web_api',
        'claude_note.enqueue',
        'claude_note.synthesizer',
        'claude_note.note_router',
        'claude_note.config',
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
    a.binaries,
    a.datas,
    [],
    name='cn',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowless — только трей
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
