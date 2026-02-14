package froq

// Gap report: surfaces genes missing from each data source.
// Drives research prioritization — if a gene has OMIM disease
// association but no FaceBase experimental data, that's a research gap.

// Pre-compute per-gene source count using flag struct.
_source_flags: {for k, v in genes {
	(k): {
		_c_go:           v._in_go
		_c_omim:         v._in_omim
		_c_hpo:          v._in_hpo
		_c_uniprot:      v._in_uniprot
		_c_facebase:     v._in_facebase
		_c_clinvar:      v._in_clinvar
		_c_pubmed:       v._in_pubmed
		_c_gnomad:           v._in_gnomad
		_c_nih_reporter:     v._in_nih_reporter
		_c_gtex:             v._in_gtex
		_c_clinicaltrials:   v._in_clinicaltrials
		_c_string:           v._in_string
	}
}}

gap_report: {
	summary: {
		total:            len(genes)
		in_all_five:      len(_all_five)
		in_all_seven:     len(_all_seven)
		in_all_ten:       len(_all_ten)
		missing_go_count:           len(missing_go)
		missing_omim_count:         len(missing_omim)
		missing_hpo_count:          len(missing_hpo)
		missing_uniprot_count:      len(missing_uniprot)
		missing_facebase_count:     len(missing_facebase)
		missing_clinvar_count:      len(missing_clinvar)
		missing_pubmed_count:       len(missing_pubmed)
		missing_gnomad_count:           len(missing_gnomad)
		missing_nih_reporter_count:     len(missing_nih_reporter)
		missing_gtex_count:             len(missing_gtex)
		missing_clinicaltrials_count:   len(missing_clinicaltrials)
		missing_string_count:           len(missing_string)
	}

	// Key research gap: known disease genes with no experimental coverage at NIDCR.
	research_gaps: [for k, v in genes if v._in_omim && !v._in_facebase {
		symbol: k
		if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
	}]

	// Per-source missing lists
	missing_go: [for k, v in genes if !v._in_go {symbol: k}]
	missing_omim: [for k, v in genes if !v._in_omim {symbol: k}]
	missing_hpo: [for k, v in genes if !v._in_hpo {symbol: k}]
	missing_uniprot: [for k, v in genes if !v._in_uniprot {symbol: k}]
	missing_facebase: [for k, v in genes if !v._in_facebase {symbol: k}]
	missing_clinvar: [for k, v in genes if !v._in_clinvar {symbol: k}]
	missing_pubmed: [for k, v in genes if !v._in_pubmed {symbol: k}]
	missing_gnomad: [for k, v in genes if !v._in_gnomad {symbol: k}]
	missing_nih_reporter: [for k, v in genes if !v._in_nih_reporter {symbol: k}]
	missing_gtex: [for k, v in genes if !v._in_gtex {symbol: k}]
	missing_clinicaltrials: [for k, v in genes if !v._in_clinicaltrials {symbol: k}]
	missing_string: [for k, v in genes if !v._in_string {symbol: k}]

	_all_five: [for k, v in genes
		if v._in_go && v._in_omim && v._in_hpo && v._in_uniprot && v._in_facebase {k}]
	_all_seven: [for k, v in genes
		if v._in_go && v._in_omim && v._in_hpo && v._in_uniprot && v._in_facebase && v._in_clinvar && v._in_pubmed {k}]
	_all_ten: [for k, v in genes
		if v._in_go && v._in_omim && v._in_hpo && v._in_uniprot && v._in_facebase && v._in_clinvar && v._in_pubmed && v._in_gnomad && v._in_nih_reporter && v._in_gtex {k}]
}
