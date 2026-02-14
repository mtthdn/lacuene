package froq

// Enrichment tiers: how many biological layers describe each gene?
// A gene with all 10 sources = fully characterized.
// A gene with 1 source = integration blind spot.
enrichment: {
	tiers: {for k, v in genes {
		(k): {
			has_function:    v._in_go
			has_disease:     v._in_omim
			has_phenotype:   v._in_hpo
			has_protein:     v._in_uniprot
			has_experiment:  v._in_facebase
			has_variants:    v._in_clinvar
			has_literature:  v._in_pubmed
			has_constraint:  v._in_gnomad
			has_funding:     v._in_nih_reporter
			has_expression:  v._in_gtex
			has_trials:      v._in_clinicaltrials
			has_interactions: v._in_string
		}
	}}
}
