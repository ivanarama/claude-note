# Literature Note Format

Use this format when creating literature notes from external sources (papers, articles, documentation).

## Template

```markdown
---
tags:
  - literature
  - {topic-tag}
  - {optional-additional-tags}
source: "{filename-or-url}"
author: "{author-name-if-known}"
year: {year-if-known}
ingested: {YYYY-MM-DD}
---

# {Document Title}

## Summary

{2-3 sentence overview of what this document covers and its main contribution}

## Key Concepts

- **{Concept 1}**: {Brief explanation}
- **{Concept 2}**: {Brief explanation}
- **{Concept 3}**: {Brief explanation}

## Highlights

{Most important findings, insights, or actionable information}

Key points:
- {Highlight 1}
- {Highlight 2}
- {Highlight 3}

{Optional: Include a brief quote if particularly insightful}

## Questions

- {Question or area for further exploration}
- {Another question raised by the content}

## Related

- [[{related-topic-1}]] - {brief context}
- [[{related-topic-2}]] - {brief context}
```

## Field Guidelines

### Tags
- Always include `literature`
- Add 1-2 topic tags (e.g., `machine-learning`, `api-design`, `architecture`)
- Optional: add project tags if relevant (e.g., `project/myproject`)

### Source
- For files: use the original filename
- For URLs: use the full URL

### Author/Year
- Include if available from the document
- Omit the field entirely if unknown (don't use "Unknown")

### Summary
- 2-3 sentences maximum
- Focus on what the document contributes, not just what it covers
- Write in present tense

### Key Concepts
- Extract 3-7 main concepts
- Each should be self-contained and understandable
- Bold the concept name, then explain

### Highlights
- The most actionable or important information
- Include specific numbers, results, or findings when available
- Keep it scannable with bullet points

### Questions
- What questions does this raise?
- What would you want to explore further?
- What's not clear or needs more research?

### Related
- Link to existing notes in your vault using `[[note-name]]` syntax
- Add brief context for why it's related

## Example

```markdown
---
tags:
  - literature
  - machine-learning
  - transformers
source: "attention-is-all-you-need.pdf"
author: "Vaswani et al."
year: 2017
ingested: 2024-01-15
---

# Attention Is All You Need

## Summary

Introduces the Transformer architecture, which relies entirely on attention mechanisms without recurrence or convolution. Achieves state-of-the-art results on machine translation while being more parallelizable and faster to train.

## Key Concepts

- **Self-attention**: Mechanism to compute representations by attending to different positions in the same sequence
- **Multi-head attention**: Running attention multiple times in parallel with different learned projections
- **Positional encoding**: Injecting sequence order information using sinusoidal functions

## Highlights

Achieves 28.4 BLEU on EN-DE translation, a new state-of-the-art at the time.

Key points:
- Training takes only 3.5 days on 8 GPUs (vs weeks for RNNs)
- Generalizes well to other tasks like parsing
- Attention visualizations show interpretable patterns

## Questions

- How do positional encodings compare to learned position embeddings?
- What are the memory requirements for very long sequences?
- How does performance scale with model size?

## Related

- [[transformers]] - Architecture family this introduced
- [[attention-mechanisms]] - Core concept explained in depth
- [[neural-machine-translation]] - Application domain
```
