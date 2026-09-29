#!/usr/bin/env python3
"""Build the HECTOR unit catalogue (PLAN.md task 18) and emit unit records (task 20).

    .venv/bin/python -m tools.rates.parse_bor          # first: build/rates/rates.jsonl
    .venv/bin/python -m tools.export.export_hector     # first: build/site/ (it rebuilds the site)
    .venv/bin/python -m tools.units.build_units        # then this: build/units/, build/site/unit/
    .venv/bin/python tools/validate.py --root build/site

Reads the LCA checkout by path (never writes to it):
  docs/data/glossary_data.json         entries whose `groups` include "Units, weights & measures"
  docs/data/ladings/*.json.gz          spans of type `unit` / `commodity-unit`, `matches[0].key`
  data/bor/Jenks index of subjects English books of rates_units.tsv   conversion statements
  data/valuation/duty_rates.tsv, duty_measures.tsv   statutory duty ratios (process/duty_rates.py)
  data/valuation/equivalences.tsv, conflations.tsv   value-model evidence (process/valuation_model.py)
and this repo's build/rates/rates.jsonl (tools/rates/parse_bor.py) for the units the Books of
Rates are charged by.

Everything written is derived from Jenks's transcriptions or from the LCA glossary built on
them, so it goes ONLY to git-ignored build/ until the Jenks permission (PLAN.md task 1):
  build/units/catalogue.tsv    one row per candidate unit concept: basis, dimension, counts
  build/units/rates_join.tsv   each unit the rates parser recognises -> catalogue key
  build/units/conversions.tsv  every conversion statement found, with its source
  build/units/report.md        counts and the lists a human should look at
  build/ledger/units.tsv       the slug ledger (docs/uri-policy.md §3); NOT authoritative until
                               first publication, then committed and never regenerated
  build/site/unit/...          unit/<slug>/ontology.json (task 20); unit/dimension/<dim> Types
                               (D7, 29 Sep 2026: no dimension in a unit's URI)

Who is a unit (the population, PLAN.md task 18):
  1. the glossary entries in group "Units, weights & measures", less a short hand list of
     entries that are goods, not units (balances, scale weights, `loose`, ...: NOT_UNITS);
  2. corpus-attested unit concepts: the glossary keys the LCA tagger typed `unit` or
     `commodity-unit`. The tagger types by group, so every vessel ("bowl", "salt cellar")
     attests as a unit. Outside group 1, a concept counts as a unit only if it is a cask or its
     glossary description calls it a packing unit or measure (CONTAINER_RULE); the rest are
     listed as goods counted by the piece and not emitted;
  3. rates-only units: units the Books of Rates charge by that match no glossary unit
     (`hundred`, `score`, `the cloth`, ...), keyed `bor:<unit>`, plus `hector:each` for rates
     charged per item ("the hawke", "the skynne").

Dimensions are assigned by hand, below. Since D7 (29 Sep 2026) a dimension is a PROPERTY of a
unit (quantityKind, which may hold several: a sack is mass and package), not part of its URI,
so a reclassification changes a record, never a URI:
mass, length, volume and count only where a source defines the unit by a fixed quantity of
that kind; everything else is `package` (a packing or transport unit of customary, variable or
commodity-specific content). This is a proposal for Stephen, not a settled classification.

Conversions: a unit record carries `definedAs` (proposed term, see PROPOSED_TERMS) only for a
general, exact statement whose target is also an emitted unit, and `conversionToGram` only
where a chain of such statements reaches the pound avoirdupois. Approximate, conflicting and
commodity-specific statements stay in conversions.tsv, with their sources.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import glob
import gzip
import hashlib
import json
import re
import shutil
import sys
from fractions import Fraction
from pathlib import Path
from urllib.parse import quote

from tools.export.export_hector import (AAT_DESCRIPTION, AAT_PREFERRED, ATTESTED, CONTEXT, LCA,
                                        MLCA, W3ID, load_ledger as _load_rows, map_identifiers,
                                        names, slugify, successor)
from tools.rates.parse_bor import UNIT_VARIANTS, unit_lookup

REPO = Path(__file__).resolve().parents[2]
UNITS_GROUP = "Units, weights & measures"
UNITS_TSV = "data/bor/Jenks index of subjects English books of rates_units.tsv"
DIMENSIONS = ("mass", "length", "volume", "count", "package")
LEDGER_FIELDS = ["slug", "dimension", "key", "minted", "status", "replaced_by", "content_sha256",
                 "modified"]
AAT_BRIEF = {"id": "aat:300418049", "type": "Type", "_label": "brief texts"}
GRAMS_PER_POUND = Fraction("453.59237")  # pound avoirdupois, international definition (1959)

# --------------------------------------------------------------------------- classification

# In the units group, but goods rather than units (instruments, a packing state, objects).
NOT_UNITS = {
    "balance": "a weighing instrument (goods)",
    "goldweight": "scales for weighing gold (goods)",
    "ounce balaunce": "a set of scales (goods)",
    "weights": "a set of troy weights (goods)",
    "troy": "a set of weights / 'meaning unknown' (goods or unresolved)",
    "weight": "ambiguous: scale weights (the glossary gloss) vs weight as a measure; "
              "valuation equivalences.tsv has prune pound ≈ weight. Needs a human",
    "poise": "'a declared weight of goods': a word for weight, not a unit",
    "loose": "'not packed': a packing state, not a unit",
    "gold pipe": "a gold tube or roll for gold thread (goods)",
    "iron rod": "rods of iron (goods), though said to weigh 60 lb",
}

MASS = {"clove", "hundredweight", "quintal", "pound", "ounce", "uncia", "stone", "ston", "wey",
        "pondus", "mark_2", "mast", "lucepond", "schippond", "roba", "mais", "mece",
        "thousandweight_2", "pipe (weight)", "fother", "libri de venis", "poiz", "bar", "cantar",
        "sack"}
LENGTH = {"ell", "aune_2", "yard", "virga", "foot", "fathom", "brasa", "bracium", "gode",
          "bor:cloth"}
VOLUME = {"aum", "bote", "bushel", "butt_2", "chalder", "eightendel", "furthindell", "gallon",
          "kilderkin", "mesane", "muid", "malter", "pint pot", "pipe", "pot (measure)", "potelle",
          "quartellus", "quartellus_2", "quarter", "raser", "roda", "skipple", "stoop (measure)",
          "stoppa", "tierce", "tun", "moy", "barrel", "hogshead", "firkin", "puncheon"}
COUNT = {"dozen", "gross", "pair", "couple", "dicker", "shock", "timber", "pane", "skive",
         "suma", "tale", "cast", "warpe", "quire", "ream", "sheaf", "garba", "nest", "set",
         "mark", "bende", "kip", "bor:hundred", "bor:thousand", "bor:score", "bor:flock",
         "hector:each"}

# A second dimension, for units that are containers as well as measures (D7: quantityKind is
# multi-valued). The primary is dimension_of(); these add "package".
EXTRA_DIMENSIONS = {k: ("package",) for k in ("sack", "barrel", "hogshead", "firkin", "puncheon",
                                              "tun", "pipe", "butt_2", "bote")}

# Slugs that must never be minted for a unit: `unit/dimension/<dim>` holds the dimensions, and
# `unit/mass` is the deprecation record of the pre-D7 dimension document.
RESERVED_SLUGS = {"dimension", "mass", "length", "volume", "count", "package"}

# Corpus-attested concepts outside the units group that are casks (always measures) ...
CASKS = {"barrel", "hogshead", "firkin", "puncheon", "vat", "dry vat", "foist", "tonekyn",
         "werkbarellus"}
# ... or used as packing units though their gloss (the AAT scope note) does not say so ...
PACKING_INCLUDE = {
    "basket": "packing unit: LCA valuation equivalences.tsv has book basket = maund = vat",
    "wrapper": "packing unit for cloth exports (the glossary: 'for cloth exports')",
}
# ... or whose description calls them a packing unit or a measure.
CONTAINER_RULE = re.compile(r"packing unit|transport unit|as a measure|a measure|measure of|"
                            r"conventional measure|liquid measure", re.I)
# Described as a measure, but the measure sense has its own entry: the vessel is goods.
CONTAINER_GOODS = {"pot": "the vessel; the measure sense is `pot (measure)`",
                   "bottle": "the vessel; the measure sense is `botellus_2`",
                   "quart": "a one-quart pot (goods); the measure sense is `pot (measure)`",
                   "potel pot": "a pot (goods); the measure sense is `potelle`",
                   "soap box": "goods traded by the shock",
                   "packing": "packing material",
                   "cage": "the enclosure; the measure sense is `cage_2`",
                   "garner_2": "a grain bin (fixture)"}

# Rates-only units: label, variants for the Name records, dimension set above.
RATES_ONLY = {
    "bor:hundred": ("hundred", "the hundred (C): nominally 100; the long hundred of 120 (six "
                    "score) is stated for some goods (see conversions)"),
    "bor:thousand": ("thousand", "the thousand (M): ten hundreds"),
    "bor:score": ("score", "the score: twenty"),
    "bor:cloth": ("cloth", "the cloth as a unit of account for customs: the statutory cloth "
                  "(of assize); the Books of Rates reckon other cloths as fractions of it "
                  "(\"6 statutes for a clothe\")"),
    "bor:flock": ("flock", "the flock (floke): a count of pieces, 40 or 60 by commodity"),
    "bor:fur": ("fur", "the fur (furre): a fur lining, reckoned in panes (4 panes to the fur)"),
    "bor:cag": ("keg", "the keg (cagge), of eels"),
    "bor:band": ("band", "the band (bonde), of faggot iron"),
    "bor:standard": ("standard", "the standard (standerde), a set of knives"),
    "hector:each": ("each", "one of the thing named, counted individually: rates charged "
                    "'the hawke', 'the skynne', 'the hide' and the like"),
}
PACKAGE_EXTRA = {"bor:fur", "bor:cag", "bor:band", "bor:standard"}

# parse_bor canonical unit -> catalogue key, where the glossary-form match is absent or wrong.
JOIN_OVERRIDES = {
    "hundred": "bor:hundred", "thousand": "bor:thousand", "score": "bor:score",
    "cloth": "bor:cloth", "flock": "bor:flock", "fur": "bor:fur", "cag": "bor:cag",
    "band": "bor:band", "standard": "bor:standard",
    "piece": "pecia", "mantle": "pane",   # the glossary: a pane of 100 skins "(= a mantle)"
    "way": "wey", "fat": "vat", "fodder": "fother", "chaldron": "chalder", "frail": "fraile",
    "sum": "suma", "topnet": "tapnet", "tuft": "tufte", "mount": "mownt", "bolt": "bolt_3",
    "butt": "butt_2", "paper": "paper (measure)", "pipe": "pipe", "pack": "pack",
    "pocket": "pocket", "box": "box", "bale": "bale", "last": "last", "mast": "mast",
    "timber": "timber", "pair": "pair", "ell": "ell", "stone": "stone", "case": "case",
    "packing": "pack", "suit": "set", "cade": "cade", "tike": "hector:each",
    **{u: "hector:each" for u in ("skin", "hide", "hawk", "fin", "saddle", "staff", "rope",
                                  "board", "plate", "flitch")},
}


def join_row(canonical: str, commodity: str) -> str | None:
    """Row-level exceptions to the canonical join."""
    if canonical == "mark":  # the mark of gold/silver thread is a weight; of shears, 2 dozen
        return "mark_2" if re.search(r"thre|threed|thred", commodity, re.I) else "mark"
    return None


# --------------------------------------------------------------------------- conversions

# General definitions (not commodity-specific), each with its source. (key, value, target,
# exact?, source, note). Target is a catalogue key or free text (then not emitted).
DEFINITIONS = [
    ("pound", "1", "pound avoirdupois (453.59237 g)", True, "international definition (1959)",
     "HECTOR takes the customs pound as avoirdupois; not a measured Tudor standard"),
    ("ounce", "1/16", "pound", True, "avoirdupois definition", "16 oz to the lb avoirdupois"),
    ("uncia", "1", "ounce", True, "LCA glossary (uncia: 'ounce, a unit of weight')", ""),
    ("clove", "7", "pound", True, "LCA glossary (clove: 'a unit of weight for wool (7 lb)')", ""),
    ("stone", "14", "pound", True, "LCA glossary (stone: 'a unit of weight (14 lb.)')", ""),
    ("ston", "14", "pound", True, "LCA glossary (ston: 'a unit of weight (14 lb.)')", ""),
    ("hundredweight", "112", "pound", True,
     "Jenks index of subjects, units.tsv ('at 112 lb./cwt', 13 rows)",
     "one row has 'at 120 lb./cwt' (Irish yarn): see the commodity-specific rows"),
    ("quintal", "1", "hundredweight", True, "LCA glossary (quintal: 'a cwt')", ""),
    ("sack", "364", "pound", True,
     "LCA glossary (sack: 'the standard sack of English wool weighed 364 lb'); units.tsv "
     "('sack (English) wool 364 lb.')", "26 stone of 14 lb; other sacks differ by commodity"),
    ("pipe (weight)", "10", "hundredweight", True,
     "LCA glossary (pipe (weight): '10 cwt, i.e. ½ tun')", ""),
    ("fother", "19.5", "hundredweight", True,
     "LCA glossary; units.tsv ('fodder lead 19½ cwt at 112 lb./cwt')", "for lead"),
    ("mece", "300", "pound", False, "LCA glossary (mece: '300 lb.')", "stated, but a customary weight"),
    ("mais", "300", "pound", False, "LCA glossary (mais: 'roughly 300 lb')", ""),
    ("mark_2", "2/3", "pound", True, "LCA glossary (mark: 'two-thirds of a pound')",
     "which pound is not stated"),
    ("mast", "2.5", "pound troy", True, "LCA glossary (mast: '2½ lb. troy')", ""),
    ("lucepond", "1/20", "schippond", True, "LCA glossary (lucepond: '1/20 of a schippond', Wolf 43)", ""),
    ("lucepond", "15", "pound", False, "LCA glossary (lucepond: '6.846 kg or 15 lb.')", ""),
    ("schippond", "300", "pound", False, "LCA glossary (schippond: 'approximately 136 kg (300 lb.)')", ""),
    ("roba", "25", "pound", False, "LCA glossary (roba: 'approximately 25 English pounds')", ""),
    ("wey", "12", "stone", False, "LCA glossary (wey: 'usually equal to twelve stone or c. 300 lb.')",
     "self-inconsistent: 12 stone is 168 lb, not c. 300 lb; varies by commodity"),
    # D7 (29 Sep 2026): where a source gives two readings, each is its own statement and
    # neither is chosen.
    ("wey", "300", "pound", False, "LCA glossary (wey: 'usually equal to twelve stone or c. 300 lb.')",
     "the same description's other reading; 300 lb is not twelve stone (168 lb)"),
    ("yard", "3", "foot", True, "LCA glossary (yard: '3 feet or 36 inches')",
     "0.9144 m by the 1959 agreement"),
    ("virga", "1", "yard", True, "LCA glossary (virga: 'one yard (3 feet)')", ""),
    ("ell", "1.25", "yard", True, "LCA glossary (ell: '45 in. in England, 27 in. in Flanders')",
     "the English ell; the Flemish ell is 0.75 yard"),
    ("gode", "1.5", "yard", True, "LCA glossary (gode: 'a cloth measure for Welsh cloth (4½ ft.)')", ""),
    ("fathom", "6", "foot", True, "LCA glossary (fathom: '6 ft.')", ""),
    ("bracium", "2", "foot", False, "LCA glossary (bracium: 'nearly two English feet')", ""),
    ("bor:cloth", "24", "virga", True,
     "LCA data/valuation/duty_rates.tsv (process/duty_rates.py, 19 Sep 2026): counted cloth "
     "custom 33d alien / 14d denizen per cloth against 1.375d / 0.583d per virga = 24 yards to "
     "the cloth; of 2,348 counted-cloth rows off the rate, 2,119 are lots of 'N pannis, M "
     "virgis' charged at 24 yards to the cloth",
     "a customs equivalence (the cloth of assize), not a physical length of every cloth"),
    ("gallon", "4", "quart", True, "LCA glossary (gallon: '4 quarts')", ""),
    ("potelle", "1/2", "gallon", True, "LCA glossary (potelle: 'two quarts (half a gallon)')", ""),
    ("pipe", "126", "gallon", True, "LCA glossary (pipe: '126 old gallons, equivalent to 2 hogsheads')",
     "old (wine) gallons"),
    ("pipe", "1/2", "tun", True, "LCA glossary (pipe: '2 hogsheads'; butt/bote: '2 hogsheads or ½ tun')", ""),
    ("hogshead", "1/2", "pipe", True, "LCA glossary (pipe, butt_2: 'equivalent to 2 hogsheads')", ""),
    ("butt_2", "2", "hogshead", True, "LCA glossary (butt_2: 'equivalent to 2 hogsheads')",
     "CONFLICT: duty_measures.tsv charges tun and butt_2 alike for wine (ratio 1.0)"),
    ("bote", "1/2", "tun", True, "LCA glossary (bote: 'equivalent to 2 hogsheads or ½ tun')", ""),
    ("tierce", "1/3", "pipe", True, "LCA glossary (tierce: 'one third of a pipe (usually 42 gallons)')", ""),
    ("puncheon", "1/4", "tun", True, "LCA glossary (puncheon: 'wine = 1 hogshead or 1/4 tun')", "for wine"),
    ("furthindell", "1/4", "tun", True, "LCA glossary (furthindell: 'a quarter tun')", ""),
    ("quartellus", "1/6", "tun", True, "LCA glossary (quartellus: '½ bota or 1/6 tun')", "of sweet wine"),
    ("mesane", "3/4", "tun", True, "LCA glossary (mesane: 'equivalent to ¾ tun')", "of sweet wine"),
    ("roda", "2", "tun", True, "LCA glossary (roda: 'equivalent to 2 tuns')", "of Rhine wine"),
    ("aum", "1/3", "tun", False, "LCA glossary (aum: '⅓ of a dolium')",
     "CONFLICT in the same description: '1/5 of a dolium', '5 aumes = 1 dolium'"),
    ("aum", "1/5", "tun", False, "LCA glossary (aum: '1/5 of a dolium', '5 aumes = 1 dolium')",
     "the same description's other reading (it also says ⅓)"),
    ("eightendel", "1/8", "barrel", True, "LCA glossary (eightendel: '⅛ of a barrel')", ""),
    ("firkin", "1/4", "barrel", True, "LCA glossary (firkin: 'a quarter of a barrel or half a kilderkin', Getty AAT)", ""),
    ("kilderkin", "1/2", "barrel", True, "LCA glossary (firkin: 'half a kilderkin' => kilderkin = ½ barrel)", "derived"),
    ("kilderkin", "16.5", "gallon", False, "LCA glossary (kilderkin: '15-18 gallons')", "a range"),
    ("barrel", "1/6", "tun", True,
     "LCA data/valuation/duty_measures.tsv (process/duty_rates.py): wine subsidy (tunnage) "
     "barrel vs tun ratio 6.0 ('wine 3s a tun (a barrel 1/6)')",
     "for wine, as charged. The later statutory wine barrel is 1/8 tun (31½ gal): a finding to check"),
    ("quarter", "8", "bushel", True, "LCA glossary (quarter: '8 bushels')", ""),
    ("raser", "4", "bushel", False, "LCA glossary (raser: 'ca. 4 bushels')", ""),
    ("dozen", "12", "hector:each", True, "LCA glossary (dozen: 'twelve'); parse_bor COUNT_UNITS", ""),
    ("gross", "12", "dozen", True, "LCA glossary (gross: '144 pieces'); parse_bor COUNT_UNITS", ""),
    ("bor:score", "20", "hector:each", True, "parse_bor COUNT_UNITS", ""),
    ("bor:hundred", "5", "bor:score", True, "units.tsv ('3 hundreds at 5 score/hundred', vitry canvas)",
     "nominal; the long hundred of 6 score (120) is stated for some goods: commodity rows"),
    ("bor:thousand", "10", "bor:hundred", True, "parse_bor COUNT_UNITS", ""),
    ("pair", "2", "hector:each", True, "LCA glossary (pair: 'a counting unit of two')", ""),
    ("couple", "2", "hector:each", True, "LCA glossary (couple: 'Two')", ""),
    ("dicker", "10", "hector:each", True, "LCA glossary (dicker: 'a numerical unit of ten', Zupko 107-9); "
     "Books of Rates ('the dycker cont' 10')", ""),
    ("shock", "60", "hector:each", True, "LCA glossary (shock: '60 pieces'); units.tsv ('shock (skoke) 60 pieces')", ""),
    ("timber", "40", "hector:each", True, "LCA glossary (timber: '40 skins', Zupko 413-4); units.tsv ('tymbre 40 furs')", "of furs"),
    ("pane", "100", "hector:each", True, "LCA glossary (pane: 'containing 100 skins (= a mantle)')", "of skins"),
    ("warpe", "4", "hector:each", True, "LCA glossary (warpe: 'a counting measure for pots (4 pots)')", ""),
    ("ream", "20", "quire", True, "LCA glossary (ream: 'containing 20 quires'); units.tsv ('realme paper 20 quires')", ""),
    ("mark", "2", "dozen", True, "units.tsv ('marke sheres for semesters 2 dozen pieces'); Books of Rates "
     "('the marke conteyninge two dossyn')",
     "CONFLICT: the glossary says '20 pieces, or 2 dozen'"),
    ("mark", "20", "hector:each", False, "LCA glossary (mark: '20 pieces, or 2 dozen')",
     "the glossary's other reading; the Books of Rates give 2 dozen"),
    ("skive", "100", "hector:each", False, "LCA glossary (skive: 'approximately 100 in number (Cobb 186)')",
     "CONFLICT: Zupko 383 gives 500"),
    ("skive", "500", "hector:each", False, "Zupko, A Dictionary of Weights and Measures for the British "
     "Isles, p. 383, as noted against the LCA glossary's skive", "against the glossary's 'approximately 100'"),
    ("cast", "3", "hector:each", False, "LCA glossary (cast: 'a set of three or four')", ""),
    ("cast", "4", "hector:each", False, "LCA glossary (cast: 'a set of three or four')", ""),
]


def frac(s: str) -> Fraction:
    return Fraction(s)


def num_text(fr: Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    d = f"{float(fr):.10f}".rstrip("0").rstrip(".")
    return d


# units.tsv amounts ------------------------------------------------------------------------

AMOUNT_WORDS = {"cwt": "hundredweight", "lb": "pound", "oz": "ounce", "pieces": "pecia",
                "peces": "pecia", "peece": "pecia", "ells": "ell", "elles": "ell",
                "yards": "yard", "yeardes": "yard", "bushels": "bushel", "gallons": "gallon",
                "quarters": "quarter", "quires": "quire", "realme": "ream", "reams": "ream",
                "bunches": "bunch", "furs": "bor:fur", "bundelles": "bundle", "bales": "bale",
                "hundreds": "bor:hundred", "hundred": "bor:hundred", "c": "bor:hundred",
                "gross": "gross", "groce": "gross", "dozen": "dozen", "timber": "timber",
                "burden": None}
ITEM_WORDS = {"staves", "nails", "fish", "boardes", "sheets", "ropes", "pipes"}


def parse_amount(text: str) -> dict:
    """'3 cwt at 112 lb./cwt' -> {'value': 3, 'unit': 'hundredweight', 'basis': '...'}."""
    # '221⁄2' is 22½ (the numerator is the last digit before the fraction slash)
    t = re.sub(r"(\d*)(\d)⁄(\d)", lambda m: f"{m.group(1) or 0}+{m.group(2)}/{m.group(3)}", text or "")
    t = t.strip()
    out = {"value": None, "unit": None, "unit_text": "", "basis": ""}
    at = re.search(r"\s(?:at|@)\s(.+)$", t)
    if at:
        out["basis"] = at.group(1).strip()
        t = t[:at.start()]
    m = re.match(r"^(?:a\s+)?(half|\d[\d,]*(?:\+\d+/\d+)?)\s*(.*)$", t, re.I)
    if not m:
        if re.match(r"^C\b", t):
            out["value"], rest = Fraction(1), t[1:]
            out["unit"] = "bor:hundred"
            return out
        return out
    n = m.group(1).replace(",", "")
    if n.lower() == "half":
        value = Fraction(1, 2)
    elif "+" in n:
        a, b = n.split("+")
        value = Fraction(int(a)) + Fraction(b)
    else:
        value = Fraction(int(n))
    out["value"] = value
    rest = m.group(2).strip()
    words = [w for w in re.split(r"\s+", rest) if w and w.lower() not in ("smale", "small")]
    if not words or re.match(r"^\(", rest):
        out["unit"] = "hector:each"  # a bare number: '1000 (1558)'
        return out
    w = re.sub(r"[.,;:()]", "", words[0].lower())
    out["unit_text"] = words[0]
    if w in AMOUNT_WORDS:
        out["unit"] = AMOUNT_WORDS[w]
    elif w in ITEM_WORDS:
        out["unit"] = "hector:each"
    else:
        canon = unit_lookup(w)
        out["unit"] = JOIN_OVERRIDES.get(canon, canon) if canon else None
    return out


# --------------------------------------------------------------------------- inputs

def corpus_attestations(lca: Path) -> tuple[collections.Counter, collections.Counter]:
    unit, cu = collections.Counter(), collections.Counter()

    def walk(o):
        if isinstance(o, dict):
            t = o.get("type")
            if t in ("unit", "commodity-unit") and o.get("matches"):
                (unit if t == "unit" else cu)[o["matches"][0]["key"]] += 1
            for v in o.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for f in sorted(glob.glob(str(lca / "docs/data/ladings/*.json.gz"))):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            walk(json.load(fh))
    return unit, cu


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


# --------------------------------------------------------------------------- catalogue

def base_label(key: str) -> str:
    k = re.sub(r"^(bor|hector):", "", key)
    k = re.sub(r"_\d+$", "", k)
    return re.sub(r"\s*\(measure\)$", "", k)


def dimension_of(key: str) -> str:
    for dim, keys in (("mass", MASS), ("length", LENGTH), ("volume", VOLUME), ("count", COUNT)):
        if key in keys:
            return dim
    return "package"


def build_catalogue(entries: dict, unit_att, cu_att, report) -> dict[str, dict]:
    cat: dict[str, dict] = {}
    group = {k for k, e in entries.items() if UNITS_GROUP in (e.get("groups") or [])}
    attested = set(unit_att) | set(cu_att)
    for k in sorted(group | attested):
        e = entries.get(k)
        if e is None:
            report["attested_not_in_glossary"].append(k)
            continue
        row = {"key": k, "label": base_label(k), "in_units_group": k in group,
               "attest_unit": unit_att.get(k, 0), "attest_commodity_unit": cu_att.get(k, 0),
               "rates_rows": 0, "rates_units": set(), "emit": True, "reason": ""}
        if k in group:
            if k in NOT_UNITS:
                row["emit"], row["reason"] = False, NOT_UNITS[k]
        elif k in CASKS:
            row["reason"] = "cask (corpus-attested, outside the units group)"
        elif k in PACKING_INCLUDE:
            row["reason"] = PACKING_INCLUDE[k] + " (corpus-attested, outside the units group)"
        elif k in CONTAINER_GOODS:
            row["emit"], row["reason"] = False, CONTAINER_GOODS[k]
        elif CONTAINER_RULE.search(e.get("d") or ""):
            row["reason"] = "described as a packing unit or measure (corpus-attested, outside the units group)"
        else:
            row["emit"] = False
            row["reason"] = "goods counted by the piece: typed unit by the tagger from its group"
        row["dimension"] = dimension_of(k) if row["emit"] else ""
        cat[k] = row
    for k, (label, _d) in RATES_ONLY.items():
        cat[k] = {"key": k, "label": label, "in_units_group": False, "attest_unit": 0,
                  "attest_commodity_unit": 0, "rates_rows": 0, "rates_units": set(), "emit": True,
                  "reason": "rates-only" if k != "hector:each" else "HECTOR-authored",
                  "dimension": dimension_of(k)}
    return cat


def join_rates(rates: list[dict], cat: dict, entries: dict, report) -> list[dict]:
    formidx = form_index(cat, entries)
    by_unit = collections.Counter(r["unit"] for r in rates if r.get("unit"))
    out = []
    for canon, n in by_unit.most_common():
        if canon in JOIN_OVERRIDES:
            key, method = JOIN_OVERRIDES[canon], "override"
        else:
            hits = collections.Counter()
            for v in [canon] + UNIT_VARIANTS.get(canon, []):
                for k in formidx.get(v, ()):
                    hits[k] += 1
            if len(hits) == 1:
                key, method = next(iter(hits)), "glossary form"
            elif hits:
                best = hits.most_common()
                key, method = (best[0][0], "glossary form (most variants)") if best[0][1] > best[1][1] else (None, f"ambiguous: {dict(hits)}")
            else:
                key, method = None, "no catalogue unit"
        out.append({"rates_unit": canon, "rows": n, "key": key or "", "method": method})
    joined = {j["rates_unit"]: j["key"] for j in out}
    for r in rates:
        if not r.get("unit"):
            continue
        k = join_row(r["unit"], r.get("commodity_raw") or "") or joined.get(r["unit"])
        if k and k in cat:
            cat[k]["rates_rows"] += 1
            cat[k]["rates_units"].add(r["unit"])
        elif k:
            report["join_target_missing"].append(f"{r['unit']} -> {k}")
    for j in out:
        if j["rates_unit"] == "mark":
            j["method"] = "row rule: thread -> mark_2 (weight), else mark (2 dozen)"
    return out


def form_index(cat: dict, entries: dict) -> dict[str, set]:
    """Lower-cased glossary forms -> emitted catalogue keys."""
    idx = collections.defaultdict(set)
    for k, r in cat.items():
        if r["emit"] and k in entries:
            for f in entries[k].get("f", []):
                idx[f["t"].lower()].add(k)
            idx[base_label(k).lower()].add(k)
    return idx


def conversions(lca: Path, rates: list[dict], cat: dict, entries: dict, report) -> list[dict]:
    rows = []
    formidx = form_index(cat, entries)
    for key, value, target, exact, source, note in DEFINITIONS:
        rows.append({"unit": key, "value": num_text(frac(value)), "target": target, "commodity": "",
                     "exact": exact, "scope": "general", "source": source, "note": note})
    # units.tsv: commodity-specific contents
    for r in read_tsv(lca / UNITS_TSV):
        subj = r["unit"].strip()
        head = re.split(r",|\s+or\s+|\s+as\s+|\s*\(", subj)[0].strip()
        half = "di’" in subj or subj.lower().startswith("half")
        head = re.sub(r"^(half|great)\s+", "", head, flags=re.I)
        canon = unit_lookup(head.split()[0]) if head else None
        key = join_row(canon, r["commodity"]) if canon else None
        key = key or (JOIN_OVERRIDES.get(canon) if canon else None)
        if not key and canon:
            key = next((j for j in [canon] if j in cat), None)
        if not key and head:
            hits = formidx.get(head.split()[0].lower(), set())
            key = next(iter(hits)) if len(hits) == 1 else None
        a = parse_amount(r["amount"])
        note = []
        if half:
            note.append("of a half unit")
        if subj.lower().startswith("great"):
            note.append(f"'{subj}': the great unit, not the ordinary one")
            key = None
        if a["basis"]:
            note.append(f"basis: {a['basis']}")
        rows.append({"unit": key or f"(unjoined: {subj})",
                     "value": num_text(a["value"]) if a["value"] is not None else "",
                     "target": a["unit"] or f"(unparsed: {r['amount']})",
                     "commodity": r["commodity"], "exact": a["value"] is not None and bool(a["unit"]),
                     "scope": "commodity", "source": f"Jenks index of subjects, units.tsv: "
                     f"'{subj} | {r['commodity']} | {r['amount']}'", "note": "; ".join(note)})
        if not key or not a["unit"]:
            report["units_tsv_unparsed"].append(f"{subj} | {r['commodity']} | {r['amount']}")
    # rates contents clauses, aggregated per (unit, contents value, contents unit)
    joined = {}
    agg = collections.defaultdict(list)
    for r in rates:
        if r.get("unit") and r.get("contents_quantity") and r.get("contents_unit"):
            k = join_row(r["unit"], r.get("commodity_raw") or "") or JOIN_OVERRIDES.get(r["unit"]) or \
                next((c for c in cat if c == r["unit"]), None)
            if r["unit"] in ("hundred", "thousand"):
                continue  # 'the C cont' 112 lb.' is a hundredweight statement, read below
            t = JOIN_OVERRIDES.get(r["contents_unit"], r["contents_unit"])
            if t in ("skin", "hide") or JOIN_OVERRIDES.get(r["contents_unit"]) == "hector:each":
                t = "hector:each"
            agg[(k or f"(rates: {r['unit']})", r["contents_quantity"], t)].append(
                f"{r['book']} {r['direction']} l.{r['source_line']}: {r['commodity_raw'][:60]}")
    for (k, q, t), where in sorted(agg.items(), key=lambda x: (-len(x[1]), x[0])):
        rows.append({"unit": k, "value": q, "target": t, "commodity": "(see source)",
                     "exact": True, "scope": "commodity (Books of Rates contents clause)",
                     "source": f"Books of Rates, {len(where)} row(s): " + " | ".join(where[:3]) +
                     (" …" if len(where) > 3 else ""), "note": ""})
    # value-model evidence (LCA process/valuation_model.py)
    for r in read_tsv(lca / "data/valuation/equivalences.tsv"):
        rows.append({"unit": r["unit_a"], "value": "1", "target": r["unit_b"], "commodity": r["concept"],
                     "exact": False, "scope": "commodity (empirical)",
                     "source": f"LCA data/valuation/equivalences.tsv (process/valuation_model.py): "
                     f"deflated medians agree, n={r['n_a']}/{r['n_b']}, log diff {r['log_diff']}",
                     "note": "same value per unit: candidates for one measure, not a definition"})
    for r in read_tsv(lca / "data/valuation/conflations.tsv"):
        rows.append({"unit": r["unit"], "value": r["ratio"], "target": f"(a second '{r['unit']}')",
                     "commodity": r["concept"], "exact": False, "scope": "commodity (empirical)",
                     "source": f"LCA data/valuation/conflations.tsv (process/valuation_model.py): "
                     f"n={r['n']}, two clusters, low share {r['low_share']}",
                     "note": "two measures under one label, the larger this many times the smaller"})
    for r in read_tsv(lca / "data/valuation/duty_measures.tsv"):
        rows.append({"unit": r["unit_small"], "value": r["ratio"], "target": f"per {r['unit_large']} (duty ratio)",
                     "commodity": r["concept"], "exact": False, "scope": "commodity (statutory duty)",
                     "source": f"LCA data/valuation/duty_measures.tsv (process/duty_rates.py): "
                     f"{r['charge']} {r['status']} {r['customs_type']}",
                     "note": "ratio of modal duty rates: how many of the smaller the accounts charge "
                             "as one of the larger"})
    return rows


# --------------------------------------------------------------------------- ledger

def reconcile(ledger: list[dict], cat: dict, entries: dict, meta: dict, today: str, report) -> dict:
    by_key = {r["key"]: r for r in ledger if r["status"] == "active"}
    slugs = {r["slug"] for r in ledger} | RESERVED_SLUGS
    for key, row in list(by_key.items()):
        if key in cat and cat[key]["emit"]:
            if cat[key]["dimension"] != row["dimension"]:
                # A property since D7, not a path: follow the classification, URI unchanged.
                report["dimension_reclassified"].append(
                    f"{key}: {row['dimension']} -> {cat[key]['dimension']} (unit/{row['slug']} unchanged)")
                row["dimension"] = cat[key]["dimension"]
            continue
        if key.startswith(("bor:", "hector:")) or key in entries:
            row["status"] = "deleted"  # no longer counted as a unit
            report["deprecated"].append(f"{key}: no longer classed as a unit")
            del by_key[key]
            continue
        kind, new = successor(key, meta, entries)
        if kind == "rekey" and new not in by_key and new in cat and cat[new]["emit"]:
            row["key"] = new
            by_key[new] = row
            report["rekeyed"].append(f"{key} -> {new}")
        elif kind in ("rekey", "merge") and new in by_key:
            row["status"], row["replaced_by"] = "deprecated", by_key[new]["slug"]
            report["deprecated"].append(f"{key} -> {new}")
            del by_key[key]
        elif kind == "delete":
            row["status"] = "deleted"
            report["deprecated"].append(f"{key}: deleted in LCA")
            del by_key[key]
        else:
            report["missing"].append(key)
    for key in sorted(k for k, r in cat.items() if r["emit"]):
        if key in by_key:
            continue
        base = slugify(base_label(key))
        slug, n = base, 2
        while slug in slugs:
            slug, n = f"{base}-{n}", n + 1
        row = {"slug": slug, "dimension": cat[key]["dimension"], "key": key, "minted": today,
               "status": "active", "replaced_by": "", "content_sha256": "", "modified": ""}
        ledger.append(row)
        by_key[key] = row
        slugs.add(slug)
        if slug != base:
            report["slug_collisions"].append(f"{key!r} -> {slug}")
    return by_key


def save_ledger(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, LEDGER_FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["dimension"], r["slug"])):
            w.writerow({k: r.get(k, "") for k in LEDGER_FIELDS})


# --------------------------------------------------------------------------- JSON-LD

# `definedAs` and the unit sense of `attestationCount` were proposed here on 19 Sep and ADOPTED
# on 29 Sep (D7): both are now in the committed context/hector.jsonld and ontology/ontology.json,
# so nothing is added to the staged copy any more. Kept as the place for the next proposal.
PROPOSED_TERMS = {}
ATTESTATION_COMMENT = None

DIMENSION_DOCS = {
    "length": ("length", "The dimension measured by units of length (ell, yard, foot).",
               [{"id": "quantitykind:Length", "type": "Type", "_label": "Length"},
                {"id": "wd:Q36253", "type": "Type", "_label": "length"}]),
    "volume": ("volume", "The dimension measured by units of capacity, liquid and dry (gallon, "
               "tun, bushel, quarter), including casks that the sources define by capacity.",
               [{"id": "quantitykind:Volume", "type": "Type", "_label": "Volume"},
                {"id": "wd:Q39297", "type": "Type", "_label": "volume"}]),
    "count": ("count", "Units of number: a count of items (dozen, gross, pair, the timber of 40 "
              "skins), and `each`, one item counted individually.", []),
    "package": ("package", "Packing and transport units (bale, fardel, chest, sack as a packing "
                "unit, basket) whose content is customary, variable or specific to the commodity "
                "packed. Not a physical dimension: a unit here gives a count of packages, and any "
                "known contents are commodity-specific statements, not definitions. A cask or a "
                "sack is both a measure and a package, and carries both dimensions.", []),
}


def unit_uri(row: dict) -> str:
    return f"{W3ID}unit/{row['slug']}"          # D7: no dimension in the URI


def dimensions_of(key: str, row: dict) -> list[str]:
    return [row["dimension"], *(d for d in EXTRA_DIMENSIONS.get(key, ()) if d != row["dimension"])]


def ref(row: dict, cat: dict) -> dict:
    return {"id": unit_uri(row), "type": "MeasurementUnit", "_label": cat[row["key"]]["label"]}


def unit_names(key: str, entries: dict, sources: list) -> list[dict]:
    if key in entries:
        ns = names(key, entries[key], sources)
        label = base_label(key)
        if label != key:  # preferred name is the headword, not the disambiguated key
            for n in ns:
                n["classified_as"] = [c for c in n["classified_as"] if c is not AAT_PREFERRED]
            ns = [n for n in ns if n["classified_as"]]
            hit = next((n for n in ns if n["content"] == label), None)
            if hit:
                hit["classified_as"].insert(0, AAT_PREFERRED)
            else:
                ns.insert(0, {"type": "Name", "content": label, "classified_as": [AAT_PREFERRED]})
        return ns
    label = RATES_ONLY[key][0]
    canon = next((c for c, k in JOIN_OVERRIDES.items() if k == key), None)
    ns = [{"type": "Name", "content": label, "classified_as": [AAT_PREFERRED]}]
    for v in (UNIT_VARIANTS.get(canon, []) if canon and key.startswith("bor:") else []):
        if v != label and not v.isdigit() and len(v) > 1:
            ns.append({"type": "Name", "content": v, "classified_as": [ATTESTED]})
    return ns


def grams(key: str, defs: dict, seen=()) -> Fraction | None:
    """Follow exact general definitions down to the pound avoirdupois."""
    if key == "pound":
        return GRAMS_PER_POUND
    if key in seen or key not in defs:
        return None
    for value, target in defs[key]:
        g = grams(target, defs, seen + (key,))
        if g is not None:
            return value * g
    return None


def unit_doc(key: str, row: dict, cat: dict, by_key: dict, entries: dict, sources: list,
             defs_by_unit: dict, exact_defs: dict, report) -> dict:
    c = cat[key]
    doc = {"@context": CONTEXT, "id": unit_uri(row), "type": "MeasurementUnit", "_label": c["label"]}
    notes = []
    e = entries.get(key)
    if e and e.get("d"):
        notes.append({"type": "LinguisticObject", "classified_as": [AAT_DESCRIPTION], "content": e["d"]})
    elif key in RATES_ONLY:
        notes.append({"type": "LinguisticObject", "classified_as": [AAT_DESCRIPTION],
                      "content": RATES_ONLY[key][1]})
    g = grams(key, exact_defs)
    if g is not None:
        notes.append({"type": "LinguisticObject", "classified_as": [AAT_BRIEF],
                      "content": "conversionToGram follows the definitions given under definedAs "
                      "down to the pound avoirdupois at its 1959 international value "
                      "(453.59237 g). It is a modern reference value, not a measured historical standard."})
    if notes:
        doc["referred_to_by"] = notes
    doc["identified_by"] = unit_names(key, entries, sources)
    doc["quantityKind"] = [f"hectorid:unit/dimension/{d}" for d in dimensions_of(key, row)]
    if g is not None:
        doc["conversionToGram"] = num_text(g) if g.denominator == 1 or len(num_text(g)) < 24 else f"{float(g):.6f}"
    defined = []
    readings = [d for d in defs_by_unit.get(key, []) if by_key.get(d["target"])]
    for d in readings:
        t = by_key[d["target"]]
        status = []
        if not d["exact"]:
            status.append("Not exact: approximate, or one of several readings")
        if len(readings) > 1:
            status.append(f"One of {len(readings)} readings the sources give for this unit; none is preferred")
        defined.append({"type": "Dimension", "value": _json_num(frac(d["value"])),
                        "unit": ref(t, cat),
                        "referred_to_by": [{"type": "LinguisticObject", "classified_as": [AAT_BRIEF],
                                            "content": "Source: " + d["source"] +
                                            (f". Note: {d['note']}" if d["note"] else "") +
                                            "".join(f". {x}" for x in status)}]})
    if defined:
        doc["definedAs"] = defined
    if e:
        doc.update(map_identifiers(e.get("aat") or [], report, key))
        see = [{"id": MLCA + quote(key, safe=""), "type": "Type",
                "_label": f"{key} (London Customs Accounts glossary)"}]
        if row.get("_commodity_slug"):
            see.append({"id": f"{W3ID}commodity/{row['_commodity_slug']}", "type": "Type", "_label": key})
        doc["seeAlso"] = see
    if key == "pound":  # the exemplar's alignments, checked 2026-09-18 (task 19 not done)
        doc.setdefault("equivalent", [])
        have = {x["id"] for x in doc["equivalent"]}
        for x in ({"id": "wd:Q100995", "type": "MeasurementUnit", "_label": "pound"},
                  {"id": "qudtunit:LB", "type": "MeasurementUnit", "_label": "Pound Mass"}):
            if x["id"] not in have:
                doc["equivalent"].append(x)
    n = c["attest_unit"] + c["attest_commodity_unit"]
    if n:
        doc["attestationCount"] = n
    return doc


def _json_num(fr: Fraction):
    if fr.denominator == 1:
        return fr.numerator
    return float(num_text(fr))


def content_hash(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k != "modified"}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def stage_vocabulary(site: Path):
    """Add the proposed terms to the STAGED context and vocabulary only (build/site)."""
    cpath = site / "context" / "hector.jsonld"
    ctx = json.loads(cpath.read_text(encoding="utf-8"))
    for term, (definition, _doc) in PROPOSED_TERMS.items():
        ctx["@context"][term] = definition
    cpath.write_text(json.dumps(ctx, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    vpath = site / "ontology" / "ontology.json"
    voc = json.loads(vpath.read_text(encoding="utf-8"))
    ids = {n["id"] for n in voc["@graph"]}
    for _term, (_d, doc) in PROPOSED_TERMS.items():
        if doc["id"] not in ids:
            voc["@graph"].append(doc)
    for n in voc["@graph"]:
        if ATTESTATION_COMMENT and n["id"] == "hector:attestationCount":
            n["rdfs:comment"] = ATTESTATION_COMMENT
    vpath.write_text(json.dumps(voc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def dimension_doc(dim: str) -> dict:
    label, text, eq = DIMENSION_DOCS[dim]
    doc = {"@context": CONTEXT, "id": f"{W3ID}unit/dimension/{dim}", "type": "Type", "_label": label,
           "referred_to_by": [{"type": "LinguisticObject", "classified_as": [AAT_BRIEF], "content": text}]}
    if eq:
        doc["equivalent"] = eq
    return doc


# --------------------------------------------------------------------------- main

def build(lca: Path, site: Path, out: Path, ledger_path: Path, rates_path: Path,
          today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    report = collections.defaultdict(list)
    g = json.loads((lca / "docs/data/glossary_data.json").read_text(encoding="utf-8"))
    entries, meta = g["entries"], g["metadata"]
    sources = meta.get("source_registry", {}).get("sources", [])
    if not rates_path.exists():
        raise SystemExit(f"{rates_path} missing: run python -m tools.rates.parse_bor first")
    rates = [json.loads(l) for l in rates_path.open(encoding="utf-8")]
    unit_att, cu_att = corpus_attestations(lca)

    cat = build_catalogue(entries, unit_att, cu_att, report)
    join = join_rates(rates, cat, entries, report)
    conv = conversions(lca, rates, cat, entries, report)

    ledger = [dict(r) for r in _load_rows(ledger_path)] if ledger_path.exists() else []
    by_key = reconcile(ledger, cat, entries, meta, today, report)

    # link a unit to its HECTOR commodity record (same glossary key), if the export minted one
    com_ledger = ledger_path.parent / "commodities.tsv"
    com = {r["glossary_key"]: r["slug"] for r in _load_rows(com_ledger) if r["status"] == "active"} \
        if com_ledger.exists() else {}
    for k, row in by_key.items():
        if k in com and (site / "commodity" / com[k] / "ontology.json").exists():
            row["_commodity_slug"] = com[k]

    defs_by_unit = collections.defaultdict(list)
    exact_defs = collections.defaultdict(list)
    for d in conv:
        # D7 (29 Sep 2026): EVERY general reading is published, each with its source; an inexact
        # one says so, and none is chosen where sources disagree. conversionToGram still follows
        # exact definitions only.
        if d["scope"] == "general" and d["target"] in by_key and d["unit"] in by_key:
            defs_by_unit[d["unit"]].append(d)
            if d["exact"]:
                exact_defs[d["unit"]].append((frac(d["value"]), d["target"]))

    # stage: rebuild build/site/unit from this repo's unit/ and add the generated records
    if not (site / "context" / "hector.jsonld").exists():
        raise SystemExit(f"{site} is not a staged site: run python -m tools.export.export_hector first")
    shutil.rmtree(site / "unit", ignore_errors=True)
    shutil.copytree(REPO / "unit", site / "unit")
    stage_vocabulary(site)
    for dim in DIMENSIONS:
        p = site / "unit" / "dimension" / dim / "ontology.json"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(dimension_doc(dim), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    counts = collections.Counter()
    for row in ledger:
        key = row["key"]
        if row["status"] == "active" and key in cat and cat[key]["emit"]:
            doc = unit_doc(key, row, cat, by_key, entries, sources, defs_by_unit, exact_defs, report)
            counts[f"unit records: {row['dimension']}"] += 1
            counts["with definedAs"] += bool(doc.get("definedAs"))
            counts["with conversionToGram"] += "conversionToGram" in doc
        elif row["status"] in ("deprecated", "deleted"):
            doc = {"@context": CONTEXT, "id": unit_uri(row), "type": "MeasurementUnit",
                   "_label": base_label(key), "deprecated": True}
            if row.get("replaced_by"):
                doc["isReplacedBy"] = {"id": f"{W3ID}unit/{row['replaced_by']}", "type": "MeasurementUnit"}
            counts["deprecation records"] += 1
        else:
            continue
        h = content_hash(doc)
        if h != row.get("content_sha256"):
            row["content_sha256"], row["modified"] = h, today
        doc["modified"] = row["modified"]
        p = site / "unit" / row["slug"] / "ontology.json"
        if p.exists() and not (REPO / "unit" / row["slug"] / "ontology.json").exists():
            report["path_clash"].append(str(p))
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for r in ledger:
        r.pop("_commodity_slug", None)
    save_ledger(ledger_path, ledger)

    write_tables(out, cat, join, conv, by_key)
    counts.update(summary(cat, join, conv, rates))
    report["counts"] = dict(counts)
    return report


def summary(cat: dict, join: list, conv: list, rates: list) -> dict:
    s = collections.Counter()
    gl = [r for r in cat.values() if not r["key"].startswith(("bor:", "hector:"))]
    s["A glossary entries in units group"] = sum(r["in_units_group"] for r in gl)
    s["B corpus-attested unit concepts (unit/commodity-unit spans)"] = sum(
        1 for r in gl if r["attest_unit"] + r["attest_commodity_unit"])
    s["B of which outside the units group"] = sum(
        1 for r in gl if not r["in_units_group"] and r["attest_unit"] + r["attest_commodity_unit"])
    s["A∪B candidate concepts"] = len(gl)
    s["A∪B emitted as units"] = sum(r["emit"] for r in gl)
    s["A∪B not units (goods / excluded)"] = sum(not r["emit"] for r in gl)
    s["rates-only units (bor:, hector:each)"] = len(cat) - len(gl)
    s["rates canonical units"] = len(join)
    s["rates canonical units joined"] = sum(1 for j in join if j["key"])
    s["rates canonical units joined to a glossary unit"] = sum(
        1 for j in join if j["key"] and not j["key"].startswith(("bor:", "hector:")))
    with_unit = [r for r in rates if r.get("unit")]
    s["rate rows with a unit"] = len(with_unit)
    s["rate rows joined"] = sum(r["rates_rows"] for r in cat.values())
    s["catalogue units with rate rows"] = sum(1 for r in cat.values() if r["rates_rows"])
    s["conversion statements (all)"] = len(conv)
    s["conversion statements: general"] = sum(1 for c in conv if c["scope"] == "general")
    s["conversion statements: general & exact"] = sum(1 for c in conv if c["scope"] == "general" and c["exact"])
    s["conversion statements: commodity-specific"] = sum(1 for c in conv if c["scope"] != "general")
    return dict(s)


def write_tables(out: Path, cat: dict, join: list, conv: list, by_key: dict):
    out.mkdir(parents=True, exist_ok=True)
    with (out / "catalogue.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(["key", "label", "emit", "dimension", "uri", "in_units_group", "attest_unit",
                    "attest_commodity_unit", "rates_rows", "rates_units", "reason"])
        for k, r in sorted(cat.items()):
            row = by_key.get(k)
            w.writerow([k, r["label"], int(r["emit"]), r["dimension"], unit_uri(row) if row else "",
                        int(r["in_units_group"]), r["attest_unit"], r["attest_commodity_unit"],
                        r["rates_rows"], ",".join(sorted(r["rates_units"])), r["reason"]])
    with (out / "rates_join.tsv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, ["rates_unit", "rows", "key", "method"], delimiter="\t", lineterminator="\n")
        w.writeheader()
        w.writerows(join)
    with (out / "conversions.tsv").open("w", encoding="utf-8", newline="") as f:
        fields = ["unit", "value", "target", "commodity", "exact", "scope", "source", "note"]
        w = csv.DictWriter(f, fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for c in conv:
            w.writerow({**c, "exact": int(bool(c["exact"]))})


def write_report(report: dict, path: Path):
    c = report["counts"]
    lines = ["# HECTOR unit catalogue report (PLAN.md tasks 18, 20)", "",
             "**Derived from the LCA glossary and Jenks's transcriptions: local only, do not commit "
             "or publish** (PLAN.md task 1). Tables: `build/units/`; records: `build/site/unit/`; "
             "ledger: `build/ledger/units.tsv` (not authoritative until first publication).", "",
             "| | count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in c.items()]
    for section, title in [("missing", "Ledger keys with no LCA history (need a human)"),
                           ("dimension_conflict", "Dimension changed since minting"),
                           ("rekeyed", "Keys renamed in LCA"), ("deprecated", "Deprecated / deleted"),
                           ("slug_collisions", "Slug collisions (suffixed)"),
                           ("path_clash", "Generated records replacing a file of the same path"),
                           ("join_target_missing", "Rates joins to a key not in the catalogue"),
                           ("units_tsv_unparsed", "units.tsv rows not fully parsed"),
                           ("duplicate_identifier", "Identifier given twice (lower role dropped)"),
                           ("attested_not_in_glossary", "Attested keys missing from the glossary")]:
        items = report.get(section) or []
        if section == "join_target_missing":
            items = [f"{k} × {n}" for k, n in collections.Counter(items).most_common()]
        lines += ["", f"## {title}: {len(items)}", ""] + [f"- {x}" for x in items[:200]]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lca", type=Path, default=LCA)
    ap.add_argument("--site", type=Path, default=REPO / "build" / "site")
    ap.add_argument("--out", type=Path, default=REPO / "build" / "units")
    ap.add_argument("--ledger", type=Path, default=REPO / "build" / "ledger" / "units.tsv")
    ap.add_argument("--rates", type=Path, default=REPO / "build" / "rates" / "rates.jsonl")
    a = ap.parse_args(argv)
    report = build(a.lca, a.site, a.out, a.ledger, a.rates)
    write_report(report, a.out / "report.md")
    print(json.dumps(report["counts"], ensure_ascii=False, indent=1))
    return 1 if report.get("missing") else 0


if __name__ == "__main__":
    sys.exit(main())
