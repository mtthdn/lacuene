# CLAUDE.md — lacuene

## What This Is
Neural crest gene reconciliation pipeline. Normalizers transform biomedical
database exports (APIs, bulk files) into CUE files. CUE unifies them via
lattice semantics. Generators produce JSON summaries and VizData.

## Commands
- `just validate` — CUE model validation
- `just generate` — Export projections as JSON (includes anomalies)
- `just vizdata` — Generate VizData for graph explorer
- `just site` — Build full static site (index + about)
- `just serve` — Local preview server at localhost:8000
- `just rebuild` — Full pipeline from API data
- `just test` — Run integration tests
- `just summary` — Quick coverage stats
- `just check <gene>` — Spot-check a specific gene (e.g., `just check IRF6`)
- `just gaps` — Show research gap report
- `just anomalies` — Show cross-source anomalies
- `just digest` — Weekly digest markdown
- `just bulk` — Genome-wide bulk analysis (moved to lacuene-exp)
- `just bulk-craniofacial` — Craniofacial bulk analysis (moved to lacuene-exp)
- `just hgnc` — Download/refresh HGNC gene data (moved to lacuene-exp)

## Architecture
```
normalizers/ (API/file inputs) -> model/ (CUE unification) -> generators/ (JSON/VizData)
```

## Key Patterns
- Sources OBSERVE, Resolutions DECIDE (no shared mutable fields)
- Per-source ID namespacing: `go_id`, `omim_id`, etc.
- Defaulted booleans for source markers: `_in_go: *false | true`
- Canonical key is HGNC gene symbol
- CUE CONSTRUCTS the reconciled model through lattice unification
- See ADDING-A-SOURCE.md for the plugin pattern

## Key Files
- `model/schema.cue` — #Gene type definition (the contract)
- `model/proj_anomalies.cue` — Cross-source anomaly detection rules
- `normalizers/genes.py` — 95 curated craniofacial genes + HGNC ID lookup table
- `normalizers/utils.py` — Shared HTTP retry/backoff utilities
- `normalizers/from_*.py` — Per-source normalizers (16 sources)
- `generators/to_vizdata.py` — VizData JSON for graph explorer
- `generators/to_site.py` — Static site generator (Jinja2 templates)
- `generators/to_summary.py` — Human-readable summary
- `generators/to_digest.py` — Weekly digest generator (GitHub issue posting)
- `generators/templates/` — Jinja2 templates (index, about, base)
- `generators/static/` — CSS and JS (inlined into HTML at build time)

## Related Repos
- **lacuene-exp** (`~/lacuene-exp`) — Derived data layer, expanded gene sets, Flask API, overnight workers
  - API: `lacuene-api.apercue.ca` (LXC 638 on tulip, port 5100)
  - Static site: `lacuene.apercue.ca` (LXC 612 Caddy)
  - Bulk/expanded scripts moved here (bulk_hgnc.py, bulk_downloads.py, expand_genes.py)
  - 95 curated genes stay in lacuene; 494 expanded served from lacuene-exp
