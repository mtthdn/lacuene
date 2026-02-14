# Grant Gap Finder Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PubMed as 7th source, then rebuild the site as a grant-gap-finder dashboard that helps an NIDCR program officer identify underfunded craniofacial research genes.

**Architecture:** Same normalizer→CUE→generator pipeline. PubMed normalizer queries NCBI E-utilities for publication counts. Site generator (`to_site.py`) is rewritten with three query-card layout: funding gaps, understudied genes, and landscape graph. All data flows through the existing CUE unification model.

**Tech Stack:** Python 3, CUE, NCBI E-utilities (PubMed), Cytoscape.js, static HTML

---

## Pre-requisites: Commit existing agent work

The following files were modified by parallel agents but not yet committed. Commit them before starting.

```bash
git add normalizers/genes.py generators/to_vizdata.py generators/to_site.py \
  normalizers/from_clinvar.py model/schema.cue model/proj_sources.cue \
  model/proj_enrichment.cue model/proj_gap_report.cue justfile
git commit -m "Expand to 95 genes, add ClinVar source, site improvements

- genes.py: 20 -> 95 neural crest genes across 8 developmental roles
- from_clinvar.py: 6th normalizer (NCBI E-utilities)
- schema.cue: ClinVar fields + #ClinVarVariant type
- proj_*.cue: ClinVar added to all projections
- to_vizdata.py: 8 role colors, expanded ROLE_LABELS
- to_site.py: PubMed/OMIM/ClinVar links, CSV export, dynamic legend
- justfile: normalize-clinvar recipe"
```

---

### Task 1: Write the PubMed normalizer

**Files:**
- Create: `normalizers/from_pubmed.py`
- Create: `data/pubmed/` (directory, created by normalizer)

**Step 1: Create the normalizer**

Write `normalizers/from_pubmed.py`. Pattern is identical to `from_clinvar.py`:

```python
#!/usr/bin/env python3
"""
Normalizer: PubMed -> model/pubmed.cue

Queries NCBI PubMed via E-utilities (esearch + esummary) for each gene,
counting craniofacial/neural-crest publications and fetching top 3 recent.

Cached at data/pubmed/pubmed_cache.json. Respects NCBI rate limits.

Usage:
    python3 normalizers/from_pubmed.py
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "normalizers"))

from genes import GENES

CACHE_DIR = REPO_ROOT / "data" / "pubmed"
CACHE_FILE = CACHE_DIR / "pubmed_cache.json"
OUTPUT_FILE = REPO_ROOT / "model" / "pubmed.cue"

# Search for gene + craniofacial context
SEARCH_TERM = '({gene}[Title/Abstract]) AND (craniofacial OR "neural crest" OR dental OR orofacial OR craniosynostosis)'

ESEARCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&retmode=json&retmax=0"
    "&term={term}"
)

# For recent count: add date filter
ESEARCH_RECENT_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&retmode=json&retmax=0"
    "&term={term}&mindate=2021&maxdate=2026&datetype=pdat"
)

# Get top 3 recent PMIDs
ESEARCH_TOP_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&retmode=json&retmax=3&sort=date"
    "&term={term}"
)

ESUMMARY_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=pubmed&retmode=json&id={ids}"
)

REQUEST_DELAY = 0.35


def fetch_json(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, json.JSONDecodeError) as e:
        print(f"  WARNING: request failed: {e}", file=sys.stderr)
        return None


def query_pubmed_gene(symbol: str) -> dict | None:
    term = SEARCH_TERM.format(gene=symbol)
    encoded_term = urllib.parse.quote(term, safe="")

    # Total count
    url = ESEARCH_URL.format(term=encoded_term)
    data = fetch_json(url)
    if data is None or "esearchresult" not in data:
        return None
    total = int(data["esearchresult"].get("count", 0))
    time.sleep(REQUEST_DELAY)

    # Recent count (last 5 years)
    url = ESEARCH_RECENT_URL.format(term=encoded_term)
    data = fetch_json(url)
    recent = 0
    if data and "esearchresult" in data:
        recent = int(data["esearchresult"].get("count", 0))
    time.sleep(REQUEST_DELAY)

    # Top 3 recent papers
    url = ESEARCH_TOP_URL.format(term=encoded_term)
    data = fetch_json(url)
    papers = []
    if data and "esearchresult" in data:
        id_list = data["esearchresult"].get("idlist", [])
        if id_list:
            time.sleep(REQUEST_DELAY)
            ids_param = ",".join(id_list[:3])
            url = ESUMMARY_URL.format(ids=ids_param)
            sdata = fetch_json(url)
            if sdata and "result" in sdata:
                for uid in sdata["result"].get("uids", [])[:3]:
                    entry = sdata["result"].get(uid, {})
                    title = entry.get("title", "")
                    pubdate = entry.get("pubdate", "")
                    year = 0
                    if pubdate:
                        try:
                            year = int(pubdate[:4])
                        except ValueError:
                            pass
                    if title:
                        papers.append({
                            "title": title,
                            "pmid": uid,
                            "year": year,
                        })

    return {"pubmed_total": total, "pubmed_recent": recent, "papers": papers}


def load_cache() -> dict:
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)


def escape_cue_string(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_cue(pubmed_data: dict) -> str:
    lines = [
        "package lacuene",
        "",
        "// PubMed: craniofacial publication data for neural crest genes.",
        "// Source: NCBI PubMed via E-utilities (esearch + esummary)",
        f"// Generated by normalizers/from_pubmed.py -- {len(pubmed_data)} genes",
        "",
        "genes: {",
    ]

    for symbol in sorted(pubmed_data.keys()):
        entry = pubmed_data[symbol]
        ncbi_id = GENES[symbol]["ncbi"]

        lines.append(f'\t"{symbol}": {{')
        lines.append(f"\t\t_in_pubmed:     true")
        lines.append(f'\t\tpubmed_gene_id: "{ncbi_id}"')
        lines.append(f"\t\tpubmed_total:   {entry['pubmed_total']}")
        lines.append(f"\t\tpubmed_recent:  {entry['pubmed_recent']}")

        papers = entry.get("papers", [])
        if papers:
            lines.append(f"\t\tpubmed_papers: [")
            for p in papers:
                title = escape_cue_string(p["title"])
                lines.append(f"\t\t\t{{")
                lines.append(f'\t\t\t\ttitle: "{title}"')
                lines.append(f'\t\t\t\tpmid:  "{p["pmid"]}"')
                lines.append(f"\t\t\t\tyear:  {p['year']}")
                lines.append(f"\t\t\t}},")
            lines.append(f"\t\t]")

        lines.append(f"\t}}")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def main():
    import urllib.parse

    print(f"from_pubmed: querying PubMed for {len(GENES)} genes...")
    cache = load_cache()
    pubmed_data = {}
    fetched = 0

    for symbol in sorted(GENES.keys()):
        if symbol in cache:
            print(f"  {symbol}: cached ({cache[symbol]['pubmed_total']} pubs)")
            pubmed_data[symbol] = cache[symbol]
            continue

        print(f"  {symbol}: querying PubMed...", end=" ", flush=True)
        result = query_pubmed_gene(symbol)
        time.sleep(REQUEST_DELAY)

        if result is None:
            print("FAILED")
            continue

        print(f"{result['pubmed_total']} total, {result['pubmed_recent']} recent")
        pubmed_data[symbol] = result
        cache[symbol] = result
        fetched += 1

    save_cache(cache)

    cue_source = generate_cue(pubmed_data)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(cue_source)

    print(f"from_pubmed: wrote {OUTPUT_FILE} ({len(pubmed_data)} genes)")
    print(f"  {fetched} fetched, {len(pubmed_data) - fetched} cached")


if __name__ == "__main__":
    main()
```

**Step 2: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('normalizers/from_pubmed.py', doraise=True); print('OK')"`
Expected: `OK`

**Step 3: Commit**

```bash
git add normalizers/from_pubmed.py
git commit -m "Add PubMed normalizer: craniofacial publication counts per gene"
```

---

### Task 2: Update CUE schema and projections for PubMed

**Files:**
- Modify: `model/schema.cue`
- Modify: `model/proj_sources.cue`
- Modify: `model/proj_enrichment.cue`
- Modify: `model/proj_gap_report.cue`
- Modify: `justfile`

**Step 1: Add PubMed fields to schema.cue**

After the ClinVar block (line 51), add:

```cue
	// PubMed-owned fields (craniofacial publication data)
	pubmed_gene_id: *"" | string
	_in_pubmed:     *false | true
	pubmed_total?:  int
	pubmed_recent?: int
	pubmed_papers?: [...#PubMedPaper]
```

After `#ClinVarVariant` (line 70), add:

```cue
#PubMedPaper: {
	title: string
	pmid:  string
	year:  int
}
```

**Step 2: Add `in_pubmed` to proj_sources.cue**

Add `in_pubmed: v._in_pubmed` after the `in_clinvar` line.

**Step 3: Add `has_literature` to proj_enrichment.cue**

Add `has_literature: v._in_pubmed` after `has_variants`.

**Step 4: Add `missing_pubmed` to proj_gap_report.cue**

- Add `_c_pubmed: v._in_pubmed` to `_source_flags`
- Add `missing_pubmed_count: len(missing_pubmed)` to `summary`
- Add `missing_pubmed: [for k, v in genes if !v._in_pubmed {symbol: k}]` to gap lists
- Add PubMed to `_all_seven` check

**Step 5: Add justfile recipe**

Add to normalize recipe: `python3 normalizers/from_pubmed.py`
Add individual recipe:
```
normalize-pubmed:
    python3 normalizers/from_pubmed.py
```

**Step 6: Validate**

Run: `cue vet -c ./model/`
Expected: no output (success)

**Step 7: Commit**

```bash
git add model/schema.cue model/proj_sources.cue model/proj_enrichment.cue \
  model/proj_gap_report.cue justfile
git commit -m "Add PubMed to CUE schema, projections, and justfile"
```

---

### Task 3: Expand OMIM bundled data for 95 genes

**Files:**
- Modify: `data/omim/omim_subset.json`

The OMIM normalizer reads from `data/omim/omim_subset.json`. It currently only has 20 genes. Research and add entries for the 75 new genes.

**Step 1: Check which genes are missing**

Run: `python3 -c "from normalizers.genes import GENES; import json; d=json.load(open('data/omim/omim_subset.json')); missing=sorted(set(GENES)-set(d['genes'])); print(f'{len(missing)} missing: {missing}')"`

**Step 2: Research and add OMIM data for missing genes**

Use web search to find OMIM titles, syndromes, and inheritance modes for each missing gene. Add entries to the JSON file following the existing pattern.

**Step 3: Re-run OMIM normalizer**

Run: `python3 normalizers/from_omim.py`
Expected: `Wrote model/omim.cue (95 genes, ...)`

**Step 4: Validate**

Run: `cue vet -c ./model/`

**Step 5: Commit**

```bash
git add data/omim/omim_subset.json model/omim.cue
git commit -m "Expand OMIM data to 95 genes"
```

---

### Task 4: Run all normalizers for 95 genes

**Files:**
- Modified by normalizers: `model/go.cue`, `model/hpo.cue`, `model/uniprot.cue`, `model/facebase.cue`, `model/clinvar.cue`, `model/pubmed.cue`

This task calls live APIs and takes several minutes. Run normalizers that hit APIs sequentially.

**Step 1: Run HPO normalizer** (bulk file, fast)

Run: `python3 normalizers/from_hpo.py`
Expected: found N genes with HPO data

**Step 2: Run GO normalizer** (95 API calls)

Run: `python3 normalizers/from_go.py`
Expected: ~95 genes, many GO terms

**Step 3: Run UniProt normalizer** (95 API calls)

Run: `python3 normalizers/from_uniprot.py`

**Step 4: Run FaceBase normalizer** (95 API calls)

Run: `python3 normalizers/from_facebase.py`

**Step 5: Run ClinVar normalizer** (95 API calls)

Run: `python3 normalizers/from_clinvar.py`

**Step 6: Run PubMed normalizer** (95 API calls)

Run: `python3 normalizers/from_pubmed.py`

**Step 7: Validate the unified model**

Run: `cue vet -c ./model/`
Expected: no errors

**Step 8: Check summary**

Run: `cue export ./model/ -e gap_report.summary 2>/dev/null | jq .`
Expected: JSON with total=95, source counts

**Step 9: Commit**

```bash
git add model/go.cue model/hpo.cue model/uniprot.cue model/facebase.cue \
  model/clinvar.cue model/pubmed.cue data/
git commit -m "Run all 7 normalizers for 95 genes"
```

---

### Task 5: Add gap severity scoring to CUE projections

**Files:**
- Create: `model/proj_funding_gaps.cue`

**Step 1: Create the funding gaps projection**

This CUE file computes gap severity for each gene using the flags:

```cue
package lacuene

// Funding gap analysis for NIDCR program officers.
// Scores genes by: has disease + has phenotype + no experimental data + low/no publications.
// Higher score = higher funding priority.

funding_gaps: {
	// Per-gene gap assessment
	genes_assessed: {for k, v in genes {
		(k): {
			symbol:          k
			has_disease:     v._in_omim
			has_phenotype:   v._in_hpo
			has_experiment:  v._in_facebase
			has_variants:    v._in_clinvar
			has_literature:  v._in_pubmed
			if v.pubmed_total != _|_ {pub_count: v.pubmed_total}
			if v.pubmed_total == _|_ {pub_count: 0}
			if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
			if v.pathogenic_count != _|_ {variant_count: v.pathogenic_count}
		}
	}}

	// Critical gaps: disease genes with NO FaceBase data
	critical: [for k, v in genes if v._in_omim && !v._in_facebase {
		symbol: k
		if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
		if v.pubmed_total != _|_ {pub_count: v.pubmed_total}
		if v.pubmed_total == _|_ {pub_count: 0}
		if v.phenotypes != _|_ {phenotype_count: len(v.phenotypes)}
		if v.pathogenic_count != _|_ {variant_count: v.pathogenic_count}
	}]

	// Understudied: genes in model but with very few craniofacial publications
	// (PubMed total is captured but comparison is done in Python generators)

	summary: {
		total_genes:    len(genes)
		critical_count: len(critical)
	}
}
```

**Step 2: Validate**

Run: `cue vet -c ./model/`

**Step 3: Test the projection**

Run: `cue export ./model/ -e funding_gaps.summary 2>/dev/null | jq .`
Expected: JSON with total_genes and critical_count

**Step 4: Commit**

```bash
git add model/proj_funding_gaps.cue
git commit -m "Add funding gap severity projection for NIDCR analysis"
```

---

### Task 6: Rewrite site generator with Grant Gap Finder layout

**Files:**
- Modify: `generators/to_site.py` (full rewrite of `build_html`)
- Modify: `generators/to_vizdata.py` (add pubmed_total to node data)

**Step 1: Update to_vizdata.py**

Add `pubmed_total` to node data so graph can size nodes by publication count. In `build_nodes()`, after the `source_count` line, add logic to read the gene's pubmed_total from the exported genes data and include it in the node data object.

**Step 2: Update to_site.py main() to export funding_gaps**

Add: `funding_gaps = cue_export("funding_gaps")` and pass it to `build_html`.

**Step 3: Rewrite build_html with three-card layout**

The HTML needs:

**Card 1: "Where are the funding gaps?"**
- List of critical gap genes (from funding_gaps.critical)
- Each shows: gene, disease, phenotype count, pub count
- Color: red for critical, orange for moderate, green for covered

**Card 2: "Which genes are understudied?"**
- Ranked list of genes by pub_count ascending, filtered to those with disease associations
- Each shows: gene, pub_count, disease name

**Card 3: "What does the landscape look like?"**
- The existing Cytoscape.js graph (already has 8 role colors, layout switcher)
- Node size driven by `pubmed_total` instead of source_count
- Node opacity driven by source coverage

**Detail panel enhancements:**
- Auto-generated "funding case" blurb
- Publication list (top 3 papers from PubMed)
- All external links (already added by site agent)

**Table section:**
- Add pubmed_total and pubmed_recent columns
- CSV export includes new columns

**Briefing summary button:**
- Generates a plain-text paragraph about the top 5 gaps

**Step 4: Verify syntax**

Run: `python3 -c "import py_compile; py_compile.compile('generators/to_site.py', doraise=True); print('OK')"`

**Step 5: Commit**

```bash
git add generators/to_site.py generators/to_vizdata.py
git commit -m "Rewrite site as Grant Gap Finder dashboard for NIDCR"
```

---

### Task 7: Generate and deploy

**Step 1: Generate VizData**

Run: `python3 generators/to_vizdata.py`
Expected: N nodes, N edges

**Step 2: Generate site**

Run: `python3 generators/to_site.py`
Expected: wrote output/site/index.html

**Step 3: Verify locally**

Open `output/site/index.html` in browser. Check:
- Three query cards render
- Graph shows 95 nodes with 8 colors
- Gap list shows critical genes
- Detail panel shows funding case blurb + publications
- CSV export works
- Briefing summary generates text

**Step 4: Deploy**

```bash
just deploy
```
Expected: non-zero count

**Step 6: Final commit**

```bash
git add output/
git commit -m "Generate and deploy Grant Gap Finder site with 95 genes"
```
