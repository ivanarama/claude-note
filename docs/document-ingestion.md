# Document Ingestion

Claude Note can ingest external documents (research papers, documentation, technical specs) and convert them into structured literature notes in your vault.

## Two Ways to Ingest

| Method | When to Use |
|--------|-------------|
| `/ingest` skill | Interactive use in Claude Code sessions |
| `claude-note ingest` CLI | Batch processing, automation, scripts |

### Using /ingest Skill (Recommended for single documents)

In any Claude Code session:
```
/ingest ~/Downloads/paper.pdf
/ingest https://example.com/article --internal
/ingest spec.docx --title "API Specification v2"
```

The skill uses Claude directly to extract knowledge - no separate API call needed.

### Using CLI (For batch/automation)

```bash
# Process multiple files
for f in ~/papers/*.pdf; do
    claude-note ingest "$f"
done

# Ingest with options
claude-note ingest report.pdf --title "Q4 Review" --dry-run
```

The CLI calls the Claude API programmatically and is better for processing multiple documents or scripted workflows.

---

## Overview

```
External Document          →    Ingestion    →    Vault Notes
├── paper.pdf                                    ├── lit-paper-title.md
├── spec.docx                                    ├── topic-concepts.md (updated)
└── notes.md                                     └── inbox (unroutable items)
```

## Quick Start

```bash
# Ingest a PDF
claude-note ingest ~/Downloads/attention-paper.pdf

# Ingest with custom title
claude-note ingest report.docx --title "Q4 Architecture Review"

# Preview without writing
claude-note ingest paper.pdf --dry-run
```

## Supported Formats

| Format | Extension | Requirements |
|--------|-----------|--------------|
| PDF | `.pdf` | pandoc or pdftotext |
| Word | `.docx` | pandoc |
| Markdown | `.md` | None |
| Plain text | `.txt` | None |

### Installing Dependencies

```bash
# macOS
brew install pandoc

# Ubuntu/Debian
sudo apt install pandoc

# Verify
pandoc --version
```

## How It Works

### 1. Text Extraction

The document is converted to plain text:
- **PDF:** Uses pandoc (preserves structure) or pdftotext (fallback)
- **DOCX:** Uses pandoc (preserves headings, lists)
- **MD/TXT:** Read directly

### 2. Knowledge Extraction

Claude analyzes the document and extracts:
- **Summary:** 2-3 sentence overview
- **Key concepts:** Main ideas and terminology
- **Highlights:** Important quotes or findings
- **Questions:** Things worth exploring further
- **Related topics:** Connections to other knowledge

### 3. Duplicate Detection

If qmd is enabled, semantic search checks for existing similar content:
- High similarity (>85%): Merge into existing note
- Medium similarity: Prompt for decision
- No match: Create new note

### 4. Note Creation/Updates

Based on extracted knowledge:
- **Main literature note:** `lit-{title}.md` created in `literature/`
- **Topic updates:** Existing notes get links to new content
- **New topics:** Optionally create topic notes for novel concepts

---

## Command Reference

```bash
claude-note ingest <file> [options]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `file` | Path to document (.pdf, .docx, .md, .txt) |

### Options

| Option | Description |
|--------|-------------|
| `--title`, `-t` | Override note title (default: filename) |
| `--model`, `-m` | Override Claude model |
| `--dry-run`, `-n` | Extract and display without writing |
| `--internal`, `-i` | Create `int-*` notes in `internal/` |
| `--no-topics` | Don't update/create topic notes |
| `--force` | Ignore duplicate warnings |

---

## Output Structure

### Literature Note

Created at `literature/lit-{title}.md`:

```markdown
---
tags:
  - literature
  - machine-learning
  - transformers
source: attention-is-all-you-need.pdf
author: Vaswani et al.
year: 2017
ingested: 2024-01-15
---

# Attention Is All You Need

## Summary

This paper introduces the Transformer architecture, which relies entirely on
attention mechanisms without recurrence or convolution. The model achieves
state-of-the-art results on machine translation while being more parallelizable.

## Key Concepts

- **Self-attention**: Mechanism to compute representations by attending to
  different positions in the same sequence
- **Multi-head attention**: Running attention multiple times in parallel
- **Positional encoding**: Injecting sequence order information

## Highlights

> "Attention is all you need" - The paper's central claim is that attention
> mechanisms alone are sufficient for sequence modeling tasks.

Key findings:
- BLEU score of 28.4 on EN-DE translation (new SOTA)
- 3.5 days training on 8 GPUs
- Generalizes to other tasks (parsing)

## Questions

- How do positional encodings compare to learned position embeddings?
- What is the computational complexity vs RNNs?

## Related

- [[transformers]] - Architecture family
- [[attention-mechanisms]] - Core concept
- [[sequence-models]] - Broader context
- [[neural-machine-translation]] - Application domain
```

### Topic Note Updates

Existing topic notes get links in their "Related" or "From Literature" section:

```markdown
<!-- In transformers.md -->

## From Literature

- [[lit-attention-is-all-you-need]] - Original Transformer paper (2017)
- [[lit-bert-paper]] - Bidirectional pre-training
```

### Internal Documents

With `--internal`, creates `internal/int-{title}.md`:

```markdown
---
tags:
  - internal
  - architecture
source: team-rfc.docx
ingested: 2024-01-15
---

# Authentication Service RFC

[extracted content...]
```

---

## Examples

### Research Paper

```bash
# Ingest a machine learning paper
claude-note ingest ~/papers/attention-paper.pdf

# Output:
# Created: literature/lit-attention-is-all-you-need.md
# Updated: transformers.md (added reference)
# Updated: attention-mechanisms.md (added reference)
```

### Technical Specification

```bash
# Ingest API spec with custom title
claude-note ingest api-spec.docx --title "Payment Gateway API v2"

# Output:
# Created: literature/lit-payment-gateway-api-v2.md
# Created: payment-processing.md (new topic)
```

### Team Documentation

```bash
# Ingest internal doc
claude-note ingest team-process.md --internal

# Output:
# Created: internal/int-team-process.md
```

### Preview Mode

```bash
# See what would be created without writing
claude-note ingest paper.pdf --dry-run

# Output:
# Would create: literature/lit-paper-title.md
# Would update: existing-topic.md
#
# === Extracted Content ===
# Summary: ...
# Key Concepts: ...
# [full preview]
```

---

## Duplicate Handling

### Automatic Detection

When qmd is enabled, ingestion checks for existing similar content:

```
Ingesting: new-paper.pdf

Checking for duplicates...
Found similar: lit-existing-paper.md (87% match)

Options:
1. Merge into existing note
2. Create separate note anyway
3. Cancel ingestion

Choice [1/2/3]:
```

### Merge Behavior

When merging:
- New highlights appended
- New concepts added (deduplicated)
- Questions merged
- Source reference added

### Force Override

```bash
# Skip duplicate check
claude-note ingest paper.pdf --force
```

---

## Configuration

### Default Settings

```toml
[ingest]
# Where literature notes go
literature_dir = "literature"

# Where internal notes go
internal_dir = "internal"

# Create topic notes for novel concepts
create_topics = true

# Update existing topic notes with references
update_topics = true
```

### QMD for Better Results

Enable semantic search for:
- Better duplicate detection
- Smarter topic matching
- More relevant related links

```toml
[qmd]
enabled = true
ingest_dupe_threshold = 0.85
```

---

## Best Practices

### 1. Use Descriptive Filenames

The filename becomes the default title:
- Good: `attention-is-all-you-need.pdf`
- Bad: `paper.pdf`, `doc1.pdf`

Or use `--title`:
```bash
claude-note ingest paper.pdf --title "Attention Is All You Need (2017)"
```

### 2. Organize by Type

- Research papers → default (literature/)
- Team docs → `--internal`
- External specs → default with appropriate tags

### 3. Review and Refine

After ingestion:
1. Check the created note
2. Fix any extraction errors
3. Add manual annotations
4. Strengthen links to other notes

### 4. Index After Batch Ingestion

If ingesting many documents:
```bash
# Ingest all papers
for f in ~/papers/*.pdf; do
    claude-note ingest "$f"
done

# Rebuild qmd index
cd ~/vault && qmd index
```

---

## Troubleshooting

### "pandoc not found"

```bash
# Install pandoc
brew install pandoc  # macOS
sudo apt install pandoc  # Ubuntu

# Verify
which pandoc
```

### Poor extraction quality

- Try a different source format (DOCX often better than PDF)
- Use `--model claude-opus-4-20250514` for complex documents
- For scanned PDFs, use OCR first

### "File too large"

Very large documents may exceed token limits:
```bash
# Split large PDFs first
pdftk large.pdf cat 1-50 output part1.pdf
pdftk large.pdf cat 51-100 output part2.pdf

# Ingest separately
claude-note ingest part1.pdf --title "Large Doc - Part 1"
claude-note ingest part2.pdf --title "Large Doc - Part 2"
```

### Wrong topics matched

If topics are mismatched:
- Check your topic notes have good titles/aliases
- Enable qmd for semantic matching
- Use `--no-topics` and link manually

---

## Comparison with Session Synthesis

| Aspect | Session Synthesis | Document Ingestion |
|--------|-------------------|-------------------|
| Source | Claude Code transcript | External document |
| Trigger | Automatic (session end) | Manual command |
| Output | Updates + inbox | Literature note + updates |
| Structure | Learnings, decisions, patterns | Summary, concepts, highlights |
| Best for | Work knowledge | Research, references |
