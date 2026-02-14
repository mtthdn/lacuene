#!/usr/bin/env python3
"""
Normalizer: GTEx -> model/gtex.cue

Maps HGNC symbols to Ensembl gene IDs via MyGene.info, then queries the
GTEx Portal API v2 for median gene expression across tissues. Extracts
top 5 tissues by median TPM and computes craniofacial_expression as the
average TPM across relevant head/face tissues.

Results are cached in data/gtex/gtex_cache.json for reproducibility.

Usage:
    python3 normalizers/from_gtex.py
"""

import json
import sys
import time
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "normalizers"))

from genes import GENES
from pipeline import PipelineReport, escape_cue_string
from utils import fetch_json_with_retry

CACHE_DIR = REPO_ROOT / "data" / "gtex"
CACHE_FILE = CACHE_DIR / "gtex_cache.json"
OUTPUT_FILE = REPO_ROOT / "model" / "gtex.cue"

# MyGene.info: symbol -> Ensembl gene ID
MYGENE_URL = "https://mygene.info/v3/query?q=symbol:{symbol}&species=human&fields=ensembl.gene"

# GTEx Portal API v2: median gene expression by tissue
GTEX_EXPRESSION_URL = (
    "https://gtexportal.org/api/v2/expression/medianGeneExpression"
    "?gencodeId={ensembl_id}&datasetId=gtex_v8"
)

REQUEST_DELAY = 0.5  # seconds between requests

# Tissues used to compute craniofacial_expression (average of available)
CRANIOFACIAL_TISSUES = {
    "Minor Salivary Gland",
    "Nerve - Tibial",
    "Skin - Sun Exposed (Lower leg)",
    "Brain - Cerebellum",
    "Brain - Cortex",
}


def fetch_json(url: str) -> dict | None:
    """Fetch a URL and return parsed JSON, or None on failure."""
    try:
        return fetch_json_with_retry(url, headers={"Accept": "application/json"})
    except Exception as e:
        print(f"  WARNING: request failed: {e}", file=sys.stderr)
        return None


def resolve_ensembl_id(symbol: str) -> str | None:
    """Resolve HGNC symbol to Ensembl gene ID via MyGene.info."""
    url = MYGENE_URL.format(symbol=urllib.parse.quote(symbol))
    data = fetch_json(url)
    if data is None:
        return None

    hits = data.get("hits", [])
    if not hits:
        return None

    # Take the top hit
    hit = hits[0]
    ensembl = hit.get("ensembl", {})

    # ensembl can be a list (multiple transcripts) or a dict
    if isinstance(ensembl, list):
        # Take the first entry
        ensembl = ensembl[0] if ensembl else {}

    gene_id = ensembl.get("gene", "")
    if gene_id and gene_id.startswith("ENSG"):
        return gene_id

    return None


def query_gtex_expression(ensembl_id: str) -> list[dict] | None:
    """
    Query GTEx Portal for median gene expression. Returns list of
    {tissue, median_tpm} dicts, or None on failure.

    Tries unversioned Ensembl ID first, then falls back to versioned.
    """
    # Try unversioned first
    url = GTEX_EXPRESSION_URL.format(ensembl_id=urllib.parse.quote(ensembl_id))
    data = fetch_json(url)

    # Check if we got valid expression data
    expression_data = None
    if data is not None:
        expression_data = data.get("data", [])
        if not expression_data:
            expression_data = None

    # If unversioned failed, try with a version suffix
    if expression_data is None:
        time.sleep(REQUEST_DELAY)
        versioned_id = f"{ensembl_id}.1"
        url = GTEX_EXPRESSION_URL.format(ensembl_id=urllib.parse.quote(versioned_id))
        data = fetch_json(url)
        if data is not None:
            expression_data = data.get("data", [])
            if not expression_data:
                expression_data = None

    if expression_data is None:
        return None

    tissues = []
    for entry in expression_data:
        tissue_name = entry.get("tissueSiteDetailId", "") or entry.get("tissueId", "")
        # GTEx API may use tissueSiteDetailId or a description field
        tissue_desc = entry.get("tissueSiteDetail", tissue_name)
        median_tpm = entry.get("median", 0.0)
        if tissue_desc and median_tpm is not None:
            tissues.append({
                "tissue": tissue_desc,
                "median_tpm": round(float(median_tpm), 2),
            })

    return tissues


def extract_top_tissues(tissues: list[dict], n: int = 5) -> list[dict]:
    """Return the top N tissues by median TPM."""
    sorted_tissues = sorted(tissues, key=lambda t: t["median_tpm"], reverse=True)
    return sorted_tissues[:n]


def compute_craniofacial_expression(tissues: list[dict]) -> float:
    """
    Compute average TPM across craniofacial-relevant tissues.
    Uses whichever of CRANIOFACIAL_TISSUES are present in the data.
    """
    relevant = [t for t in tissues if t["tissue"] in CRANIOFACIAL_TISSUES]
    if not relevant:
        return 0.0
    avg = sum(t["median_tpm"] for t in relevant) / len(relevant)
    return round(avg, 2)


def query_gene(symbol: str) -> dict | None:
    """
    Full pipeline for one gene: resolve Ensembl ID, query GTEx expression.
    Returns dict with ensembl_id, top_tissues, craniofacial_expression,
    or a partial dict with just ensembl_id if expression lookup fails,
    or None if even Ensembl resolution fails.
    """
    ensembl_id = resolve_ensembl_id(symbol)
    if ensembl_id is None:
        return None

    time.sleep(REQUEST_DELAY)

    tissues = query_gtex_expression(ensembl_id)
    if tissues is None or len(tissues) == 0:
        # Partial result: we know the Ensembl ID but have no expression data
        return {
            "ensembl_id": ensembl_id,
            "top_tissues": [],
            "craniofacial_expression": 0.0,
        }

    top = extract_top_tissues(tissues)
    cranio = compute_craniofacial_expression(tissues)

    return {
        "ensembl_id": ensembl_id,
        "top_tissues": top,
        "craniofacial_expression": cranio,
    }


def load_cache() -> dict:
    """Load cached GTEx data if available."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    """Persist the GTEx cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    print(f"  cached: {CACHE_FILE}")


def generate_cue(gtex_data: dict) -> str:
    """Generate CUE source from GTEx data, keyed by HGNC symbol."""
    gene_count = len(gtex_data)
    lines = [
        "package froq",
        "",
        "// GTEx: tissue expression data for neural crest genes.",
        "// Source: GTEx Portal API v2 + MyGene.info (Ensembl ID resolution)",
        f"// Generated by normalizers/from_gtex.py -- {gene_count} genes",
        "",
        "genes: {",
    ]

    for symbol in sorted(gtex_data.keys()):
        entry = gtex_data[symbol]
        ensembl_id = escape_cue_string(entry["ensembl_id"])
        cranio = entry["craniofacial_expression"]
        top_tissues = entry.get("top_tissues", [])

        lines.append(f'\t"{symbol}": {{')
        lines.append(f"\t\t_in_gtex:  true")
        lines.append(f'\t\tgtex_id:   "{ensembl_id}"')
        lines.append(f"\t\tcraniofacial_expression: {cranio}")

        if top_tissues:
            lines.append(f"\t\ttop_tissues: [")
            for t in top_tissues:
                tissue = escape_cue_string(t["tissue"])
                tpm = t["median_tpm"]
                lines.append(f'\t\t\t{{tissue: "{tissue}", median_tpm: {tpm}}},')
            lines.append(f"\t\t]")

        lines.append(f"\t}}")

    lines.append("}")
    lines.append("")  # trailing newline

    return "\n".join(lines)


def main():
    report = PipelineReport("from_gtex")
    print(f"from_gtex: querying GTEx for {len(GENES)} neural crest genes...")

    cache = load_cache()
    gtex_data = {}
    fetched = 0

    for symbol in sorted(GENES.keys()):
        if symbol in cache:
            entry = cache[symbol]
            n_tissues = len(entry.get("top_tissues", []))
            print(f"  {symbol}: cached (ensembl={entry['ensembl_id']}, {n_tissues} tissues)")
            gtex_data[symbol] = entry
            report.cached(symbol, f"ensembl={entry['ensembl_id']}")
            continue

        print(f"  {symbol}: querying...", end=" ", flush=True)
        result = query_gene(symbol)
        time.sleep(REQUEST_DELAY)

        if result is None:
            print("FAILED (no Ensembl ID)")
            report.failed(symbol, "could not resolve Ensembl ID")
            continue

        n_tissues = len(result.get("top_tissues", []))
        cranio = result["craniofacial_expression"]
        print(f"ensembl={result['ensembl_id']}, {n_tissues} tissues, cranio={cranio}")

        gtex_data[symbol] = result
        cache[symbol] = result
        report.ok(symbol, f"ensembl={result['ensembl_id']}, {n_tissues} tissues")
        fetched += 1

    # Save updated cache
    save_cache(cache)

    if not gtex_data:
        print("ERROR: no GTEx data retrieved for any gene", file=sys.stderr)
        sys.exit(1)

    # Write CUE output
    print("from_gtex: writing model/gtex.cue...")
    cue_source = generate_cue(gtex_data)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(cue_source)

    print(f"from_gtex: wrote {OUTPUT_FILE}")
    print(report.summary())


if __name__ == "__main__":
    main()
