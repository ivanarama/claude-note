# Configuration Reference

Complete reference for all Claude Note configuration options.

## Config File Location

```
~/.config/claude-note/config.toml
```

This follows the [XDG Base Directory specification](https://specifications.freedesktop.org/basedir-spec/latest/).

## Minimal Config

```toml
vault_root = "/path/to/your/vault"
```

That's it! Everything else has sensible defaults.

---

## All Settings

### Core Settings

#### vault_root (required)

Path to your Obsidian vault or markdown notes directory.

```toml
vault_root = "/Users/you/Documents/notes"
```

**Environment:** `CLAUDE_NOTE_VAULT`

**Notes:**
- Must be an absolute path
- Directory must exist
- Claude Note creates `.claude-note/` subdirectory here

#### inbox_file

Where synthesized knowledge lands (for inbox and route modes).

```toml
inbox_file = "claude-note-inbox.md"  # default
```

**Environment:** `CLAUDE_NOTE_INBOX`

**Notes:**
- Path relative to vault_root
- Created automatically if doesn't exist
- Can be in subdirectory: `"inbox/claude-note.md"`

#### open_questions_file

Path to open questions tracker.

```toml
open_questions_file = "open-questions.md"  # default
```

**Environment:** `CLAUDE_NOTE_OPEN_QUESTIONS`

**Notes:**
- Path relative to vault_root
- Questions from sessions are added here
- See [Open Questions](#open-questions-settings) for more options

---

### Synthesis Settings

```toml
[synthesis]
mode = "route"
model = "claude-sonnet-4-5-20250929"
```

#### mode

Controls how session knowledge is processed and stored.

| Value | Behavior |
|-------|----------|
| `log` | No synthesis. Raw session transcript saved. |
| `inbox` | Full synthesis. Everything appends to inbox file. |
| `route` | Full synthesis + intelligent routing to notes. |

```toml
[synthesis]
mode = "route"  # default
```

**Environment:** `CLAUDE_NOTE_MODE`

**See also:** [Synthesis Modes](synthesis-modes.md) for detailed explanation.

#### model

Claude model used for synthesis.

```toml
[synthesis]
model = "claude-sonnet-4-5-20250929"  # default
```

**Environment:** `CLAUDE_NOTE_MODEL`

**Available models:**
- `claude-sonnet-4-5-20250929` - Fast, good quality (default)
- `claude-opus-4-20250514` - Slower, highest quality
- `claude-haiku-3-5-20250929` - Fastest, lower quality

**When to change:**
- Use Opus for complex technical sessions
- Use Haiku if API costs are a concern

#### max_transcript_tokens

Maximum transcript size sent for synthesis.

```toml
[synthesis]
max_transcript_tokens = 50000  # default
```

**Notes:**
- Longer sessions are truncated (most recent content kept)
- Increase if sessions are very long
- Higher values = more API cost

#### session_timeout_minutes

How long to wait for activity before considering a session ended.

```toml
[synthesis]
session_timeout_minutes = 30  # default
```

**Notes:**
- After this period of no events, session is auto-closed
- Synthesis triggers on timeout
- Lower for faster synthesis, higher if you take breaks

---

### QMD Settings

[QMD](https://github.com/tobi/qmd) integration for semantic search.

```toml
[qmd]
enabled = false
synth_max_notes = 5
route_threshold = 0.7
ingest_dupe_threshold = 0.85
```

#### enabled

Whether to use qmd for semantic search.

```toml
[qmd]
enabled = true
```

**Environment:** `CLAUDE_NOTE_QMD_ENABLED`

**Requirements:**
- qmd must be installed and in PATH
- Vault must be indexed (`qmd index`)

#### synth_max_notes

How many related notes to include as context during synthesis.

```toml
[qmd]
synth_max_notes = 5  # default
```

**Trade-offs:**
- Higher = better context, more API cost
- Lower = faster, cheaper, possibly missing context
- Recommended: 3-7

#### route_threshold

Minimum similarity score (0.0-1.0) for routing in `route` mode.

```toml
[qmd]
route_threshold = 0.7  # default
```

**Trade-offs:**
- Higher = stricter matching, more items go to inbox
- Lower = more aggressive routing, risk of mismatches
- Start at 0.7, adjust based on inbox review

#### ingest_dupe_threshold

Minimum score to consider documents as duplicates during ingestion.

```toml
[qmd]
ingest_dupe_threshold = 0.85  # default
```

**See also:** [QMD Integration](qmd-integration.md)

---

### Open Questions Settings

```toml
[open_questions]
enabled = true
auto_close = true
```

#### enabled

Track questions that arise during sessions.

```toml
[open_questions]
enabled = true  # default
```

**What it does:**
- Detects questions in user messages
- Adds to open_questions_file
- Marks as answered when synthesis finds answers

#### auto_close

Automatically mark questions as answered when synthesis finds answers.

```toml
[open_questions]
auto_close = true  # default
```

**When to disable:**
- You want manual control over question status
- Auto-detection isn't accurate for your domain

---

### Routing Settings

Advanced settings for `route` mode.

```toml
[routing]
create_new_notes = true
max_updates_per_note = 3
managed_section = "## From Sessions"
```

#### create_new_notes

Allow automatic creation of new topic notes.

```toml
[routing]
create_new_notes = true  # default
```

**When to disable:**
- You prefer inbox-only workflow
- Vault structure is strictly controlled

#### max_updates_per_note

Maximum items to append to a single note per session.

```toml
[routing]
max_updates_per_note = 3  # default
```

**Why limit:**
- Prevents flooding a note with too much content
- Excess goes to inbox for review

#### managed_section

Heading where session content is appended.

```toml
[routing]
managed_section = "## From Sessions"  # default
```

**Notes:**
- Created automatically if doesn't exist
- Uses managed blocks (won't overwrite manual edits)

---

### Worker Settings

Background worker configuration.

```toml
[worker]
poll_interval_seconds = 5
max_retries = 3
```

#### poll_interval_seconds

How often worker checks for new events.

```toml
[worker]
poll_interval_seconds = 5  # default
```

**Trade-offs:**
- Lower = faster response, more CPU
- Higher = slower response, less CPU

#### max_retries

Retry count for failed synthesis.

```toml
[worker]
max_retries = 3  # default
```

---

### Logging Settings

```toml
[logging]
level = "INFO"
max_log_days = 7
```

#### level

Log verbosity.

```toml
[logging]
level = "INFO"  # default
```

**Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`

**Environment:** `CLAUDE_NOTE_LOG_LEVEL`

#### max_log_days

Days to keep log files.

```toml
[logging]
max_log_days = 7  # default
```

---

## Environment Variables

All settings can be overridden with environment variables.

| Variable | Config Key | Example |
|----------|------------|---------|
| `CLAUDE_NOTE_VAULT` | vault_root | `/path/to/vault` |
| `CLAUDE_NOTE_INBOX` | inbox_file | `my-inbox.md` |
| `CLAUDE_NOTE_OPEN_QUESTIONS` | open_questions_file | `questions.md` |
| `CLAUDE_NOTE_MODE` | synthesis.mode | `inbox` |
| `CLAUDE_NOTE_MODEL` | synthesis.model | `claude-opus-4-20250514` |
| `CLAUDE_NOTE_QMD_ENABLED` | qmd.enabled | `true` |
| `CLAUDE_NOTE_LOG_LEVEL` | logging.level | `DEBUG` |
| `CLAUDE_NOTE_DEBUG` | (enables all debug) | `1` |

**Precedence:** Environment variables > Config file > Defaults

---

## Complete Example

```toml
# =============================================================================
# Claude Note Configuration
# =============================================================================

# Required: Path to your vault
vault_root = "/Users/you/Documents/notes"

# Where synthesized knowledge lands
inbox_file = "claude-note-inbox.md"

# Open questions tracker
open_questions_file = "open-questions.md"

# -----------------------------------------------------------------------------
# Synthesis
# -----------------------------------------------------------------------------
[synthesis]
# Mode: log | inbox | route
mode = "route"

# Claude model for synthesis
model = "claude-sonnet-4-5-20250929"

# Max transcript tokens (longer sessions truncated)
max_transcript_tokens = 50000

# Session timeout (minutes of inactivity)
session_timeout_minutes = 30

# -----------------------------------------------------------------------------
# QMD Semantic Search
# -----------------------------------------------------------------------------
[qmd]
# Enable qmd integration (requires qmd installed)
enabled = true

# Related notes to include as context
synth_max_notes = 5

# Routing similarity threshold (0.0-1.0)
route_threshold = 0.7

# Duplicate detection threshold for ingestion
ingest_dupe_threshold = 0.85

# -----------------------------------------------------------------------------
# Open Questions
# -----------------------------------------------------------------------------
[open_questions]
# Track questions from sessions
enabled = true

# Auto-mark as answered when found
auto_close = true

# -----------------------------------------------------------------------------
# Routing (route mode only)
# -----------------------------------------------------------------------------
[routing]
# Create new topic notes automatically
create_new_notes = true

# Max items to append to one note per session
max_updates_per_note = 3

# Section heading for session content
managed_section = "## From Sessions"

# -----------------------------------------------------------------------------
# Worker
# -----------------------------------------------------------------------------
[worker]
# Queue poll interval (seconds)
poll_interval_seconds = 5

# Retry count for failed synthesis
max_retries = 3

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
[logging]
# Level: DEBUG | INFO | WARNING | ERROR
level = "INFO"

# Days to keep log files
max_log_days = 7
```

---

## Config Validation

Check your configuration:

```bash
claude-note status
```

This validates:
- Config file syntax
- Required settings present
- Vault path exists
- Dependencies available

For verbose validation:

```bash
CLAUDE_NOTE_DEBUG=1 claude-note status
```

---

## Multiple Vaults

### Using environment variables

```bash
# In terminal for project A
export CLAUDE_NOTE_VAULT="/path/to/vault-a"
claude-note status

# In terminal for project B
export CLAUDE_NOTE_VAULT="/path/to/vault-b"
claude-note status
```

### Using direnv

Create `.envrc` in each project:

```bash
# /project-a/.envrc
export CLAUDE_NOTE_VAULT="/path/to/vault-a"

# /project-b/.envrc
export CLAUDE_NOTE_VAULT="/path/to/vault-b"
```

Then `direnv allow` in each directory.

### Multiple worker services

See [Service Setup](service-setup.md#multiple-vaults) for running separate workers.
