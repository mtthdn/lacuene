package froq

// Unified gene schema. Ten sources contribute fields.
// Each source claims its own identifiers — no shared mutable fields.
//
// Pattern: sources OBSERVE, resolutions DECIDE.
// Canonical key: HGNC gene symbol.

#Gene: {
	symbol: string // HGNC canonical gene symbol

	// Per-source identifiers (never conflict — each source owns its own)
	go_id:       *"" | string // UniProtKB accession used by GO
	omim_id:     *"" | string // MIM number
	hpo_gene_id: *"" | string // NCBIGene ID used by HPO
	uniprot_id:  *"" | string // UniProt accession
	facebase_id: *"" | string // DERIVA RID

	// Source presence markers (default false, sources override to true)
	_in_go:       *false | true
	_in_omim:     *false | true
	_in_hpo:      *false | true
	_in_uniprot:  *false | true
	_in_facebase: *false | true

	// GO-owned fields (Gene Ontology annotations)
	go_terms?: [...#GOAnnotation]

	// OMIM-owned fields (Mendelian disease associations)
	omim_title?:     string
	omim_syndromes?: [...string]
	inheritance?:    string // "AD", "AR", "XL", etc.

	// HPO-owned fields (clinical phenotypes)
	phenotypes?: [...string]

	// UniProt-owned fields (protein data)
	protein_name?:          string
	organism?:              string
	sequence_length?:       int
	subcellular_locations?: [...string]
	functions?:             [...string]

	// FaceBase-owned fields (craniofacial research datasets)
	facebase_datasets?: [...#FaceBaseDataset]

	// ClinVar-owned fields (pathogenic variant data)
	clinvar_gene_id: *"" | string
	_in_clinvar:     *false | true
	pathogenic_count?: int
	clinvar_variants?: [...#ClinVarVariant]

	// PubMed-owned fields (craniofacial publication data)
	pubmed_gene_id: *"" | string
	_in_pubmed:     *false | true
	pubmed_total?:  int
	pubmed_recent?: int
	pubmed_papers?: [...#PubMedPaper]

	// gnomAD-owned fields (population constraint data)
	gnomad_id:  *"" | string // Ensembl gene ID
	_in_gnomad: *false | true
	pli_score?:  number // probability of LoF intolerance (0-1)
	loeuf_score?: number // loss-of-function observed/expected upper bound
	oe_lof?:     number // observed/expected ratio for LoF variants

	// NIH Reporter-owned fields (active grant data)
	_in_nih_reporter: *false | true
	active_grant_count?: int
	nih_reporter_projects?: [...#NIHProject]

	// GTEx-owned fields (tissue expression data)
	gtex_id:  *"" | string // Ensembl gene ID
	_in_gtex: *false | true
	top_tissues?: [...#GTExTissue]
	craniofacial_expression?: number // TPM in relevant tissues

	// ClinicalTrials.gov-owned fields (active clinical trials)
	_in_clinicaltrials: *false | true
	active_trial_count?: int
	clinicaltrials_studies?: [...#ClinicalTrial]

	// STRING-owned fields (protein-protein interactions)
	string_id: *"" | string // STRING protein ID
	_in_string: *false | true
	string_interaction_count?: int
	string_partners?: [...string] // top interaction partner gene symbols
}

#GOAnnotation: {
	term_id:   string // "GO:0003700"
	term_name: string // "DNA-binding transcription factor activity"
	aspect:    string // "F" (function), "P" (process), "C" (component)
}

#FaceBaseDataset: {
	title:       string
	species?:    string // "Mus musculus", "Homo sapiens"
	assay_type?: string // "RNA-seq", "ChIP-seq", "imaging"
}

#ClinVarVariant: {
	name:                  string
	clinical_significance: string
	condition:             string
}

#PubMedPaper: {
	title: string
	pmid:  string
	year:  int
}

#NIHProject: {
	project_num:   string // e.g. "R01DE028561"
	project_title: string
	pi_name?:      string
	org_name?:     string
	fiscal_year?:  int
}

#GTExTissue: {
	tissue:     string // e.g. "Brain - Cortex"
	median_tpm: number
}

#ClinicalTrial: {
	nct_id: string // e.g. "NCT04123456"
	title:  string
	status: string // "Recruiting", "Completed", etc.
	phase?: string // "Phase 1", "Phase 2", etc.
}

genes: [Symbol=string]: #Gene & {symbol: Symbol}
