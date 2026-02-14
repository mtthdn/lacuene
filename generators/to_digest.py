#!/usr/bin/env python3
"""
Weekly digest generator: produces a markdown summary of pipeline changes.

Compares the two most recent snapshots to compute:
- Gap changes (opened/closed)
- FaceBase coverage changes
- Source coverage stats
- Overall delta

Output: prints markdown to stdout (piped to `gh issue comment` by workflow).

Usage:
    python3 generators/to_digest.py
    python3 generators/to_digest.py --output output/digest.md
"""

import json
import subprocess
import sys
from datetime import date
from glob import glob
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def cue_export(expr: str):
    result = subprocess.run(
        ["cue", "export", "./model/", "-e", expr],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    if result.returncode != 0:
        return None
    return json.loads(result.stdout)


def load_snapshots():
    snap_dir = REPO_ROOT / "output" / "snapshots"
    snapshots = []
    for snap_file in sorted(snap_dir.glob("*.json")):
        with open(snap_file) as f:
            snapshots.append(json.load(f))
    return snapshots


def build_digest() -> str:
    lines = []
    today = date.today().isoformat()

    # Load current model stats
    gap_report = cue_export("gap_report")
    sources = cue_export("gene_sources")

    if not gap_report or not sources:
        return "**Digest failed:** could not export CUE model.\n"

    summary = gap_report["summary"]
    total = summary["total"]

    # Source coverage
    source_labels = {
        "in_go": "Gene Ontology", "in_omim": "OMIM", "in_hpo": "HPO",
        "in_uniprot": "UniProt", "in_facebase": "FaceBase",
        "in_clinvar": "ClinVar", "in_pubmed": "PubMed",
        "in_gnomad": "gnomAD", "in_nih_reporter": "NIH Reporter",
        "in_gtex": "GTEx", "in_clinicaltrials": "ClinicalTrials",
        "in_string": "STRING", "in_orphanet": "Orphanet",
        "in_opentargets": "Open Targets", "in_models": "MGI/ZFIN",
        "in_structures": "AlphaFold/PDB",
    }

    source_counts = {}
    for key in source_labels:
        source_counts[key] = sum(
            1 for s in sources.values() if s.get(key, False)
        )

    # Header
    lines.append(f"## Weekly Pipeline Digest — {today}")
    lines.append("")
    lines.append(f"**{total} genes** across **{len(source_labels)} sources**")
    lines.append("")

    # Source coverage table
    lines.append("### Source Coverage")
    lines.append("")
    lines.append("| Source | Coverage | % |")
    lines.append("|--------|----------|---|")
    for key, label in source_labels.items():
        count = source_counts[key]
        pct = count * 100 // total if total else 0
        bar = "█" * (pct // 10)
        lines.append(f"| {label} | {count}/{total} | {bar} {pct}% |")
    lines.append("")

    # Gap summary
    critical_count = len(gap_report.get("research_gaps", []))
    lines.append(f"### Gaps")
    lines.append("")
    lines.append(
        f"**{critical_count}** genes with OMIM disease association "
        f"but no FaceBase experimental data."
    )
    lines.append("")

    # Snapshot diff
    snapshots = load_snapshots()
    if len(snapshots) >= 2:
        prev = snapshots[-2]
        curr = snapshots[-1]
        prev_gaps = set(prev.get("gap_symbols", []))
        curr_gaps = set(curr.get("gap_symbols", []))
        prev_fb = set(prev.get("facebase_symbols", []))
        curr_fb = set(curr.get("facebase_symbols", []))

        gaps_closed = sorted(prev_gaps - curr_gaps)
        gaps_opened = sorted(curr_gaps - prev_gaps)
        new_fb = sorted(curr_fb - prev_fb)
        lost_fb = sorted(prev_fb - curr_fb)

        lines.append(f"### Changes Since {prev['date']}")
        lines.append("")

        if gaps_closed:
            lines.append(
                f"**Gaps closed ({len(gaps_closed)}):** "
                + ", ".join(f"`{g}`" for g in gaps_closed)
            )
        if gaps_opened:
            lines.append(
                f"**Gaps opened ({len(gaps_opened)}):** "
                + ", ".join(f"`{g}`" for g in gaps_opened)
            )
        if new_fb:
            lines.append(
                f"**New FaceBase coverage ({len(new_fb)}):** "
                + ", ".join(f"`{g}`" for g in new_fb)
            )
        if lost_fb:
            lines.append(
                f"**Lost FaceBase coverage ({len(lost_fb)}):** "
                + ", ".join(f"`{g}`" for g in lost_fb)
            )
        if not (gaps_closed or gaps_opened or new_fb or lost_fb):
            lines.append("No changes detected since last snapshot.")

        # Gene count changes
        prev_total = prev.get("total_genes", 0)
        curr_total = curr.get("total_genes", 0)
        if curr_total != prev_total:
            lines.append(
                f"\nGene count: {prev_total} → {curr_total} "
                f"({'+' if curr_total > prev_total else ''}"
                f"{curr_total - prev_total})"
            )
        lines.append("")
    else:
        lines.append("### Changes")
        lines.append("")
        lines.append(
            "First snapshot recorded. Diffs will appear after the next run."
        )
        lines.append("")

    # Missing sources (only show sources with gaps)
    lines.append("### Missing Data")
    lines.append("")
    missing_sources = []
    for key in sorted(summary.keys()):
        if key.startswith("missing_") and key.endswith("_count"):
            count = summary[key]
            if count > 0:
                source_name = key.replace("missing_", "").replace("_count", "")
                missing_sources.append((source_name, count))

    if missing_sources:
        for name, count in sorted(missing_sources, key=lambda x: -x[1]):
            lines.append(f"- **{name}**: {count} genes missing")
    else:
        lines.append("All sources have complete coverage.")
    lines.append("")

    # Expanded pipeline (lacuene-exp)
    exp_dir = REPO_ROOT / ".." / "lacuene-exp" / "derived"
    gap_file = exp_dir / "gap_candidates.json"
    enrichment_file = exp_dir / "candidate_enrichment.json"
    status_file = exp_dir / "pipeline_status.json"

    if gap_file.exists():
        with open(gap_file) as f:
            gap_data = json.load(f)

        candidate_count = gap_data.get("candidate_count", 0)
        candidates = gap_data.get("candidates", [])
        score_dist = gap_data.get("score_distribution", {})

        # Load enrichment data (craniofacial publication counts)
        cf_pubs = {}
        if enrichment_file.exists():
            with open(enrichment_file) as f:
                enrich_data = json.load(f)
            for ec in enrich_data.get("candidates", []):
                cf_pubs[ec["symbol"]] = ec.get("pubmed_craniofacial_count", 0)

        lines.append("### Expanded Pipeline (lacuene-exp)")
        lines.append("")

        # Show last run date if status file available
        if status_file.exists():
            with open(status_file) as f:
                status = json.load(f)
            last_run = status.get("last_run", "unknown")
            lines.append(f"*Last run: {last_run}*")
            lines.append("")

        lines.append(
            f"**{candidate_count} gap candidates** identified "
            f"with disease signal not in curated set."
        )
        if score_dist:
            high = score_dist.get("high (7+)", 0)
            med = score_dist.get("medium (4-6.9)", 0)
            lines.append(
                f" ({high} high-confidence, {med} medium)"
            )
        lines.append("")

        # Top 10 by confidence score, with enrichment data
        top = sorted(
            candidates, key=lambda c: c.get("confidence_score", 0),
            reverse=True
        )[:10]

        if top:
            lines.append("| Gene | Score | HPO | Orphanet | CF Pubs | Name |")
            lines.append("|------|------:|----:|---------:|--------:|------|")
            for c in top:
                ev = c.get("evidence", {})
                hpo = ev.get("hpo_phenotype_count", 0)
                orph = ev.get("orphanet_disorder_count", 0)
                pubs = cf_pubs.get(c["symbol"], "—")
                name = c.get("name", "")[:40]
                score = c.get("confidence_score", 0)
                lines.append(
                    f"| `{c['symbol']}` | {score} | {hpo} | {orph} "
                    f"| {pubs} | {name} |"
                )
            lines.append("")

            if cf_pubs:
                lines.append(
                    "*CF Pubs = PubMed articles mentioning gene + craniofacial terms*"
                )
                lines.append("")

        lines.append("Run `just rebuild` in lacuene-exp to refresh.")
        lines.append("")
    else:
        lines.append("### Expanded Pipeline")
        lines.append("")
        lines.append(
            "No derived data available. "
            "Run overnight pipeline in lacuene-exp."
        )
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        f"*Generated by `generators/to_digest.py` on {today}*"
    )

    return "\n".join(lines)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Generate weekly digest")
    parser.add_argument(
        "--output", "-o", type=str, default=None,
        help="Write to file instead of stdout"
    )
    args = parser.parse_args()

    digest = build_digest()

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(digest)
        print(f"Digest written to {args.output}", file=sys.stderr)
    else:
        print(digest)


if __name__ == "__main__":
    main()
