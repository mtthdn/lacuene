#!/usr/bin/env python3
"""
VizData generator: produces Cytoscape.js-compatible JSON from the unified CUE model.

Nodes = genes (colored by developmental role, sized by publication count).
Edges = shared HPO phenotypes, OMIM syndromes, or GO biological process terms.
"""

import json
import math
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

# Import gene metadata for roles and coloring
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "normalizers"))
from genes import GENES, SYMBOL_TO_ROLE

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "output", "vizdata.json")

# Color scheme by developmental role
ROLE_COLORS = {
    "border_spec": "#58a6ff",    # blue — border specification
    "nc_specifier": "#a371f7",   # purple — neural crest specifiers
    "emt_migration": "#3fb950",  # green — EMT and migration
    "signaling": "#d29922",      # orange — signaling pathways
    "craniofacial": "#f85149",   # red — craniofacial patterning
    "melanocyte": "#db61a2",     # pink — melanocyte/pigmentation
    "enteric": "#79c0ff",        # light blue — enteric nervous system
    "cardiac": "#f0883e",        # dark orange — cardiac neural crest
    "patterning": "#f85149",     # red — legacy, keep for backward compat
    "expanded": "#484f58",       # muted gray — expanded-tier genes
}

ROLE_LABELS = {
    "border_spec": "Border specification",
    "nc_specifier": "NC specifier",
    "emt_migration": "EMT / migration",
    "signaling": "Signaling",
    "craniofacial": "Craniofacial",
    "melanocyte": "Melanocyte",
    "enteric": "Enteric NS",
    "cardiac": "Cardiac NC",
    "patterning": "Patterning / disease",
    "expanded": "Expanded",
}


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


def build_nodes(sources: dict, genes_data: dict) -> list[dict]:
    """Create Cytoscape.js node objects from gene source data."""
    nodes = []
    for sym in sorted(sources.keys()):
        flags = sources[sym]
        source_count = sum(1 for v in flags.values() if v)
        role = SYMBOL_TO_ROLE.get(sym, "patterning")
        color = ROLE_COLORS.get(role, "#999999")
        gene = genes_data.get(sym, {})
        pub_count = gene.get("pubmed_total", 0)
        pub_recent = gene.get("pubmed_recent", 0)

        # Size by publication count (log scale, 10-35px range)
        size = 10 + min(25, math.log(1 + pub_count) * 4)

        # Publication trend: recent (last 5 years) as fraction of total
        if pub_count > 0:
            velocity = round(pub_recent / pub_count, 2)
            if velocity > 0.5:
                trend = "rising"
            elif velocity > 0.2:
                trend = "stable"
            else:
                trend = "declining"
        else:
            velocity = 0
            trend = "none"

        nodes.append({
            "data": {
                "id": sym,
                "label": sym,
                "type": role,
                "role_label": ROLE_LABELS.get(role, role),
                "source_count": source_count,
                "pub_count": pub_count,
                "pub_recent": pub_recent,
                "velocity": velocity,
                "trend": trend,
                "color": color,
                "size": round(size),
            }
        })
    return nodes


def build_edges(genes_data: dict) -> list[dict]:
    """Create edges between genes that share HPO phenotypes or OMIM syndromes."""
    # Index: phenotype -> set of gene symbols
    phenotype_index: dict[str, set[str]] = defaultdict(set)
    syndrome_index: dict[str, set[str]] = defaultdict(set)

    for sym, gene in genes_data.items():
        # HPO phenotypes (top-level clinical terms, not every sub-phenotype)
        phenotypes = gene.get("phenotypes", [])
        # Only index the more common/interesting phenotypes to avoid edge explosion
        for p in phenotypes:
            phenotype_index[p].add(sym)

        # OMIM syndromes
        syndromes = gene.get("omim_syndromes", [])
        for s in syndromes:
            # Strip MIM number for matching: "Crouzon syndrome, 123500" -> "Crouzon syndrome"
            name = s.split(",")[0].strip() if "," in s else s
            syndrome_index[name].add(sym)

    edges = []
    edge_set = set()  # deduplicate

    # Shared phenotype edges (only phenotypes shared by 2-5 genes — not universal ones)
    for phenotype, syms in phenotype_index.items():
        if 2 <= len(syms) <= 5:
            sym_list = sorted(syms)
            for i in range(len(sym_list)):
                for j in range(i + 1, len(sym_list)):
                    key = (sym_list[i], sym_list[j], "shared_phenotype")
                    if key not in edge_set:
                        edge_set.add(key)
                        edges.append({
                            "data": {
                                "source": sym_list[i],
                                "target": sym_list[j],
                                "type": "shared_phenotype",
                                "label": phenotype,
                            }
                        })

    # Shared syndrome edges
    for syndrome, syms in syndrome_index.items():
        if len(syms) >= 2:
            sym_list = sorted(syms)
            for i in range(len(sym_list)):
                for j in range(i + 1, len(sym_list)):
                    key = (sym_list[i], sym_list[j], "shared_syndrome")
                    if key not in edge_set:
                        edge_set.add(key)
                        edges.append({
                            "data": {
                                "source": sym_list[i],
                                "target": sym_list[j],
                                "type": "shared_syndrome",
                                "label": syndrome,
                            }
                        })

    return edges


def build_pathway_edges(genes_data: dict) -> list[dict]:
    """Create edges between genes sharing GO biological process terms."""
    process_index: dict[str, set[str]] = defaultdict(set)
    for sym, gene in genes_data.items():
        for term in gene.get("go_terms", []):
            if term.get("aspect") == "P":
                name = term.get("term_name", "")
                if name:
                    process_index[name].add(sym)

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


def build_ppi_edges(genes_data: dict) -> list[dict]:
    """Create edges between genes with STRING protein-protein interactions."""
    gene_set = set(genes_data.keys())
    edges = []
    edge_set = set()

    for sym, gene in genes_data.items():
        partners = gene.get("string_partners", [])
        if not partners:
            continue
        for partner in partners:
            partner_sym = partner if isinstance(partner, str) else partner.get("symbol", "")
            if not partner_sym or partner_sym not in gene_set:
                continue
            key = tuple(sorted([sym, partner_sym]) + ["ppi"])
            if key not in edge_set:
                edge_set.add(key)
                score = partner.get("score", 0) if isinstance(partner, dict) else 0
                label = f"{sym}-{partner_sym}"
                if score:
                    label += f" ({score})"
                edges.append({
                    "data": {
                        "source": sorted([sym, partner_sym])[0],
                        "target": sorted([sym, partner_sym])[1],
                        "type": "ppi",
                        "label": label,
                    }
                })
    return edges


def load_expanded_genes(curated_symbols: set[str]) -> list[dict]:
    """Load expanded-tier genes from lacuene-exp, if available.

    Returns Cytoscape.js node objects for genes not already in the curated set,
    excluding ZNF-family genes. Returns an empty list if the file is not found.
    """
    # Try sibling repo path first, then environment variable override
    exp_path = Path(os.path.dirname(__file__)).parent.parent / "lacuene-exp" / "expanded" / "hgnc_craniofacial.json"
    if not exp_path.exists():
        exp_path = Path(os.environ.get("LACUENE_EXP_PATH", "")) / "expanded" / "hgnc_craniofacial.json"
    if not exp_path.exists():
        return []

    with open(exp_path) as f:
        expanded = json.load(f)

    nodes = []
    for gene in expanded:
        sym = gene.get("symbol", "")
        if not sym:
            continue
        # Skip genes already in curated set
        if sym in curated_symbols:
            continue
        # Filter out ZNF-family genes (large, low-signal cluster)
        if sym.startswith("ZNF"):
            continue
        nodes.append({
            "data": {
                "id": sym,
                "label": sym,
                "type": "expanded",
                "role_label": ROLE_LABELS["expanded"],
                "source_count": 0,
                "pub_count": 0,
                "pub_recent": 0,
                "velocity": 0,
                "trend": "none",
                "color": ROLE_COLORS["expanded"],
                "size": 8,
                "opacity": 0.5,
            }
        })
    return nodes


def main():
    print("to_vizdata: exporting model data...")
    sources = cue_export("gene_sources")
    genes_data = cue_export("genes")

    print(f"to_vizdata: building graph for {len(sources)} genes...")
    nodes = build_nodes(sources, genes_data)
    curated_count = len(nodes)
    edges = build_edges(genes_data)
    pathway_edges = build_pathway_edges(genes_data)
    ppi_edges = build_ppi_edges(genes_data)
    edges.extend(pathway_edges)
    edges.extend(ppi_edges)

    # Load expanded-tier genes from lacuene-exp (optional, no edges)
    curated_symbols = set(sources.keys())
    expanded_nodes = load_expanded_genes(curated_symbols)
    if expanded_nodes:
        nodes.extend(expanded_nodes)
        print(f"to_vizdata: added {len(expanded_nodes)} expanded-tier genes")

    vizdata = {
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "title": "lacuene: Neural Crest Gene Reconciliation",
            "gene_count": len(nodes),
            "curated_count": curated_count,
            "expanded_count": len(expanded_nodes),
            "edge_count": len(edges),
            "sources": ["Gene Ontology", "OMIM", "HPO", "UniProt", "FaceBase",
                        "ClinVar", "PubMed", "gnomAD", "NIH Reporter", "GTEx",
                        "ClinicalTrials", "STRING"],
            "roles": {k: v for k, v in ROLE_LABELS.items()},
        }
    }

    output = os.path.normpath(OUTPUT_PATH)
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w") as f:
        json.dump(vizdata, f, indent=2)

    print(f"to_vizdata: wrote {output}")
    print(f"  {len(nodes)} nodes ({curated_count} curated, {len(expanded_nodes)} expanded), {len(edges)} edges")

    # Print edge type breakdown
    pheno_edges = sum(1 for e in edges if e["data"]["type"] == "shared_phenotype")
    syn_edges = sum(1 for e in edges if e["data"]["type"] == "shared_syndrome")
    path_edges = sum(1 for e in edges if e["data"]["type"] == "shared_pathway")
    ppi_count = sum(1 for e in edges if e["data"]["type"] == "ppi")
    print(f"  {pheno_edges} phenotype, {syn_edges} syndrome, {path_edges} pathway, {ppi_count} PPI edges")


if __name__ == "__main__":
    main()
