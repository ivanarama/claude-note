#!/usr/bin/env python3
"""
Main CLI entry point for claude-note.

Commands:
    enqueue   - Hook handler (reads stdin)
    worker    - Background daemon
    drain     - One-shot processing
    status    - Show queue/session status
    resynth   - Re-run synthesis for a session
    index     - Rebuild vault index
    clean     - Daily cleanup operations
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime

from . import __version__
from . import config
from . import queue_manager
from . import session_tracker
from . import note_router
from . import vault_indexer
from . import cleaner
from . import enqueue as enqueue_module
from . import worker as worker_module
from . import drain as drain_module
from . import synthesizer


def cmd_enqueue(args) -> int:
    """Handle enqueue command."""
    return enqueue_module.main()


def cmd_worker(args) -> int:
    """Handle worker command."""
    return worker_module.run_worker(foreground=args.foreground, verbose=args.verbose)


def cmd_drain(args) -> int:
    """Handle drain command."""
    return drain_module.main()


def _format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}" if unit != "B" else f"{size}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m"
    elif seconds < 86400:
        return f"{int(seconds // 3600)}h"
    else:
        return f"{int(seconds // 86400)}d"


def cmd_status(args) -> int:
    """Handle status command - show queue and session status."""
    from . import version_checker

    # Header with version
    update_status = version_checker.get_update_status()
    version_str = f"v{__version__}"
    if update_status["update_available"]:
        version_str += f" (update available: v{update_status['latest']})"

    print(f"claude-note {version_str}")
    print("=" * 50)

    # Config summary
    print(f"\nConfig")
    print(f"  Vault:     {config.VAULT_ROOT}")
    print(f"  Mode:      {config.SYNTH_MODE}")
    print(f"  Model:     {config.SYNTH_MODEL}")

    # Queue summary
    print(f"\nQueue")
    total_events = 0
    total_size = 0
    queue_files = []
    if config.QUEUE_DIR.exists():
        queue_files = sorted(config.QUEUE_DIR.glob("*.jsonl"))
        for qf in queue_files:
            total_size += qf.stat().st_size

    # Count sessions and their states
    sessions: dict[str, int] = {}
    for event in queue_manager.read_all_events():
        sessions[event.session_id] = sessions.get(event.session_id, 0) + 1
        total_events += 1

    written_count = 0
    pending_count = 0
    for session_id in sessions:
        state = session_tracker.load_session_state(session_id)
        if state and state.last_write_ts:
            written_count += 1
        else:
            pending_count += 1

    print(f"  Files:     {len(queue_files)} ({_format_bytes(total_size)})")
    print(f"  Events:    {total_events}")
    print(f"  Sessions:  {len(sessions)} ({written_count} written, {pending_count} pending)")

    # State directory
    print(f"\nState")
    if config.STATE_DIR.exists():
        state_files = list(config.STATE_DIR.glob("*.json"))
        lock_files = list(config.STATE_DIR.glob("*.lock"))
        print(f"  Sessions:  {len(state_files)} state files")
        print(f"  Locks:     {len(lock_files)} active")
    else:
        print("  (not initialized)")

    # Vault index
    print(f"\nVault Index")
    if config.INDEX_PATH.exists():
        index = vault_indexer.load_index()
        if index:
            age = time.time() - index.last_full_scan
            print(f"  Notes:     {len(index.notes)}")
            print(f"  Age:       {_format_duration(age)}")
        else:
            print("  (corrupted)")
    else:
        print("  (not built - run: claude-note index)")

    # Inbox
    print(f"\nInbox")
    if config.INBOX_PATH.exists():
        entries = note_router.get_inbox_entries(limit=3)
        if entries:
            print(f"  Recent:")
            for e in entries:
                title = e['title'][:45] + "..." if len(e['title']) > 45 else e['title']
                print(f"    {e['date']}  {title}")
        else:
            print("  (empty)")
    else:
        print("  (not created yet)")

    print()

    return 0


def cmd_resynth(args) -> int:
    """Handle resynth command - re-run synthesis for a session."""
    session_id = args.session_id
    model = args.model

    print(f"Re-synthesizing session {session_id[:8]}...")
    if model:
        print(f"Using model: {model}")

    try:
        pack = synthesizer.resynthesize_session(session_id, model=model)

        if pack is None or pack.is_empty():
            print("No knowledge extracted from session.")
            return 0

        print(f"Extracted:")
        print(f"  Title: {pack.title}")
        print(f"  Highlights: {len(pack.highlights)}")
        print(f"  Concepts: {len(pack.concepts)}")
        print(f"  Decisions: {len(pack.decisions)}")
        print(f"  Open questions: {len(pack.open_questions)}")
        print(f"  How-tos: {len(pack.howtos)}")
        print(f"  Note ops: {len(pack.note_ops)}")

        # Apply based on mode (or use explicit mode from args)
        mode = args.mode if args.mode else config.SYNTH_MODE
        if mode == "log":
            mode = "inbox"  # For resynth, at least write to inbox

        print(f"\nApplying with mode: {mode}")
        results = note_router.apply_note_ops(pack, mode=mode)

        if results["inbox_updated"]:
            print("  Updated inbox")
        if results["notes_created"]:
            print(f"  Created: {', '.join(results['notes_created'])}")
        if results["notes_updated"]:
            print(f"  Updated: {', '.join(results['notes_updated'])}")
        if results["errors"]:
            print(f"  Errors: {', '.join(results['errors'])}")

        return 0

    except Exception as e:
        print(f"Error: {e}")
        return 1


def cmd_index(args) -> int:
    """Handle index command - rebuild vault index."""
    print("Rebuilding vault index...")

    index = vault_indexer.build_index()
    vault_indexer.save_index(index)

    summary = vault_indexer.get_index_summary()

    print(f"Indexed {summary['total_notes']} notes")
    print(f"Found {summary['unique_tags']} unique tags")
    print("\nTop tags:")
    for tag, count in summary['top_tags'][:10]:
        print(f"  #{tag}: {count}")

    return 0


def cmd_clean(args) -> int:
    """Handle clean command - daily cleanup operations."""
    # Determine what to clean
    clean_all = args.all
    clean_state = args.state or clean_all
    clean_sessions = args.sessions or clean_all
    clean_inbox = args.inbox or clean_all
    clean_topics = args.topics or clean_all

    # If nothing specified, default to all
    if not any([args.state, args.sessions, args.inbox, args.topics, args.all]):
        clean_state = clean_sessions = clean_inbox = clean_topics = True

    # Run cleanup
    results = cleaner.run_daily_clean(
        date=args.date,
        dry_run=not args.execute,
        clean_state=clean_state,
        clean_sessions=clean_sessions,
        clean_inbox=clean_inbox,
        clean_topics=clean_topics,
    )

    # Format and print results
    output = cleaner.format_clean_results(results)
    print(output)

    if not args.execute:
        print("\nThis was a dry-run. Use --execute (-x) to apply changes.")

    return 0


def cmd_ingest(args) -> int:
    """Handle ingest command - ingest external research documents."""
    from . import ingest
    return ingest.main(args)


def cmd_update(args) -> int:
    """Handle update command - check and apply updates."""
    from . import version_checker

    print(f"Current version: {__version__}")

    status = version_checker.get_update_status()

    if status["latest"] is None:
        print("Could not check for updates (network error)")
        return 1

    if not status["update_available"]:
        print(f"Already on latest version ({__version__})")
        return 0

    print(f"New version available: {status['latest']}")
    print("\nUpdating...")

    result = subprocess.run(
        ["uv", "tool", "install", "--force", "--upgrade",
         "https://github.com/artemiin/claude-note.git"],
        capture_output=False
    )

    if result.returncode == 0:
        print("\nUpdate complete! Restart the worker to use the new version:")
        print("  launchctl kickstart -k gui/$(id -u)/com.claude-note.worker")

    return result.returncode


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Claude Note - session logging for Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # enqueue command
    enqueue_parser = subparsers.add_parser(
        "enqueue", help="Hook handler (reads JSON from stdin)"
    )
    enqueue_parser.set_defaults(func=cmd_enqueue)

    # worker command
    worker_parser = subparsers.add_parser("worker", help="Background daemon")
    worker_parser.add_argument(
        "--foreground", "-f", action="store_true", help="Run in foreground"
    )
    worker_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Verbose logging"
    )
    worker_parser.set_defaults(func=cmd_worker)

    # drain command
    drain_parser = subparsers.add_parser(
        "drain", help="One-shot processing (ignore debounce)"
    )
    drain_parser.set_defaults(func=cmd_drain)

    # status command
    status_parser = subparsers.add_parser("status", help="Show queue/session status")
    status_parser.set_defaults(func=cmd_status)

    # update command
    update_parser = subparsers.add_parser("update", help="Check for and apply updates")
    update_parser.set_defaults(func=cmd_update)

    # resynth command
    resynth_parser = subparsers.add_parser(
        "resynth", help="Re-run synthesis for a session"
    )
    resynth_parser.add_argument(
        "session_id", help="Session ID (full or prefix)"
    )
    resynth_parser.add_argument(
        "--mode", "-m", choices=["inbox", "route"],
        help="Override synthesis mode"
    )
    resynth_parser.add_argument(
        "--model", help="Override model (e.g., claude-opus-4-20250514)"
    )
    resynth_parser.set_defaults(func=cmd_resynth)

    # index command
    index_parser = subparsers.add_parser(
        "index", help="Rebuild vault index"
    )
    index_parser.set_defaults(func=cmd_index)

    # clean command
    clean_parser = subparsers.add_parser(
        "clean", help="Daily cleanup (dedupe inbox, compress timelines, etc.)"
    )
    clean_parser.add_argument(
        "--date", "-d",
        help="Date to clean (YYYY-MM-DD, default: today)"
    )
    clean_parser.add_argument(
        "--execute", "-x", action="store_true",
        help="Actually execute changes (default: dry-run)"
    )
    clean_parser.add_argument(
        "--state", action="store_true",
        help="Clean state directory (orphan locks, old sessions)"
    )
    clean_parser.add_argument(
        "--sessions", action="store_true",
        help="Compress session timelines"
    )
    clean_parser.add_argument(
        "--inbox", action="store_true",
        help="Deduplicate inbox entries"
    )
    clean_parser.add_argument(
        "--topics", action="store_true",
        help="Consolidate redundant blocks in topic notes"
    )
    clean_parser.add_argument(
        "--all", "-a", action="store_true",
        help="Run all cleanup types"
    )
    clean_parser.set_defaults(func=cmd_clean)

    # ingest command
    ingest_parser = subparsers.add_parser(
        "ingest", help="Ingest external research (papers, docs) as lit-* notes"
    )
    ingest_parser.add_argument(
        "file", help="Document to ingest (.pdf, .docx, .md, .txt)"
    )
    ingest_parser.add_argument(
        "--title", "-t", help="Override title (default: filename)"
    )
    ingest_parser.add_argument(
        "--model", "-m", help="Override Claude model"
    )
    ingest_parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Extract knowledge but don't create notes"
    )
    ingest_parser.add_argument(
        "--internal", "-i", action="store_true",
        help="Internal mode: create int-* notes in internal/ (default: lit-* in literature/)"
    )
    ingest_parser.set_defaults(func=cmd_ingest)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
