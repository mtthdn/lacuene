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
    """gene_sources has all 12 source flags."""
    sources = cue_export("gene_sources")
    first_gene = next(iter(sources.values()))
    expected_flags = [
        "in_go", "in_omim", "in_hpo", "in_uniprot", "in_facebase",
        "in_clinvar", "in_pubmed", "in_gnomad", "in_nih_reporter", "in_gtex",
        "in_clinicaltrials", "in_string",
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
