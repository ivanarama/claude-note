"""Entry point for PyInstaller build."""
import multiprocessing
multiprocessing.freeze_support()

from claude_note.cli import main
import sys
sys.exit(main())
