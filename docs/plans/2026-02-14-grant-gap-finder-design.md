# Grant Gap Finder + PubMed Integration

**Date:** 2026-02-14
**Status:** Approved

## Purpose

Turn lacuene from a technical demo into a research utility for Dr. Jamie Kugler
(NIDCR, NIH). She's a program officer managing dental/craniofacial research
grants. Her core question: "Where should NIDCR be directing funding?"

lacuene answers this by cross-referencing disease severity (OMIM), clinical
phenotypes (HPO), experimental data (FaceBase), variant pathogenicity (ClinVar),
and now publication volume (PubMed) to surface **genes that are clinically
important but scientifically understudied**.

## Component 1: PubMed Normalizer (7th Source)

### Data

For each of the 95 neural crest genes, query PubMed E-utilities:
- Total publication count: `{gene} AND (craniofacial OR neural crest OR dental)`
- Recent count: same query filtered to last 5 years
- Top 3 most recent papers: title, PMID, year

### Implementation

Same plugin pattern as the other 6 normalizers:

- `normalizers/from_pubmed.py` — NCBI E-utilities `esearch` + `esummary`
- Cache: `data/pubmed/pubmed_cache.json`
- Output: `model/pubmed.cue`
- Rate limit: `time.sleep(0.35)` between requests (no API key)

### Schema additions

```cue
// PubMed-owned fields
pubmed_gene_id: *"" | string  // NCBI Gene ID (same as HPO)
_in_pubmed: *false | true
pubmed_total?: int            // total craniofacial publications
pubmed_recent?: int           // last 5 years
pubmed_papers?: [...#PubMedPaper]

#PubMedPaper: {
    title: string
    pmid:  string
    year:  int
}
```

### Projection updates

- `proj_sources.cue`: add `in_pubmed: v._in_pubmed`
- `proj_enrichment.cue`: add `has_literature: v._in_pubmed`
- `proj_gap_report.cue`: add `missing_pubmed` list, count in summary

## Component 2: Grant Gap Finder Dashboard

### Layout: Three query cards

**Card 1: "Where are the funding gaps?"**
- Genes with OMIM disease association + low FaceBase coverage + low PubMed counts
- Gap severity score: has_disease + has_phenotype + !has_experiment + low_publication
- Color-coded: red = critical gap, orange = moderate, green = well-covered
- Each entry shows: symbol, disease, phenotype count, pub count, FaceBase datasets

**Card 2: "Which genes are understudied?"**
- Scatter/ranked view: disease severity (syndrome count) vs publication count
- Bottom-right quadrant (high disease, low literature) = funding targets
- Click gene -> detail panel with full cross-source view

**Card 3: "What does the landscape look like?"**
- Existing Cytoscape.js graph, now 95 genes, 8 role-based colors
- Node SIZE driven by publication count (bigger = more studied)
- Node OPACITY driven by source coverage (faded = fewer sources)
- Shared-syndrome edges show disease clusters

### Detail panel enhancements

- Auto-generated "funding case" blurb: "{GENE} is associated with N Mendelian
  phenotypes, has M craniofacial publications, but has zero FaceBase datasets.
  This represents a research gap for NIDCR."
- Publication list: top 3 recent papers with PubMed links
- All existing links: HGNC, UniProt, QuickGO, OMIM, ClinVar, PubMed

### Exportable outputs

- CSV export: now includes pubmed_total, pubmed_recent, gap_severity
- "Briefing summary" button: plain-text paragraph summarizing top 5 gaps,
  suitable for email or slide deck

## Component 3: Integration Work

### Re-run all normalizers for 95 genes

The gene list expanded from 20 to 95. All 7 normalizers need to run against
the full set:

1. `from_go.py` — QuickGO API (95 queries)
2. `from_omim.py` — Bundled data needs expansion
3. `from_hpo.py` — Bulk file, automatic
4. `from_uniprot.py` — REST API (95 queries)
5. `from_facebase.py` — DERIVA API (95 queries)
6. `from_clinvar.py` — NCBI E-utilities (95 queries)
7. `from_pubmed.py` — NCBI E-utilities (95 queries, NEW)

### Site regeneration and deployment

After normalizers complete:
1. `just validate` — CUE model with all 95 genes
2. `just vizdata` — regenerate graph JSON
3. `just site` — regenerate static site
4. Deploy site

## Success Criteria

1. 95 genes with publication counts visible on the site
2. Gap severity ranking surfaces at least 5 actionable funding gaps
3. Jamie can export a CSV and share it in a meeting
4. "Briefing summary" generates a readable paragraph about top gaps
5. Site loads in under 3 seconds with 95 nodes
6. `just rebuild` completes end-to-end with 7 sources

## Non-Goals

- No authentication or user accounts
- No live editing (curation is Approach 3, deferred)
- No automated grant database cross-referencing (future)
- No mobile optimization beyond basic responsiveness
