# lacuene: Neural Crest Gene Reconciliation Pipeline

**Date:** 2026-02-14
**Status:** Approved

## Purpose

Apply CUE lattice unification to biomedical data integration.
Target audience: Dr. Jamie Kugler (NIDCR, NIH) — developmental biology background,
manages scientific programs at the National Institute of Dental and Craniofacial Research.

The repo must be:
- Standalone-runnable (`git clone` + `just rebuild`)
- Demo-ready (walkthrough-friendly with clear output)
- Structurally clear with documented patterns

## Architecture

```
normalizers/ (any inputs) -> model/ (CUE unification) -> generators/ (any outputs)
```

Each source gets one normalizer. CUE unifies via struct merge.
Projections compute gap reports, ID conflicts, and enrichment tiers at eval time.
Generators produce JSON summaries and VizData for graph visualization.

## Gene List (20 Neural Crest Development Genes)

Organized by developmental role in the neural crest -> craniofacial pipeline:

### Neural plate border specification
- PAX3, PAX7, ZIC1, MSX1, MSX2

### Neural crest specifiers
- SOX9, SOX10, FOXD3, TFAP2A, SNAI1, SNAI2, TWIST1

### Craniofacial patterning + disease genes
- IRF6 (cleft lip/palate)
- TCOF1 (Treacher Collins syndrome)
- CHD7 (CHARGE syndrome)
- FGFR2 (craniosynostosis)
- TBX1 (DiGeorge/22q11.2 deletion)
- EVC (Ellis-van Creveld syndrome)
- RUNX2 (cleidocranial dysplasia)
- SHH (holoprosencephaly)

## Data Sources (5)

| Source | API/Format | Auth | Join Key |
|--------|-----------|------|----------|
| Gene Ontology | QuickGO REST API (`ebi.ac.uk/QuickGO/api/`) | None | HGNC symbol via gene name |
| OMIM | Bundled `genemap2.txt` snapshot | None (pre-downloaded) | Gene symbol column |
| HPO | Bulk annotation file (`phenotype_to_genes.txt`) | None | HGNC symbol column |
| UniProt | REST API (`rest.uniprot.org`) | None | Gene name field |
| FaceBase | DERIVA REST or pre-cached JSON | Open-access | Gene symbol in metadata |

### Name Resolution

Canonical key: **HGNC gene symbol** (e.g., `"IRF6"`, `"PAX3"`).

For 20 genes, each normalizer includes a manual HGNC lookup table.
At scale, normalizers would use the HGNC complete set download for mapping.

Source-native IDs are preserved in per-source fields.

## Schema (`model/schema.cue`)

```cue
package lacuene

#Gene: {
    symbol: string

    // Per-source identifiers
    go_id:       *"" | string
    omim_id:     *"" | string
    hpo_gene_id: *"" | string
    uniprot_id:  *"" | string
    facebase_id: *"" | string

    // Source presence markers
    _in_go:       *false | true
    _in_omim:     *false | true
    _in_hpo:      *false | true
    _in_uniprot:  *false | true
    _in_facebase: *false | true

    // GO-owned fields
    go_terms?: [...#GOAnnotation]

    // OMIM-owned fields
    omim_title?:     string
    omim_syndromes?: [...string]
    inheritance?:    string

    // HPO-owned fields
    phenotypes?: [...string]

    // UniProt-owned fields
    protein_name?:          string
    organism?:              string
    sequence_length?:       int
    subcellular_locations?: [...string]
    functions?:             [...string]

    // FaceBase-owned fields
    facebase_datasets?: [...#FaceBaseDataset]
}

#GOAnnotation: {
    term_id:   string
    term_name: string
    aspect:    string  // "F", "P", "C"
}

#FaceBaseDataset: {
    title:      string
    species?:   string
    assay_type?: string
}

genes: [Symbol=string]: #Gene & {symbol: Symbol}
```

## Projections

### proj_gap_report.cue
- `research_gaps`: Genes in OMIM (disease) but not FaceBase (no experimental data)
- `phenotype_gaps`: Genes in FaceBase but not HPO (no clinical phenotype mapping)
- `missing_*`: Per-source gap lists (same as prior pipeline)
- Summary counts

### proj_id_conflicts.cue
- Detects where sources use conflicting identifiers for the same gene
- Pre-computed flag struct pattern (same as prior pipeline IP conflicts)

### proj_sources.cue
- Exports `_in_*` hidden fields as visible fields for downstream consumers

### proj_enrichment.cue
- Coverage tiers: how many sources describe each gene (tier 5 = all sources)
- Cross-source enrichment stats

## Generators

### generators/to_summary.py
- Pretty-prints unified results: per-gene table with source coverage
- Gap report in human-readable format
- Coverage tier breakdown

### generators/to_vizdata.py
- Produces Cytoscape.js-compatible VizData JSON
- **Nodes**: each gene, sized by source coverage tier
- **Node color**: by developmental role (border spec = blue, NC specifier = purple,
  patterning/disease = red/orange)
- **Edges**: shared HPO phenotype, shared OMIM syndrome, shared GO biological process
- Compatible with infra-graph graph explorer

## File Layout

```
lacuene/
├── model/
│   ├── schema.cue
│   ├── go.cue               (generated)
│   ├── omim.cue             (generated)
│   ├── hpo.cue              (generated)
│   ├── uniprot.cue          (generated)
│   ├── facebase.cue         (generated)
│   ├── resolutions.cue      (generated)
│   ├── proj_gap_report.cue
│   ├── proj_id_conflicts.cue
│   ├── proj_sources.cue
│   └── proj_enrichment.cue
├── normalizers/
│   ├── from_go.py
│   ├── from_omim.py
│   ├── from_hpo.py
│   ├── from_uniprot.py
│   └── from_facebase.py
├── generators/
│   ├── to_summary.py
│   └── to_vizdata.py
├── data/
│   ├── omim/genemap2.txt    (bundled snapshot)
│   ├── hpo/phenotype_to_genes.txt (bundled or downloaded)
│   └── facebase/            (cached API responses)
├── output/                  (generated JSON)
├── examples/
│   ├── schema.cue           (3 genes, 2 sources)
│   ├── source_a.cue
│   └── source_b.cue
├── justfile
├── CLAUDE.md
├── ADDING-A-SOURCE.md
└── README.md
```

## Justfile Recipes

```
just rebuild        # Full pipeline: normalize all -> validate -> generate
just validate       # cue vet -c ./model/
just generate       # Export projections as JSON
just summary        # Quick stats
just check GENE     # Spot-check: cue export ./model/ -e 'genes["IRF6"]'
just gaps           # Research gap report
just vizdata        # Generate VizData JSON
just normalize      # Run all normalizers
just normalize-go   # Run individual normalizer
```

## Design Principles

1. **Sources OBSERVE, Resolutions DECIDE** — each source owns its fields
2. **Per-source ID namespacing** — `go_id`, `omim_id`, etc. never conflict
3. **Defaulted markers for comprehension guards** — `*false | true`
4. **Pre-computed flag structs** — CUE equivalent of SQL CTEs

## Success Criteria

1. `just rebuild` runs end-to-end with no errors
2. 20 genes unified across 5 sources
3. Gap report shows at least 1 meaningful research gap
4. VizData loads in a browser (Cytoscape.js)
5. `ADDING-A-SOURCE.md` documents how to add a 6th source
6. Examples directory works standalone (`cue eval ./examples/`)
7. Jamie can clone it and run it without asking questions
