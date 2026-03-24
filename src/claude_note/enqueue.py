#!/usr/bin/env python3
"""
Fast hook handler for claude-note.

Reads hook event from stdin and appends to queue.
Must be FAST - exits immediately, even on errors.
"""

import json
import os
import sys

from . import models
from . import queue_manager


def main() -> int:
    """Main entry point for enqueue command."""
    try:
        # Skip if running inside synthesizer (prevents recursive loop)
        if os.environ.get("CLAUDE_NOTE_SYNTHESIS") == "1":
            return 0

        # Read JSON from stdin (use binary buffer to ensure UTF-8 on Windows)
        raw_input = sys.stdin.buffer.read().decode("utf-8")
        if not raw_input.strip():
            # No input is fine, just exit
            return 0

        hook_data = json.loads(raw_input)

        # Create event and enqueue
        event = models.QueuedEvent.from_hook_input(hook_data)
        queue_manager.enqueue_event(event)

        return 0

    except json.JSONDecodeError as e:
        # Log to stderr but don't fail the hook
        print(f"claude-note: JSON decode error: {e}", file=sys.stderr)
        return 0

    except Exception as e:
        # Log to stderr but don't fail the hook
        print(f"claude-note: Error: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
