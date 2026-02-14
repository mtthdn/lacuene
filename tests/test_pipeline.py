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
        assert flags.get("in_go", False), f"{gene} missing GO"
        assert flags.get("in_omim", False), f"{gene} missing OMIM"


def test_twelve_source_flags():
    """gene_sources has all source flags including orphanet."""
    sources = cue_export("gene_sources")
    first_gene = next(iter(sources.values()))
    expected_flags = [
        "in_go", "in_omim", "in_hpo", "in_uniprot", "in_facebase",
        "in_clinvar", "in_pubmed", "in_gnomad", "in_nih_reporter", "in_gtex",
        "in_clinicaltrials", "in_string", "in_orphanet",
    ]
    for flag in expected_flags:
        assert flag in first_gene, f"Missing source flag: {flag}"


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
    assert len(sox9.get("go_terms", [])) > 10
    assert len(sox9.get("omim_syndromes", [])) > 0
    assert sox9.get("pubmed_total", 0) > 100


def test_funding_gaps():
    """Funding gaps projection works."""
    funding = cue_export("funding_gaps")
    assert "genes_assessed" in funding
    assert "critical" in funding
    assert "summary" in funding


def test_weighted_gaps():
    """Weighted gaps projection produces priority scores."""
    weighted = cue_export("weighted_gaps")
    assert len(weighted) >= 5
    sox9 = weighted.get("SOX9")
    assert sox9 is not None, "SOX9 missing from weighted_gaps"
    assert "priority_score" in sox9
    assert sox9["priority_score"] >= 0


def run_generator(script: str) -> subprocess.CompletedProcess:
    """Run a generator script from the repo root."""
    result = subprocess.run(
        ["python3", script],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    assert result.returncode == 0, f"{script} failed: {result.stderr}"
    return result


def test_vizdata_structure():
    """VizData generator produces valid Cytoscape.js-compatible JSON."""
    run_generator("generators/to_vizdata.py")
    vizdata_path = REPO_ROOT / "output" / "vizdata.json"
    assert vizdata_path.exists(), "output/vizdata.json not found"
    with open(vizdata_path) as f:
        vizdata = json.load(f)

    # Top-level structure
    assert "nodes" in vizdata, "vizdata missing 'nodes'"
    assert "edges" in vizdata, "vizdata missing 'edges'"
    assert isinstance(vizdata["nodes"], list)
    assert isinstance(vizdata["edges"], list)

    # At least 90 nodes (95 genes in the pipeline)
    assert len(vizdata["nodes"]) >= 90, f"Expected >= 90 nodes, got {len(vizdata['nodes'])}"

    # Each node has required data fields
    for node in vizdata["nodes"]:
        d = node.get("data", {})
        assert "id" in d, f"Node missing data.id: {node}"
        assert "label" in d, f"Node missing data.label: {node}"
        assert "type" in d, f"Node missing data.type: {node}"
        assert "color" in d, f"Node missing data.color: {node}"

    # At least 4 edge types present
    edge_types = set(e["data"]["type"] for e in vizdata["edges"])
    required_types = {"shared_phenotype", "shared_syndrome", "shared_pathway", "ppi"}
    missing = required_types - edge_types
    assert not missing, f"Missing edge types: {missing}"


def test_site_output_files():
    """Site generator produces index.html and about.html with expected content."""
    run_generator("generators/to_site.py")
    site_dir = REPO_ROOT / "output" / "site"

    index_path = site_dir / "index.html"
    assert index_path.exists(), "output/site/index.html not found"
    index_size = index_path.stat().st_size
    assert index_size > 100_000, f"index.html too small: {index_size} bytes (expected > 100KB)"

    about_path = site_dir / "about.html"
    assert about_path.exists(), "output/site/about.html not found"
    about_size = about_path.stat().st_size
    assert about_size > 10_000, f"about.html too small: {about_size} bytes (expected > 10KB)"

    # index.html contains key sections
    index_html = index_path.read_text()
    for section in ["Gene Table", "Gene Landscape", "Funding Gaps"]:
        assert section in index_html, f"index.html missing section: '{section}'"


def test_anomaly_projection():
    """Anomalies projection returns valid cross-source inconsistencies."""
    anomalies = cue_export("anomalies")
    assert "genes_with_anomalies" in anomalies, "anomalies missing 'genes_with_anomalies'"
    assert isinstance(anomalies["genes_with_anomalies"], list)
    assert "summary" in anomalies, "anomalies missing 'summary'"
    summary = anomalies["summary"]
    assert "total_anomalies" in summary, "summary missing 'total_anomalies'"
    assert "omim_no_clinvar_count" in summary, "summary missing 'omim_no_clinvar_count'"
    assert "high_pli_no_trials_count" in summary, "summary missing 'high_pli_no_trials_count'"


def test_weighted_gaps_structure():
    """Weighted gaps have valid priority scores for all genes."""
    weighted = cue_export("weighted_gaps")
    assert len(weighted) >= 90, f"Expected >= 90 genes in weighted_gaps, got {len(weighted)}"
    for sym, entry in weighted.items():
        assert "symbol" in entry, f"{sym} missing 'symbol'"
        assert "priority_score" in entry, f"{sym} missing 'priority_score'"
        score = entry["priority_score"]
        assert isinstance(score, (int, float)), f"{sym} priority_score is not numeric: {type(score)}"
        assert score >= 0, f"{sym} has negative priority_score: {score}"


def main():
    tests = [
        test_model_validates,
        test_gene_sources,
        test_twelve_source_flags,
        test_gap_report,
        test_enrichment,
        test_gene_detail,
        test_funding_gaps,
        test_weighted_gaps,
        test_vizdata_structure,
        test_site_output_files,
        test_anomaly_projection,
        test_weighted_gaps_structure,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  PASS: {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {test.__name__}: {e}")
            failed += 1

    print(f"\n{passed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
