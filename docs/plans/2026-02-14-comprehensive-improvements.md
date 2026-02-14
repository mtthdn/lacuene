# Comprehensive Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add 3 new data sources (gnomAD, NIH Reporter, GTEx), harden the pipeline, enhance analytics, and improve the site — 20 items across 5 workstreams.

**Architecture:** Each new source follows the existing normalizer pattern (cache in `data/`, write to `model/`, own fields exclusively). Pipeline improvements add shared infrastructure in `normalizers/pipeline.py`. Site extraction splits the 2194-line `to_site.py` into Jinja2 templates + static assets. All CUE projections updated for 10 sources.

**Tech Stack:** Python 3.11+, CUE, requests, jinja2 (new), concurrent.futures (stdlib)

---

## Group A: Infrastructure & Pipeline Hardening

### Task 1: Add requirements.txt and pin CUE version

**Files:**
- Create: `requirements.txt`
- Create: `.cue-version`
- Modify: `justfile`

**Step 1: Create requirements.txt**

```
requests>=2.28
jinja2>=3.1
```

**Step 2: Create .cue-version**

Run `cue version` to get current version, write to `.cue-version`.

**Step 3: Add version check to justfile**

Add at top of justfile:

```just
# Check CUE version matches pinned version
check-cue:
    @if [ -f .cue-version ]; then \
        expected=$(cat .cue-version | head -1); \
        actual=$(cue version 2>/dev/null | head -1 | awk '{print $NF}'); \
        if [ "$expected" != "$actual" ]; then \
            echo "WARNING: CUE version mismatch (expected $expected, got $actual)"; \
        fi; \
    fi
```

Make `validate` depend on `check-cue`.

**Step 4: Commit**

```bash
git add requirements.txt .cue-version justfile
git commit -m "Add requirements.txt and pin CUE version"
```

---

### Task 2: Structured error reporting — normalizers/pipeline.py

**Files:**
- Create: `normalizers/pipeline.py`
- Modify: all `normalizers/from_*.py` (import and use PipelineReport)

**Step 1: Create normalizers/pipeline.py**

```python
#!/usr/bin/env python3
"""Shared pipeline infrastructure for normalizers."""

import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GeneResult:
    symbol: str
    status: str  # "ok", "cached", "failed", "skipped"
    detail: str = ""


@dataclass
class PipelineReport:
    source: str
    results: list[GeneResult] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    def ok(self, symbol: str, detail: str = ""):
        self.results.append(GeneResult(symbol, "ok", detail))

    def cached(self, symbol: str, detail: str = ""):
        self.results.append(GeneResult(symbol, "cached", detail))

    def failed(self, symbol: str, detail: str = ""):
        self.results.append(GeneResult(symbol, "failed", detail))
        print(f"  WARNING: {symbol}: {detail}", file=sys.stderr)

    def skipped(self, symbol: str, detail: str = ""):
        self.results.append(GeneResult(symbol, "skipped", detail))

    def summary(self) -> str:
        elapsed = time.time() - self.start_time
        ok = sum(1 for r in self.results if r.status == "ok")
        cached = sum(1 for r in self.results if r.status == "cached")
        failed = sum(1 for r in self.results if r.status == "failed")
        skipped = sum(1 for r in self.results if r.status == "skipped")
        lines = [
            f"{self.source}: {ok + cached} genes ({ok} fetched, {cached} cached)",
        ]
        if failed:
            lines.append(f"  {failed} FAILED: {', '.join(r.symbol for r in self.results if r.status == 'failed')}")
        if skipped:
            lines.append(f"  {skipped} skipped")
        lines.append(f"  elapsed: {elapsed:.1f}s")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "elapsed_s": round(time.time() - self.start_time, 1),
            "ok": sum(1 for r in self.results if r.status == "ok"),
            "cached": sum(1 for r in self.results if r.status == "cached"),
            "failed": sum(1 for r in self.results if r.status == "failed"),
            "failures": [{"symbol": r.symbol, "detail": r.detail}
                         for r in self.results if r.status == "failed"],
        }


def escape_cue_string(s: str) -> str:
    """Escape a string for CUE literal output."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def check_staleness(cache_file: Path, max_age_days: int = 30) -> bool:
    """Return True if cache file is older than max_age_days or doesn't exist."""
    if not cache_file.exists():
        return True
    age = time.time() - cache_file.stat().st_mtime
    return age > max_age_days * 86400
```

**Step 2: Update each existing normalizer to use PipelineReport**

For each `normalizers/from_*.py`, replace ad-hoc print statements with `report.ok()`, `report.cached()`, `report.failed()`. At end of `main()`, print `report.summary()`. Use shared `escape_cue_string` from `pipeline.py`.

This is mechanical — each normalizer gets ~5 lines changed. Example for `from_clinvar.py`:

```python
from pipeline import PipelineReport, escape_cue_string

# In main():
report = PipelineReport("from_clinvar")
# Replace: print(f"  {symbol}: cached ...")
# With: report.cached(symbol, f"{cache[symbol]['pathogenic_count']} pathogenic")
# Replace: print(f"FAILED (skipping)")
# With: report.failed(symbol, "API error")
# At end: print(report.summary())
```

**Step 3: Commit**

```bash
git add normalizers/pipeline.py normalizers/from_*.py
git commit -m "Add structured error reporting to normalizers"
```

---

### Task 3: Staleness-aware refresh and parallel fetching

**Files:**
- Modify: `justfile`
- Create: `normalizers/run_parallel.py`

**Step 1: Add staleness check to justfile**

```just
# Refresh only stale sources (default: 30 days)
refresh stale_days="30":
    python3 normalizers/run_parallel.py --stale-days {{stale_days}}
```

**Step 2: Create normalizers/run_parallel.py**

```python
#!/usr/bin/env python3
"""Run all normalizers in parallel with staleness checking."""

import argparse
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NORMALIZERS = [
    "from_go.py", "from_omim.py", "from_hpo.py", "from_uniprot.py",
    "from_facebase.py", "from_clinvar.py", "from_pubmed.py",
    "from_gnomad.py", "from_nih_reporter.py", "from_gtex.py",
]

# Map normalizer to its cache file for staleness checking
CACHE_FILES = {
    "from_go.py": None,  # no cache file, always run
    "from_omim.py": None,
    "from_hpo.py": "data/hpo/phenotype.hpoa",
    "from_uniprot.py": None,
    "from_facebase.py": "data/facebase/facebase_cache.json",
    "from_clinvar.py": "data/clinvar/clinvar_cache.json",
    "from_pubmed.py": "data/pubmed/pubmed_cache.json",
    "from_gnomad.py": "data/gnomad/gnomad_cache.json",
    "from_nih_reporter.py": "data/nih_reporter/nih_reporter_cache.json",
    "from_gtex.py": "data/gtex/gtex_cache.json",
}


def is_stale(normalizer: str, max_age_days: int) -> bool:
    cache = CACHE_FILES.get(normalizer)
    if cache is None:
        return True
    path = REPO_ROOT / cache
    if not path.exists():
        return True
    import time
    age = time.time() - path.stat().st_mtime
    return age > max_age_days * 86400


def run_normalizer(name: str) -> tuple[str, int, str]:
    script = REPO_ROOT / "normalizers" / name
    if not script.exists():
        return name, -1, f"Script not found: {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    output = result.stdout + result.stderr
    return name, result.returncode, output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    to_run = []
    for name in NORMALIZERS:
        script = REPO_ROOT / "normalizers" / name
        if not script.exists():
            print(f"  skip {name} (not yet created)")
            continue
        if args.force or is_stale(name, args.stale_days):
            to_run.append(name)
        else:
            print(f"  skip {name} (cache fresh)")

    if not to_run:
        print("All caches fresh, nothing to do.")
        return

    print(f"Running {len(to_run)} normalizers in parallel...")
    failed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_normalizer, n): n for n in to_run}
        for future in as_completed(futures):
            name, rc, output = future.result()
            status = "OK" if rc == 0 else "FAILED"
            print(f"  [{status}] {name}")
            if output.strip():
                for line in output.strip().split("\n")[-3:]:
                    print(f"    {line}")
            if rc != 0:
                failed.append(name)

    if failed:
        print(f"\n{len(failed)} normalizer(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print("\nAll normalizers complete.")


if __name__ == "__main__":
    main()
```

**Step 3: Add parallel normalize to justfile**

```just
# Run normalizers in parallel
normalize-parallel:
    python3 normalizers/run_parallel.py --force
```

**Step 4: Commit**

```bash
git add normalizers/run_parallel.py justfile
git commit -m "Add parallel normalizer runner with staleness checking"
```

---

### Task 4: Integration test (5-gene subset)

**Files:**
- Create: `tests/test_pipeline.py`
- Modify: `justfile`

**Step 1: Create tests/test_pipeline.py**

Tests the full pipeline on 5 representative genes using cached data.
Validates CUE model structure, projection outputs, and source coverage.

```python
#!/usr/bin/env python3
"""Integration test: validates pipeline on 5-gene subset."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_GENES = ["SOX9", "IRF6", "PAX3", "RET", "MITF"]


def cue_export(expr: str) -> dict:
    result = subprocess.run(
        ["cue", "export", "./model/", "-e", expr],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert result.returncode == 0, f"cue export -e '{expr}' failed: {result.stderr}"
    return json.loads(result.stdout)


def test_model_validates():
    """CUE model passes validation."""
    result = subprocess.run(
        ["cue", "vet", "-c", "./model/"],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert result.returncode == 0, f"cue vet failed: {result.stderr}"


def test_gene_sources():
    """All 5 test genes have source flags."""
    sources = cue_export("gene_sources")
    for gene in TEST_GENES:
        assert gene in sources, f"{gene} missing from gene_sources"
        flags = sources[gene]
        assert isinstance(flags, dict)
        # At minimum, GO and OMIM should be present for all test genes
        assert flags.get("in_go", False), f"{gene} missing GO"
        assert flags.get("in_omim", False), f"{gene} missing OMIM"


def test_gap_report():
    """Gap report has expected structure."""
    gap = cue_export("gap_report")
    assert "summary" in gap
    assert "total" in gap["summary"]
    assert gap["summary"]["total"] >= 5
    assert "research_gaps" in gap


def test_enrichment():
    """Enrichment tiers exist for test genes."""
    enrichment = cue_export("enrichment")
    assert "tiers" in enrichment
    for gene in TEST_GENES:
        assert gene in enrichment["tiers"]


def test_gene_detail():
    """SOX9 has rich data from multiple sources."""
    genes = cue_export("genes")
    sox9 = genes["SOX9"]
    assert sox9["symbol"] == "SOX9"
    assert sox9["_in_go"] is True  # hidden field exported via genes
    assert len(sox9.get("go_terms", [])) > 10
    assert len(sox9.get("omim_syndromes", [])) > 0
    assert sox9.get("pubmed_total", 0) > 100


def test_funding_gaps():
    """Funding gaps projection works."""
    funding = cue_export("funding_gaps")
    assert "genes_assessed" in funding
    assert "critical" in funding
    assert "summary" in funding


def main():
    tests = [
        test_model_validates,
        test_gene_sources,
        test_gap_report,
        test_enrichment,
        test_gene_detail,
        test_funding_gaps,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except (AssertionError, Exception) as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Add to justfile**

```just
# Run integration tests
test:
    python3 tests/test_pipeline.py
```

**Step 3: Run tests**

```bash
just test
```

Expected: All 6 tests pass (using existing cached data).

**Step 4: Commit**

```bash
git add tests/test_pipeline.py justfile
git commit -m "Add integration test suite for pipeline validation"
```

---

## Group B: New Data Sources

### Task 5: gnomAD normalizer (constraint scores)

**Files:**
- Create: `normalizers/from_gnomad.py`
- Modify: `model/schema.cue` (add gnomAD fields)
- Model output: `model/gnomad.cue`
- Cache: `data/gnomad/gnomad_cache.json`

**Step 1: Add gnomAD fields to schema.cue**

After the PubMed block in `model/schema.cue`, add:

```cue
	// gnomAD-owned fields (population constraint data)
	gnomad_id: *"" | string  // Ensembl gene ID
	_in_gnomad:     *false | true
	pli_score?:     number  // probability of LoF intolerance (0-1)
	loeuf_score?:   number  // loss-of-function observed/expected upper bound
	oe_lof?:        number  // observed/expected ratio for LoF variants
	gnomad_gene_id?: string
```

**Step 2: Create normalizers/from_gnomad.py**

Query gnomAD GraphQL API at `https://gnomad.broadinstitute.org/api` for constraint metrics per gene. The query:

```graphql
{
  gene(gene_symbol: "SOX9", reference_genome: GRCh38) {
    gene_id
    gnomad_constraint {
      pLI
      oe_lof
      oe_lof_upper
    }
  }
}
```

Follow the same pattern as `from_clinvar.py`: cache results, write CUE, use `PipelineReport`.

**Step 3: Run and validate**

```bash
python3 normalizers/from_gnomad.py
cue vet -c ./model/
```

**Step 4: Commit**

```bash
git add normalizers/from_gnomad.py model/schema.cue model/gnomad.cue data/gnomad/
git commit -m "Add gnomAD source: constraint scores for 95 genes"
```

---

### Task 6: NIH Reporter normalizer (active grants)

**Files:**
- Create: `normalizers/from_nih_reporter.py`
- Modify: `model/schema.cue` (add NIH Reporter fields)
- Model output: `model/nih_reporter.cue`
- Cache: `data/nih_reporter/nih_reporter_cache.json`

**Step 1: Add NIH Reporter fields to schema.cue**

```cue
	// NIH Reporter-owned fields (active grant data)
	_in_nih_reporter: *false | true
	active_grant_count?: int
	nih_reporter_projects?: [...#NIHProject]
```

And add the type:

```cue
#NIHProject: {
	project_num:  string  // e.g. "R01DE028561"
	project_title: string
	pi_name?:     string
	org_name?:    string
	fiscal_year?: int
}
```

**Step 2: Create normalizers/from_nih_reporter.py**

Query NIH Reporter v2 API at `https://api.reporter.nih.gov/v2/projects/search`.
POST body:

```json
{
  "criteria": {
    "advanced_text_search": {
      "operator": "and",
      "search_field": "terms",
      "search_text": "SOX9 craniofacial"
    },
    "agencies": ["NIDCR"],
    "is_active": true
  },
  "limit": 10,
  "offset": 0
}
```

Follow existing normalizer pattern. Cache in `data/nih_reporter/`.

**Step 3: Run and validate**

```bash
python3 normalizers/from_nih_reporter.py
cue vet -c ./model/
```

**Step 4: Commit**

```bash
git add normalizers/from_nih_reporter.py model/schema.cue model/nih_reporter.cue data/nih_reporter/
git commit -m "Add NIH Reporter source: active NIDCR grants for 95 genes"
```

---

### Task 7: GTEx normalizer (tissue expression)

**Files:**
- Create: `normalizers/from_gtex.py`
- Modify: `model/schema.cue` (add GTEx fields)
- Model output: `model/gtex.cue`
- Cache: `data/gtex/gtex_cache.json`

**Step 1: Add GTEx fields to schema.cue**

```cue
	// GTEx-owned fields (tissue expression data)
	gtex_id: *"" | string  // Ensembl gene ID
	_in_gtex:     *false | true
	top_tissues?: [...#GTExTissue]
	craniofacial_expression?: number  // TPM in relevant tissues
```

And:

```cue
#GTExTissue: {
	tissue:     string  // e.g. "Brain - Cortex"
	median_tpm: number
}
```

**Step 2: Create normalizers/from_gtex.py**

Use GTEx Portal API: `https://gtexportal.org/api/v2/expression/medianGeneExpression`
with params `gencodeId=<ensembl_id>&datasetId=gtex_v8`.

Need to map HGNC symbols to Ensembl IDs. Use the MyGene.info API for bulk lookup:
`https://mygene.info/v3/query?q=symbol:SOX9&species=human&fields=ensembl.gene`

Top 5 tissues by TPM, plus a computed `craniofacial_expression` averaging
relevant tissues (salivary gland, nerve - tibial, skin - sun exposed, brain - cerebellum).

**Step 3: Run and validate**

```bash
python3 normalizers/from_gtex.py
cue vet -c ./model/
```

**Step 4: Commit**

```bash
git add normalizers/from_gtex.py model/schema.cue model/gtex.cue data/gtex/
git commit -m "Add GTEx source: tissue expression for 95 genes"
```

---

## Group C: Schema & Model Enhancements

### Task 8: Gene list as CUE

**Files:**
- Create: `model/gene_list.cue`
- Modify: `normalizers/genes.py` (add export function)

**Step 1: Add CUE export to genes.py**

Add a function that writes the gene list as a CUE file:

```python
def export_cue(output_path: str):
    """Export gene list as CUE for model self-description."""
    lines = [
        "package lacuene",
        "",
        "// Canonical gene list with HGNC symbols and developmental roles.",
        "// Auto-generated from normalizers/genes.py — do not hand-edit.",
        "",
    ]
    for symbol in sorted(GENES.keys()):
        role = SYMBOL_TO_ROLE.get(symbol, "unknown")
        lines.append(f'genes: "{symbol}": symbol: "{symbol}"')
    lines.append("")
    with open(output_path, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    import os
    output = os.path.join(os.path.dirname(__file__), "..", "model", "gene_list.cue")
    export_cue(output)
    print(f"Exported {len(GENES)} genes to {output}")
```

**Step 2: Run and validate**

```bash
python3 normalizers/genes.py
cue vet -c ./model/
```

**Step 3: Commit**

```bash
git add normalizers/genes.py model/gene_list.cue
git commit -m "Export canonical gene list as CUE for model self-description"
```

---

### Task 9: Update projections for 10 sources

**Files:**
- Modify: `model/proj_sources.cue`
- Modify: `model/proj_enrichment.cue`
- Modify: `model/proj_gap_report.cue`
- Modify: `model/proj_funding_gaps.cue`

**Step 1: Update proj_sources.cue**

Add the 3 new source flags:

```cue
gene_sources: {for k, v in genes {
	(k): {
		in_go:           v._in_go
		in_omim:         v._in_omim
		in_hpo:          v._in_hpo
		in_uniprot:      v._in_uniprot
		in_facebase:     v._in_facebase
		in_clinvar:      v._in_clinvar
		in_pubmed:       v._in_pubmed
		in_gnomad:       v._in_gnomad
		in_nih_reporter: v._in_nih_reporter
		in_gtex:         v._in_gtex
	}
}}
```

**Step 2: Update proj_enrichment.cue**

Add:
```cue
has_constraint: v._in_gnomad
has_funding:    v._in_nih_reporter
has_expression: v._in_gtex
```

**Step 3: Update proj_gap_report.cue**

Add `_c_gnomad`, `_c_nih_reporter`, `_c_gtex` to `_source_flags`.
Add `missing_gnomad`, `missing_nih_reporter`, `missing_gtex` lists.
Update `_all_*` counters.

**Step 4: Update proj_funding_gaps.cue**

Add:
```cue
has_constraint: v._in_gnomad
has_funding:    v._in_nih_reporter
has_expression: v._in_gtex
if v.pli_score != _|_ {pli_score: v.pli_score}
if v.active_grant_count != _|_ {grant_count: v.active_grant_count}
```

**Step 5: Validate**

```bash
cue vet -c ./model/
```

**Step 6: Commit**

```bash
git add model/proj_*.cue
git commit -m "Update all projections for 10-source model"
```

---

### Task 10: Weighted gap scoring

**Files:**
- Create: `model/proj_weighted_gaps.cue`
- Modify: `justfile` (add export)

**Step 1: Create proj_weighted_gaps.cue**

```cue
package lacuene

// Weighted gap priority scoring.
// Higher score = higher funding priority for NIDCR.
//
// Scoring:
//   +5 per OMIM syndrome
//   +3 if has HPO phenotypes (>10 phenotypes)
//   +10 if NO FaceBase data (the key gap)
//   +3 if high constraint (pLI > 0.9)
//   +2 per 50 pathogenic ClinVar variants (capped at 10)
//   -2 per active NIH grant (already funded)
//   +1 if low publications (<10)

weighted_gaps: {for k, v in genes {
	(k): {
		symbol: k

		// Component scores (computed from available data)
		_syndrome_score: len(v.omim_syndromes) * 5 if v.omim_syndromes != _|_ else 0
		_phenotype_score: 3 if v._in_hpo && v.phenotypes != _|_ && len(v.phenotypes) > 10 else 0
		_facebase_gap: 10 if !v._in_facebase else 0
		_variant_score: v.pathogenic_count / 50 * 2 if v.pathogenic_count != _|_ else 0
		_pub_understudied: 1 if v.pubmed_total != _|_ && v.pubmed_total < 10 else 0

		// Compute total priority score
		priority_score: _syndrome_score + _phenotype_score + _facebase_gap + _variant_score + _pub_understudied

		// Metadata for display
		has_disease:    v._in_omim
		has_experiment: v._in_facebase
		if v.omim_syndromes != _|_ {syndrome_count: len(v.omim_syndromes)}
		if v.pubmed_total != _|_ {pub_count: v.pubmed_total}
		if v.pathogenic_count != _|_ {variant_count: v.pathogenic_count}
	}
}}
```

Note: CUE doesn't support inline conditionals like Python. Use CUE guard syntax instead. The implementer should use proper CUE conditional syntax:

```cue
_syndrome_score: *0 | int
if v.omim_syndromes != _|_ { _syndrome_score: len(v.omim_syndromes) * 5 }
```

**Step 2: Add to justfile generate target**

```just
cue export ./model/ -e weighted_gaps > output/weighted_gaps.json
```

**Step 3: Validate and test**

```bash
cue vet -c ./model/
cue export ./model/ -e 'weighted_gaps["SOX9"]' | python3 -m json.tool
```

**Step 4: Commit**

```bash
git add model/proj_weighted_gaps.cue justfile
git commit -m "Add weighted gap scoring for funding prioritization"
```

---

## Group D: VizData & Analytics Enhancements

### Task 11: GO pathway cluster edges in VizData

**Files:**
- Modify: `generators/to_vizdata.py`

**Step 1: Add pathway edge builder**

In `to_vizdata.py`, add a new function `build_pathway_edges()` that:
1. Indexes GO biological_process terms (aspect "P") per gene
2. Creates edges for genes sharing process terms (2-8 genes, same as phenotype threshold)
3. Edge type: `"shared_pathway"`

```python
def build_pathway_edges(genes_data: dict) -> list[dict]:
    """Create edges between genes sharing GO biological process terms."""
    process_index: dict[str, set[str]] = defaultdict(set)
    for sym, gene in genes_data.items():
        for term in gene.get("go_terms", []):
            if term.get("aspect") == "P":
                process_index[term["term_name"]].add(sym)

    edges = []
    edge_set = set()
    for process, syms in process_index.items():
        if 2 <= len(syms) <= 8:
            sym_list = sorted(syms)
            for i in range(len(sym_list)):
                for j in range(i + 1, len(sym_list)):
                    key = (sym_list[i], sym_list[j], "shared_pathway")
                    if key not in edge_set:
                        edge_set.add(key)
                        edges.append({
                            "data": {
                                "source": sym_list[i],
                                "target": sym_list[j],
                                "type": "shared_pathway",
                                "label": process,
                            }
                        })
    return edges
```

**Step 2: Merge into main edge list**

In `main()`, after `edges = build_edges(genes_data)`:

```python
pathway_edges = build_pathway_edges(genes_data)
edges.extend(pathway_edges)
```

Update the edge breakdown print to include pathway edges.

**Step 3: Validate**

```bash
just vizdata
```

Check that pathway edges appear in `output/vizdata.json`.

**Step 4: Commit**

```bash
git add generators/to_vizdata.py
git commit -m "Add GO pathway cluster edges to VizData graph"
```

---

### Task 12: Publication trend analysis

**Files:**
- Modify: `generators/to_vizdata.py` (add trend data to nodes)
- Modify: `generators/to_site.py` or templates (display trends)

**Step 1: Compute publication velocity**

In `to_vizdata.py`, `build_nodes()`, add trend computation per gene:

```python
pub_recent = genes_data.get(sym, {}).get("pubmed_recent", 0)
pub_total = genes_data.get(sym, {}).get("pubmed_total", 0)

# Velocity: recent (last 5 years) as fraction of total
if pub_total > 0:
    velocity = round(pub_recent / pub_total, 2)
    if velocity > 0.5:
        trend = "rising"
    elif velocity > 0.2:
        trend = "stable"
    else:
        trend = "declining"
else:
    velocity = 0
    trend = "none"
```

Add `pub_recent`, `velocity`, and `trend` to node data.

**Step 2: Commit**

```bash
git add generators/to_vizdata.py
git commit -m "Add publication trend analysis to VizData nodes"
```

---

### Task 13: Comparative portfolio analysis (pre-loaded NIDCR sets)

**Files:**
- Create: `data/portfolios/nidcr_known.json`
- Wire into site generator (Task 17-18 will handle display)

**Step 1: Create known portfolio data**

Create `data/portfolios/nidcr_known.json` with the 22 FaceBase-covered genes as a baseline NIDCR portfolio:

```json
{
  "name": "NIDCR FaceBase Portfolio",
  "description": "Genes with existing FaceBase experimental datasets",
  "genes": ["AXIN2", "BMP4", "CTNNB1", "DLX2", "DLX3", "DLX5", "FGF8", "FGFR1", "FGFR2", "HAND2", "IRF6", "MSX1", "RUNX2", "SHH", "SOX2", "SOX9", "TBX1", "TFAP2A", "TFAP2B", "TGFBR2", "TWIST1", "WNT1"],
  "source": "FaceBase DERIVA catalog"
}
```

**Step 2: Commit**

```bash
git add data/portfolios/
git commit -m "Add pre-loaded NIDCR portfolio for comparison analysis"
```

---

## Group E: Site Improvements

### Task 14: Extract to_site.py into Jinja2 templates

This is the largest single task. The 2194-line `to_site.py` becomes:

**Files:**
- Create: `generators/templates/base.html.j2` (CSS + layout)
- Create: `generators/templates/index.html.j2` (main page)
- Create: `generators/templates/about.html.j2` (about page)
- Create: `generators/static/style.css` (extracted CSS)
- Create: `generators/static/app.js` (extracted JS)
- Rewrite: `generators/to_site.py` (~200 lines, data injection + render)

**Step 1: Install jinja2**

```bash
pip install jinja2
```

**Step 2: Extract CSS from build_html()**

Read the current `to_site.py` `build_html()` function. Everything inside `<style>...</style>` goes to `generators/static/style.css`. Replace double-braces `{{` with `{` (un-escape from f-string).

**Step 3: Extract JS from build_html()**

Everything inside `<script>` tags (excluding Cytoscape CDN) goes to `generators/static/app.js`. Template variables become `const DATA = {{ data_json }};` Jinja2 expressions.

**Step 4: Create base.html.j2**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{% block title %}lacuene{% endblock %}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible+Next:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{% include "style.css" %}</style>
{% block head_extra %}{% endblock %}
</head>
<body>
<a href="#main" class="skip-link">Skip to content</a>
{% block body %}{% endblock %}
</body>
</html>
```

Note: CSS/JS are inlined via `{% include %}` to keep the site as a single HTML file (no static file server needed).

**Step 5: Create index.html.j2**

Convert the f-string HTML in `build_html()` to Jinja2 template syntax:
- `{variable}` → `{{ variable }}`
- `{{` literal braces → `{` (they were escaped for f-strings)
- Loops use `{% for ... %}{% endfor %}`

**Step 6: Create about.html.j2**

Same conversion for `build_about_html()`.

**Step 7: Rewrite to_site.py**

```python
#!/usr/bin/env python3
"""Site generator using Jinja2 templates."""

import json
import os
import subprocess
import sys
from datetime import date
from glob import glob
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"


def cue_export(expr: str) -> dict | list:
    result = subprocess.run(
        ["cue", "export", "./model/", "-e", expr],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    if result.returncode != 0:
        print(f"ERROR: cue export -e '{expr}' failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    # ... (same data loading as current to_site.py main())
    # ... (same snapshot logic)

    env = Environment(loader=FileSystemLoader([str(TEMPLATE_DIR), str(STATIC_DIR)]))

    # Render index
    template = env.get_template("index.html.j2")
    html = template.render(
        vizdata_json=json.dumps(vizdata),
        gene_rows_json=json.dumps(gene_rows),
        # ... all template variables
    )

    # Render about
    about_template = env.get_template("about.html.j2")
    about_html = about_template.render(...)

    # Write outputs
    out_dir = REPO_ROOT / "output" / "site"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html)
    (out_dir / "about.html").write_text(about_html)
```

**Step 8: Validate output matches**

```bash
just site
diff output/site/index.html output/site/index.html.bak
```

The output HTML should be functionally identical.

**Step 9: Commit**

```bash
git add generators/templates/ generators/static/ generators/to_site.py requirements.txt
git commit -m "Extract site generator into Jinja2 templates"
```

---

### Task 15: Wire temporal diffing into site

**Files:**
- Modify: `generators/templates/index.html.j2` (or `generators/static/app.js`)
- Modify: `generators/to_site.py` (compute diffs)

**Step 1: Compute snapshot diffs in to_site.py**

After loading snapshots, compute diff between most recent two:

```python
if len(snapshots) >= 2:
    prev = snapshots[-2]
    curr = snapshots[-1]
    diff = {
        "prev_date": prev["date"],
        "curr_date": curr["date"],
        "new_facebase": sorted(set(curr["facebase_symbols"]) - set(prev["facebase_symbols"])),
        "lost_facebase": sorted(set(prev["facebase_symbols"]) - set(curr["facebase_symbols"])),
        "gaps_closed": sorted(set(prev["gap_symbols"]) - set(curr["gap_symbols"])),
        "gaps_opened": sorted(set(curr["gap_symbols"]) - set(prev["gap_symbols"])),
    }
else:
    diff = None
```

Pass `diff` and `snapshots` to template.

**Step 2: Add change history panel to index template**

Add a "Changes Since Last Snapshot" card that shows:
- Date range
- Genes that gained FaceBase data
- Gaps that closed/opened
- "No changes" if diff is empty

**Step 3: Commit**

```bash
git add generators/to_site.py generators/templates/index.html.j2
git commit -m "Wire temporal diffing into site change history panel"
```

---

### Task 16: Mobile responsiveness

**Files:**
- Modify: `generators/static/style.css`

**Step 1: Add media queries**

At the end of `style.css`:

```css
/* Mobile: stack layout */
@media (max-width: 768px) {
  .header { padding: 1rem; }
  .header h1 { font-size: 1.3rem; }
  .container { padding: 1rem; }
  .query-grid { grid-template-columns: 1fr; }
  .filter-grid { gap: 0.3rem; }
  .gene-table { font-size: 0.7rem; }
  .gene-table th, .gene-table td { padding: 0.4rem 0.3rem; }
  #cy { height: 300px !important; }
  .detail-panel { width: 100%; right: 0; }
  .filter-ranges { flex-direction: column; }
}

/* Tablet */
@media (max-width: 1024px) {
  .query-grid { grid-template-columns: repeat(2, 1fr); }
  .detail-panel { width: 50%; }
}
```

**Step 2: Test at multiple widths**

Open site in browser, resize to 375px, 768px, 1024px. Verify layout doesn't overflow.

**Step 3: Commit**

```bash
git add generators/static/style.css
git commit -m "Add mobile responsiveness with CSS media queries"
```

---

### Task 17: Accessibility improvements

**Files:**
- Modify: `generators/templates/index.html.j2`
- Modify: `generators/templates/base.html.j2`
- Modify: `generators/static/style.css`
- Modify: `generators/static/app.js`

**Step 1: Add skip-to-content link**

Already in base.html.j2 from Task 14. Add CSS:

```css
.skip-link {
  position: absolute;
  top: -40px;
  left: 0;
  background: var(--accent);
  color: var(--bg);
  padding: 8px 16px;
  z-index: 100;
  font-weight: 600;
}
.skip-link:focus { top: 0; }
```

**Step 2: Add ARIA labels to tri-state toggles**

In the filter toggle JS, add:
```javascript
btn.setAttribute('role', 'switch');
btn.setAttribute('aria-checked', state === 'required' ? 'true' : 'false');
btn.setAttribute('aria-label', `Filter: ${sourceName} — ${state}`);
```

**Step 3: Add ARIA to gene table**

```html
<table class="gene-table" role="grid" aria-label="Gene source coverage">
  <thead role="rowgroup">
    <tr role="row">
      <th role="columnheader" aria-sort="none">Gene</th>
      ...
```

**Step 4: Add keyboard navigation for detail panel**

```javascript
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeDetailPanel();
});
```

**Step 5: Commit**

```bash
git add generators/templates/ generators/static/
git commit -m "Improve accessibility: ARIA labels, keyboard nav, skip link"
```

---

### Task 18: Update to_summary.py for 10 sources

**Files:**
- Modify: `generators/to_summary.py`

**Step 1: Update source labels and counting**

Add ClinVar, PubMed, gnomAD, NIH Reporter, GTEx to the source list. Update tier counting from 5 to 10. Update the per-gene table to show all 10 sources.

**Step 2: Commit**

```bash
git add generators/to_summary.py
git commit -m "Update summary generator for 10-source model"
```

---

### Task 19: Update justfile for complete pipeline

**Files:**
- Modify: `justfile`

**Step 1: Update normalize target**

Add the 3 new normalizers to the `normalize` target:

```just
normalize:
    python3 normalizers/from_go.py
    python3 normalizers/from_omim.py
    python3 normalizers/from_hpo.py
    python3 normalizers/from_uniprot.py
    python3 normalizers/from_facebase.py
    python3 normalizers/from_clinvar.py
    python3 normalizers/from_pubmed.py
    python3 normalizers/from_gnomad.py
    python3 normalizers/from_nih_reporter.py
    python3 normalizers/from_gtex.py
```

**Step 2: Update generate target**

Add weighted_gaps export:

```just
generate: validate
    mkdir -p output
    cue export ./model/ -e gap_report > output/gap_report.json
    cue export ./model/ -e enrichment > output/enrichment.json
    cue export ./model/ -e gene_sources > output/sources.json
    cue export ./model/ -e funding_gaps > output/funding_gaps.json
    cue export ./model/ -e weighted_gaps > output/weighted_gaps.json
    @echo "Generated: $(du -sh output | cut -f1) in output/"
```

**Step 3: Commit**

```bash
git add justfile
git commit -m "Update justfile for 10-source pipeline with weighted gaps"
```

---

### Task 20: Final validation and integration test

**Step 1: Run full pipeline validation**

```bash
cue vet -c ./model/
just generate
just test
just vizdata
just site
```

**Step 2: Verify all outputs**

- `output/sources.json` has 10 source flags
- `output/gap_report.json` has 10 missing_* lists
- `output/weighted_gaps.json` has priority scores
- `output/vizdata.json` has pathway edges and trend data
- `output/site/index.html` renders with all new features

**Step 3: Commit any fixes**

```bash
git add -A
git commit -m "Final integration: 10-source pipeline validated"
```
