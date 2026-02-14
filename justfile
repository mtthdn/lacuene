# froq: Neural crest gene reconciliation pipeline
# Unifies 12 biomedical sources into one CUE model via lattice semantics.

default: validate generate

# Check CUE version matches pinned version
check-cue:
    #!/usr/bin/env bash
    if [ -f .cue-version ]; then
        expected=$(cat .cue-version | head -1)
        actual=$(cue version 2>/dev/null | head -1 | awk '{print $NF}')
        if [ "$expected" != "$actual" ]; then
            echo "WARNING: CUE version mismatch (expected $expected, got $actual)"
        fi
    fi

# Normalize all sources into CUE model files
normalize:
    python3 normalizers/from_go.py
    python3 normalizers/from_omim.py
    python3 normalizers/from_hpo.py
    python3 normalizers/from_uniprot.py
    python3 normalizers/from_facebase.py
    python3 normalizers/from_clinvar.py
    python3 normalizers/from_pubmed.py
    python3 normalizers/from_gnomad.py
    python3 normalizers/from_nih_reporter.py
    python3 normalizers/from_gtex.py
    python3 normalizers/from_clinicaltrials.py
    python3 normalizers/from_string.py

# Run normalizers in parallel
normalize-parallel:
    python3 normalizers/run_parallel.py --force

# Refresh only stale sources (default: 30 days)
refresh stale_days="30":
    python3 normalizers/run_parallel.py --stale-days {{stale_days}}

# Validate the unified CUE model
validate: check-cue
    cue vet -c ./model/

# Generate all projection outputs as JSON
generate: validate
    mkdir -p output
    cue export ./model/ -e gap_report > output/gap_report.json
    cue export ./model/ -e enrichment > output/enrichment.json
    cue export ./model/ -e gene_sources > output/sources.json
    cue export ./model/ -e funding_gaps > output/funding_gaps.json
    cue export ./model/ -e weighted_gaps > output/weighted_gaps.json
    @echo "Generated: $(du -sh output | cut -f1) in output/"

# Quick summary stats
summary:
    @cue export ./model/ -e gap_report.summary 2>/dev/null | python3 -m json.tool

# Spot-check a specific gene
check gene:
    cue export ./model/ -e 'genes["{{gene}}"]' | python3 -m json.tool

# Research gap report
gaps:
    @cue export ./model/ -e gap_report | python3 -m json.tool

# Full rebuild from API data
rebuild: normalize validate generate
    @echo "Full rebuild complete."

# Generate VizData JSON for graph explorer
vizdata: validate
    python3 generators/to_vizdata.py

# Generate human-readable summary
report: validate
    python3 generators/to_summary.py

# Run integration tests
test: validate
    python3 tests/test_pipeline.py

# Validate examples (self-contained, no API)
examples:
    cue vet -c ./examples/

# Normalize individual sources
normalize-go:
    python3 normalizers/from_go.py

normalize-omim:
    python3 normalizers/from_omim.py

normalize-hpo:
    python3 normalizers/from_hpo.py

normalize-uniprot:
    python3 normalizers/from_uniprot.py

normalize-facebase:
    python3 normalizers/from_facebase.py

normalize-clinvar:
    python3 normalizers/from_clinvar.py

normalize-pubmed:
    python3 normalizers/from_pubmed.py

normalize-gnomad:
    python3 normalizers/from_gnomad.py

normalize-nih-reporter:
    python3 normalizers/from_nih_reporter.py

normalize-gtex:
    python3 normalizers/from_gtex.py

normalize-clinicaltrials:
    python3 normalizers/from_clinicaltrials.py

normalize-string:
    python3 normalizers/from_string.py

# Build static site
site: vizdata
    python3 generators/to_site.py

# Deploy site
deploy: site
    bash deploy.sh

# Generate all outputs
all: generate vizdata report site
