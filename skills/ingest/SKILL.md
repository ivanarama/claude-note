---
name: ingest
description: Ingest documents (PDF, DOCX, MD, TXT, URLs) into your knowledge vault as structured literature or internal notes. Use when you want to extract knowledge from research papers, documentation, specs, or web pages and create permanent notes.
disable-model-invocation: true
argument-hint: [file-or-url] [--internal]
allowed-tools: Read, Write, Bash, WebFetch
---

# Document Ingestion Skill

Ingest external documents into your claude-note vault as structured, linkable notes.

## Quick Start

```
/ingest ~/Downloads/attention-paper.pdf
/ingest https://example.com/api-docs --internal
/ingest spec.docx --title "API Specification v2"
```

## Modes

- **Literature** (default): Creates `literature/lit-{slug}.md` for external research, papers, articles
- **Internal** (`--internal`): Creates `internal/int-{slug}.md` for team docs, internal specs, processes

## Arguments

| Argument | Description |
|----------|-------------|
| `[file-or-url]` | Path to document (.pdf, .docx, .md, .txt) or URL |
| `--internal` | Create internal note instead of literature note |
| `--title "..."` | Override the note title (default: derived from filename/URL) |

## Process

When the user invokes `/ingest`, you should:

### 1. Read the Document

**For files:**
- Use the Read tool for `.md` and `.txt` files
- For `.pdf` files: use Bash with `pdftotext` or `pandoc` to extract text
- For `.docx` files: use Bash with `pandoc -t plain` to extract text

**For URLs:**
- Use WebFetch to retrieve the content

### 2. Get Configuration

Read the vault path from `~/.config/claude-note/config.toml`:
```bash
cat ~/.config/claude-note/config.toml
```

Look for `vault_root = "..."` to find where notes should be created.

### 3. Extract Knowledge

As Claude, you directly analyze the content and extract:
- **Summary**: 2-3 sentence overview of what the document covers
- **Key Concepts**: Main ideas, terminology, and definitions
- **Highlights**: Important findings, quotes, or actionable insights
- **Questions**: Open questions or things worth exploring further
- **Related Topics**: Connections to other knowledge areas

### 4. Create the Note

Write a structured note using the appropriate format:
- Literature notes: See [literature-format.md](references/literature-format.md)
- Internal notes: See [internal-format.md](references/internal-format.md)

**Filename conventions:**
- Literature: `literature/lit-{slug}.md`
- Internal: `internal/int-{slug}.md`

Where `{slug}` is a kebab-case version of the title (max 50 chars).

### 5. Handle Duplicates

Before creating a new note, check if a similar note exists:
```bash
ls {vault_path}/literature/ | grep -i "{keywords}"
ls {vault_path}/internal/ | grep -i "{keywords}"
```

If a similar note exists, ask the user if they want to:
1. Merge new content into the existing note
2. Create a separate note anyway
3. Cancel

## Example Workflow

User: `/ingest ~/Downloads/transformer-paper.pdf`

1. Extract text from PDF:
   ```bash
   pdftotext ~/Downloads/transformer-paper.pdf - 2>/dev/null || pandoc ~/Downloads/transformer-paper.pdf -t plain
   ```

2. Read config:
   ```bash
   cat ~/.config/claude-note/config.toml
   ```

3. Analyze the content and extract knowledge

4. Create note at `{vault_root}/literature/lit-attention-is-all-you-need.md`

5. Confirm to user what was created

## URL Ingestion

For URLs, use WebFetch to get the content:

```
/ingest https://docs.example.com/api-guide --internal
```

WebFetch will retrieve the content, then follow the same extraction process.

## Tips

- Use descriptive filenames or `--title` for better slugs
- Review created notes and add manual annotations
- Link to existing topic notes in your vault using `[[note-name]]` syntax
- For large documents, focus on the most important 3-5 concepts

## See Also

- [literature-format.md](references/literature-format.md) - Template for literature notes
- [internal-format.md](references/internal-format.md) - Template for internal notes
- [sample-output.md](examples/sample-output.md) - Example of a created note

## CLI Alternative

For batch processing or automation, use the CLI command instead:
```bash
claude-note ingest ~/papers/*.pdf
```

The CLI calls Claude API programmatically and is better for processing multiple documents.
