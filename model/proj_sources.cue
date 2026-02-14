package froq

// Export source provenance as visible fields.
// Hidden _in_* fields aren't exported by CUE; this projection makes them available.
gene_sources: {for k, v in genes {
	(k): {
		in_go:           v._in_go
		in_omim:         v._in_omim
		in_hpo:          v._in_hpo
		in_uniprot:      v._in_uniprot
		in_facebase:     v._in_facebase
		in_clinvar:      v._in_clinvar
		in_pubmed:       v._in_pubmed
		in_gnomad:           v._in_gnomad
		in_nih_reporter:     v._in_nih_reporter
		in_gtex:             v._in_gtex
		in_clinicaltrials:   v._in_clinicaltrials
		in_string:           v._in_string
	}
}}
