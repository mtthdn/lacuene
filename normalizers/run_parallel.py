#!/usr/bin/env python3
"""Run all normalizers in parallel with staleness checking."""

import argparse
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

NORMALIZERS = [
    "from_go.py", "from_omim.py", "from_hpo.py", "from_uniprot.py",
    "from_facebase.py", "from_clinvar.py", "from_pubmed.py",
    "from_gnomad.py", "from_nih_reporter.py", "from_gtex.py",
    "from_clinicaltrials.py", "from_string.py",
]

# Map normalizer to its cache file for staleness checking
CACHE_FILES = {
    "from_go.py": None,  # no cache file, always run
    "from_omim.py": None,
    "from_hpo.py": "data/hpo/phenotype.hpoa",
    "from_uniprot.py": None,
    "from_facebase.py": "data/facebase/facebase_cache.json",
    "from_clinvar.py": "data/clinvar/clinvar_cache.json",
    "from_pubmed.py": "data/pubmed/pubmed_cache.json",
    "from_gnomad.py": "data/gnomad/gnomad_cache.json",
    "from_nih_reporter.py": "data/nih_reporter/nih_reporter_cache.json",
    "from_gtex.py": "data/gtex/gtex_cache.json",
    "from_clinicaltrials.py": "data/clinicaltrials/clinicaltrials_cache.json",
    "from_string.py": "data/string/string_cache.json",
}


def is_stale(normalizer: str, max_age_days: int) -> bool:
    cache = CACHE_FILES.get(normalizer)
    if cache is None:
        return True
    path = REPO_ROOT / cache
    if not path.exists():
        return True
    age = time.time() - path.stat().st_mtime
    return age > max_age_days * 86400


def run_normalizer(name: str) -> tuple[str, int, str]:
    script = REPO_ROOT / "normalizers" / name
    if not script.exists():
        return name, -1, f"Script not found: {script}"
    result = subprocess.run(
        [sys.executable, str(script)],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    output = result.stdout + result.stderr
    return name, result.returncode, output


def main():
    parser = argparse.ArgumentParser(description="Run normalizers in parallel")
    parser.add_argument("--stale-days", type=int, default=30,
                        help="Max cache age in days (default: 30)")
    parser.add_argument("--force", action="store_true",
                        help="Run all normalizers regardless of cache freshness")
    args = parser.parse_args()

    to_run = []
    for name in NORMALIZERS:
        script = REPO_ROOT / "normalizers" / name
        if not script.exists():
            print(f"  skip {name} (not yet created)")
            continue
        if args.force or is_stale(name, args.stale_days):
            to_run.append(name)
        else:
            print(f"  skip {name} (cache fresh)")

    if not to_run:
        print("All caches fresh, nothing to do.")
        return

    print(f"Running {len(to_run)} normalizers in parallel...")
    failed = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(run_normalizer, n): n for n in to_run}
        for future in as_completed(futures):
            name, rc, output = future.result()
            status = "OK" if rc == 0 else "FAILED"
            print(f"  [{status}] {name}")
            if output.strip():
                for line in output.strip().split("\n")[-3:]:
                    print(f"    {line}")
            if rc != 0:
                failed.append(name)

    if failed:
        print(f"\n{len(failed)} normalizer(s) failed: {', '.join(failed)}")
        sys.exit(1)
    print("\nAll normalizers complete.")


if __name__ == "__main__":
    main()
