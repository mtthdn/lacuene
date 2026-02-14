# lacuene Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a 20-gene biomedical reconciliation pipeline that proves the CUE lattice unification pattern works identically for genes as it does for VMs.

**Architecture:** `normalizers/ (Python, hits public APIs) -> model/ (CUE unification) -> generators/ (JSON + VizData)`. Each source writes one CUE file keyed on HGNC gene symbol. CUE merges them. Projections detect gaps and conflicts at eval time.

**Tech Stack:** CUE, Python 3, public REST APIs (QuickGO, UniProt, HPO, FaceBase), bundled OMIM snapshot, Cytoscape.js VizData output.

**Repo:** `./` (already initialized, design doc committed)

**Reference:** The CUE lattice unification pattern for multi-source reconciliation.

---

### Task 1: Scaffold Repo

**Files:**
- Create: `CLAUDE.md`
- Create: `.gitignore`
- Create: `justfile`
- Create: `model/` directory
- Create: `normalizers/` directory
- Create: `generators/` directory
- Create: `data/` directory
- Create: `output/` directory
- Create: `examples/` directory

**Step 1: Create .gitignore**

```
output/
data/omim/genemap2.txt
data/hpo/phenotype_to_genes.txt
data/cache/
__pycache__/
*.pyc
.env
```

**Step 2: Create CLAUDE.md**

```markdown
# CLAUDE.md — lacuene

## What This Is
Neural crest gene reconciliation pipeline. Normalizers transform biomedical
database exports (APIs, bulk files) into CUE files. CUE unifies them via
lattice semantics. Generators produce JSON summaries and VizData.

## Commands
- `just validate` — CUE model validation
- `just generate` — Export projections as JSON
- `just vizdata` — Generate VizData for graph explorer
- `just rebuild` — Full pipeline from API data
- `just summary` — Quick coverage stats
- `just check <gene>` — Spot-check a specific gene (e.g., `just check IRF6`)
- `just gaps` — Show research gap report

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
- `normalizers/from_*.py` — Per-source normalizers
- `generators/to_vizdata.py` — VizData JSON for graph explorer
- `generators/to_summary.py` — Human-readable summary
```

**Step 3: Create justfile skeleton**

```just
# lacuene: Neural crest gene reconciliation pipeline
# Unifies GO, OMIM, HPO, UniProt, and FaceBase into one CUE model.

default: validate generate

# Normalize all sources into CUE model files
normalize:
    python3 normalizers/from_go.py
    python3 normalizers/from_omim.py
    python3 normalizers/from_hpo.py
    python3 normalizers/from_uniprot.py
    python3 normalizers/from_facebase.py

# Validate the unified CUE model
validate:
    cue vet -c ./model/

# Generate all projection outputs as JSON
generate: validate
    mkdir -p output
    cue export ./model/ -e gap_report > output/gap_report.json
    cue export ./model/ -e enrichment > output/enrichment.json
    cue export ./model/ -e gene_sources > output/sources.json
    @echo "Generated: $(du -sh output | cut -f1) in output/"

# Quick summary stats
summary:
    @cue export ./model/ -e gap_report.summary 2>/dev/null | python3 -m json.tool

# Spot-check a specific gene
check gene:
    cue export ./model/ -e 'genes["{{gene}}"]' | python3 -m json.tool

# Research gap report
gaps:
    @cue export ./model/ -e gap_report | python3 -m json.tool

# Full rebuild from API data
rebuild: normalize validate generate
    @echo "Full rebuild complete."

# Generate VizData JSON for graph explorer
vizdata: validate
    python3 generators/to_vizdata.py

# Generate human-readable summary
report: validate
    python3 generators/to_summary.py

# Validate examples (self-contained, no API)
examples:
    cue vet -c ./examples/

# Normalize individual sources
normalize-go:
    python3 normalizers/from_go.py

normalize-omim:
    python3 normalizers/from_omim.py

normalize-hpo:
    python3 normalizers/from_hpo.py

normalize-uniprot:
    python3 normalizers/from_uniprot.py

normalize-facebase:
    python3 normalizers/from_facebase.py

# Generate all outputs
all: generate vizdata report
```

**Step 4: Create directory stubs**

```bash
mkdir -p ./{model,normalizers,generators,data/{omim,hpo,facebase,cache},output,examples}
```

**Step 5: Commit**

```bash
git add -A && git commit -m "Scaffold repo: CLAUDE.md, justfile, directory structure"
```

---

### Task 2: Schema + Gene List

**Files:**
- Create: `model/schema.cue`
- Create: `normalizers/genes.py` (shared gene list + HGNC lookup)

**Step 1: Write model/schema.cue**

```cue
package lacuene

// Unified gene schema. Five sources contribute fields.
// Each source claims its own identifiers — no shared mutable fields.
//
// Pattern: sources OBSERVE, resolutions DECIDE.
// Canonical key: HGNC gene symbol.

#Gene: {
	symbol: string // HGNC canonical gene symbol

	// Per-source identifiers (never conflict — each source owns its own)
	go_id:       *"" | string // UniProtKB accession used by GO
	omim_id:     *"" | string // MIM number
	hpo_gene_id: *"" | string // NCBIGene ID used by HPO
	uniprot_id:  *"" | string // UniProt accession
	facebase_id: *"" | string // DERIVA RID

	// Source presence markers (default false, sources override to true)
	_in_go:       *false | true
	_in_omim:     *false | true
	_in_hpo:      *false | true
	_in_uniprot:  *false | true
	_in_facebase: *false | true

	// GO-owned fields (Gene Ontology annotations)
	go_terms?: [...#GOAnnotation]

	// OMIM-owned fields (Mendelian disease associations)
	omim_title?:     string
	omim_syndromes?: [...string]
	inheritance?:    string // "AD", "AR", "XL", etc.

	// HPO-owned fields (clinical phenotypes)
	phenotypes?: [...string]

	// UniProt-owned fields (protein data)
	protein_name?:          string
	organism?:              string
	sequence_length?:       int
	subcellular_locations?: [...string]
	functions?:             [...string]

	// FaceBase-owned fields (craniofacial research datasets)
	facebase_datasets?: [...#FaceBaseDataset]
}

#GOAnnotation: {
	term_id:   string // "GO:0003700"
	term_name: string // "DNA-binding transcription factor activity"
	aspect:    string // "F" (function), "P" (process), "C" (component)
}

#FaceBaseDataset: {
	title:      string
	species?:   string // "Mus musculus", "Homo sapiens"
	assay_type?: string // "RNA-seq", "ChIP-seq", "imaging"
}

genes: [Symbol=string]: #Gene & {symbol: Symbol}
```

**Step 2: Write normalizers/genes.py (shared gene list and ID lookup)**

This is the name resolution table — the equivalent of `extract_vm_code()` in prior pipeline.

```python
#!/usr/bin/env python3
"""
Canonical gene list and cross-reference IDs for the 20 neural crest genes.

This is the name resolution layer. Every normalizer imports GENES to know
which genes to query and how to map source-native IDs back to HGNC symbols.
"""

# Each entry: HGNC symbol -> known IDs across sources.
# This is the equivalent of prior pipeline's extract_vm_code() — the join key.
GENES = {
    # --- Neural plate border specification ---
    "PAX3":  {"ncbi": "5077",  "uniprot": "P23760", "omim": "606597"},
    "PAX7":  {"ncbi": "5081",  "uniprot": "P23759", "omim": "167410"},
    "ZIC1":  {"ncbi": "7545",  "uniprot": "Q15915", "omim": "600470"},
    "MSX1":  {"ncbi": "4487",  "uniprot": "P28360", "omim": "142983"},
    "MSX2":  {"ncbi": "4488",  "uniprot": "P35548", "omim": "123101"},
    # --- Neural crest specifiers ---
    "SOX9":  {"ncbi": "6662",  "uniprot": "P48436", "omim": "608160"},
    "SOX10": {"ncbi": "6663",  "uniprot": "P56693", "omim": "602229"},
    "FOXD3": {"ncbi": "27022", "uniprot": "Q9UJU5", "omim": "611539"},
    "TFAP2A":{"ncbi": "7020",  "uniprot": "P05549", "omim": "107580"},
    "SNAI1": {"ncbi": "6615",  "uniprot": "O95863", "omim": "604238"},
    "SNAI2": {"ncbi": "6591",  "uniprot": "O43623", "omim": "602150"},
    "TWIST1":{"ncbi": "7291",  "uniprot": "Q15672", "omim": "601622"},
    # --- Craniofacial patterning + disease ---
    "IRF6":  {"ncbi": "3664",  "uniprot": "O14896", "omim": "607199"},
    "TCOF1": {"ncbi": "6949",  "uniprot": "Q13428", "omim": "606847"},
    "CHD7":  {"ncbi": "55636", "uniprot": "Q9P2D1", "omim": "608892"},
    "FGFR2": {"ncbi": "2263",  "uniprot": "P21802", "omim": "176943"},
    "TBX1":  {"ncbi": "6899",  "uniprot": "O43435", "omim": "602054"},
    "EVC":   {"ncbi": "2121",  "uniprot": "P57679", "omim": "604831"},
    "RUNX2": {"ncbi": "860",   "uniprot": "Q13950", "omim": "600211"},
    "SHH":   {"ncbi": "6469",  "uniprot": "Q15465", "omim": "600725"},
}

# Reverse lookups
NCBI_TO_SYMBOL = {v["ncbi"]: k for k, v in GENES.items()}
UNIPROT_TO_SYMBOL = {v["uniprot"]: k for k, v in GENES.items()}
OMIM_TO_SYMBOL = {v["omim"]: k for k, v in GENES.items()}


def gene_symbols() -> list[str]:
    """Return sorted list of all gene symbols."""
    return sorted(GENES.keys())
```

**Step 3: Verify schema validates**

```bash
cd . && cue vet ./model/
```

Should pass (schema only, no data yet — no concrete instances to check).

**Step 4: Commit**

```bash
git add model/schema.cue normalizers/genes.py
git commit -m "Add gene schema and HGNC lookup table for 20 neural crest genes"
```

---

### Task 3: Self-Contained Examples

**Files:**
- Create: `examples/schema.cue`
- Create: `examples/source_a.cue`
- Create: `examples/source_b.cue`

Port the prior pipeline examples pattern. 3 genes, 2 sources.

**Step 1: Write examples/schema.cue**

```cue
package example

#Gene: {
	symbol:      string
	source_a_id: *"" | string
	source_b_id: *"" | string
	in_source_a: *false | true
	in_source_b: *false | true
	function?:   string
	phenotypes?: [...string]
}

genes: [Symbol=string]: #Gene & {symbol: Symbol}
```

**Step 2: Write examples/source_a.cue**

```cue
package example

// Source A: Gene function database (3 genes)

genes: {
	"IRF6": {
		in_source_a: true
		source_a_id: "GO:IRF6"
		function:    "DNA-binding transcription factor"
	}
	"PAX3": {
		in_source_a: true
		source_a_id: "GO:PAX3"
		function:    "Paired box transcription factor"
	}
	"SOX9": {
		in_source_a: true
		source_a_id: "GO:SOX9"
		function:    "SRY-box transcription factor"
	}
}
```

**Step 3: Write examples/source_b.cue**

```cue
package example

// Source B: Disease phenotype database (3 genes, 1 overlap missing)

genes: {
	"IRF6": {
		in_source_b: true
		source_b_id: "OMIM:607199"
		phenotypes: ["Cleft lip", "Cleft palate", "Lip pit"]
	}
	"PAX3": {
		in_source_b: true
		source_b_id: "OMIM:606597"
		phenotypes: ["Waardenburg syndrome", "White forelock", "Hearing loss"]
	}
	// SOX9 missing from source B — this is the gap
}
```

**Step 4: Validate examples**

```bash
cd . && cue vet -c ./examples/
```

**Step 5: Test unified output**

```bash
cue export ./examples/ -e genes | python3 -m json.tool
```

Expected: IRF6 and PAX3 have fields from both sources. SOX9 has `in_source_b: false`.

**Step 6: Commit**

```bash
git add examples/ && git commit -m "Add self-contained example: 3 genes, 2 sources"
```

---

### Task 4: Gene Ontology Normalizer

**Files:**
- Create: `normalizers/from_go.py`

Hits QuickGO REST API for GO annotations on each gene (human, taxon 9606).

**Step 1: Write normalizers/from_go.py**

The normalizer should:
1. For each gene in `genes.py`, query QuickGO API by gene symbol
2. Extract GO term annotations (molecular function, biological process, cellular component)
3. Write `model/go.cue`

API endpoint: `https://www.ebi.ac.uk/QuickGO/services/annotation/search?geneProductId={uniprot_id}&taxonId=9606&limit=100`

Output format matches prior pipeline pattern:
```cue
package lacuene

genes: {
    "IRF6": {
        _in_go: true
        go_id: "O14896"
        go_terms: [{term_id: "GO:0003700", term_name: "...", aspect: "F"}, ...]
    }
}
```

**Step 2: Test it**

```bash
cd . && python3 normalizers/from_go.py
cue vet ./model/
cue export ./model/ -e 'genes["IRF6"].go_terms' | python3 -m json.tool
```

**Step 3: Commit**

```bash
git add normalizers/from_go.py model/go.cue
git commit -m "Add Gene Ontology normalizer: QuickGO API for 20 genes"
```

---

### Task 5: OMIM Normalizer

**Files:**
- Create: `normalizers/from_omim.py`
- Create: `data/omim/README.md` (instructions for obtaining genemap2.txt)

Uses bundled `genemap2.txt` snapshot. Parse tab-delimited file, extract disease
associations for our 20 genes.

**Step 1: Write data/omim/README.md**

```markdown
# OMIM Data

Download `genemap2.txt` from https://omim.org/downloads/
Place it in this directory.

For this demo, a pre-extracted subset for 20 neural crest genes is
included in `omim_subset.json`.
```

**Step 2: Write normalizers/from_omim.py**

The normalizer should:
1. If `genemap2.txt` exists, parse it for our 20 genes
2. If not, fall back to a bundled `data/omim/omim_subset.json` (the 20-gene extract)
3. Extract: MIM number, gene title, associated phenotypes/syndromes, inheritance
4. Write `model/omim.cue`

Since OMIM download requires registration, include a pre-built JSON subset
so the demo works without the full file.

**Step 3: Test + commit**

```bash
python3 normalizers/from_omim.py && cue vet ./model/
git add normalizers/from_omim.py data/omim/ model/omim.cue
git commit -m "Add OMIM normalizer: disease associations for 20 genes"
```

---

### Task 6: HPO Normalizer

**Files:**
- Create: `normalizers/from_hpo.py`

HPO publishes `phenotype_to_genes.txt` (bulk download, no auth).
URL: `http://purl.obolibrary.org/obo/hp/hpoa/phenotype_to_genes.txt`

**Step 1: Write normalizers/from_hpo.py**

The normalizer should:
1. Download `phenotype_to_genes.txt` if not cached in `data/hpo/`
2. Parse: HPO term ID, HPO term name, NCBI Gene ID, Gene Symbol
3. Filter for our 20 genes (match on gene symbol)
4. Group phenotype terms by gene
5. Write `model/hpo.cue`

**Step 2: Test + commit**

```bash
python3 normalizers/from_hpo.py && cue vet ./model/
cue export ./model/ -e 'genes["IRF6"].phenotypes' | python3 -m json.tool
git add normalizers/from_hpo.py model/hpo.cue
git commit -m "Add HPO normalizer: clinical phenotypes for 20 genes"
```

---

### Task 7: UniProt Normalizer

**Files:**
- Create: `normalizers/from_uniprot.py`

UniProt REST API: `https://rest.uniprot.org/uniprotkb/{accession}?format=json`

**Step 1: Write normalizers/from_uniprot.py**

The normalizer should:
1. For each gene, fetch UniProt entry by accession (from `genes.py` lookup table)
2. Extract: protein name, organism, sequence length, subcellular locations, function descriptions
3. Write `model/uniprot.cue`

**Step 2: Test + commit**

```bash
python3 normalizers/from_uniprot.py && cue vet ./model/
cue export ./model/ -e 'genes["IRF6"].protein_name'
git add normalizers/from_uniprot.py model/uniprot.cue
git commit -m "Add UniProt normalizer: protein data for 20 genes"
```

---

### Task 8: FaceBase Normalizer

**Files:**
- Create: `normalizers/from_facebase.py`
- Create: `data/facebase/README.md`

FaceBase uses DERIVA platform. The API is complex but open-access data is public.
For the demo, we'll query the dataset catalog for our gene symbols and cache results.

DERIVA ERMrest endpoint: `https://www.facebase.org/ermrest/catalog/1/entity/`

**Step 1: Write normalizers/from_facebase.py**

Strategy:
1. Query FaceBase dataset search for each gene symbol
2. If the DERIVA API is too complex, fall back to a pre-cached `data/facebase/facebase_cache.json`
3. Extract: dataset title, species, assay type
4. Write `model/facebase.cue`

Include a bundled cache file so the demo works offline.
The normalizer should try the API first, fall back to cache.

**Step 2: Test + commit**

```bash
python3 normalizers/from_facebase.py && cue vet ./model/
git add normalizers/from_facebase.py data/facebase/ model/facebase.cue
git commit -m "Add FaceBase normalizer: craniofacial datasets for 20 genes"
```

---

### Task 9: Projections

**Files:**
- Create: `model/proj_gap_report.cue`
- Create: `model/proj_sources.cue`
- Create: `model/proj_enrichment.cue`

**Step 1: Write model/proj_sources.cue**

```cue
package lacuene

// Export source provenance as visible fields.
gene_sources: {for k, v in genes {
	(k): {
		in_go:       v._in_go
		in_omim:     v._in_omim
		in_hpo:      v._in_hpo
		in_uniprot:  v._in_uniprot
		in_facebase: v._in_facebase
	}
}}
```

**Step 2: Write model/proj_gap_report.cue**

```cue
package lacuene

// Gap report: which genes are missing from which sources?

gap_report: {
	summary: {
		total:           len(genes)
		in_all_five:     len(_all_five)
		in_four:         len(_in_four)
		in_three:        len(_in_three)
		in_two:          len(_in_two)
		in_one:          len(_in_one)
		missing_go:       len(missing_go)
		missing_omim:     len(missing_omim)
		missing_hpo:      len(missing_hpo)
		missing_uniprot:  len(missing_uniprot)
		missing_facebase: len(missing_facebase)
	}

	// Genes with OMIM disease association but no FaceBase experimental data.
	// Known craniofacial disease genes with no NIDCR experimental coverage.
	research_gaps: [for k, v in genes if v._in_omim && !v._in_facebase {
		symbol: k
		if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
	}]

	// Per-source missing lists
	missing_go: [for k, v in genes if !v._in_go {symbol: k}]
	missing_omim: [for k, v in genes if !v._in_omim {symbol: k}]
	missing_hpo: [for k, v in genes if !v._in_hpo {symbol: k}]
	missing_uniprot: [for k, v in genes if !v._in_uniprot {symbol: k}]
	missing_facebase: [for k, v in genes if !v._in_facebase {symbol: k}]

	_source_count: {for k, v in genes {
		(k): (0 +
			(1 & v._in_go | 0) +
			(1 & v._in_omim | 0) +
			(1 & v._in_hpo | 0) +
			(1 & v._in_uniprot | 0) +
			(1 & v._in_facebase | 0))
	}}

	_all_five: [for k, v in genes if v._in_go && v._in_omim && v._in_hpo && v._in_uniprot && v._in_facebase {k}]
	_in_four: [for k, _ in _source_count if _source_count[k] == 4 {k}]
	_in_three: [for k, _ in _source_count if _source_count[k] == 3 {k}]
	_in_two: [for k, _ in _source_count if _source_count[k] == 2 {k}]
	_in_one: [for k, _ in _source_count if _source_count[k] == 1 {k}]
}
```

Note: The `_source_count` comprehension may need adjustment based on CUE's boolean-to-int
conversion. If CUE doesn't support `1 & bool`, use a pre-computed flag struct instead:

```cue
_flags: {for k, v in genes {
	(k): {
		_count_go:       1 if v._in_go, 0
		// etc.
	}
}}
```

Test with `cue eval` and adjust the counting pattern if needed.

**Step 3: Write model/proj_enrichment.cue**

```cue
package lacuene

// Enrichment tiers: how many biological layers describe each gene?
enrichment: {
	tiers: {for k, v in genes {
		(k): {
			has_function:   v._in_go
			has_disease:    v._in_omim
			has_phenotype:  v._in_hpo
			has_protein:    v._in_uniprot
			has_experiment: v._in_facebase
		}
	}}
}
```

**Step 4: Validate all projections**

```bash
cue vet -c ./model/
cue export ./model/ -e gap_report.summary | python3 -m json.tool
cue export ./model/ -e gap_report.research_gaps | python3 -m json.tool
```

**Step 5: Commit**

```bash
git add model/proj_*.cue
git commit -m "Add projections: gap report, source provenance, enrichment tiers"
```

---

### Task 10: Summary Generator

**Files:**
- Create: `generators/to_summary.py`

**Step 1: Write generators/to_summary.py**

Python script that runs `cue export` and pretty-prints results.
Shows: per-gene table with source coverage, gap report, enrichment breakdown.

Output format:
```
=== lacuene: Neural Crest Gene Reconciliation ===
20 genes unified across 5 sources

Coverage:
  All 5 sources:  12 genes
  4 sources:       5 genes
  3 sources:       2 genes
  2 sources:       1 gene

Source Coverage:
  Gene Ontology:  20/20 (100%)
  OMIM:           18/20 (90%)
  HPO:            17/20 (85%)
  UniProt:        20/20 (100%)
  FaceBase:       14/20 (70%)

Research Gaps (OMIM disease but no FaceBase data):
  ZIC1 — [syndromes]
  ...

Per-Gene Detail:
  Symbol    GO  OMIM  HPO  UniProt  FaceBase  Phenotypes
  ------    --  ----  ---  -------  --------  ----------
  CHD7      ✓   ✓     ✓    ✓        ✓         CHARGE syndrome
  ...
```

**Step 2: Test + commit**

```bash
python3 generators/to_summary.py
git add generators/to_summary.py
git commit -m "Add summary generator: human-readable coverage report"
```

---

### Task 11: VizData Generator

**Files:**
- Create: `generators/to_vizdata.py`

Produces Cytoscape.js-compatible JSON. Same VizData schema as infra-graph.

**Step 1: Write generators/to_vizdata.py**

Node generation:
- One node per gene
- `data.id` = HGNC symbol
- `data.label` = symbol
- `data.type` = developmental role ("border_spec", "nc_specifier", "patterning")
- `data.size` = source coverage count (1-5)
- `data.color` = by role (blue/purple/red)

Edge generation:
- Parse HPO phenotypes: if two genes share a phenotype term, create edge
- Parse OMIM syndromes: if two genes share a syndrome, create edge
- `data.type` = "shared_phenotype" or "shared_syndrome"

Output: `output/vizdata.json`

**Step 2: Test + commit**

```bash
python3 generators/to_vizdata.py
# Verify JSON is valid
python3 -c "import json; d=json.load(open('output/vizdata.json')); print(f'{len(d[\"nodes\"])} nodes, {len(d[\"edges\"])} edges')"
git add generators/to_vizdata.py
git commit -m "Add VizData generator: Cytoscape.js graph of gene relationships"
```

---

### Task 12: README + ADDING-A-SOURCE

**Files:**
- Create: `README.md`
- Create: `ADDING-A-SOURCE.md`

**Step 1: Write README.md**

Should cover:
1. What this is (1 paragraph)
2. Quick start (`just rebuild`)
3. The 20 genes and why they were chosen
4. Architecture diagram (ASCII)
5. Example output (gap report snippet)
6. Comparison to the prior pipeline pipeline (1:1 mapping table)
7. How to add a source

**Step 2: Write ADDING-A-SOURCE.md**

Port from `prior pipeline/ADDING-A-SOURCE.md`. Same structure, biomedical terminology.
Include a concrete example: "Adding KEGG pathway data as a 6th source."

**Step 3: Commit**

```bash
git add README.md ADDING-A-SOURCE.md
git commit -m "Add README and ADDING-A-SOURCE documentation"
```

---

### Task 13: Final Validation + Polish

**Step 1: Full rebuild**

```bash
cd . && just rebuild
```

Should produce no errors and generate output/.

**Step 2: Run all recipes**

```bash
just summary
just check IRF6
just check PAX3
just gaps
just vizdata
just examples
```

**Step 3: Fix any issues found**

**Step 4: Final commit**

```bash
git add -A && git commit -m "Polish: fix any issues from full rebuild validation"
```

---

## Task Dependency Graph

```
Task 1 (scaffold) -> Task 2 (schema + genes)
Task 2 -> Task 3 (examples)
Task 2 -> Task 4 (GO normalizer)      \
Task 2 -> Task 5 (OMIM normalizer)     \
Task 2 -> Task 6 (HPO normalizer)       > can run in parallel
Task 2 -> Task 7 (UniProt normalizer)  /
Task 2 -> Task 8 (FaceBase normalizer)/
Tasks 4-8 -> Task 9 (projections)
Task 9 -> Task 10 (summary generator)
Task 9 -> Task 11 (VizData generator)
Tasks 10-11 -> Task 12 (README)
Task 12 -> Task 13 (final validation)
```

Tasks 4-8 (the 5 normalizers) are independent and can be dispatched in parallel.
