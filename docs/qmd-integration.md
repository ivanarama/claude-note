# QMD Integration

Claude Note integrates with [qmd](https://github.com/tobi/qmd) for semantic search, dramatically improving synthesis quality and note routing.

## What is QMD?

QMD (Quick Markdown Search) is a semantic search tool for markdown files. It creates embeddings of your notes and enables similarity search.

**Without qmd:** Claude Note uses basic keyword matching to find related notes.

**With qmd:** Claude Note understands the *meaning* of your notes and finds conceptually related content even without keyword overlap.

## Why Use QMD?

### Better Synthesis Context

When synthesizing a session about "JWT authentication", qmd might find:
- `security-best-practices.md` (mentions "token validation")
- `api-design.md` (discusses "stateless auth")
- `session-management.md` (related concept)

This context helps Claude produce more relevant, connected insights.

### Smarter Note Routing

In `route` mode, qmd enables semantic matching:

| Without qmd | With qmd |
|-------------|----------|
| Exact title/tag matches only | Conceptual similarity |
| "JWT" only matches "jwt.md" | "JWT" matches "auth.md", "security.md", "api-tokens.md" |
| Many items go to inbox | More items routed correctly |

### Duplicate Detection

For document ingestion, qmd detects if you've already captured similar content:

```
Ingesting: "attention-paper.pdf"
Found similar: "transformers.md" (92% match)
Merging instead of creating duplicate...
```

## Installation

### Using bun (recommended)

```bash
# Install bun if needed
curl -fsSL https://bun.sh/install | bash

# Install qmd
bun install -g qmd
```

### Using npm

```bash
npm install -g qmd
```

### Verify Installation

```bash
qmd --version
which qmd
```

## Configuration

### Enable in Claude Note

Edit `~/.config/claude-note/config.toml`:

```toml
[qmd]
enabled = true
synth_max_notes = 5    # How many related notes to include as context
```

### Index Your Vault

```bash
cd ~/path/to/vault
qmd index
```

This creates embeddings for all markdown files. Run periodically or after major vault changes.

### launchd/systemd PATH

The background worker needs to find qmd. Add to your service config:

**macOS (plist):**
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/Users/you/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
</dict>
```

**Linux (systemd):**
```ini
[Service]
Environment=PATH=/home/you/.bun/bin:/usr/local/bin:/usr/bin:/bin
```

Then reload the service:
```bash
# macOS
launchctl unload ~/Library/LaunchAgents/com.claude-note.worker.plist
launchctl load ~/Library/LaunchAgents/com.claude-note.worker.plist

# Linux
systemctl --user daemon-reload
systemctl --user restart claude-note
```

## How It Works

### During Synthesis

```
Session ends
    │
    ▼
Extract key topics from transcript
    │
    ▼
qmd search for each topic
    │
    ▼
Top N related notes retrieved
    │
    ▼
Notes included in synthesis prompt
    │
    ▼
Claude has context about your existing knowledge
```

### During Routing

```
For each extracted insight:
    │
    ▼
qmd search for similar content
    │
    ▼
Score matches (0.0 - 1.0)
    │
    ├── Score > 0.8: Strong match → Update that note
    ├── Score 0.5-0.8: Possible match → Check title/tags
    └── Score < 0.5: No match → Create new or inbox
```

### Search Examples

```python
# What Claude Note does internally:

# Find notes related to a session about debugging
results = qmd.search("debugging async race condition", limit=5)
# Returns: ["concurrency.md", "debugging-tips.md", "async-patterns.md"]

# Find potential duplicate before creating note
results = qmd.search("JWT token expiration handling", limit=3)
# Returns: [{"file": "auth.md", "score": 0.87}]
# High score → update auth.md instead of creating new note
```

## Configuration Options

```toml
[qmd]
# Enable/disable qmd integration
enabled = true

# Max notes to include as synthesis context
# More = better context but slower/more expensive
synth_max_notes = 5

# Minimum similarity score for routing (0.0-1.0)
# Higher = stricter matching, more items to inbox
# Lower = more aggressive routing, risk of mismatches
route_threshold = 0.7

# Minimum score for duplicate detection during ingest
ingest_dupe_threshold = 0.85
```

## Manual QMD Usage

### Indexing

```bash
cd ~/vault

# Index all markdown files
qmd index

# Index specific directory
qmd index ./projects/

# Reindex everything
qmd index --force
```

### Searching

```bash
# Basic search
qmd search "authentication patterns"

# Limit results
qmd search "react hooks" --limit 10

# JSON output (what Claude Note uses)
qmd search "api design" --json
```

### Checking Index

```bash
# See index status
qmd status

# List indexed files
qmd list
```

## Troubleshooting

### "qmd not found" in worker

The background service can't find qmd.

**Solution:** Add qmd's directory to PATH in service config (see Configuration section).

### Search returns no results

Index might be empty or stale.

```bash
# Check index
qmd status

# Rebuild index
cd ~/vault
qmd index --force
```

### Poor quality matches

Embeddings might be outdated.

```bash
# Full reindex
qmd index --force

# Check specific search
qmd search "your topic" --limit 10
```

### High memory usage

Large vaults can use significant memory during indexing.

```bash
# Index in batches
qmd index ./folder1/
qmd index ./folder2/
```

## Without QMD

Claude Note works without qmd but with reduced functionality:

| Feature | With qmd | Without qmd |
|---------|----------|-------------|
| Synthesis context | Semantic search | Vault index (title/tags) |
| Note routing | Similarity matching | Keyword matching |
| Duplicate detection | Yes | No |
| Ingest quality | High | Basic |

To disable qmd:

```toml
[qmd]
enabled = false
```

## Best Practices

1. **Reindex after major changes:**
   ```bash
   qmd index  # After importing many notes
   ```

2. **Use descriptive note titles:**
   Better titles improve both qmd matching and fallback keyword search.

3. **Add aliases in frontmatter:**
   ```yaml
   aliases: [JWT, JSON Web Token, auth tokens]
   ```

4. **Start with `synth_max_notes = 3`:**
   Increase if synthesis seems to miss context.

5. **Monitor inbox in route mode:**
   If too many items go to inbox, lower `route_threshold`.
