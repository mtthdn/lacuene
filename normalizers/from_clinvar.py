#!/usr/bin/env python3
"""
Normalizer: ClinVar -> model/clinvar.cue

Queries NCBI ClinVar via E-utilities (esearch + esummary) for each of the
20 neural crest genes, extracting pathogenic/likely pathogenic variant counts
and top variant details.

Results are cached in data/clinvar/clinvar_cache.json for reproducibility.
Respects NCBI rate limits (3 req/sec without API key).

Usage:
    python3 normalizers/from_clinvar.py
"""

import json
import sys
import time
from pathlib import Path

# Resolve paths relative to repo root (parent of normalizers/)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "normalizers"))

from genes import GENES
from utils import fetch_json_with_retry

CACHE_DIR = REPO_ROOT / "data" / "clinvar"
CACHE_FILE = CACHE_DIR / "clinvar_cache.json"
OUTPUT_FILE = REPO_ROOT / "model" / "clinvar.cue"

ESEARCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=clinvar&retmode=json&retmax=0"
    "&term={gene}[gene]+AND+(clinsig_pathogenic[prop]+OR+clinsig_likely_pathogenic[prop])"
)

# esearch with retmax=5 to get IDs for top variants
ESEARCH_IDS_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=clinvar&retmode=json&retmax=5&sort=clinical_significance"
    "&term={gene}[gene]+AND+(clinsig_pathogenic[prop]+OR+clinsig_likely_pathogenic[prop])"
)

ESUMMARY_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=clinvar&retmode=json&id={ids}"
)

REQUEST_DELAY = 0.5  # seconds between requests (NCBI rate limits without API key)


def fetch_json(url: str) -> dict | None:
    """Fetch a URL and return parsed JSON, or None on failure."""
    try:
        return fetch_json_with_retry(url, headers={"Accept": "application/json"})
    except Exception as e:
        print(f"  WARNING: request failed: {e}", file=sys.stderr)
        return None


def query_clinvar_gene(symbol: str) -> dict | None:
    """
    Query ClinVar for a gene symbol. Returns dict with:
      - pathogenic_count: int
      - variants: list of {name, clinical_significance, condition}
    Or None on failure.
    """
    # Step 1: get total count of pathogenic/likely pathogenic variants
    url = ESEARCH_URL.format(gene=symbol)
    data = fetch_json(url)
    if data is None or "esearchresult" not in data:
        return None

    count = int(data["esearchresult"].get("count", 0))
    time.sleep(REQUEST_DELAY)

    # Step 2: get IDs for top 5 variants
    url = ESEARCH_IDS_URL.format(gene=symbol)
    data = fetch_json(url)
    if data is None or "esearchresult" not in data:
        return {"pathogenic_count": count, "variants": []}

    id_list = data["esearchresult"].get("idlist", [])
    if not id_list:
        return {"pathogenic_count": count, "variants": []}

    time.sleep(REQUEST_DELAY)

    # Step 3: get variant summaries
    ids_param = ",".join(id_list)
    url = ESUMMARY_URL.format(ids=ids_param)
    data = fetch_json(url)
    if data is None or "result" not in data:
        return {"pathogenic_count": count, "variants": []}

    variants = []
    uids = data["result"].get("uids", [])
    for uid in uids[:5]:
        entry = data["result"].get(uid, {})
        if not entry:
            continue

        # Extract variant title
        name = entry.get("title", "")

        # Extract clinical significance
        clin_sig = entry.get("clinical_significance", {})
        if isinstance(clin_sig, dict):
            sig_text = clin_sig.get("description", "")
        else:
            sig_text = str(clin_sig) if clin_sig else ""

        # Extract condition/trait names
        trait_set = entry.get("trait_set", [])
        conditions = []
        if isinstance(trait_set, list):
            for trait in trait_set:
                if isinstance(trait, dict):
                    trait_name = trait.get("trait_name", "")
                    if trait_name:
                        conditions.append(trait_name)
        condition = "; ".join(conditions) if conditions else "not specified"

        if name:
            variants.append({
                "name": name,
                "clinical_significance": sig_text,
                "condition": condition,
            })

    return {"pathogenic_count": count, "variants": variants}


def load_cache() -> dict:
    """Load cached ClinVar data if available."""
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {}


def save_cache(cache: dict) -> None:
    """Persist the ClinVar cache to disk."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
    print(f"  cached: {CACHE_FILE}")


def escape_cue_string(s: str) -> str:
    """Escape a string for CUE literal output."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def generate_cue(clinvar_data: dict) -> str:
    """Generate CUE source from ClinVar data, keyed by HGNC symbol."""
    gene_count = len(clinvar_data)
    lines = [
        "package froq",
        "",
        "// ClinVar: pathogenic variant data for neural crest genes.",
        "// Source: NCBI ClinVar via E-utilities (esearch + esummary)",
        f"// Generated by normalizers/from_clinvar.py -- {gene_count} genes",
        "",
        "genes: {",
    ]

    for symbol in sorted(clinvar_data.keys()):
        entry = clinvar_data[symbol]
        gene_info = GENES[symbol]
        ncbi_id = gene_info["ncbi"]
        pathogenic_count = entry["pathogenic_count"]
        variants = entry.get("variants", [])

        lines.append(f'\t"{symbol}": {{')
        lines.append(f"\t\t_in_clinvar:     true")
        lines.append(f'\t\tclinvar_gene_id: "{ncbi_id}"')
        lines.append(f"\t\tpathogenic_count: {pathogenic_count}")

        if variants:
            lines.append(f"\t\tclinvar_variants: [")
            for v in variants:
                name = escape_cue_string(v["name"])
                sig = escape_cue_string(v["clinical_significance"])
                cond = escape_cue_string(v["condition"])
                lines.append(f"\t\t\t{{")
                lines.append(f'\t\t\t\tname:                  "{name}"')
                lines.append(f'\t\t\t\tclinical_significance: "{sig}"')
                lines.append(f'\t\t\t\tcondition:             "{cond}"')
                lines.append(f"\t\t\t}},")
            lines.append(f"\t\t]")

        lines.append(f"\t}}")

    lines.append("}")
    lines.append("")  # trailing newline

    return "\n".join(lines)


def main():
    print("from_clinvar: querying ClinVar for neural crest genes...")

    cache = load_cache()
    clinvar_data = {}
    fetched = 0
    cached_count = 0
    failed = 0

    for symbol in sorted(GENES.keys()):
        if symbol in cache:
            print(f"  {symbol}: cached ({cache[symbol]['pathogenic_count']} pathogenic)")
            clinvar_data[symbol] = cache[symbol]
            cached_count += 1
            continue

        print(f"  {symbol}: querying ClinVar...", end=" ", flush=True)
        result = query_clinvar_gene(symbol)
        time.sleep(REQUEST_DELAY)

        if result is None:
            print(f"FAILED (skipping)", file=sys.stderr)
            failed += 1
            continue

        print(f"{result['pathogenic_count']} pathogenic, "
              f"{len(result['variants'])} top variants")
        clinvar_data[symbol] = result
        cache[symbol] = result
        fetched += 1

    # Save updated cache
    save_cache(cache)

    if not clinvar_data:
        print("ERROR: no ClinVar data retrieved for any gene", file=sys.stderr)
        sys.exit(1)

    # Write CUE output
    print("from_clinvar: writing model/clinvar.cue...")
    cue_source = generate_cue(clinvar_data)
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        f.write(cue_source)

    # Stats
    total_pathogenic = sum(d["pathogenic_count"] for d in clinvar_data.values())
    total_variants = sum(len(d.get("variants", [])) for d in clinvar_data.values())

    print(f"from_clinvar: wrote {OUTPUT_FILE}")
    print(f"  {len(clinvar_data)} genes, {total_pathogenic} total pathogenic variants, "
          f"{total_variants} top variant records")
    print(f"  ({fetched} fetched, {cached_count} cached, {failed} failed)")


if __name__ == "__main__":
    main()
