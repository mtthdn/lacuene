#!/usr/bin/env python3
"""
Canonical gene list and cross-reference IDs for neural crest genes.

This is the name resolution layer. Every normalizer imports GENES to know
which genes to query and how to map source-native IDs back to HGNC symbols.

Covers the full neural crest gene regulatory network (GRN):
  - Neural plate border specification
  - Neural crest specifiers
  - EMT and migration
  - Signaling pathways (BMP, WNT, FGF, SHH, NOTCH, EDN, RA)
  - Craniofacial patterning and disease
  - Melanocyte / pigmentation
  - Enteric nervous system
  - Cardiac neural crest

References:
  Simoes-Costa & Bronner, Development 142:242-257 (2015)
  Martik & Bronner, Nat Rev Mol Cell Biol 18:453-464 (2017)
  Sauka-Spengler & Bronner-Fraser, Nat Rev Mol Cell Biol 9:557-568 (2008)
"""

# Each entry: HGNC symbol -> known IDs across sources.
# ncbi   = NCBI Gene ID (human)
# uniprot = UniProt canonical accession (human)
# omim   = OMIM gene/locus MIM number
GENES = {
    # ── Neural plate border specification ──────────────────────────
    "DLX2":    {"ncbi": "1746",   "uniprot": "Q07687", "omim": "126255"},
    "DLX3":    {"ncbi": "1747",   "uniprot": "O60479", "omim": "600525"},
    "DLX5":    {"ncbi": "1749",   "uniprot": "P56178", "omim": "600028"},
    "DLX6":    {"ncbi": "1750",   "uniprot": "P56182", "omim": "600030"},
    "GBX2":    {"ncbi": "2637",   "uniprot": "P40424", "omim": "601135"},
    "MSX1":    {"ncbi": "4487",   "uniprot": "P28360", "omim": "142983"},
    "MSX2":    {"ncbi": "4488",   "uniprot": "P35548", "omim": "123101"},
    "PAX3":    {"ncbi": "5077",   "uniprot": "P23760", "omim": "606597"},
    "PAX6":    {"ncbi": "5080",   "uniprot": "P26367", "omim": "607108"},
    "PAX7":    {"ncbi": "5081",   "uniprot": "P23759", "omim": "167410"},
    "TFAP2A":  {"ncbi": "7020",   "uniprot": "P05549", "omim": "107580"},
    "TFAP2B":  {"ncbi": "7021",   "uniprot": "Q92481", "omim": "601601"},
    "ZIC1":    {"ncbi": "7545",   "uniprot": "Q15915", "omim": "600470"},

    # ── Neural crest specifiers ────────────────────────────────────
    "ETS1":    {"ncbi": "2113",   "uniprot": "P14921", "omim": "164720"},
    "FOXD3":   {"ncbi": "27022",  "uniprot": "Q9UJU5", "omim": "611539"},
    "MYCN":    {"ncbi": "4613",   "uniprot": "P04198", "omim": "164840"},
    "NR2F1":   {"ncbi": "7025",   "uniprot": "P10589", "omim": "132890"},
    "NR2F2":   {"ncbi": "7026",   "uniprot": "P24468", "omim": "107773"},
    "SNAI1":   {"ncbi": "6615",   "uniprot": "O95863", "omim": "604238"},
    "SNAI2":   {"ncbi": "6591",   "uniprot": "O43623", "omim": "602150"},
    "SOX5":    {"ncbi": "6660",   "uniprot": "P35711", "omim": "604975"},
    "SOX8":    {"ncbi": "30812",  "uniprot": "P57073", "omim": "605923"},
    "SOX9":    {"ncbi": "6662",   "uniprot": "P48436", "omim": "608160"},
    "SOX10":   {"ncbi": "6663",   "uniprot": "P56693", "omim": "602229"},
    "TWIST1":  {"ncbi": "7291",   "uniprot": "Q15672", "omim": "601622"},
    "TWIST2":  {"ncbi": "117581", "uniprot": "Q8WVJ9", "omim": "607556"},

    # ── EMT and migration ─────────────────────────────────────────
    "CDH2":    {"ncbi": "1000",   "uniprot": "P19022", "omim": "114020"},
    "CDH6":    {"ncbi": "1004",   "uniprot": "P55285", "omim": "603007"},
    "CDH11":   {"ncbi": "1009",   "uniprot": "P55287", "omim": "600023"},
    "CXCR4":   {"ncbi": "7852",   "uniprot": "P61073", "omim": "162643"},
    "FN1":     {"ncbi": "2335",   "uniprot": "P02751", "omim": "135600"},
    "ITGB1":   {"ncbi": "3688",   "uniprot": "P05556", "omim": "135630"},
    "MMP2":    {"ncbi": "4313",   "uniprot": "P08253", "omim": "120360"},
    "MMP9":    {"ncbi": "4318",   "uniprot": "P14780", "omim": "120361"},
    "NGFR":    {"ncbi": "4804",   "uniprot": "P08138", "omim": "162010"},
    "RAC1":    {"ncbi": "5879",   "uniprot": "P63000", "omim": "602048"},
    "RHOA":    {"ncbi": "387",    "uniprot": "P61586", "omim": "165390"},
    "ZEB2":    {"ncbi": "9839",   "uniprot": "O60315", "omim": "605802"},

    # ── Signaling pathways ────────────────────────────────────────
    "ADAM10":   {"ncbi": "102",    "uniprot": "O14672", "omim": "602192"},
    "ALDH1A2": {"ncbi": "8854",   "uniprot": "O94788", "omim": "603687"},
    "AXIN2":   {"ncbi": "8313",   "uniprot": "Q9Y2T1", "omim": "604025"},
    "BMP2":    {"ncbi": "650",    "uniprot": "P12643", "omim": "112261"},
    "BMP4":    {"ncbi": "652",    "uniprot": "P12644", "omim": "112262"},
    "BMP7":    {"ncbi": "655",    "uniprot": "P18075", "omim": "112267"},
    "CTNNB1":  {"ncbi": "1499",   "uniprot": "P35222", "omim": "116806"},
    "DLL1":    {"ncbi": "28514",  "uniprot": "O00548", "omim": "606582"},
    "EDN1":    {"ncbi": "1906",   "uniprot": "P05305", "omim": "131240"},
    "EDN3":    {"ncbi": "1908",   "uniprot": "P14138", "omim": "131242"},
    "EDNRA":   {"ncbi": "1909",   "uniprot": "P25101", "omim": "131243"},
    "EDNRB":   {"ncbi": "1910",   "uniprot": "P24530", "omim": "131244"},
    "FGF8":    {"ncbi": "2253",   "uniprot": "P55075", "omim": "600483"},
    "FGFR1":   {"ncbi": "2260",   "uniprot": "P11362", "omim": "136350"},
    "FGFR2":   {"ncbi": "2263",   "uniprot": "P21802", "omim": "176943"},
    "FGFR3":   {"ncbi": "2261",   "uniprot": "P22607", "omim": "134934"},
    "JAG1":    {"ncbi": "182",    "uniprot": "P78504", "omim": "601920"},
    "LEF1":    {"ncbi": "51176",  "uniprot": "Q9UJU2", "omim": "153245"},
    "NOTCH1":  {"ncbi": "4851",   "uniprot": "P46531", "omim": "190198"},
    "NOTCH2":  {"ncbi": "4853",   "uniprot": "Q04721", "omim": "600275"},
    "RARA":    {"ncbi": "5914",   "uniprot": "P10276", "omim": "180240"},
    "SHH":     {"ncbi": "6469",   "uniprot": "Q15465", "omim": "600725"},
    "SMAD1":   {"ncbi": "4086",   "uniprot": "Q15797", "omim": "601595"},
    "TGFBR1":  {"ncbi": "7046",   "uniprot": "P36897", "omim": "190181"},
    "TGFBR2":  {"ncbi": "7048",   "uniprot": "P37173", "omim": "190182"},
    "WNT1":    {"ncbi": "7471",   "uniprot": "P04628", "omim": "164820"},
    "WNT3A":   {"ncbi": "89780",  "uniprot": "P56704", "omim": "606359"},

    # ── Craniofacial patterning and disease ───────────────────────
    "CHD7":    {"ncbi": "55636",  "uniprot": "Q9P2D1", "omim": "608892"},
    "ECE1":    {"ncbi": "1889",   "uniprot": "P42892", "omim": "600423"},
    "ERBB3":   {"ncbi": "2065",   "uniprot": "P21860", "omim": "190151"},
    "EVC":     {"ncbi": "2121",   "uniprot": "P57679", "omim": "604831"},
    "IRF6":    {"ncbi": "3664",   "uniprot": "O14896", "omim": "607199"},
    "NF1":     {"ncbi": "4763",   "uniprot": "P21359", "omim": "613113"},
    "RUNX2":   {"ncbi": "860",    "uniprot": "Q13950", "omim": "600211"},
    "SOX2":    {"ncbi": "6657",   "uniprot": "P48431", "omim": "184429"},
    "TBX1":    {"ncbi": "6899",   "uniprot": "O43435", "omim": "602054"},
    "TCOF1":   {"ncbi": "6949",   "uniprot": "Q13428", "omim": "606847"},

    # ── Melanocyte / pigmentation ─────────────────────────────────
    "DCT":     {"ncbi": "1638",   "uniprot": "P40126", "omim": "191275"},
    "KIT":     {"ncbi": "3815",   "uniprot": "P10721", "omim": "164920"},
    "MITF":    {"ncbi": "4286",   "uniprot": "O75030", "omim": "156845"},
    "PMEL":    {"ncbi": "6490",   "uniprot": "P40967", "omim": "155550"},
    "TYR":     {"ncbi": "7299",   "uniprot": "P14679", "omim": "606933"},
    "TYRP1":   {"ncbi": "7306",   "uniprot": "P17643", "omim": "115501"},

    # ── Enteric nervous system ────────────────────────────────────
    "GDNF":    {"ncbi": "2668",   "uniprot": "P39905", "omim": "600837"},
    "GFRA1":   {"ncbi": "2674",   "uniprot": "P56159", "omim": "601496"},
    "PHOX2B":  {"ncbi": "8929",   "uniprot": "Q99453", "omim": "603851"},
    "RET":     {"ncbi": "5979",   "uniprot": "P07949", "omim": "164761"},
    "SEMA3A":  {"ncbi": "10371",  "uniprot": "Q14563", "omim": "603961"},
    "NRP1":    {"ncbi": "8829",   "uniprot": "O14786", "omim": "602069"},

    # ── Cardiac neural crest ──────────────────────────────────────
    "GATA4":   {"ncbi": "2626",   "uniprot": "P43694", "omim": "600576"},
    "HAND1":   {"ncbi": "9421",   "uniprot": "O96004", "omim": "602406"},
    "HAND2":   {"ncbi": "9464",   "uniprot": "P61296", "omim": "602407"},
    "MEF2C":   {"ncbi": "4208",   "uniprot": "Q06413", "omim": "600662"},
    "NKX2-5":  {"ncbi": "1482",   "uniprot": "P52952", "omim": "600584"},
    "PLXNA2":  {"ncbi": "5362",   "uniprot": "O75051", "omim": "601054"},
    "SEMA3C":  {"ncbi": "10512",  "uniprot": "Q99985", "omim": "602645"},
    "TBX5":    {"ncbi": "6910",   "uniprot": "Q99593", "omim": "601620"},
}

# Developmental role classification (for VizData coloring)
ROLES = {
    "border_spec": [
        "DLX2", "DLX3", "DLX5", "DLX6", "GBX2",
        "MSX1", "MSX2", "PAX3", "PAX6", "PAX7",
        "TFAP2A", "TFAP2B", "ZIC1",
    ],
    "nc_specifier": [
        "ETS1", "FOXD3", "MYCN", "NR2F1", "NR2F2",
        "SNAI1", "SNAI2", "SOX5", "SOX8", "SOX9", "SOX10",
        "TWIST1", "TWIST2",
    ],
    "emt_migration": [
        "CDH2", "CDH6", "CDH11", "CXCR4", "FN1",
        "ITGB1", "MMP2", "MMP9", "NGFR",
        "RAC1", "RHOA", "ZEB2",
    ],
    "signaling": [
        "ADAM10", "ALDH1A2", "AXIN2",
        "BMP2", "BMP4", "BMP7", "CTNNB1",
        "DLL1", "EDN1", "EDN3", "EDNRA", "EDNRB",
        "FGF8", "FGFR1", "FGFR2", "FGFR3",
        "JAG1", "LEF1", "NOTCH1", "NOTCH2",
        "RARA", "SHH", "SMAD1",
        "TGFBR1", "TGFBR2",
        "WNT1", "WNT3A",
    ],
    "craniofacial": [
        "CHD7", "ECE1", "ERBB3", "EVC", "IRF6",
        "NF1", "RUNX2", "SOX2", "TBX1", "TCOF1",
    ],
    "melanocyte": [
        "DCT", "KIT", "MITF", "PMEL", "TYR", "TYRP1",
    ],
    "enteric": [
        "GDNF", "GFRA1", "NRP1", "PHOX2B", "RET", "SEMA3A",
    ],
    "cardiac": [
        "GATA4", "HAND1", "HAND2", "MEF2C",
        "NKX2-5", "PLXNA2", "SEMA3C", "TBX5",
    ],
}

SYMBOL_TO_ROLE = {}
for role, symbols in ROLES.items():
    for s in symbols:
        SYMBOL_TO_ROLE[s] = role

# Reverse lookups
NCBI_TO_SYMBOL = {v["ncbi"]: k for k, v in GENES.items()}
UNIPROT_TO_SYMBOL = {v["uniprot"]: k for k, v in GENES.items()}
OMIM_TO_SYMBOL = {v["omim"]: k for k, v in GENES.items()}


def gene_symbols() -> list[str]:
    """Return sorted list of all gene symbols."""
    return sorted(GENES.keys())


def export_cue(output_path: str):
    """Export gene list as CUE for model self-description."""
    lines = [
        "package lacuene",
        "",
        "// Canonical gene list with HGNC symbols.",
        "// Auto-generated from normalizers/genes.py -- do not hand-edit.",
        f"// {len(GENES)} genes across {len(ROLES)} developmental roles.",
        "",
    ]
    for symbol in sorted(GENES.keys()):
        lines.append(f'genes: "{symbol}": symbol: "{symbol}"')
    lines.append("")
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"Exported {len(GENES)} genes to {output_path}")


if __name__ == "__main__":
    import os
    output = os.path.join(os.path.dirname(__file__), "..", "model", "gene_list.cue")
    export_cue(output)

