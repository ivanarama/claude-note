# Claude Note

Automatic knowledge extraction from Claude Code sessions into your Obsidian vault.

Claude Note runs as a background service, watching your Claude Code sessions and synthesizing key learnings, decisions, and questions into structured notes.

**✨ Now with Windows support!** Works on macOS, Linux, and Windows 10/11. Current version: **v1.5.0**.

## Features

- **Session Logging**: Automatically captures Claude Code sessions as markdown notes
- **Knowledge Synthesis**: Uses Claude to extract key concepts, code patterns, and learnings
- **Smart Routing**: Routes synthesized knowledge to your inbox, specific notes, or creates new ones
- **Open Questions Tracking**: Detects and tracks questions that come up during sessions
- **Vault Integration**: Understands your existing notes for better context
- **Multilingual**: Synthesis prompts and UI in English and Russian
- **Prompts Archive**: Saves all user prompts to a dedicated Obsidian note
- **Auto-Memory**: After each session, updates `MEMORY.md` in your Claude Code project directory with durable knowledge (decisions, patterns, gotchas, how-tos)
- **Web UI**: Browser dashboard showing session list, processing stats, and live worker status (`http://127.0.0.1:8080`)

## Requirements

- Python 3.11+ (for built-in `tomllib`)
- [Claude CLI](https://github.com/anthropics/claude-cli) (for knowledge synthesis)
- An Obsidian vault (or any markdown-based notes system)
- **Platforms**: macOS, Linux, **Windows** (10/11)

## Quick Start

### macOS / Linux

```bash
# Clone and install
git clone https://github.com/ivanarama/claude-note.git
cd claude-note
./install.sh
```

### Windows

**Вариант 1 — готовый EXE (рекомендуется)**

Скачайте `cn.exe` из [Releases](https://github.com/ivanarama/claude-note/releases), положите куда удобно и запустите. При двойном клике появляется иконка в трее — worker и Web UI стартуют автоматически.

```powershell
# Создать конфиг
mkdir $env:USERPROFILE\.config\claude-note
echo 'vault_root = "C:\\path\\to\\your\\vault"' > $env:USERPROFILE\.config\claude-note\config.toml

# Запустить (трей + автозапуск worker и Web UI)
.\cn.exe

# Или отдельные команды
.\cn.exe status
.\cn.exe worker --foreground
.\cn.exe web
```

Хуки для Claude Code (укажите полный путь до cn.exe):
```json
{
  "hooks": {
    "PostToolUse":      [{"type": "command", "command": "C:\\tools\\cn.exe enqueue", "timeout": 5000}],
    "UserPromptSubmit": [{"type": "command", "command": "C:\\tools\\cn.exe enqueue", "timeout": 5000}],
    "Stop":             [{"type": "command", "command": "C:\\tools\\cn.exe enqueue", "timeout": 5000}]
  }
}
```

**Вариант 2 — из исходников**

```powershell
git clone https://github.com/ivanarama/claude-note.git
cd claude-note
pip install -e .

# Создать конфиг
mkdir $env:USERPROFILE\.config\claude-note
echo 'vault_root = "C:\\path\\to\\your\\vault"' > $env:USERPROFILE\.config\claude-note\config.toml

# Запустить
python -m claude_note worker --foreground
```

**Собрать EXE самостоятельно**

```powershell
# Из корня репозитория
.\build.ps1
# Готовый файл: dist\cn.exe
```

The installer (macOS/Linux) will:
1. Check dependencies
2. Ask for your vault path
3. Set up the background service
4. Print instructions for Claude Code hook configuration

## How It Works

1. **Hook Integration**: Claude Code hooks notify claude-note when sessions start/stop
2. **Queue Processing**: Events are queued and processed by the background worker
3. **Synthesis**: When a session ends, Claude analyzes the transcript
4. **Note Routing**: Extracted knowledge is written to your vault

```
Claude Code Session
        │
        ▼
   [Hooks fire]
        │
        ▼
  ┌─────────────┐
  │ Event Queue │
  └─────────────┘
        │
        ▼
  ┌─────────────┐      ┌─────────────┐
  │   Worker    │─────▶│  Synthesize │
  └─────────────┘      └─────────────┘
                              │
                              ▼
                       ┌─────────────┐
                       │    Vault    │
                       │  - inbox.md │
                       │  - notes/   │
                       └─────────────┘
```

## Commands

```bash
claude-note status                      # Check worker and queue status
claude-note update                      # Check for and apply updates
claude-note drain                       # Process all pending sessions now
claude-note clean                       # Cleanup duplicate sessions, old locks
claude-note index                       # Rebuild vault index for synthesis context
claude-note resynth <id>                # Re-synthesize a session (also updates memory)
claude-note resynth <id> --memory-only  # Only update memory, skip note ops
claude-note ingest <file>               # Ingest PDF/DOCX into literature notes
claude-note prompts                     # Show prompts archive stats
claude-note backfill-prompts            # Backfill prompts archive from past sessions
claude-note web                         # Start Web UI on http://127.0.0.1:8080
claude-note tray                        # Start system tray app (Windows)
```

## Configuration

Config file: `~/.config/claude-note/config.toml`

```toml
vault_root = "/path/to/your/vault"

# Optional settings
open_questions_file = "open-questions.md"  # relative to vault

[synthesis]
mode = "route"           # log | inbox | route
model = "claude-sonnet-4-5-20250929"

[language]
code = "en"              # en | ru

[prompts_archive]
enabled = true           # Save user prompts to a dedicated note
file = "prompts-archive.md"
include_plan_summary = true

[memory]
enabled = true           # Update MEMORY.md in Claude Code project dir after each session
# model = "claude-z:glm-4.7"  # Override model for memory curation (default: uses synthesis models)
max_lines = 190          # Budget for MEMORY.md
stale_days = 90          # Remove entries older than N days when over budget
dedup_threshold = 0.6    # Similarity threshold for deduplication (0.0–1.0)

[qmd]
enabled = false          # Enable qmd semantic search for context
synth_max_notes = 5
```

All settings can be overridden with environment variables:
- `CLAUDE_NOTE_VAULT` - vault path
- `CLAUDE_NOTE_MODE` - synthesis mode
- `CLAUDE_NOTE_MODEL` - Claude model for synthesis

See [docs/configuration.md](docs/configuration.md) for full reference.

## Claude Code Hook Setup

Add to your Claude Code settings (`~/.claude/settings.json`):

**macOS / Linux:**
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

**Windows:**
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "hooks": [
          { "type": "command", "command": "python -m claude_note enqueue", "timeout": 5000 }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          { "type": "command", "command": "python -m claude_note enqueue", "timeout": 5000 }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "python -m claude_note enqueue", "timeout": 5000 }
        ]
      }
    ]
  }
}
```

See [docs/hook-setup.md](docs/hook-setup.md) for detailed instructions.

## Service Management

### macOS (launchd)

```bash
# Status
launchctl list | grep claude-note

# Stop
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist

# Start
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist

# Logs
tail -f /path/to/vault/.claude-note/logs/worker-*.log
```

### Linux (systemd)

```bash
# Status
systemctl --user status claude-note

# Stop/Start
systemctl --user stop claude-note
systemctl --user start claude-note

# Logs
journalctl --user -u claude-note -f
```

### Windows (cn.exe + трей)

Самый простой способ — запустить `cn.exe` и управлять через иконку в трее:

- **Правый клик** → Start/Stop Worker, Start/Stop Web UI, Открыть Web UI
- **Иконка зелёная** — всё работает; **серая** — остановлено
- Web UI открывается в браузере на `http://127.0.0.1:8080` — показывает список сессий, статистику и статус воркера в реальном времени

```powershell
# Статус
.\cn.exe status

# Форсированная обработка очереди
.\cn.exe drain

# Логи
Get-Content "$env:USERPROFILE\vault\.claude-note\logs\worker-*.log" -Tail 20 -Wait
```

**Автозапуск вместе с Windows** — добавьте ярлык на `cn.exe` в папку автозагрузки:
```powershell
$startup = [Environment]::GetFolderPath("Startup")
Copy-Item "C:\tools\cn.exe" "$startup\cn.lnk"  # или создайте ярлык вручную
```

## Vault Structure

Claude Note creates/uses these files in your vault:

```
your-vault/
├── .claude-note/           # Internal data (gitignore this)
│   ├── queue/              # Event queue
│   ├── state/              # Session state
│   ├── logs/               # Worker logs
│   └── vault_index.json    # Note index for context
├── claude-note-inbox.md    # Synthesized knowledge lands here
├── open-questions.md       # Questions tracker
└── claude-session-*.md     # Session logs (optional)
```

## Auto-Memory

After each session ends, claude-note calls Claude to curate project-specific knowledge into `MEMORY.md` inside your Claude Code project directory:

```
~/.claude/projects/{project}/memory/MEMORY.md
```

This file is automatically loaded into future Claude Code sessions as context. It contains:

```markdown
## Decisions
- Use stdin instead of -p flag for Claude CLI on Windows (2026-03-27)

## Patterns
- Always resolve .bat/.cmd paths with shutil.which on Windows (2026-03-27)

## Gotchas
- archive_path must be defined before _is_duplicate_entry call (2026-03-27)

## How-tos
- Backfill missed prompts: python -m claude_note backfill-prompts --since YYYY-MM-DD (2026-03-27)
```

Memory entries are automatically deduplicated and pruned when they exceed the line budget.

### Backfilling missed sessions

If sessions were missed (e.g. due to a bug), restore them without re-running synthesis:

```bash
# Dry-run first
python -m claude_note backfill-prompts --since 2026-03-25 --dry-run

# Apply
python -m claude_note backfill-prompts --since 2026-03-25
```

To also update memory from past sessions (uses Claude):

```bash
python -m claude_note resynth <session-id> --memory-only
```

### Verifying it works

After closing a Claude Code session:

1. **Worker log** — look for synthesis and memory lines:
   ```
   [INFO] Synthesizing session abc12345...
   [INFO] Memory: +2/-0 entries
   [DEBUG] Archived 5 items (prompts, plan, summary)
   ```

2. **Memory file** — check entries were added:
   ```bash
   # Windows
   type %USERPROFILE%\.claude\projects\{project-dir}\memory\MEMORY.md
   ```

3. **Prompts archive** — check last entry date:
   ```bash
   python -m claude_note prompts
   ```

## Uninstall

```bash
./uninstall.sh
```

This removes the service, CLI, and source files. Your vault data is preserved.

## Optional: QMD Integration

If you have [qmd](https://github.com/tobi/qmd) installed for semantic search, enable it in config:

```toml
[qmd]
enabled = true
synth_max_notes = 5  # Include top N relevant notes as context
```

This improves synthesis quality by providing relevant vault context.

## Testing

```bash
python -m pytest tests/ -v
```

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Step-by-step installation walkthrough |
| [Configuration](docs/configuration.md) | Complete config reference |
| [Commands](docs/commands.md) | All CLI commands explained |
| [Synthesis Modes](docs/synthesis-modes.md) | log vs inbox vs route |
| [Hook Setup](docs/hook-setup.md) | Claude Code integration |
| [Service Setup](docs/service-setup.md) | launchd/systemd configuration |
| [QMD Integration](docs/qmd-integration.md) | Semantic search setup |
| [Document Ingestion](docs/document-ingestion.md) | Importing papers and docs |
| [Architecture](docs/architecture.md) | How it works internally |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and fixes |

## License

MIT


[**Этот репозиторий использован в статье**](https://infostart.ru/1c/articles/2659511).
![alt text](https://infostart.ru/bitrix/templates/sandbox_empty/assets/tpl/abo/img/logo.svg)
