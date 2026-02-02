# Commands Reference

Complete reference for all `claude-note` CLI commands.

## Overview

```bash
claude-note <command> [options]
```

| Command | Description |
|---------|-------------|
| `status` | Show worker status and queue info |
| `enqueue` | Queue a session event (used by hooks) |
| `drain` | Process all pending sessions immediately |
| `worker` | Run the background worker (used by service) |
| `clean` | Clean up stale locks and duplicate sessions |
| `index` | Rebuild vault index for synthesis context |
| `resynth` | Re-synthesize a specific session |
| `ingest` | Ingest external documents as literature notes |

---

## status

Show current status of the Claude Note system.

```bash
claude-note status
```

### Output

```
Worker: running (PID 12345)
Queue: 2 pending events
Sessions: 1 active, 5 completed today
Last synthesis: 2024-01-15 14:32:00

Active sessions:
  abc123 - /Users/you/project (started 5m ago)

Recent completions:
  def456 - /Users/you/other-project (synthesized)
  ghi789 - /Users/you/project (synthesized)
```

### What it shows

| Field | Description |
|-------|-------------|
| Worker | Whether background worker is running and its PID |
| Queue | Number of events waiting to be processed |
| Sessions | Active (in-progress) and completed today |
| Last synthesis | When knowledge extraction last ran |
| Active sessions | Currently open Claude Code sessions |
| Recent completions | Sessions that finished and were synthesized |

---

## enqueue

Queue a session event. This is called automatically by Claude Code hooks.

```bash
claude-note enqueue [event_type] [session_id]
```

### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `event_type` | Type of event: `tool_use`, `prompt`, `stop`, `test` | Auto-detected from stdin |
| `session_id` | Session identifier | From `$CLAUDE_SESSION_ID` env var |

### How hooks use it

Claude Code passes session data via stdin (JSON) and environment variables:

```bash
# Environment variables set by Claude Code
CLAUDE_SESSION_ID=abc-123-def
CLAUDE_WORKING_DIR=/Users/you/project

# Hook invocation (data comes via stdin)
echo '{"type":"tool_use","tool":"Read",...}' | claude-note enqueue
```

### Manual testing

```bash
# Test that enqueue works
CLAUDE_SESSION_ID=test-123 claude-note enqueue test

# Check it was queued
claude-note status
```

---

## drain

Process all pending sessions immediately, without waiting for the worker's normal schedule.

```bash
claude-note drain [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run`, `-n` | Show what would be processed without doing it |
| `--verbose`, `-v` | Show detailed processing output |

### When to use

- After installation, to process any backlogged sessions
- When you want immediate synthesis instead of waiting
- After fixing configuration issues

### Example

```bash
# See what's pending
claude-note drain --dry-run

# Process everything now
claude-note drain --verbose
```

---

## worker

Run the background worker process. This is called by launchd/systemd, not manually.

```bash
claude-note worker
```

### What it does

1. Monitors the queue directory for new events
2. Tracks session state (start/activity/stop)
3. Triggers synthesis when sessions end
4. Writes results to vault

### Running manually (for debugging)

```bash
# Stop the service first
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist  # macOS
# or
systemctl --user stop claude-note  # Linux

# Run in foreground
claude-note worker

# Restart service when done
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist  # macOS
# or
systemctl --user start claude-note  # Linux
```

---

## clean

Clean up stale state files and fix common issues.

```bash
claude-note clean [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run`, `-n` | Show what would be cleaned without doing it |
| `--force`, `-f` | Clean without confirmation prompts |

### What it cleans

| Item | Condition |
|------|-----------|
| Stale locks | Lock files older than 1 hour |
| Orphaned state | Session state with no recent activity |
| Duplicate sessions | Multiple state files for same session ID |
| Empty queue files | Queue files with no valid events |

### Example

```bash
# See what would be cleaned
claude-note clean --dry-run

# Clean everything
claude-note clean --force
```

---

## index

Rebuild the vault index used for synthesis context.

```bash
claude-note index [options]
```

### Options

| Option | Description |
|--------|-------------|
| `--full` | Full reindex (slower, more thorough) |
| `--verbose`, `-v` | Show indexing progress |

### What it indexes

- Note titles and aliases
- Tags and frontmatter
- First paragraph/summary of each note
- Wiki-link connections

### When to use

- After major vault reorganization
- If synthesis isn't finding relevant notes
- After importing many new notes

### Example

```bash
# Quick incremental index
claude-note index

# Full reindex
claude-note index --full --verbose
```

---

## resynth

Re-run synthesis for a specific session.

```bash
claude-note resynth <session_id> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `session_id` | The session ID to re-synthesize (from status or logs) |

### Options

| Option | Description |
|--------|-------------|
| `--dry-run`, `-n` | Show synthesis output without writing to vault |
| `--model`, `-m` | Override the Claude model |
| `--mode` | Override synthesis mode (log/inbox/route) |

### When to use

- Synthesis failed due to temporary error
- You want to try different synthesis settings
- Testing changes to synthesis prompts

### Example

```bash
# Re-synthesize with defaults
claude-note resynth abc-123-def

# Test with different model
claude-note resynth abc-123-def --model claude-opus-4-20250514 --dry-run
```

---

## ingest

Ingest external documents (papers, docs) as structured literature notes.

> **Tip:** For single documents in Claude Code sessions, use the `/ingest` skill instead.
> The CLI is best for batch processing or automation scripts.

```bash
claude-note ingest <file> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `file` | Document to ingest (.pdf, .docx, .md, .txt) |

### Options

| Option | Description |
|--------|-------------|
| `--title`, `-t` | Override the note title (default: filename) |
| `--model`, `-m` | Override Claude model for extraction |
| `--dry-run`, `-n` | Extract knowledge but don't create notes |
| `--internal`, `-i` | Create `int-*` notes in `internal/` instead of `lit-*` |

### Supported formats

| Format | Requirements |
|--------|--------------|
| `.pdf` | Requires `pandoc` or `pdftotext` |
| `.docx` | Requires `pandoc` |
| `.md` | Native support |
| `.txt` | Native support |

### What it does

1. **Extracts text** from the document
2. **Analyzes content** using Claude to identify key concepts
3. **Checks for duplicates** using semantic search (if qmd enabled)
4. **Creates/updates notes**:
   - Main literature note (`lit-{title}.md`)
   - Links to existing topic notes
   - Optionally creates new topic notes for novel concepts

### Output structure

```
vault/
├── literature/
│   └── lit-some-paper.md      # Main literature note
├── topic-from-paper.md         # New topic note (if created)
└── existing-topic.md           # Updated with link to paper
```

### Examples

```bash
# Ingest a research paper
claude-note ingest ~/Downloads/attention-is-all-you-need.pdf

# Ingest with custom title
claude-note ingest report.docx --title "Q4 Architecture Review"

# Preview without writing
claude-note ingest paper.pdf --dry-run

# Ingest internal doc
claude-note ingest team-process.md --internal
```

### Literature note format

```markdown
---
tags: [literature, machine-learning]
source: attention-is-all-you-need.pdf
ingested: 2024-01-15
---

# Attention Is All You Need

## Summary
[AI-generated summary]

## Key Concepts
- [[transformers]] - Novel architecture introduced
- [[self-attention]] - Core mechanism

## Highlights
- [extracted key points]

## Questions
- [questions that arose during reading]

## Related
- [[neural-networks]]
- [[sequence-models]]
```

---

## Environment Variables

All commands respect these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `CLAUDE_NOTE_VAULT` | Override vault path | From config |
| `CLAUDE_NOTE_MODE` | Override synthesis mode | From config |
| `CLAUDE_NOTE_MODEL` | Override Claude model | From config |
| `CLAUDE_NOTE_DEBUG` | Enable debug logging | `false` |

### Example

```bash
# Use different vault temporarily
CLAUDE_NOTE_VAULT=~/other-vault claude-note status

# Debug mode
CLAUDE_NOTE_DEBUG=1 claude-note drain --verbose
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | Missing dependency |
| 4 | Vault not found |
| 5 | Worker not running (for commands that need it) |
