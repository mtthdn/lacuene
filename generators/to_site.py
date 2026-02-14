#!/usr/bin/env python3
"""
Site generator: builds the Grant Gap Finder.

Three query cards: funding gaps, understudied genes, landscape graph.
Plus detail panel with funding case blurbs, publication lists, and
exportable CSV/briefing summary.

Dark theme, Atkinson Hyperlegible Next, CSS custom properties,
WCAG 2.1 AA compliant.

Templates live in generators/templates/ and generators/static/.
CSS and JS are inlined via Jinja2 {% include %} for single-file output.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import date
from glob import glob
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

GENERATOR_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = GENERATOR_DIR / "templates"
STATIC_DIR = GENERATOR_DIR / "static"


def cue_export(expr: str) -> dict | list:
    result = subprocess.run(
        ["cue", "export", "./model/", "-e", expr],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        print(f"ERROR: cue export -e '{expr}' failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    return json.loads(result.stdout)


def main():
    print("to_site: exporting model data...")
    sources: dict = cue_export("gene_sources")  # type: ignore[assignment]
    gap: dict = cue_export("gap_report")  # type: ignore[assignment]
    genes: dict = cue_export("genes")  # type: ignore[assignment]
    funding: dict = cue_export("funding_gaps")  # type: ignore[assignment]

    # Load vizdata
    vizdata_path = os.path.join(os.path.dirname(__file__), "..", "output", "vizdata.json")
    with open(vizdata_path) as f:
        vizdata = json.load(f)

    total = gap["summary"]["total"]
    source_names = {
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
        "in_orphanet": "ORPHANET",
        "in_opentargets": "Open Targets",
        "in_structures": "Structures",
        "in_models": "Models",
    }
    source_urls = {
        "in_go": "http://geneontology.org/",
        "in_omim": "https://www.omim.org/",
        "in_hpo": "https://hpo.jax.org/",
        "in_uniprot": "https://www.uniprot.org/",
        "in_facebase": "https://www.facebase.org/",
        "in_clinvar": "https://www.ncbi.nlm.nih.gov/clinvar/",
        "in_pubmed": "https://pubmed.ncbi.nlm.nih.gov/",
        "in_gnomad": "https://gnomad.broadinstitute.org/",
        "in_nih_reporter": "https://reporter.nih.gov/",
        "in_gtex": "https://gtexportal.org/",
        "in_clinicaltrials": "https://clinicaltrials.gov/",
        "in_string": "https://string-db.org/",
        "in_orphanet": "https://www.orpha.net/",
        "in_opentargets": "https://platform.opentargets.io/",
        "in_structures": "https://alphafold.ebi.ac.uk/",
        "in_models": "https://www.alliancegenome.org/",
    }

    # Mapping from source key (in_go) to the gene_rows field name (go)
    filter_keys = {
        "in_go": "go",
        "in_omim": "omim",
        "in_hpo": "hpo",
        "in_uniprot": "uniprot",
        "in_facebase": "facebase",
        "in_clinvar": "clinvar",
        "in_pubmed": "pubmed",
        "in_gnomad": "gnomad",
        "in_nih_reporter": "nih_reporter",
        "in_gtex": "gtex",
        "in_clinicaltrials": "clinicaltrials",
        "in_string": "string",
        "in_orphanet": "orphanet",
        "in_opentargets": "opentargets",
        "in_structures": "structures",
        "in_models": "models",
    }

    source_count = len(source_names)

    # Per-source counts
    source_counts = {}
    for key in source_names:
        source_counts[key] = sum(1 for s in sources.values() if s.get(key, False))

    # Build gene detail rows (all 12 sources)
    gene_rows = []
    for sym in sorted(sources.keys()):
        flags = sources[sym]
        count = sum(1 for v in flags.values() if v)
        gene = genes[sym]
        syndromes = gene.get("omim_syndromes", [])
        syn_short = syndromes[0].split(",")[0] if syndromes else ""
        pub_total = gene.get("pubmed_total", 0)
        pub_recent = gene.get("pubmed_recent", 0)
        papers = gene.get("pubmed_papers", [])
        pathogenic = gene.get("pathogenic_count", 0)
        phenotypes = gene.get("phenotypes", [])

        gene_rows.append({
            "symbol": sym,
            "go": flags.get("in_go", False),
            "omim": flags.get("in_omim", False),
            "hpo": flags.get("in_hpo", False),
            "uniprot": flags.get("in_uniprot", False),
            "facebase": flags.get("in_facebase", False),
            "clinvar": flags.get("in_clinvar", False),
            "pubmed": flags.get("in_pubmed", False),
            "gnomad": flags.get("in_gnomad", False),
            "nih_reporter": flags.get("in_nih_reporter", False),
            "gtex": flags.get("in_gtex", False),
            "clinicaltrials": flags.get("in_clinicaltrials", False),
            "string": flags.get("in_string", False),
            "orphanet": flags.get("in_orphanet", False),
            "opentargets": flags.get("in_opentargets", False),
            "count": count,
            "syndrome": syn_short,
            "protein": gene.get("protein_name", ""),
            "pub_total": pub_total,
            "pub_recent": pub_recent,
            "papers": papers,
            "pathogenic": pathogenic,
            "phenotype_count": len(phenotypes),
            "syndromes": syndromes,
            "pli_score": gene.get("pli_score", None),
            "loeuf_score": gene.get("loeuf_score", None),
            "grant_count": gene.get("active_grant_count", 0),
            "trial_count": gene.get("active_trial_count", 0),
            "top_tissues": gene.get("top_tissues", []),
            "nih_projects": gene.get("nih_reporter_projects", []),
            "string_partners": gene.get("string_partners", []),
            "craniofacial_expression": gene.get("craniofacial_expression", None),
            "prevalence": gene.get("orphanet_prevalence", ""),
            "orphanet_disorders": gene.get("orphanet_disorders", []),
            "is_drug_target": gene.get("is_drug_target", False),
            "drug_count": gene.get("drug_count", 0),
            "max_clinical_phase": gene.get("max_clinical_phase", 0),
            "opentargets_drugs": gene.get("opentargets_drugs", []),
            "structures": flags.get("in_structures", False),
            "has_alphafold": gene.get("has_alphafold", False),
            "alphafold_confidence": gene.get("alphafold_confidence", None),
            "pdb_count": gene.get("pdb_count", 0),
            "has_experimental_structure": gene.get("has_experimental_structure", False),
            "models": flags.get("in_models", False),
            "has_mouse_model": gene.get("has_mouse_model", False),
            "has_zebrafish_model": gene.get("has_zebrafish_model", False),
            "mouse_model_count": gene.get("mouse_model_count", 0),
            "zebrafish_model_count": gene.get("zebrafish_model_count", 0),
        })

    # Compute translational readiness per gene
    for entry in gene_rows:
        sym = entry["symbol"]
        gene = genes[sym]
        tr_score = 0
        tr_components = []

        path_count = gene.get("pathogenic_count", 0) or 0
        if path_count > 10:
            tr_score += 3
            tr_components.append("many pathogenic variants")
        elif path_count > 0:
            tr_score += 2
            tr_components.append("pathogenic variants")

        trials = gene.get("active_trial_count", 0) or 0
        if trials > 0:
            tr_score += 3
            tr_components.append(f"{trials} clinical trial(s)")

        pli = gene.get("pli_score")
        if pli is not None and pli > 0.9:
            tr_score += 2
            tr_components.append("highly constrained")

        cf_exp = gene.get("craniofacial_expression")
        if cf_exp is not None and cf_exp > 10:
            tr_score += 2
            tr_components.append("craniofacial expression")

        if gene.get("omim_syndromes"):
            tr_score += 1
            tr_components.append("Mendelian syndrome")

        entry["translational_score"] = tr_score
        entry["translational_components"] = tr_components

    # Critical gaps from CUE projection
    critical_gaps = funding.get("critical", [])
    funding_summary = funding.get("summary", {})

    # Weighted priority scores
    weighted = cue_export("weighted_gaps")

    # Cross-source anomalies
    anomalies = cue_export("anomalies")

    # === Tier 1 Analytics: Funding Intelligence ===
    funding_intel = []
    for sym in sorted(sources.keys()):
        gene = genes[sym]
        grants = gene.get("active_grant_count", 0)
        pubs = gene.get("pubmed_total", 0) or 0
        recent = gene.get("pubmed_recent", 0) or 0
        velocity = round(recent / pubs, 2) if pubs > 0 else 0
        has_disease = bool(gene.get("omim_syndromes"))
        pathogenic = gene.get("pathogenic_count", 0) or 0

        # Funding efficiency: pubs per grant (higher = more productive)
        efficiency = round(pubs / grants, 1) if grants > 0 else None
        # Momentum without funding: high recent pubs, zero grants
        unfunded_momentum = recent > 5 and grants == 0
        # Funded but quiet: grants > 0 but few recent pubs
        funded_quiet = grants > 0 and recent < 3

        # Emerging hotspot score
        hotspot_score = 0
        if velocity > 0.4:
            hotspot_score += 3
        if grants == 0:
            hotspot_score += 2
        if has_disease:
            hotspot_score += 2
        if pathogenic > 0:
            hotspot_score += 1

        funding_intel.append({
            "symbol": sym,
            "grants": grants,
            "pubs": pubs,
            "recent": recent,
            "velocity": velocity,
            "efficiency": efficiency,
            "unfunded_momentum": unfunded_momentum,
            "funded_quiet": funded_quiet,
            "hotspot_score": hotspot_score,
            "has_disease": has_disease,
        })

    # === Tier 1 Analytics: Syndrome-Level Funding ===
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
            sf["total_pubs"] += gene.get("pubmed_total", 0) or 0
            sf["total_recent"] += gene.get("pubmed_recent", 0) or 0
            if sources[sym].get("in_facebase", False):
                sf["fb_count"] += 1
            sf["trial_count"] += gene.get("active_trial_count", 0)

    # === Tier 1 Analytics: Translational Readiness ===
    # Computed per gene_row so it's available in the gene table
    # (added to gene_rows after they're built below)

    # Temporal snapshots
    snap_dir = os.path.join(os.path.dirname(__file__), "..", "output", "snapshots")
    os.makedirs(snap_dir, exist_ok=True)

    # Load existing snapshots
    snapshots = []
    for snap_file in sorted(glob(os.path.join(snap_dir, "*.json"))):
        with open(snap_file) as f:
            snapshots.append(json.load(f))

    # Compute current snapshot
    today = date.today().isoformat()
    gap_symbols = sorted([g["symbol"] for g in critical_gaps])
    fb_symbols = sorted([sym for sym, flags in sources.items() if flags.get("in_facebase", False)])
    current_snapshot = {
        "date": today,
        "total_genes": total,
        "critical_count": len(critical_gaps),
        "gap_symbols": gap_symbols,
        "facebase_symbols": fb_symbols,
    }

    # Replace today's entry if exists, else append
    snapshots = [s for s in snapshots if s["date"] != today]
    snapshots.append(current_snapshot)
    snapshots.sort(key=lambda s: s["date"])

    # Collect unique roles from vizdata nodes for dynamic legend
    roles_in_data = {}
    for node in vizdata['nodes']:
        role = node['data']['type']
        if role not in roles_in_data:
            roles_in_data[role] = {
                'label': node['data']['role_label'],
                'color': node['data']['color']
            }
    legend_items = sorted(roles_in_data.items())

    critical_count = funding_summary.get("critical_count", 0)

    # Set up Jinja2 environment
    env = Environment(loader=FileSystemLoader([str(TEMPLATE_DIR), str(STATIC_DIR)]))

    # Render index page
    index_template = env.get_template("index.html.j2")
    html = index_template.render(
        vizdata_json=json.dumps(vizdata),
        gene_rows_json=json.dumps(gene_rows),
        critical_gaps_json=json.dumps(critical_gaps),
        snapshots_json=json.dumps(snapshots),
        weighted_gaps_json=json.dumps(weighted),
        anomalies_json=json.dumps(anomalies),
        funding_intel_json=json.dumps(funding_intel),
        syndrome_funding_json=json.dumps(list(syndrome_funding.values())),
        total=total,
        source_count=source_count,
        source_names=source_names,
        source_urls=source_urls,
        source_counts=source_counts,
        filter_keys=filter_keys,
        gene_rows=gene_rows,
        critical_gaps=critical_gaps,
        critical_count=critical_count,
        funding_summary=funding_summary,
        snapshots=snapshots,
        legend_items=legend_items,
    )

    # Render about page
    about_template = env.get_template("about.html.j2")
    about_html = about_template.render(
        total=total,
        source_count=source_count,
        source_names=source_names,
        source_urls=source_urls,
        source_counts=source_counts,
        funding_summary=funding_summary,
        critical=critical_count,
        csv_column_count=source_count + 7,  # sources + symbol + pubs + recent + pathogenic + phenotypes + syndrome + count
    )

    out_dir = os.path.join(os.path.dirname(__file__), "..", "output", "site")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "index.html")
    with open(out_path, "w") as f:
        f.write(html)
    about_path = os.path.join(out_dir, "about.html")
    with open(about_path, "w") as f:
        f.write(about_html)

    # Copy CNAME for custom domain
    cname_src = STATIC_DIR / "CNAME"
    if cname_src.exists():
        shutil.copy2(cname_src, os.path.join(out_dir, "CNAME"))

    # Persist current snapshot
    snap_path = os.path.join(snap_dir, f"{today}.json")
    with open(snap_path, "w") as f:
        json.dump(current_snapshot, f, indent=2)

    print(f"to_site: wrote {os.path.normpath(out_path)}")
    print(f"  {len(vizdata['nodes'])} nodes, {len(vizdata['edges'])} edges")
    print(f"  {len(critical_gaps)} critical gaps, {total} genes total")
    print(f"  {len(snapshots)} snapshot(s) in {os.path.normpath(snap_dir)}")


if __name__ == "__main__":
    main()
