# froq — Neural Crest Gene Reconciliation

Reconciles 95 neural crest development genes across 12 public biomedical databases
using CUE's lattice unification. Each source contributes its own fields; CUE unifies
them into a single model and computes gap reports, weighted priority scoring, and
enrichment tiers automatically.

Includes a Grant Gap Finder web dashboard for identifying craniofacial research
funding opportunities.

## Quick Start

```bash
just rebuild    # full pipeline: normalize → validate → generate
just site       # build interactive dashboard
just summary    # coverage stats
just gaps       # research gap report
just report     # human-readable report
just check SOX9 # spot-check a gene
just test       # run integration tests
```

## 95 Genes

Spans the full neural crest gene regulatory network:

| Role | Count | Examples |
|------|-------|---------|
| Border specification | 13 | PAX3, PAX7, ZIC1, MSX1, TFAP2A |
| NC specifiers | 13 | SOX9, SOX10, FOXD3, TWIST1, SNAI2 |
| EMT / migration | 12 | CDH2, ZEB2, MMP2, CXCR4, RHOA |
| Signaling | 27 | SHH, BMP4, FGF8, FGFR2, WNT1, NOTCH1 |
| Craniofacial | 10 | IRF6, TCOF1, CHD7, TBX1, EVC, RUNX2 |
| Melanocyte | 6 | MITF, KIT, TYR, DCT |
| Enteric NS | 6 | RET, GDNF, PHOX2B |
| Cardiac NC | 8 | GATA4, TBX5, HAND2, NKX2-5 |

## 12 Sources

| Source | API | Fields |
|--------|-----|--------|
| Gene Ontology | QuickGO REST | GO terms (MF, BP, CC) |
| OMIM | Bundled genemap2 subset | Disease title, syndromes, inheritance |
| HPO | Bulk annotation file | Clinical phenotype terms |
| UniProt | REST API | Protein name, function, localization |
| FaceBase | DERIVA REST | Craniofacial datasets, species, assay type |
| ClinVar | NCBI E-utilities | Pathogenic variant counts, top variants |
| PubMed | NCBI E-utilities | Publication counts, recent papers |
| gnomAD | GraphQL API | pLI, LOEUF, constraint scores |
| NIH Reporter | Reporter v2 API | Active grants, PIs, organizations |
| GTEx | REST API | Tissue expression (TPM) |
| ClinicalTrials | ClinicalTrials.gov v2 | Active clinical trials |
| STRING | STRING API | Protein-protein interactions |

## Architecture

```
normalizers/     API queries / file parsing (12 sources)
    from_go.py ─────────┐
    from_omim.py ────────┤
    from_hpo.py ─────────┤
    from_uniprot.py ─────┤
    from_facebase.py ────┤
    from_clinvar.py ─────┤  each writes one CUE file
    from_pubmed.py ──────┤
    from_gnomad.py ──────┤
    from_nih_reporter.py ┤
    from_gtex.py ────────┤
    from_clinicaltrials.py ┤
    from_string.py ──────┘
                         ↓
model/           CUE lattice unification
    schema.cue ─── #Gene type definition (12 sources, 80+ fields)
    *.cue ──────── per-source data files, unify into `genes` struct
    proj_*.cue ─── computed projections (gaps, weighted scoring, enrichment)
                         ↓
generators/      outputs
    to_site.py ──── Grant Gap Finder dashboard (single-file HTML)
    to_vizdata.py ── Cytoscape.js graph (phenotype/syndrome/pathway/PPI edges)
    to_summary.py ── human-readable coverage report
```

## Key Pattern: Sources OBSERVE, Resolutions DECIDE

Each source owns its fields exclusively:
- `go.cue` sets `_in_go: true`, `go_id`, `go_terms`
- `omim.cue` sets `_in_omim: true`, `omim_id`, `omim_syndromes`
- No source touches another source's fields

Projections compute derived views (gap reports, weighted scoring, enrichment)
from the unified model.

## Adding a Source

See [ADDING-A-SOURCE.md](ADDING-A-SOURCE.md).
