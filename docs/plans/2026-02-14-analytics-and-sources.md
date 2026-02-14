# Analytics & New Sources Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 4 new analytics dashboards using existing data, 4 new biomedical data sources, automated pipeline scheduling, and genome-wide scaling preparation.

**Architecture:** Tier 1 (tasks 1-4) adds computed analytics to `generators/to_site.py` and renders them as new dashboard sections in the site. Tier 2 (tasks 5-8) follows the existing normalizer plugin pattern: one normalizer per source, schema additions in `model/schema.cue`, projections in `model/proj_sources.cue`, and site integration. Tier 3 (tasks 9-10) adds GitHub Actions workflow and bulk-download infrastructure.

**Tech Stack:** Python 3.11, CUE v0.15.4, Jinja2, Cytoscape.js, requests, GitHub Actions

---

## Workstream A: Tier 1 Analytics (existing data, new insights)

### Task 1: Funding-to-Discovery Ratio

Compute and display which genes have lots of NIH funding but few publications (wasteful) vs. lots of publications but no NIH funding (organic momentum the agency isn't backing).

**Files:**
- Modify: `generators/to_site.py` — compute ratio per gene, pass to template
- Modify: `generators/templates/index.html.j2` — add Funding Intelligence section
- Modify: `generators/static/app.js` — render scatter plot and ranked lists
- Modify: `generators/static/style.css` — styles for new section
- Test: `tests/test_pipeline.py` — add test_funding_intelligence

**Step 1: Add analytics computation to `generators/to_site.py`**

After `weighted = cue_export("weighted_gaps")` (line ~160), add:

```python
# Funding-to-Discovery analytics
funding_intel = []
for sym in sorted(sources.keys()):
    gene = genes[sym]
    grants = gene.get("active_grant_count", 0)
    pubs = gene.get("pubmed_total", 0)
    recent = gene.get("pubmed_recent", 0)
    total_pubs = pubs if pubs else 0
    velocity = round(recent / total_pubs, 2) if total_pubs > 0 else 0

    # Funding efficiency: pubs per grant (higher = more productive)
    efficiency = round(total_pubs / grants, 1) if grants > 0 else None
    # Momentum without funding: high recent pubs, zero grants
    unfunded_momentum = recent > 5 and grants == 0
    # Funded but quiet: grants > 0 but few recent pubs
    funded_quiet = grants > 0 and recent < 3

    funding_intel.append({
        "symbol": sym,
        "grants": grants,
        "pubs": total_pubs,
        "recent": recent,
        "velocity": velocity,
        "efficiency": efficiency,
        "unfunded_momentum": unfunded_momentum,
        "funded_quiet": funded_quiet,
    })
```

Pass `funding_intel_json=json.dumps(funding_intel)` to the template render call.

**Step 2: Add UI section to `generators/templates/index.html.j2`**

After the Syndrome-Centric View section (before Portfolio Overlay), add a "Funding Intelligence" section with:
- A scatter plot area (canvas-based, grants on X, recent pubs on Y)
- Two ranked lists: "Unfunded Momentum" (high recent pubs, 0 grants) and "Funded but Quiet" (grants > 0, few recent pubs)

**Step 3: Add rendering JS to `generators/static/app.js`**

Render the scatter plot using a `<canvas>` element (no extra library needed — 95 points is trivial). Each dot colored by developmental role. Hover shows gene name. Click navigates to gene detail.

Render the two lists as gap-item divs (same pattern as existing gap-list and understudied-list).

**Step 4: Add test**

```python
def test_funding_intelligence():
    """Funding intelligence data is computed for all genes."""
    # This is computed in to_site.py, so we verify the site output contains it
    site_dir = REPO_ROOT / "output" / "site"
    index_html = (site_dir / "index.html").read_text()
    assert "Funding Intelligence" in index_html
    assert "FUNDING_INTEL" in index_html  # JS constant
```

**Step 5: Run tests, commit**

```bash
python3 tests/test_pipeline.py
git add generators/ tests/
git commit -m "feat: add funding-to-discovery ratio analytics"
```

---

### Task 2: Emerging Hotspots Detection

Genes where pub_recent/pub_total ratio is high but grant count is zero = field is moving but funders haven't noticed.

**Files:**
- Modify: `generators/to_site.py` — compute hotspot scores
- Modify: `generators/static/app.js` — render hotspot cards
- Modify: `generators/templates/index.html.j2` — add hotspot section within Funding Intelligence

**Step 1: Compute hotspot scores in `generators/to_site.py`**

Extend the `funding_intel` computation from Task 1:

```python
# Emerging hotspot score: high velocity + low/no grants + has disease association
hotspot_score = 0
if velocity > 0.4:
    hotspot_score += 3  # recent surge
if grants == 0:
    hotspot_score += 2  # no NIH funding
if gene.get("omim_syndromes"):
    hotspot_score += 2  # disease-relevant
if gene.get("pathogenic_count", 0) > 0:
    hotspot_score += 1  # clinical variants
# Add to funding_intel entry
funding_intel[-1]["hotspot_score"] = hotspot_score
```

**Step 2: Render hotspot cards in app.js**

Sort by hotspot_score descending, show top 10 as styled cards with: gene symbol, velocity arrow, pub count, syndrome, and a "why" blurb.

**Step 3: Test and commit**

```bash
python3 tests/test_pipeline.py
git add generators/
git commit -m "feat: add emerging hotspot detection"
```

---

### Task 3: Syndrome-Level Funding Analysis

Aggregate grants, publications, and FaceBase coverage by syndrome rather than by gene. A syndrome with 5 causal genes and zero active grants is a bigger story than any single gene gap.

**Files:**
- Modify: `generators/to_site.py` — compute syndrome funding aggregates
- Modify: `generators/static/app.js` — enhance syndrome table with funding columns
- Modify: `generators/templates/index.html.j2` — add funding columns to syndrome table

**Step 1: Compute syndrome funding aggregates in `generators/to_site.py`**

```python
syndrome_funding = {}
for sym in sorted(sources.keys()):
    gene = genes[sym]
    for syn in gene.get("omim_syndromes", []):
        name = syn.split(",")[0].strip() if "," in syn else syn
        if name not in syndrome_funding:
            syndrome_funding[name] = {
                "name": name, "genes": [], "total_grants": 0,
                "total_pubs": 0, "total_recent": 0,
                "fb_count": 0, "trial_count": 0,
            }
        sf = syndrome_funding[name]
        sf["genes"].append(sym)
        sf["total_grants"] += gene.get("active_grant_count", 0)
        sf["total_pubs"] += gene.get("pubmed_total", 0)
        sf["total_recent"] += gene.get("pubmed_recent", 0)
        if sources[sym].get("in_facebase", False):
            sf["fb_count"] += 1
        sf["trial_count"] += gene.get("active_trial_count", 0)
```

Pass `syndrome_funding_json=json.dumps(list(syndrome_funding.values()))` to template.

**Step 2: Enhance syndrome table**

Add "Grants" and "Trials" columns to the existing syndrome table. Sort syndromes with zero grants to the top (biggest funding gaps). Color-code the grants column (red for 0, green for >0).

**Step 3: Test and commit**

```bash
python3 tests/test_pipeline.py
git add generators/
git commit -m "feat: add syndrome-level funding analysis"
```

---

### Task 4: Translational Readiness Score

Composite score: ClinVar pathogenic (clinical relevance proven) + ClinicalTrials (translation attempted) + high pLI (essential gene) + GTEx craniofacial expression (tissue-relevant) + protein structure available (when we add AlphaFold in Task 8).

**Files:**
- Modify: `generators/to_site.py` — compute translational score per gene
- Modify: `generators/static/app.js` — render as bar chart + ranked list
- Modify: `generators/templates/index.html.j2` — add Translational Readiness section
- Modify: `generators/static/style.css` — readiness bar styles

**Step 1: Compute translational readiness in `generators/to_site.py`**

```python
for entry in gene_rows:
    sym = entry["symbol"]
    gene = genes[sym]
    tr_score = 0
    tr_components = []

    # Clinical relevance (ClinVar pathogenic variants)
    path_count = gene.get("pathogenic_count", 0)
    if path_count > 10:
        tr_score += 3; tr_components.append("many pathogenic variants")
    elif path_count > 0:
        tr_score += 2; tr_components.append("pathogenic variants")

    # Active clinical trials
    trials = gene.get("active_trial_count", 0)
    if trials > 0:
        tr_score += 3; tr_components.append(f"{trials} clinical trial(s)")

    # Genetic constraint (essential gene)
    pli = gene.get("pli_score")
    if pli is not None and pli > 0.9:
        tr_score += 2; tr_components.append("highly constrained")

    # Craniofacial tissue expression
    cf_exp = gene.get("craniofacial_expression")
    if cf_exp is not None and cf_exp > 10:
        tr_score += 2; tr_components.append("craniofacial expression")

    # Disease association
    if gene.get("omim_syndromes"):
        tr_score += 1; tr_components.append("Mendelian syndrome")

    entry["translational_score"] = tr_score
    entry["translational_components"] = tr_components
```

**Step 2: Render readiness dashboard**

Horizontal bar chart ranking genes by translational score. Each bar segmented by component (color-coded). Click navigates to gene detail. Top 10 highlighted.

**Step 3: Test and commit**

```bash
python3 tests/test_pipeline.py
git add generators/
git commit -m "feat: add translational readiness scoring"
```

---

## Workstream B: New Data Sources (4 normalizers)

Each task follows ADDING-A-SOURCE.md exactly. Schema additions, normalizer, projections, site integration.

### Task 5: ORPHANET — Disease Prevalence

The single most impactful new source. Transforms gap analysis from "scientifically interesting" to "affects N patients."

**API:** Orphadata.com provides free XML/JSON bulk downloads. Use `https://www.orphadata.com/data/xml/en_product1.xml` for disease-gene associations with prevalence classes.

**Files:**
- Create: `normalizers/from_orphanet.py`
- Create: `data/orphanet/` (cache directory)
- Modify: `model/schema.cue` — add ORPHANET fields
- Create: `model/orphanet.cue` (generated)
- Modify: `model/proj_sources.cue` — add in_orphanet
- Modify: `generators/to_site.py` — add orphanet to source_names/urls/keys
- Modify: `generators/static/app.js` — show prevalence in gene detail
- Modify: `justfile` — add normalize-orphanet recipe
- Test: `tests/test_pipeline.py` — update test_twelve_source_flags to expect 13

**Step 1: Add schema fields to `model/schema.cue`**

After the STRING block, add:

```cue
// ORPHANET-owned fields (rare disease prevalence)
orphanet_id: *"" | string // Orphanet disorder number
_in_orphanet: *false | true
orphanet_prevalence?: string // "1-9 / 100 000", "<1 / 1 000 000", etc.
orphanet_inheritance?: string // "Autosomal dominant", etc.
orphanet_disorders?: [...#OrphanetDisorder]
```

Add struct:

```cue
#OrphanetDisorder: {
    orpha_code: string
    name:       string
    prevalence?: string
    inheritance?: string
}
```

**Step 2: Write normalizer `normalizers/from_orphanet.py`**

```python
#!/usr/bin/env python3
"""Normalizer: ORPHANET (Orphadata) -> model/orphanet.cue

Downloads the Orphadata XML product1 (genes-diseases) and product9
(prevalence), cross-references by OrphaCode, and emits CUE.

Cache: data/orphanet/orphanet_cache.json
"""
import json, sys, time, xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "normalizers"))
from genes import GENES
from pipeline import PipelineReport, escape_cue_string
from utils import fetch_with_retry

CACHE_DIR = REPO_ROOT / "data" / "orphanet"
CACHE_FILE = CACHE_DIR / "orphanet_cache.json"
OUTPUT_FILE = REPO_ROOT / "model" / "orphanet.cue"

# Orphadata bulk files (free, no auth)
GENE_DISEASE_URL = "https://www.orphadata.com/data/xml/en_product6.xml"
PREVALENCE_URL = "https://www.orphadata.com/data/xml/en_product9_prev.xml"
```

Follow the same pattern as `from_gnomad.py`: cache → fetch → generate_cue → write.

Key logic:
1. Download en_product6.xml (gene-disease associations)
2. Parse XML, build map: gene_symbol → list of disorders
3. Download en_product9_prev.xml (prevalence by OrphaCode)
4. Merge prevalence into disorder entries
5. Emit CUE with `_in_orphanet: true`, `orphanet_disorders: [...]`

**Step 3: Update projections**

In `model/proj_sources.cue`, add: `in_orphanet: v._in_orphanet`

**Step 4: Update site integration**

In `generators/to_site.py`, add to source_names/urls/filter_keys dicts:
```python
"in_orphanet": "ORPHANET"  # source_names
"in_orphanet": "https://www.orpha.net/"  # source_urls
"in_orphanet": "orphanet"  # filter_keys
```

In gene_rows builder, add:
```python
"orphanet": flags.get("in_orphanet", False),
"prevalence": gene.get("orphanet_prevalence", ""),
"orphanet_disorders": gene.get("orphanet_disorders", []),
```

**Step 5: Add prevalence to gene detail panel in app.js**

Show prevalence badge in detail panel and gene table (new column).

**Step 6: Update tests**

Change `test_twelve_source_flags` to `test_thirteen_source_flags` (or parameterize).

**Step 7: Add justfile recipe, commit**

```bash
cue vet -c ./model/
python3 tests/test_pipeline.py
git add normalizers/from_orphanet.py model/ generators/ tests/ justfile
git commit -m "feat: add ORPHANET disease prevalence source"
```

---

### Task 6: Open Targets — Drug Target Status

Is anyone developing therapeutics for these genes? A known drug target with no craniofacial research = massive translational opportunity.

**API:** `https://api.platform.opentargets.io/api/v4/graphql` — free, no auth, GraphQL.

**Files:**
- Create: `normalizers/from_opentargets.py`
- Create: `data/opentargets/` (cache directory)
- Modify: `model/schema.cue` — add Open Targets fields
- Create: `model/opentargets.cue` (generated)
- Modify: `model/proj_sources.cue` — add in_opentargets
- Modify: `generators/to_site.py` — integrate
- Modify: `generators/static/app.js` — show drug info in detail
- Modify: `justfile`
- Test: `tests/test_pipeline.py`

**Schema additions:**

```cue
// Open Targets-owned fields (drug target status)
_in_opentargets: *false | true
opentargets_id: *"" | string // Ensembl gene ID
is_drug_target?: bool
drug_count?: int
max_clinical_phase?: int // 0-4
opentargets_drugs?: [...#DrugEntry]
```

```cue
#DrugEntry: {
    drug_name:  string
    drug_type:  string // "Small molecule", "Antibody", etc.
    mechanism?: string
    phase:      int // clinical trial phase (1-4)
    disease?:   string
}
```

**Normalizer query:**

```graphql
query($ensemblId: String!) {
  target(ensemblId: $ensemblId) {
    id
    knownDrugs {
      count
      rows {
        drug { name mechanismOfAction drugType }
        phase
        disease { name }
      }
    }
  }
}
```

Map gene symbols to Ensembl IDs using the gnomAD cache (`data/gnomad/gnomad_cache.json` has `gene_id` for each symbol).

**Step: Normalizer, schema, projections, site integration, test, commit**

Same pattern as Task 5.

---

### Task 7: MGI/ZFIN — Model Organism Availability

Mouse and zebrafish model availability indicates how easy a gene is to study experimentally — low-hanging fruit for new grants.

**APIs:**
- MGI: `https://www.informatics.jax.org/api/gxd/markers/{symbol}` — check if mouse orthologs with phenotype data exist
- ZFIN: `https://zfin.org/action/api/marker/search?name={symbol}` — check if zebrafish models exist

**Files:**
- Create: `normalizers/from_models.py` (combined MGI + ZFIN)
- Create: `data/models/` (cache directory)
- Modify: `model/schema.cue` — add model organism fields
- Create: `model/models.cue` (generated)
- Modify: `model/proj_sources.cue`
- Modify: `generators/to_site.py`
- Modify: `generators/static/app.js`
- Modify: `justfile`
- Test: `tests/test_pipeline.py`

**Schema additions:**

```cue
// Model organism fields (MGI + ZFIN)
_in_models: *false | true
mouse_models?: int // count of MGI alleles/models
mouse_phenotypes?: [...string] // MP terms
zebrafish_models?: int
has_mouse_model?: bool
has_zebrafish_model?: bool
```

**Note:** This is ONE source ("models") combining MGI + ZFIN, since both answer the same question: "can you study this gene in a model organism?"

---

### Task 8: AlphaFold/PDB — Protein Structure Availability

Structure-known proteins are easier to study and drug. Quick API check per gene.

**API:** `https://alphafold.ebi.ac.uk/api/prediction/{uniprot_id}` — returns AlphaFold prediction metadata including confidence (pLDDT).

PDB: `https://search.rcsb.org/rcsbsearch/v2/query` — check if experimental structure exists.

**Files:**
- Create: `normalizers/from_structures.py`
- Create: `data/structures/` (cache directory)
- Modify: `model/schema.cue` — add structure fields
- Create: `model/structures.cue` (generated)
- Modify: `model/proj_sources.cue`
- Modify: `generators/to_site.py`
- Modify: `generators/static/app.js`
- Modify: `justfile`
- Test: `tests/test_pipeline.py`

**Schema additions:**

```cue
// Protein structure fields (AlphaFold + PDB)
_in_structures: *false | true
has_alphafold?: bool
alphafold_confidence?: number // mean pLDDT (0-100)
pdb_count?: int // number of experimental structures
has_experimental_structure?: bool
```

Use UniProt IDs from `genes.py` (already available as `GENES[sym]["uniprot"]`) to query AlphaFold.

---

## Workstream C: Operational Improvements

### Task 9: Automated Pipeline with Email Digest

GitHub Actions scheduled workflow that runs weekly, diffs against previous snapshot, and posts a summary to a GitHub Issue.

**Files:**
- Create: `.github/workflows/weekly-pipeline.yml`
- Modify: `generators/to_site.py` — add diff summary computation

**Workflow:**

```yaml
name: Weekly Pipeline Run
on:
  schedule:
    - cron: '0 6 * * 1'  # Every Monday 6am UTC
  workflow_dispatch:

jobs:
  pipeline:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install CUE
        run: |
          curl -fsSL https://github.com/cue-lang/cue/releases/download/v0.15.4/cue_v0.15.4_linux_amd64.tar.gz | tar xz
          sudo mv cue /usr/local/bin/
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run normalizers
        run: python3 normalizers/run_parallel.py --stale-days 7
      - name: Validate and generate
        run: |
          cue vet -c ./model/
          python3 generators/to_vizdata.py
          python3 generators/to_site.py
      - name: Compute diff summary
        id: diff
        run: python3 generators/diff_summary.py >> $GITHUB_OUTPUT
      - name: Post digest to issue
        if: steps.diff.outputs.has_changes == 'true'
        uses: peter-evans/create-or-update-comment@v4
        with:
          issue-number: 1  # Pin a "Weekly Digest" issue
          body: ${{ steps.diff.outputs.summary }}
      - name: Deploy
        uses: actions/deploy-pages@v4
```

**Create `generators/diff_summary.py`** — reads current and previous snapshot, computes diff, outputs markdown summary.

---

### Task 10: Genome-Wide Scaling Preparation

Prepare the infrastructure for scaling from 95 genes to ~20,000 protein-coding genes.

**Files:**
- Create: `normalizers/bulk_hgnc.py` — download full HGNC gene list
- Modify: `normalizers/genes.py` — support loading from bulk HGNC file
- Create: `normalizers/bulk_downloads.py` — coordinate bulk file downloads
- Modify: `normalizers/run_parallel.py` — add --genome-wide flag

**Key changes:**

1. `bulk_hgnc.py`: Download `https://ftp.ebi.ac.uk/pub/databases/genenames/hgnc/tsv/hgnc_complete_set.txt`, filter to protein-coding genes, output `data/hgnc/hgnc_complete.json` with symbol, NCBI ID, UniProt ID, Ensembl ID, OMIM ID per gene.

2. `normalizers/genes.py`: Add `load_genome_wide()` function that replaces the 95-gene GENES dict with the full ~19,200 set. Controlled by `--genome-wide` flag or env var.

3. `bulk_downloads.py`: Orchestrate bulk file downloads for the 6 sources that support it (GO, gnomAD, GTEx, ClinVar, ORPHANET, AlphaFold) and batch API calls for the rest.

4. Add `just normalize-genome-wide` recipe.

**This task is preparation only** — it sets up the infrastructure without running the full genome pipeline. The actual genome-wide run will be a separate operation.

---

## Integration Task

### Task 11: Wire Everything Together

After all sources and analytics are implemented:

1. Update `test_pipeline.py` to validate new source count (16 sources: 12 existing + ORPHANET + Open Targets + Models + Structures)
2. Update `ADDING-A-SOURCE.md` to reference 16 sources
3. Update CI workflows to include new sources
4. Regenerate site and verify all new sections render
5. Update about.html.j2 with new source descriptions
6. Final commit and deploy

```bash
just test
just site
git add -A
git commit -m "feat: complete analytics + new sources integration"
```

---

## Execution Order

**Parallel-safe groups:**

| Group | Tasks | Why parallel |
|-------|-------|-------------|
| A | 1, 2 (funding analytics) | Same files, do sequentially |
| B | 3, 4 (syndrome + translational) | Same files, do sequentially |
| C | 5 (ORPHANET) | Independent normalizer |
| D | 6 (Open Targets) | Independent normalizer |
| E | 7 (MGI/ZFIN) | Independent normalizer |
| F | 8 (AlphaFold/PDB) | Independent normalizer |

**Dependency chain:**
- Tasks 1-2 can run before Tasks 3-4
- Tasks 5-8 (normalizers) are fully independent of each other AND of Tasks 1-4
- Task 9 depends on all normalizers being done
- Task 10 is independent
- Task 11 depends on everything

**Recommended execution:**
1. Dispatch Tasks 5, 6, 7, 8 in parallel (normalizers)
2. While normalizers run, execute Tasks 1, 2, 3, 4 sequentially (analytics)
3. Execute Task 9 (pipeline automation)
4. Execute Task 10 (genome-wide prep)
5. Execute Task 11 (integration)
