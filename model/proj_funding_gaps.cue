package froq

// Funding gap analysis for NIDCR program officers.
// Scores genes by: has disease + has phenotype + no experimental data + low/no publications.
// Higher score = higher funding priority.

funding_gaps: {
	// Per-gene gap assessment
	genes_assessed: {for k, v in genes {
		(k): {
			symbol:         k
			has_disease:    v._in_omim
			has_phenotype:  v._in_hpo
			has_experiment: v._in_facebase
			has_variants:   v._in_clinvar
			has_literature: v._in_pubmed
			has_constraint: v._in_gnomad
			has_funding:      v._in_nih_reporter
			has_expression:   v._in_gtex
			has_trials:       v._in_clinicaltrials
			has_interactions: v._in_string
			if v.pubmed_total != _|_ {pub_count: v.pubmed_total}
			if v.pubmed_total == _|_ {pub_count: 0}
			if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
			if v.pathogenic_count != _|_ {variant_count: v.pathogenic_count}
			if v.pli_score != _|_ {pli_score: v.pli_score}
			if v.active_grant_count != _|_ {grant_count: v.active_grant_count}
		}
	}}

	// Critical gaps: disease genes with NO FaceBase data
	critical: [for k, v in genes if v._in_omim && !v._in_facebase {
		symbol: k
		if v.omim_syndromes != _|_ {syndromes: v.omim_syndromes}
		if v.pubmed_total != _|_ {pub_count: v.pubmed_total}
		if v.pubmed_total == _|_ {pub_count: 0}
		if v.phenotypes != _|_ {phenotype_count: len(v.phenotypes)}
		if v.pathogenic_count != _|_ {variant_count: v.pathogenic_count}
		if v.pli_score != _|_ {pli_score: v.pli_score}
		if v.active_grant_count != _|_ {grant_count: v.active_grant_count}
	}]

	summary: {
		total_genes:    len(genes)
		critical_count: len(critical)
	}
}
