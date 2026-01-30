# Getting Started with Claude Note

This guide walks you through installing and configuring Claude Note from scratch.

## What is Claude Note?

Claude Note is a background service that automatically captures knowledge from your Claude Code sessions and writes it to your Obsidian vault (or any markdown-based notes system).

When you work with Claude Code, valuable insights emerge: debugging techniques, architectural decisions, code patterns, and open questions. Without Claude Note, these insights vanish when you close your terminal. With Claude Note, they become permanent, searchable notes.

## Prerequisites

### Required

| Dependency | Version | Why |
|------------|---------|-----|
| Python | 3.11+ | Uses built-in `tomllib` for config parsing |
| git | any | Clones the repository during installation |

### Optional (but recommended)

| Dependency | Purpose |
|------------|---------|
| [Claude CLI](https://claude.ai/download) | Required for knowledge synthesis. Without it, only session logging works. |
| [qmd](https://github.com/tobi/qmd) | Semantic search for better synthesis context. Helps Claude understand your existing notes. |
| pandoc | Required for document ingestion (PDF/DOCX support) |

## Installation

### One-Command Install

```bash
git clone https://github.com/crimeacs/claude-note.git
cd claude-note
./install.sh
```

### What the Installer Does

1. **Checks dependencies** - Verifies Python 3.11+, warns about missing optional tools
2. **Prompts for vault path** - Where your Obsidian vault or notes directory lives
3. **Installs source code** - Copies to `~/.local/share/claude-note/`
4. **Creates CLI shim** - Adds `claude-note` command to `~/.local/bin/`
5. **Writes configuration** - Creates `~/.config/claude-note/config.toml`
6. **Initializes vault structure** - Creates `.claude-note/` directory in your vault
7. **Sets up background service** - launchd on macOS, systemd on Linux
8. **Prints hook instructions** - Shows how to connect Claude Code

### Manual Installation

If you prefer manual control:

```bash
# 1. Clone repository
git clone https://github.com/crimeacs/claude-note.git ~/.local/share/claude-note

# 2. Create CLI shim
mkdir -p ~/.local/bin
cat > ~/.local/bin/claude-note << 'EOF'
#!/usr/bin/env bash
INSTALL_DIR="${HOME}/.local/share/claude-note"
export PYTHONPATH="${INSTALL_DIR}/src"
if [ -t 0 ]; then
    exec python3 -m claude_note.cli "$@"
else
    exec python3 -m claude_note.cli "$@" <<< "$(cat)"
fi
EOF
chmod +x ~/.local/bin/claude-note

# 3. Add to PATH (add to ~/.bashrc or ~/.zshrc)
export PATH="$PATH:$HOME/.local/bin"

# 4. Create config
mkdir -p ~/.config/claude-note
cat > ~/.config/claude-note/config.toml << EOF
vault_root = "/path/to/your/vault"

[synthesis]
mode = "route"
model = "claude-sonnet-4-5-20250929"

[qmd]
enabled = false
EOF

# 5. Initialize vault
mkdir -p /path/to/your/vault/.claude-note/{queue,state,logs}

# 6. Set up service (see docs/service-setup.md)
```

## Connecting to Claude Code

Claude Note receives events from Claude Code through hooks. Add this to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "claude-note enqueue", "timeout": 5000 }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "claude-note enqueue", "timeout": 5000 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "claude-note enqueue", "timeout": 5000 }
        ]
      }
    ]
  }
}
```

### What Each Hook Does

| Hook | When it fires | What Claude Note does |
|------|---------------|----------------------|
| `PostToolUse` | After any tool (file read, edit, bash) | Updates session state, tracks activity |
| `UserPromptSubmit` | When you send a message | Detects questions for open questions tracker |
| `Stop` | When session ends | Triggers synthesis and note creation |

## Verifying Installation

### 1. Check CLI works

```bash
claude-note status
```

You should see:
```
Worker: running (PID 12345)
Queue: 0 pending events
Sessions: 0 active, 0 completed today
```

### 2. Check worker is running

**macOS:**
```bash
launchctl list | grep claude-note
```

**Linux:**
```bash
systemctl --user status claude-note
```

### 3. Test the pipeline

```bash
# Manually trigger an event
echo '{"event":"test"}' | claude-note enqueue

# Check it was queued
claude-note status
```

## First Session

1. Start a Claude Code session in any project
2. Do some work - ask questions, edit files
3. Exit the session (Ctrl+C or type "exit")
4. Check your vault:
   - `claude-note-inbox.md` should have new content (if using inbox/route mode)
   - Or `claude-session-*.md` files (if using log mode)

## Next Steps

- [Configuration Reference](configuration.md) - Customize behavior
- [Synthesis Modes](synthesis-modes.md) - Understand log/inbox/route
- [Commands Reference](commands.md) - All CLI commands
- [Troubleshooting](troubleshooting.md) - Common issues

## Uninstalling

```bash
cd ~/.local/share/claude-note
./uninstall.sh
```

This removes the service, CLI, and source code. Your vault data is preserved.
