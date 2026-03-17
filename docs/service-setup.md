# Service Setup

Claude Note runs as a background service that processes session events. This guide covers manual service configuration for both macOS and Linux.

## Overview

The installer automatically sets up the service, but you may need to modify it for:
- Custom environment variables
- Different Python versions
- PATH modifications (for qmd, Claude CLI)
- Debugging issues

---

## macOS (launchd)

### Plist Location

```
~/Library/LaunchAgents/com.claude-note.worker.plist
```

### Full Plist Template

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Service identifier -->
    <key>Label</key>
    <string>com.claude-note.worker</string>

    <!-- Command to run -->
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOU/.local/bin/claude-note</string>
        <string>worker</string>
    </array>

    <!-- Start on login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Restart if it crashes -->
    <key>KeepAlive</key>
    <true/>

    <!-- Log files -->
    <key>StandardOutPath</key>
    <string>/Users/YOU/vault/.claude-note/logs/launchd-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOU/vault/.claude-note/logs/launchd-stderr.log</string>

    <!-- Environment variables -->
    <key>EnvironmentVariables</key>
    <dict>
        <!-- Required: Python can find claude_note modules -->
        <key>PYTHONPATH</key>
        <string>/Users/YOU/.local/share/claude-note/src</string>

        <!-- Required: Find claude-note, claude, qmd binaries -->
        <key>PATH</key>
        <string>/Users/YOU/.local/bin:/Users/YOU/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>

        <!-- Optional: Override config values -->
        <!-- <key>CLAUDE_NOTE_VAULT</key> -->
        <!-- <string>/path/to/alternate/vault</string> -->
    </dict>

    <!-- Working directory -->
    <key>WorkingDirectory</key>
    <string>/Users/YOU</string>

    <!-- Resource limits (optional) -->
    <key>SoftResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>1024</integer>
    </dict>
</dict>
</plist>
```

### Commands

```bash
# Load service (start)
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist

# Unload service (stop)
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist

# Check if running
launchctl list | grep claude-note

# View service info
launchctl print gui/$(id -u)/com.claude-note.worker

# Force restart
launchctl kickstart -k gui/$(id -u)/com.claude-note.worker
```

### Viewing Logs

```bash
# launchd stdout/stderr
tail -f ~/vault/.claude-note/logs/launchd-stdout.log
tail -f ~/vault/.claude-note/logs/launchd-stderr.log

# Worker application logs
tail -f ~/vault/.claude-note/logs/worker-$(date +%Y-%m-%d).log

# System log for launchd errors
log show --predicate 'subsystem == "com.apple.launchd"' --last 5m | grep claude-note
```

### Common Issues

**Service won't start:**
```bash
# Check plist syntax
plutil ~/Library/LaunchAgents/com.claude-note.worker.plist

# Check all paths exist
cat ~/Library/LaunchAgents/com.claude-note.worker.plist | grep string | grep Users
```

**"Operation not permitted":**
```bash
# Grant Terminal full disk access
# System Preferences → Security & Privacy → Privacy → Full Disk Access
# Add Terminal.app
```

**Service starts but immediately exits:**
```bash
# Run manually to see errors
~/.local/bin/claude-note worker

# Check stderr log
cat ~/vault/.claude-note/logs/launchd-stderr.log
```

---

## Linux (systemd)

### Unit File Location

```
~/.config/systemd/user/claude-note.service
```

### Full Unit Template

```ini
[Unit]
Description=Claude Note Background Worker
Documentation=https://github.com/ivanarama/claude-note
After=network.target

[Service]
Type=simple

# Command to run
ExecStart=/home/YOU/.local/bin/claude-note worker

# Restart policy
Restart=always
RestartSec=5

# Environment
Environment=PYTHONPATH=/home/YOU/.local/share/claude-note/src
Environment=PATH=/home/YOU/.local/bin:/home/YOU/.bun/bin:/usr/local/bin:/usr/bin:/bin

# Optional: Override config
# Environment=CLAUDE_NOTE_VAULT=/path/to/vault

# Working directory
WorkingDirectory=/home/YOU

# Logging (goes to journald by default)
# StandardOutput=append:/home/YOU/vault/.claude-note/logs/worker.log
# StandardError=append:/home/YOU/vault/.claude-note/logs/worker-error.log

[Install]
WantedBy=default.target
```

### Commands

```bash
# Reload unit files after editing
systemctl --user daemon-reload

# Start service
systemctl --user start claude-note

# Stop service
systemctl --user stop claude-note

# Restart service
systemctl --user restart claude-note

# Enable on boot
systemctl --user enable claude-note

# Check status
systemctl --user status claude-note

# View logs
journalctl --user -u claude-note -f
```

### Enabling User Services at Boot

By default, user services only run when logged in. To run even when logged out:

```bash
# Enable lingering for your user
sudo loginctl enable-linger $USER

# Verify
loginctl show-user $USER | grep Linger
```

### Common Issues

**"Failed to connect to bus":**
```bash
# Ensure dbus session is running
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user status
```

**Service fails with exit code:**
```bash
# Check detailed status
systemctl --user status claude-note -l

# View recent logs
journalctl --user -u claude-note --no-pager | tail -50

# Run manually
~/.local/bin/claude-note worker
```

---

## Environment Variables

Both service systems need these environment variables:

### Required

| Variable | Purpose | Example |
|----------|---------|---------|
| `PYTHONPATH` | Find claude_note modules | `/home/you/.local/share/claude-note/src` |
| `PATH` | Find binaries (claude-note, claude, qmd) | `/home/you/.local/bin:/opt/homebrew/bin:...` |

### Optional

| Variable | Purpose | Example |
|----------|---------|---------|
| `CLAUDE_NOTE_VAULT` | Override vault path | `/home/you/work-vault` |
| `CLAUDE_NOTE_MODE` | Override synthesis mode | `inbox` |
| `CLAUDE_NOTE_MODEL` | Override Claude model | `claude-opus-4-20250514` |
| `CLAUDE_NOTE_DEBUG` | Enable debug logging | `1` |

---

## Multiple Vaults

To use different vaults for different projects:

### Option 1: Per-project environment

Set `CLAUDE_NOTE_VAULT` per terminal session:

```bash
# In project A
export CLAUDE_NOTE_VAULT=~/vault-a
claude-note status

# In project B
export CLAUDE_NOTE_VAULT=~/vault-b
```

### Option 2: Multiple services

Create separate service files:

**macOS:**
```bash
# Copy and modify plist
cp ~/Library/LaunchAgents/com.claude-note.worker.plist \
   ~/Library/LaunchAgents/com.claude-note.work.plist

# Edit to use different vault
# Change Label to com.claude-note.work
# Add CLAUDE_NOTE_VAULT environment variable
```

**Linux:**
```bash
# Create new unit
cp ~/.config/systemd/user/claude-note.service \
   ~/.config/systemd/user/claude-note-work.service

# Edit Environment line
# systemctl --user daemon-reload
# systemctl --user enable claude-note-work
```

---

## Debugging

### Run worker in foreground

```bash
# Stop service first
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist  # macOS
# or
systemctl --user stop claude-note  # Linux

# Run manually with debug
CLAUDE_NOTE_DEBUG=1 ~/.local/bin/claude-note worker

# When done, restart service
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist  # macOS
# or
systemctl --user start claude-note  # Linux
```

### Check service is actually running

```bash
# Find the process
ps aux | grep "claude-note worker"

# Should show one process like:
# you  12345  0.1  0.2  python3 -m claude_note.cli worker
```

### Test the full pipeline

```bash
# 1. Manually enqueue an event
CLAUDE_SESSION_ID=test-$(date +%s) echo '{"event":"test"}' | claude-note enqueue

# 2. Check it was queued
claude-note status

# 3. Watch logs
tail -f ~/vault/.claude-note/logs/worker-*.log

# 4. Process should pick it up within ~5 seconds
```

---

## Uninstalling Service

### macOS

```bash
# Stop and remove
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist
rm ~/Library/LaunchAgents/com.claude-note.worker.plist
```

### Linux

```bash
# Stop, disable, remove
systemctl --user stop claude-note
systemctl --user disable claude-note
rm ~/.config/systemd/user/claude-note.service
systemctl --user daemon-reload
```
