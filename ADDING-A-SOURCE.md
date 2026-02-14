# Adding a Source to froq

Adding a 13th (or Nth) biomedical database follows the same pattern as the existing 12.
The model uses CUE lattice unification — each source contributes its own fields,
and CUE merges them automatically.

## The Pattern

Each source needs exactly 3 things:

1. **A normalizer** (`normalizers/from_<source>.py`) — fetches data, writes CUE
2. **Source-owned fields** in `model/schema.cue` — new optional fields + `_in_<source>` flag
3. **A justfile recipe** — `normalize-<source>` entry

## Worked Example: Adding KEGG Pathway Data

### Step 1: Add fields to schema.cue

```cue
#Gene: {
    // ... existing fields ...
    kegg_id:      *"" | string
    _in_kegg:     *false | true
    pathways?:    [...string]
}
```

Rules:
- ID field defaults to `""` (empty string) — NOT optional
- Boolean flag defaults to `false` — every gene starts as "not in KEGG"
- Data fields are optional (`?`) — only present when the source has data

### Step 2: Write the normalizer

```python
#!/usr/bin/env python3
"""Normalizer: KEGG REST API -> model/kegg.cue"""

import json, os, sys, requests
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from genes import GENES

def main():
    lines = ["package froq\n"]
    for symbol in sorted(GENES.keys()):
        # Query KEGG API for this gene
        kegg_id = fetch_kegg_id(symbol)
        if not kegg_id:
            continue

        pathways = fetch_pathways(kegg_id)

        lines.append(f'genes: "{symbol}": {{')
        lines.append(f'\t_in_kegg: true')
        lines.append(f'\tkegg_id:  "{kegg_id}"')
        if pathways:
            lines.append(f'\tpathways: [')
            for p in pathways:
                lines.append(f'\t\t"{p}",')
            lines.append(f'\t]')
        lines.append(f'}}')
        lines.append('')

    with open("model/kegg.cue", "w") as f:
        f.write("\n".join(lines))
```

Key rules:
- Import `GENES` from `normalizers/genes.py` for the canonical gene list
- Write `package froq` — same package as all other model files
- Set `_in_kegg: true` for every gene you find
- Only touch KEGG-owned fields. Never set `_in_go` or any other source's fields.
- Escape strings for CUE (backslashes, double quotes)

### Step 3: Add justfile recipe

```just
normalize-kegg:
    python3 normalizers/from_kegg.py
```

Add `python3 normalizers/from_kegg.py` to the `normalize:` recipe list.

### Step 4: Update projections and site

In `model/proj_sources.cue`, add `in_kegg: v._in_kegg` to the comprehension.
In `model/proj_enrichment.cue`, add `has_pathway: v._in_kegg`.
In `model/proj_gap_report.cue`, add `missing_kegg` list comprehension.
In `generators/to_site.py`, add `"in_kegg": "KEGG"` to `source_names`, `source_urls`, and `filter_keys`.
In `generators/static/app.js`, add KEGG to the gene detail panel and filter buttons.

### Step 5: Validate

```bash
python3 normalizers/from_kegg.py
cue vet -c ./model/
just summary
```

## Rules

1. **One normalizer per source** — never combine sources in one file
2. **Source-owned fields only** — each source touches only its own fields
3. **Defaulted booleans** — `_in_<source>: *false | true` ensures missing genes get `false`
4. **HGNC symbol is the join key** — always use `genes.py` for the canonical list
5. **Deterministic output** — sort genes alphabetically for stable diffs
6. **Offline fallback** — if the API needs auth or is unreliable, bundle a cache file in `data/`
