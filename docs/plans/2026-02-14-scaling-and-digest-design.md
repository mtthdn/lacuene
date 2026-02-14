# Genome-Wide Scaling + Weekly Digest

**Date:** 2026-02-14
**Status:** In Progress

## Two Features

### 1. Weekly Digest Generator

After the weekly rebuild, post a summary to a GitHub issue showing:
- Which caches were refreshed
- Gap changes since last snapshot (opened/closed)
- Source coverage delta
- Any normalizer failures

Implementation: `generators/to_digest.py` produces markdown, weekly-rebuild
workflow calls `gh issue comment` to post it.

### 2. Genome-Wide Scaling (Tiered)

**Tier 1: Expand to ~500 genes** — grow the curated CUE model to cover all
craniofacial-adjacent genes. Requires bulk HGNC download for ID resolution.

**Tier 2: Bulk pipeline** — Python-only CSV pipeline for full 19K HGNC genes.
No CUE (too slow at that scale). Produces `output/bulk/` with per-source CSVs
and a merged summary. The interactive site stays on the curated gene set.

**Tier 3: Benchmark CUE at scale** — test whether CUE can handle 500+ genes
and document the performance ceiling.

## Architecture

```
normalizers/genes.py          95 curated genes (current)
normalizers/bulk_hgnc.py      19K genes from HGNC complete set
normalizers/bulk_downloads.py Batch API queries for bulk pipeline

model/*.cue                   Curated CUE model (95-500 genes)
output/bulk/*.csv             Genome-wide bulk analysis (19K genes)
```

## Implementation Order (fastest first)

1. Weekly digest generator + workflow wiring
2. bulk_hgnc.py — HGNC complete set downloader
3. Expand genes.py to ~500 craniofacial genes (using HGNC data)
4. bulk_downloads.py — batch source queries for genome-wide
5. CUE benchmark at 500 genes
