#!/usr/bin/env python3
"""
Summary generator: pretty-prints the unified gene model.
Runs `cue export` to extract projections and formats a human-readable report.
"""

import json
import subprocess
import sys


def cue_export(expr: str) -> dict | list:
    """Run cue export and parse the JSON result."""
    result = subprocess.run(
        ["cue", "export", "./model/", "-e", expr],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: cue export -e '{expr}' failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    gap = cue_export("gap_report")
    sources = cue_export("gene_sources")
    enrichment = cue_export("enrichment")

    summary = gap["summary"]
    total = summary["total"]

    # Count source coverage tiers (now out of 10)
    tier_counts = {}
    for sym, flags in sources.items():
        count = sum(1 for v in flags.values() if v)
        tier_counts[count] = tier_counts.get(count, 0) + 1

    # Per-source coverage
    source_keys = [
        "in_go", "in_omim", "in_hpo", "in_uniprot", "in_facebase",
        "in_clinvar", "in_pubmed", "in_gnomad", "in_nih_reporter", "in_gtex",
        "in_clinicaltrials", "in_string", "in_orphanet", "in_opentargets",
        "in_models", "in_structures",
    ]
    source_counts = {}
    for name in source_keys:
        source_counts[name] = sum(1 for s in sources.values() if s.get(name, False))

    source_labels = {
        "in_go": "Gene Ontology",
        "in_omim": "OMIM",
        "in_hpo": "HPO",
        "in_uniprot": "UniProt",
        "in_facebase": "FaceBase",
        "in_clinvar": "ClinVar",
        "in_pubmed": "PubMed",
        "in_gnomad": "gnomAD",
        "in_nih_reporter": "NIH Reporter",
        "in_gtex": "GTEx",
        "in_clinicaltrials": "ClinicalTrials",
        "in_string": "STRING",
        "in_orphanet": "Orphanet",
        "in_opentargets": "Open Targets",
        "in_models": "MGI/ZFIN",
        "in_structures": "AlphaFold/PDB",
    }

    print("=" * 60)
    print("  lacuene: Neural Crest Gene Reconciliation")
    print("=" * 60)
    source_total = len(source_keys)
    print(f"\n{total} genes unified across {source_total} sources\n")

    print("Coverage Tiers:")
    for tier in sorted(tier_counts.keys(), reverse=True):
        count = tier_counts[tier]
        label = "gene" if count == 1 else "genes"
        print(f"  {tier:2d} sources:  {count:2d} {label}")

    print("\nSource Coverage:")
    for key in source_keys:
        label = source_labels[key]
        count = source_counts[key]
        pct = count * 100 // total
        print(f"  {label:15s}  {count:2d}/{total} ({pct}%)")

    # Research gaps
    research_gaps = gap.get("research_gaps", [])
    if research_gaps:
        print(f"\nResearch Gaps (OMIM disease but no FaceBase data): {len(research_gaps)}")
        for g in research_gaps:
            syndromes = g.get("syndromes", [])
            syn_str = ", ".join(syndromes[:3]) if syndromes else "no syndromes listed"
            print(f"  {g['symbol']:8s}  {syn_str}")

    # Per-gene detail table (abbreviated: GO, OMIM, HPO, UniP, FB, CV, PM, gn, NR, GT)
    headers = ["GO", "OMIM", "HPO", "UniP", "FB", "CV", "PM", "gn", "NR", "GT", "CT", "ST", "OR", "OT", "MO", "St"]
    header_line = "  ".join(f"{h:>4s}" for h in headers)
    print(f"\n{'Symbol':10s} {header_line}  Sources")
    print("-" * 70)
    for sym in sorted(sources.keys()):
        flags = sources[sym]
        marks = []
        for key in source_keys:
            marks.append("Y" if flags.get(key, False) else "-")
        count = sum(1 for v in flags.values() if v)
        mark_line = "  ".join(f"{m:>4s}" for m in marks)
        print(f"  {sym:8s} {mark_line}  {count}/{source_total}")

    print()


if __name__ == "__main__":
    main()
