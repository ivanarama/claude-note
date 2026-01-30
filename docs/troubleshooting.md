# Troubleshooting

Common issues and their solutions.

## Quick Diagnostics

Run this first to identify the problem:

```bash
claude-note status
```

Then check logs:

```bash
# macOS
tail -100 ~/path/to/vault/.claude-note/logs/worker-$(date +%Y-%m-%d).log

# Or all recent logs
tail -f ~/path/to/vault/.claude-note/logs/worker-*.log
```

---

## Installation Issues

### "Python 3.11+ required"

**Problem:** Your Python version is too old.

**Solution:**

```bash
# macOS
brew install python@3.11

# Ubuntu/Debian
sudo apt install python3.11

# Check version
python3.11 --version
```

The installer looks for `python3.13`, `python3.12`, `python3.11`, then `python3`.

### "command not found: claude-note"

**Problem:** `~/.local/bin` not in PATH.

**Solution:**

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export PATH="$PATH:$HOME/.local/bin"
```

Then reload:
```bash
source ~/.bashrc  # or ~/.zshrc
```

### Installer fails with permission error

**Problem:** Can't write to installation directories.

**Solution:**

```bash
# Create directories with correct permissions
mkdir -p ~/.local/bin ~/.local/share ~/.config
chmod 755 ~/.local/bin ~/.local/share ~/.config

# Retry install
./install.sh
```

---

## Worker Issues

### "Worker: not running"

**Problem:** Background service isn't running.

**Solution:**

**macOS:**
```bash
# Check service status
launchctl list | grep claude-note

# Load/reload service
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist

# Check for errors
cat ~/Library/LaunchAgents/com.claude-note.worker.plist
```

**Linux:**
```bash
# Check service status
systemctl --user status claude-note

# Start service
systemctl --user start claude-note

# Enable on boot
systemctl --user enable claude-note

# Check logs
journalctl --user -u claude-note -f
```

### Worker starts but immediately stops

**Problem:** Crash on startup, usually configuration issue.

**Diagnosis:**
```bash
# Run worker manually to see errors
claude-note worker
```

**Common causes:**

1. **Invalid config.toml:**
   ```bash
   cat ~/.config/claude-note/config.toml
   # Check for syntax errors
   python3 -c "import tomllib; print(tomllib.load(open('$HOME/.config/claude-note/config.toml', 'rb')))"
   ```

2. **Vault doesn't exist:**
   ```bash
   # Check vault path in config
   grep vault_root ~/.config/claude-note/config.toml

   # Verify it exists
   ls -la /path/from/config
   ```

3. **Python import error:**
   ```bash
   # Test Python setup
   PYTHONPATH=~/.local/share/claude-note/src python3 -c "from claude_note import cli; print('OK')"
   ```

### Worker running but events not processed

**Problem:** Events queue up but nothing happens.

**Diagnosis:**
```bash
# Check queue
ls -la ~/vault/.claude-note/queue/

# Check if events exist
cat ~/vault/.claude-note/queue/$(date +%Y-%m-%d).jsonl | head

# Check worker logs
tail -50 ~/vault/.claude-note/logs/worker-$(date +%Y-%m-%d).log
```

**Common causes:**

1. **Worker watching wrong vault:**
   ```bash
   # Check config
   grep vault_root ~/.config/claude-note/config.toml
   ```

2. **File permission issues:**
   ```bash
   # Fix permissions
   chmod -R u+rw ~/vault/.claude-note/
   ```

---

## Hook Issues

### Hooks not firing

**Problem:** Claude Code sessions don't trigger any events.

**Diagnosis:**
```bash
# Test hook manually
CLAUDE_SESSION_ID=test-123 echo '{"event":"test"}' | claude-note enqueue

# Check queue
claude-note status
```

**Solutions:**

1. **Check settings.json syntax:**
   ```bash
   cat ~/.claude/settings.json | python3 -m json.tool
   ```

2. **Verify hook format (common mistake):**

   **Wrong:**
   ```json
   "hooks": ["claude-note enqueue"]
   ```

   **Correct:**
   ```json
   "hooks": [{ "type": "command", "command": "claude-note enqueue", "timeout": 5000 }]
   ```

3. **Check Claude Code version:**
   Hooks require Claude Code 1.x or later.

### "Hook timed out"

**Problem:** Hook takes too long, Claude Code kills it.

**Solution:**

1. **Increase timeout in settings.json:**
   ```json
   { "type": "command", "command": "claude-note enqueue", "timeout": 10000 }
   ```

2. **Check for slow disk I/O:**
   ```bash
   # Time the enqueue
   time (echo '{}' | claude-note enqueue)
   ```

---

## Synthesis Issues

### "Claude CLI not found"

**Problem:** Synthesis fails because Claude CLI isn't installed.

**Solution:**

1. **Install Claude CLI:**
   - Download from https://claude.ai/download
   - Or: `brew install claude` (if available)

2. **Check it's in PATH:**
   ```bash
   which claude
   claude --version
   ```

3. **For launchd (macOS), add to plist PATH:**
   ```xml
   <key>EnvironmentVariables</key>
   <dict>
       <key>PATH</key>
       <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
   </dict>
   ```

### Synthesis runs but produces empty/poor results

**Problem:** Claude returns minimal or irrelevant content.

**Solutions:**

1. **Session too short:** Very brief sessions may not have enough content.

2. **Enable qmd for context:**
   ```toml
   [qmd]
   enabled = true
   synth_max_notes = 5
   ```

3. **Try different model:**
   ```toml
   [synthesis]
   model = "claude-opus-4-20250514"  # More capable
   ```

4. **Check transcript exists:**
   ```bash
   ls ~/.claude/projects/
   # Find your project hash, then:
   ls ~/.claude/projects/{hash}/
   ```

### "Rate limited" errors

**Problem:** Too many Claude API calls.

**Solution:**

1. **Drain processes sessions sequentially** - this is normal
2. **Check for stuck synthesis:**
   ```bash
   # Kill stuck process
   ps aux | grep claude
   claude-note clean --force
   ```

---

## Vault Issues

### Notes not updating

**Problem:** Synthesis completes but notes don't change.

**Diagnosis:**
```bash
# Check inbox
cat ~/vault/claude-note-inbox.md | tail -50

# Check session notes (log mode)
ls -la ~/vault/claude-session-*.md
```

**Solutions:**

1. **Check synthesis mode:**
   ```bash
   grep mode ~/.config/claude-note/config.toml
   ```
   - `log`: Only creates session files
   - `inbox`: Only appends to inbox
   - `route`: Updates/creates notes

2. **Routing can't find matches:**
   Enable qmd and rebuild index:
   ```bash
   [qmd]
   enabled = true
   ```
   ```bash
   claude-note index --full
   ```

### "File locked" errors

**Problem:** Note file locked by another process.

**Solution:**

```bash
# Clean stale locks
claude-note clean

# Or manually
rm ~/vault/.claude-note/state/*.lock
```

### Duplicate content in notes

**Problem:** Same content appears multiple times.

**Solution:**

```bash
# Clean duplicates
claude-note clean --force

# Prevent future duplicates - check for multiple workers
ps aux | grep "claude-note worker"
# Should only see ONE worker process
```

---

## QMD Issues

### "qmd not found"

**Problem:** Semantic search disabled.

**Solution:**

```bash
# Install qmd
# See: https://github.com/tobi/qmd

# Verify installation
which qmd
qmd --version

# For launchd, add to PATH in plist:
# Include the directory where qmd is installed (often ~/.bun/bin)
```

### qmd search returns no results

**Problem:** Index might be empty or outdated.

**Solution:**

```bash
# Rebuild qmd index
cd ~/vault
qmd index

# Test search
qmd search "test query"
```

---

## Service-Specific Issues

### macOS: launchd won't load plist

**Diagnosis:**
```bash
# Check plist syntax
plutil ~/Library/LaunchAgents/com.claude-note.worker.plist

# Check for load errors
launchctl list | grep claude-note
```

**Common fixes:**

1. **Invalid XML:** Check plist with `plutil`
2. **Path doesn't exist:** Verify all paths in plist exist
3. **Permission denied:** Check file permissions

### Linux: systemd service fails

**Diagnosis:**
```bash
systemctl --user status claude-note
journalctl --user -u claude-note --no-pager | tail -50
```

**Common fixes:**

1. **User service not enabled:**
   ```bash
   loginctl enable-linger $USER
   ```

2. **ExecStart path wrong:**
   ```bash
   cat ~/.config/systemd/user/claude-note.service
   # Verify ExecStart path exists
   ```

---

## Debug Mode

For detailed debugging:

```bash
# Enable debug logging
export CLAUDE_NOTE_DEBUG=1

# Run command with verbose output
claude-note drain --verbose

# Or run worker in foreground
claude-note worker 2>&1 | tee debug.log
```

---

## Getting Help

If you're still stuck:

1. **Check logs:** `.claude-note/logs/worker-*.log`
2. **Run status:** `claude-note status`
3. **Test manually:** `claude-note drain --dry-run --verbose`
4. **Open an issue:** https://github.com/crimeacs/claude-note/issues

Include:
- OS and version
- Python version (`python3 --version`)
- Error messages from logs
- Output of `claude-note status`
