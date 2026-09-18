"""Parse the Books of Rates (Jenks transcriptions) into structured rate rows.

PLAN.md task 15, parsing only. Reads the LCA checkout by path and writes ONLY to
build/rates/, which is gitignored: everything this script produces is derived from
Stuart Jenks's transcriptions and must not be committed or published until the Jenks
permission (PLAN.md task 1) is granted.

Usage:
    .venv/bin/python -m tools.rates.parse_bor [--lca PATH] [--out build/rates]

Outputs (in --out):
    1604_raw.tsv   the 1604 book flattened from HTML to one line per rate entry
    rates.jsonl    one JSON object per row, all books
    rates.tsv      the same, flattened
    report.md      counts, unparsed patterns, failure samples

The commodity/qualifier/unit split is heuristic. The raw commodity cell and raw rate text
are always kept verbatim alongside the parsed fields.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path

DEFAULT_LCA = Path("/home/stephen/PycharmProjects/London_Customs_Accounts")
BOR_DIR = Path("data/bor")
TSV_PREFIX = "Jenks Books of Rates final 3 June 2024_"
TSV_BOOKS = {  # file suffix -> (book, direction)
    "1507": ("1507", "none"),
    "1545-Inward": ("1545", "inward"),
    "1545-Outward": ("1545", "outward"),
    "1558-Inward": ("1558", "inward"),
    "1558-Outward": ("1558", "outward"),
}
HTML_1604 = "Jenks Book of Rates 1604.html"

# --------------------------------------------------------------------------------------
# Rates: £ s d
# --------------------------------------------------------------------------------------

FRACTIONS = {"½": Fraction(1, 2), "¼": Fraction(1, 4), "¾": Fraction(3, 4)}
# ob. = obolus (halfpenny), q./qa./qua. = quadrans (farthing)
PENNY_FRACTION_WORDS = {"ob": Fraction(1, 2), "q": Fraction(1, 4), "qa": Fraction(1, 4),
                        "qua": Fraction(1, 4)}

_NUM = r"\d+(?:[½¼¾])?|[½¼¾]"
_RATE_TOKEN = re.compile(
    rf"£\s*(?P<l>{_NUM})"
    rf"|(?P<s>{_NUM})\s*s\b\.?"
    rf"|(?P<d>{_NUM})\s*d\b\.?"
    rf"|(?P<frac>ob|qua|qa|q)\b\.?",
)
# A complete monetary expression at the END of a line (used to split 1604 lines).
TRAILING_RATE = re.compile(
    rf"(?:£\s*\[?(?:{_NUM})\]?(?:\s+\[?(?:{_NUM})\]?\s*\[?s\]?)?(?:\s+\[?(?:{_NUM})\]?\s*\[?d\]?)?"
    rf"|\[?(?:{_NUM})\]?\s*\[?s\]?(?:\s+\[?(?:{_NUM})\]?\s*\[?d\]?)?"
    rf"|\[?(?:{_NUM})\]?\s*\[?d\]?"
    rf"|(?:{_NUM})\s+(?:{_NUM})\s*d)"   # '26 8d': shillings with the 's' omitted
    r"\s*$"
)


def _num(text: str) -> Fraction:
    total = Fraction(0)
    digits = re.match(r"\d+", text)
    if digits:
        total += int(digits.group())
    for ch, val in FRACTIONS.items():
        if ch in text:
            total += val
    return total


@dataclass
class Rate:
    pence: str | None = None        # exact decimal string, e.g. "160" or "5.75"
    pounds: str | None = None
    shillings: str | None = None
    pennies: str | None = None
    editorial: bool = False         # any part supplied in [...] by the editor
    status: str = "failed"          # ok | partial | failed
    reason: str = ""


def _decimal(fr: Fraction) -> str:
    if fr.denominator == 1:
        return str(fr.numerator)
    return f"{float(fr):.4f}".rstrip("0").rstrip(".")


def parse_rate(text: str) -> Rate:
    """Parse a rate like '£3 6s 8d', '13s 4d', '[13s 4d]', '33[s] 4d', '5¾d'."""
    raw = (text or "").strip()
    r = Rate(editorial="[" in raw)
    if not raw:
        r.reason = "empty rate"
        return r
    body = raw.replace("[", "").replace("]", "")
    body = re.sub(r"\s+", " ", body).strip()
    # Shillings with the 's' omitted, e.g. '26 8d'.
    body_fixed = re.sub(rf"^({_NUM}) ({_NUM})\s*d\b", r"\1s \2d", body)
    omitted_s = body_fixed != body
    body = body_fixed

    parts = {"l": Fraction(0), "s": Fraction(0), "d": Fraction(0)}
    seen = set()
    pos = 0
    leftovers = []
    # Read only the LEADING run of £/s/d tokens. Anything after it ('or 12s', 'at 3d þe lb.')
    # is reported, never added in: '50s at 3d þe lb.' is 50s, not 50s 3d.
    for m in _RATE_TOKEN.finditer(body):
        gap = body[pos:m.start()].strip(" ,")
        keys = [k for k in ("l", "s", "d") if m.group(k) is not None]
        if m.group("frac"):
            keys = ["d"]
        order = {"l": 0, "s": 1, "d": 2}
        out_of_order = seen and any(order[k] <= max(order[x] for x in seen) for k in keys
                                    if not (k == "d" and m.group("frac") and "d" in seen))
        if gap or out_of_order:
            break
        pos = m.end()
        for key in ("l", "s", "d"):
            if m.group(key) is not None:
                parts[key] += _num(m.group(key))
                seen.add(key)
        if m.group("frac"):
            parts["d"] += PENNY_FRACTION_WORDS[m.group("frac")]
            seen.add("d")
    tail = body[pos:].strip(" ,.")
    if tail:
        leftovers.append(tail)

    if not seen:
        r.reason = f"no £ s d found: {raw!r}"
        return r
    r.pounds = _decimal(parts["l"]) if "l" in seen else None
    r.shillings = _decimal(parts["s"]) if "s" in seen else None
    r.pennies = _decimal(parts["d"]) if "d" in seen else None
    r.pence = _decimal(parts["l"] * 240 + parts["s"] * 12 + parts["d"])
    if leftovers:
        r.status = "partial"
        r.reason = f"extra text in rate: {' | '.join(leftovers)!r}"
    else:
        r.status = "ok"
        r.reason = "shillings sign omitted in source" if omitted_s else ""
    return r


# --------------------------------------------------------------------------------------
# Units
# --------------------------------------------------------------------------------------

# canonical unit -> spelling variants (lower case, compared after stripping ., ’ and ,)
UNIT_VARIANTS: dict[str, list[str]] = {
    "hundred": ["c", "hundreth", "hundrith", "hunderith", "hundred", "hundrethe", "hundredth",
                "hondreth", "hundreith", "100"],
    "thousand": ["m", "ml", "thousande", "thousand", "thowsande", "thowsand", "thowsaunde",
                 "thousaunde", "1000", "thowsaund"],
    "dozen": ["dossen", "dosen", "dossyn", "dozen", "dozin", "dosyn", "dossene", "dozene",
              "doszen", "doussen", "dussen", "dosson"],
    "gross": ["grosse", "groce", "grose", "gross", "grosce"],
    "score": ["score", "skore"],
    "pound": ["pounde", "pound", "lb", "li", "poundes", "powne", "pownde"],
    "ounce": ["ounce", "unce", "ounces"],
    "hundredweight": ["cwt"],
    "piece": ["pece", "peece", "peace", "piece", "peese", "pees"],
    "yard": ["yarde", "yard", "yearde", "yeard", "yerde", "yerd", "yardes"],
    "ell": ["elle", "ell", "elles", "ells", "ellen"],
    "barrel": ["barrell", "barrelle", "barell", "barel", "barelle", "barylle", "barrel",
               "barrill", "barrelles", "barrells"],
    "last": ["laste", "last"],
    "bale": ["bale", "balle", "ballet", "ballett", "ballot", "balet"],
    "pane": ["pane", "paane"],
    "tun": ["tonne", "tunne", "tun", "tune", "ton"],
    "timber": ["tymber", "tymbre", "timber", "tymbar"],
    "pair": ["payre", "payer", "paire", "pair", "peyre", "payr"],
    "nest": ["neste", "nest"],
    "mantle": ["mantell", "mantle", "mantel"],
    "skin": ["skynne", "skyn", "skin", "skinne", "skynnes", "skynes"],
    "mast": ["maste", "mast"],
    "sack": ["sacke", "sack", "sak"],
    "box": ["boxe", "box"],
    "butt": ["butte", "butt", "but"],
    "quarter": ["quarter", "quartre", "quarters"],
    "pipe": ["pype", "pipe"],
    "bushel": ["busshell", "bushell", "busshel", "bushel", "bushells", "busshelle"],
    "sort": ["sorte", "sort"],
    "bolt": ["bolte", "bolt", "bolle"],
    "hawk": ["hawke", "hauke"],
    "chest": ["chest", "cheste"],
    "sum": ["some", "somme", "summe"],
    "pack": ["packe", "pack"],
    "roll": ["rowle", "rowlle", "roule", "rolle", "roll", "rowll"],
    "case": ["cace", "case", "casse"],
    "flock": ["flocke", "floke", "flock"],
    "maund": ["maunde", "maund", "mawnde"],
    "bundle": ["bundell", "bundelle", "bondell", "bundle", "bundel"],
    "hogshead": ["hoggeshed", "hogshead", "hogsheade", "hoggeshead", "hogshed"],
    "paper": ["paper", "papere"],
    "kip": ["kyppe", "kip"],
    "pocket": ["pocke", "pockett", "pocket"],
    "clout": ["clowte", "clout"],
    "tuft": ["tufte", "tuft"],
    "cag": ["cagge", "cag", "kegge"],
    "dicker": ["dekar", "dicker", "dyker", "dycker"],
    "cade": ["cade"],
    "shock": ["shocke", "shock"],
    "fur": ["furre", "fur"],
    "way": ["waye", "way", "weigh"],
    "load": ["lode", "loade", "load"],
    "fat": ["fatte", "fatt", "fat", "vatte"],
    "cloth": ["clothe", "cloth"],
    "ream": ["realme", "reame", "ream", "rheame"],
    "bunch": ["bonche", "bunche", "bunch"],
    "firkin": ["firkin", "fyrkyn", "ferkin", "firkyn"],
    "kilderkin": ["kilderkin", "kylderkyn"],
    "gallon": ["gallon", "galon", "gallond"],
    "stone": ["stone", "stoone"],
    "fodder": ["fodder", "fother", "foder"],
    "coffer": ["coffer", "coffre"],
    "basket": ["baskett", "basket"],
    "bag": ["bagge", "bag"],
    "bottle": ["bottell", "bottle"],
    "chaldron": ["chaldron", "chalder"],
    "topnet": ["topnett", "topnet"],
    "frail": ["frayle", "fraile", "frail"],
    "hide": ["hide", "hyde"],
    "dry vat": ["dryfatt", "dryfat"],
    "couple": ["couple", "cople"],
    "set": ["sett", "set"],
    "sheaf": ["sheaf", "sheffe", "sheafe"],
    "board": ["board", "borde", "boarde"],
    "rope": ["rope"],
    "flitch": ["flytche", "flitche", "flitch", "fleche"],
    "saddle": ["saddell", "sadle", "saddle"],
    "fin": ["fynne", "fin", "finne"],
    "tike": ["tike", "tyke"],
    "foot": ["foote", "foot", "fote"],
    "suit": ["suite", "sute", "suit"],
    "mark": ["marke", "mark"],
    "standard": ["standerde", "standard", "standarde"],
    "band": ["bonde", "band", "bande"],
    "packing": ["packyn", "packing"],
    "staff": ["staffe", "staff"],
    "plate": ["plate"],
}
UNIT_VARIANTS["piece"] += ["pyece", "peyce"]
UNIT_VARIANTS["dozen"] += ["doz"]
UNIT_VARIANTS["bolt"] += ["bowlte", "bolltte"]
UNIT_VARIANTS["chaldron"] += ["chaulder"]
UNIT_VARIANTS["barrel"] += ["barrall"]
UNIT_VARIANTS["ream"] += ["reme"]
UNIT_VARIANTS["bunch"] += ["bunchy"]
UNIT_VARIANTS["maund"] += ["mande"]
UNIT_VARIANTS["hogshead"] += ["hoggeshede"]
UNIT_VARIANTS["mantle"] += ["mantyll"]
UNIT_VARIANTS["mount"] = ["mount", "mounte"]
UNIT_VARIANTS["ounce"] += ["oz"]
UNIT_VARIANTS["shock"] += ["skoke", "shoke"]
COUNT_UNITS = {  # canonical -> nominal count (the long hundred of 120 is recorded as stated)
    "hundred": 100, "thousand": 1000, "dozen": 12, "gross": 144, "score": 20,
}
# Words that may sit between the determiner and the unit noun without ending the unit.
UNIT_MODIFIERS = {
    "small", "smalle", "smale", "great", "greate", "grett", "grete", "little", "lyttle",
    "single", "doble", "double", "duble", "half", "halfe", "hallfe", "di", "whole", "hole",
    "flemish", "flemyche", "flemysshe", "english", "englisshe", "full", "long", "short",
    "shorte", "longe", "wayte", "weight", "waight", "waighte", "weyght", "wayght", "weyte",
}
WEIGHT_WORDS = {"wayte", "weight", "waight", "waighte", "weyght", "wayght", "weyte", "wight"}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "foure": 4, "five": 5, "fyve": 5,
                "six": 6, "sixe": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "tenne": 10,
                "twelve": 12, "twelfe": 12, "twenty": 20, "twentie": 20, "half": "½", "halfe": "½"}
_VARIANT_TO_UNIT = {v: k for k, vs in UNIT_VARIANTS.items() for v in vs}
DETERMINERS = r"the|þe|thole|thelle|every|everie|a|per|le|for\s+the"
_DET = re.compile(rf"(?<![\w’'])(?P<det>{DETERMINERS})\s+", re.I)
_CONTENTS = re.compile(
    r"(?<![\w’'])(cont[’'`]?|conteyn\w*|contayn\w*|contein\w*|contain\w*|that\s+ys\s+to\s+saye?"
    r"|that\s+is\s+to\s+saye?)(?![\w])",
    re.I,
)


def _norm_word(w: str) -> str:
    return re.sub(r"[.,;:’'`\[\]()]", "", w.lower())


def unit_lookup(word: str) -> str | None:
    w = _norm_word(word)
    if w in _VARIANT_TO_UNIT:
        return _VARIANT_TO_UNIT[w]
    # plural in -s / -es
    for cut in ("es", "s"):
        if w.endswith(cut) and w[: -len(cut)] in _VARIANT_TO_UNIT:
            return _VARIANT_TO_UNIT[w[: -len(cut)]]
    return None


def _is_number(word: str) -> bool:
    return bool(re.fullmatch(r"\d[\d,]*[½¼¾]?|[½¼¾]", _norm_word(word)))


@dataclass
class UnitParse:
    unit_text: str = ""             # verbatim unit phrase (without the determiner)
    unit: str | None = None         # canonical unit, e.g. 'hundredweight', 'dozen', 'ell'
    quantity: str | None = None     # nominal count, e.g. '100' for 'the hundreth elles'
    of: str | None = None           # the counted unit, e.g. 'ell' in 'the hundreth elles'
    modifiers: list[str] = field(default_factory=list)


def parse_unit_phrase(phrase: str) -> UnitParse | None:
    """Interpret the words after a determiner. None if no unit noun is found early on."""
    words = phrase.split()
    up = UnitParse(unit_text=phrase.strip(" ,"))
    number = None
    head = None
    i = 0
    while i < len(words) and i < 5:
        w = words[i]
        nw = _norm_word(w)
        if head is None:
            if _is_number(w) and nw not in _VARIANT_TO_UNIT:
                number = _num(nw.replace(",", ""))
            elif nw in UNIT_MODIFIERS and not (nw in WEIGHT_WORDS and head is None and i == 0):
                up.modifiers.append(nw)
            elif unit_lookup(w):
                head = unit_lookup(w)
            else:
                return None
        else:
            if nw in WEIGHT_WORDS and head == "hundred":
                head = "hundredweight"
            elif unit_lookup(w) and up.of is None:
                if head == "hundred" and unit_lookup(w) == "pound" and number is None:
                    up.of = "pound"
                else:
                    up.of = unit_lookup(w)
            break
        i += 1
    if head is None:
        return None
    up.unit = head
    if head in COUNT_UNITS:
        base = COUNT_UNITS[head]
        if head == "gross" and "great" in {m.rstrip("e").replace("grett", "great") for m in up.modifiers}:
            base = 1728
        up.quantity = str(base)
    elif number is not None:
        up.quantity = _decimal(number)
        up.of = up.of or head
    if number is not None and head in COUNT_UNITS:
        up.quantity = _decimal(number * COUNT_UNITS[head])
    if {"half", "halfe", "hallfe", "di"} & set(up.modifiers):     # 'the di’ cheste'
        up.quantity = _decimal(_num(up.quantity) / 2 if up.quantity else Fraction(1, 2))
        up.of = up.of or head
    return up


@dataclass
class Split:
    commodity_text: str = ""        # everything before the unit phrase (commodity + qualifiers)
    head: str = ""                  # first word of the commodity text
    variety: str = ""               # the X in '... called X' / '... voc’ X'
    qualifier: str = ""             # commodity text minus head and variety
    determiner: str = ""
    unit: UnitParse | None = None
    contents_text: str = ""         # 'cont’ 112 lb.' and the like
    contents_quantity: str | None = None   # first number in the contents clause: '112'
    contents_unit: str | None = None       # the unit after it, canonicalised: 'pound'
    status: str = "failed"
    reason: str = ""


_CALLED = re.compile(r"\b(called|calld|voc[’']?|vocat[’']?|vocatur)\s+", re.I)


def split_commodity(cell: str) -> Split:
    text = re.sub(r"\s+", " ", cell or "").strip()
    # 'thelle' = 'the elle' (the ell), written as one word in the source
    text = re.sub(r"(?<![\w’'])thelle\b", "the elle", text, flags=re.I)
    sp = Split()
    if not text:
        sp.reason = "empty commodity cell"
        return sp
    cont = _CONTENTS.search(text)
    candidates = []
    for m in _DET.finditer(text):
        phrase_end = len(text)
        if cont and cont.start() > m.end():
            phrase_end = cont.start()
        up = parse_unit_phrase(text[m.end():phrase_end])
        if up:
            candidates.append((m, up))
    # also a bare trailing '<number> <unit>' or ', <unit>' with no determiner
    bare = re.search(r"(?:^|[\s,])(\d[\d,]*\s+\S+|\S+)\s*$", text)
    chosen = None
    if candidates:
        before_cont = [c for c in candidates if not cont or c[0].start() < cont.start()]
        chosen = (before_cont or candidates)[-1]
    if chosen:
        m, up = chosen
        sp.determiner = m.group("det")
        pre = text[: m.start()]
        tail = text[m.end():]
        sp.unit = up
        if cont and cont.start() >= m.end():
            sp.unit.unit_text = text[m.end(): cont.start()].strip(" ,")
            sp.contents_text = text[cont.start():].strip()
        else:
            sp.unit.unit_text = tail.strip(" ,")
            if cont and cont.start() < m.start():
                sp.contents_text = text[cont.start(): m.start()].strip(" ,")
                pre = text[: cont.start()]
        sp.status = "ok"
    elif bare and unit_lookup(bare.group(1).split()[-1]) and len(text.split()) > 1:
        up = parse_unit_phrase(bare.group(1))
        if up:
            sp.unit = up
            pre = text[: bare.start(1)]
            sp.status = "ok"
            sp.reason = "unit found without a determiner"
        else:
            pre = text
    else:
        pre = text
        # Fallback: a determiner followed by one or two words ending the cell ('the saddell').
        # Kept as unit_text, but not interpreted, and the row is marked partial.
        tail = re.search(rf"(?<![\w’'])(?P<det>{DETERMINERS})\s+(?P<u>[^\s,]+(?:\s+[^\s,]+)?)\s*$",
                         text, re.I)
        if tail and tail.start() > 0:
            sp.determiner = tail.group("det")
            sp.unit = UnitParse(unit_text=tail.group("u"))
            pre = text[: tail.start()]
            sp.status = "partial"
            sp.reason = f"unit word not in lexicon: {tail.group('u')!r}"
    sp.commodity_text = pre.strip(" ,")
    if sp.contents_text:
        words_as_digits = re.sub(
            r"\b(" + "|".join(NUMBER_WORDS) + r")\b",
            lambda m: str(NUMBER_WORDS[m.group(1).lower()]), sp.contents_text, flags=re.I)
        cm = re.search(r"(\d[\d,]*[½¼¾]?|[½¼¾])(?:\s+(\S+))?(?:\s+(\S+))?", words_as_digits)
        if cm:
            sp.contents_quantity = _decimal(_num(cm.group(1).replace(",", "")))
            u = unit_lookup(cm.group(2)) if cm.group(2) else None
            if u == "hundred" and cm.group(3) and _norm_word(cm.group(3)) in WEIGHT_WORDS:
                u = "hundredweight"
            sp.contents_unit = u
    if sp.unit is None:
        sp.reason = "no unit phrase recognised"
        sp.status = "failed"
    if not sp.commodity_text:
        sp.status = "failed" if sp.unit is None else "partial"
        sp.reason = (sp.reason + "; " if sp.reason else "") + "no commodity text before unit"
    words = sp.commodity_text.split()
    if words:
        sp.head = words[0].strip(",")
        rest = sp.commodity_text[len(words[0]):].strip(" ,")
        cm = _CALLED.search(rest)
        if cm:
            after = rest[cm.end():]
            variety = re.split(r",|\bthe\b|\bþe\b", after, maxsplit=1)[0].strip()
            sp.variety = variety
            rest = (rest[: cm.start()] + " " + after[len(variety):]).strip(" ,")
        sp.qualifier = re.sub(r"\s+", " ", rest).strip(" ,")
    return sp


# --------------------------------------------------------------------------------------
# 1604: HTML -> one line per entry
# --------------------------------------------------------------------------------------

FOOTNOTE_MARKERS = re.compile(r"^(?:[a-z](?:[‑-][a-z])?)\s*$")
_LETTER_HEAD = re.compile(r"^[–-]\s*[A-Z]\s*[–-]$")


def _cell_text(el) -> str:
    """Text of an element with footnote-marker superscripts dropped and others joined."""
    from bs4 import NavigableString

    out = []
    for node in el.descendants:
        if isinstance(node, NavigableString):
            parent = node.parent
            if parent is not None and parent.name == "sup":
                s = str(node).replace("\xa0", " ")
                if FOOTNOTE_MARKERS.match(s.strip()):
                    continue
                out.append("\x00" + s.strip())      # glue to the previous token
            else:
                out.append(str(node))
    text = "".join(out)
    text = re.sub(r"\s*\x00", "", text)
    text = text.replace("\xad", "").replace("‑", "-").replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _table_lines(table) -> list[tuple[list[str], str]]:
    """Expand a rowspan/colspan table into (group_path, entry_text) per row."""
    lines = []
    pending: list[list] = []   # per column: [text, rows_remaining]
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        row: list[str] = []
        col = 0
        new_cells = list(cells)
        k = 0
        while k < len(new_cells) or (col < len(pending) and pending[col][1] > 0):
            if col < len(pending) and pending[col][1] > 0:
                row.append(pending[col][0])
                pending[col][1] -= 1
                col += 1
                continue
            if k >= len(new_cells):
                break
            c = new_cells[k]
            k += 1
            t = _cell_text(c)
            rs = int(c.get("rowspan", 1))
            cs = int(c.get("colspan", 1))
            for j in range(cs):
                while len(pending) <= col:
                    pending.append(["", 0])
                pending[col] = [t if j == 0 else "", rs - 1]
                row.append(t if j == 0 else "")
                col += 1
        row = [x for x in row if x]
        if row:
            lines.append((row[:-1], row[-1]))
    return lines


@dataclass
class Raw1604:
    block: int
    direction: str
    group_path: str
    entry: str
    commodity_cell: str
    rate_text: str
    note: str


def extract_1604(html_path: Path) -> tuple[list[Raw1604], dict]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_path.read_bytes(), "lxml")
    out: list[Raw1604] = []
    stats = collections.Counter()
    direction = None
    section_group = ""       # 'Drugges voc’': a heading paragraph that runs to the next letter
    block = 0
    for el in soup.body.find_all(["p", "table"]):
        if el.name == "p" and el.find_parent("table"):
            continue
        block += 1
        if el.name == "p":
            first = next((c for c in el.children if getattr(c, "name", None) or str(c).strip()), None)
            if getattr(first, "name", None) == "sup" and FOOTNOTE_MARKERS.match(
                    first.get_text().replace("\xa0", " ").strip()):
                stats["footnote paragraphs skipped"] += 1
                continue
            text = _cell_text(el)
            low = text.lower()
            if low.startswith("rates for the subsidy of poundage inwardes"):
                direction = "inward"
                continue
            if low.startswith("rates for the subsydy of poundage outwardes"):
                direction = "outward"
                continue
            if low.startswith("custome and subsidy of wollen clothes"):
                stats["stopped at the woollen-cloth section"] += 1
                break
            if direction is None or not text:
                continue
            if _LETTER_HEAD.match(text):
                stats["letter headings skipped"] += 1
                section_group = ""
                continue
            if re.fullmatch(r"(?:Adhuc\s+)?Drugges(?:\s+voc[’']?)?", text):
                section_group = "Drugges voc’"
                stats["'Drugges' section headings (applied as group to following entries)"] += 1
                continue
            items = [([section_group] if section_group else [], text)]
        else:
            if direction is None:
                continue
            items = _table_lines(el)
        for path, entry in items:
            m = TRAILING_RATE.search(entry)
            if m and m.start() > 0:
                cell, rate, note = entry[: m.start()].strip(), m.group().strip(), ""
            else:
                cell, rate = entry, ""
                note = "cross-reference" if re.search(r"\bsee\b", entry) else "no trailing rate"
                if note == "no trailing rate" and len(entry) > 200:
                    stats["long prose paragraphs skipped"] += 1
                    continue
            full_cell = " ".join(path + [cell]).strip()
            out.append(Raw1604(block, direction, " > ".join(path), entry, full_cell, rate, note))
    return out, dict(stats)


# --------------------------------------------------------------------------------------
# Rows
# --------------------------------------------------------------------------------------

@dataclass
class Row:
    book: str
    direction: str
    source_file: str
    source_line: int                # line in the TSV (header = 1), or block index for 1604
    commodity_raw: str
    rate_raw: str
    group_path: str
    commodity_text: str
    head: str
    variety: str
    qualifier: str
    unit_text: str
    unit: str | None
    unit_quantity: str | None
    unit_of: str | None
    contents_text: str
    contents_quantity: str | None
    contents_unit: str | None
    pence: str | None
    pounds: str | None
    shillings: str | None
    pennies: str | None
    editorial: bool
    parse_status: str
    reason: str


def build_row(book, direction, source_file, source_line, commodity_raw, rate_raw,
              group_path="", note="") -> Row:
    sp = split_commodity(commodity_raw)
    rt = parse_rate(rate_raw)
    reasons = []
    if note:
        reasons.append(note)
    if rt.reason:
        reasons.append("rate: " + rt.reason)
    if sp.reason:
        reasons.append("split: " + sp.reason)
    if rt.pence is None:
        status = "failed"       # no readable rate: not a usable rate, whatever the split did
    elif rt.status == "ok" and sp.status == "ok":
        status = "ok"
    else:
        status = "partial"
    u = sp.unit
    return Row(
        book=book, direction=direction, source_file=source_file, source_line=source_line,
        commodity_raw=commodity_raw, rate_raw=rate_raw, group_path=group_path,
        commodity_text=sp.commodity_text, head=sp.head, variety=sp.variety,
        qualifier=sp.qualifier, unit_text=u.unit_text if u else "",
        unit=u.unit if u else None, unit_quantity=u.quantity if u else None,
        unit_of=u.of if u else None, contents_text=sp.contents_text,
        contents_quantity=sp.contents_quantity, contents_unit=sp.contents_unit,
        pence=rt.pence, pounds=rt.pounds, shillings=rt.shillings, pennies=rt.pennies,
        editorial=rt.editorial, parse_status=status, reason="; ".join(reasons),
    )


def read_tsv_rows(lca: Path) -> list[Row]:
    rows = []
    for suffix, (book, direction) in TSV_BOOKS.items():
        path = lca / BOR_DIR / f"{TSV_PREFIX}{suffix}.tsv"
        with path.open(encoding="utf-8", newline="") as fh:
            reader = csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE)
            header = next(reader)
            assert header[:2] == ["commodity", "rate"], (path, header)
            for lineno, rec in enumerate(reader, start=2):
                if not any(x.strip() for x in rec):
                    continue
                rec = rec + [""] * (2 - len(rec))
                rows.append(build_row(book, direction, path.name, lineno, rec[0], rec[1]))
    return rows


def rows_1604(raw: list[Raw1604]) -> list[Row]:
    return [build_row("1604", r.direction, HTML_1604, r.block, r.commodity_cell, r.rate_text,
                      group_path=r.group_path, note=r.note) for r in raw]


# --------------------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------------------

def write_report(rows: list[Row], stats1604: dict, out: Path) -> None:
    by = collections.Counter((r.book, r.direction, r.parse_status) for r in rows)
    books = sorted({(r.book, r.direction) for r in rows})
    lines = ["# Books of Rates parse report", "",
             "Generated by `tools/rates/parse_bor.py`. **Derived from Jenks's transcriptions: "
             "local only, do not commit or publish** (PLAN.md task 1).", "",
             "| book | direction | rows | ok | partial | failed | editorial |",
             "|---|---|---:|---:|---:|---:|---:|"]
    for b, d in books:
        sub = [r for r in rows if r.book == b and r.direction == d]
        lines.append(f"| {b} | {d} | {len(sub)} | {by[(b, d, 'ok')]} | {by[(b, d, 'partial')]} "
                     f"| {by[(b, d, 'failed')]} | {sum(r.editorial for r in sub)} |")
    tot = collections.Counter(r.parse_status for r in rows)
    lines.append(f"| **all** | | **{len(rows)}** | {tot['ok']} | {tot['partial']} | "
                 f"{tot['failed']} | {sum(r.editorial for r in rows)} |")
    lines += ["", "Status: **ok** = rate parsed to pence and a unit recognised; **partial** = "
              "rate parsed but the unit was not recognised, or extra text in the rate; "
              "**failed** = no monetary rate could be read.", ""]
    lines += ["## How far to trust this", "",
              "- **Rates** (£ s d → pence) and **units** are the reliable part. Only the leading "
              "£ s d expression is read; trailing text such as `at 3d þe lb.` or `or 12s` makes "
              "the row *partial* and is never added in.",
              "- `unit_quantity` is the *nominal* count (C = 100, gross = 144, great gross = "
              "1,728). The source often states the real one in `contents_text` "
              "(`cont’ 120`, `cont’ 112 lb.`): read `contents_quantity`/`contents_unit` before "
              "treating a hundred as 100.",
              "- `head` / `variety` / `qualifier` are a **naive** split: `head` is the first word, "
              "`variety` whatever follows `voc’`/`vocat’`/`called`. It is wrong for two-word "
              "commodities (`Sugar candy`, `Semen papaver`, `Gould papers`). Use "
              "`commodity_text` and match it against the glossary instead (task 16).",
              "- 1604 table groupings (`Fishe vocat’ > herringes`) and the `Drugges voc’` "
              "section are prefixed to `commodity_raw`; `group_path` holds them separately.",
              "- `editorial` means a `[...]` in the **rate** only; brackets in the commodity cell "
              "are kept in the text but not flagged.", ""]
    lines += ["## 1604 extraction", ""] + [f"- {k}: {v}" for k, v in sorted(stats1604.items())]
    lines += ["", "## Units recognised", "", "| unit | rows |", "|---|---:|"]
    for u, n in collections.Counter(r.unit or "(none)" for r in rows).most_common(40):
        lines.append(f"| {u} | {n} |")
    lines += ["", "## Unparsed rate texts (most common, digits → N)", ""]
    bad = collections.Counter(re.sub(r"\d+", "N", r.rate_raw) or "(empty)"
                              for r in rows if r.parse_status == "failed" or "rate:" in r.reason)
    lines += [f"- `{k}` × {v}" for k, v in bad.most_common(25)]
    lines += ["", "## Commodity cells with no unit recognised: last word (most common)", ""]
    nounit = collections.Counter((r.commodity_raw.split() or ["(empty)"])[-1].lower()
                                 for r in rows if r.unit is None)
    lines += [f"- `{k}` × {v}" for k, v in nounit.most_common(30)]
    lines += ["", "## Sample of non-ok rows (up to 40)", "",
              "| book | line | commodity | rate | status | reason |", "|---|---:|---|---|---|---|"]
    nonok = [r for r in rows if r.parse_status != "ok"]
    step = max(1, len(nonok) // 40)
    for r in nonok[::step][:40]:
        esc = lambda s: s.replace("|", "\\|")
        lines.append(f"| {r.book} {r.direction} | {r.source_line} | {esc(r.commodity_raw)[:90]} | "
                     f"{esc(r.rate_raw)} | {r.parse_status} | {esc(r.reason)[:100]} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lca", type=Path, default=DEFAULT_LCA)
    ap.add_argument("--out", type=Path, default=Path("build/rates"))
    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)

    raw, stats = extract_1604(args.lca / BOR_DIR / HTML_1604)
    with (args.out / "1604_raw.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["block", "direction", "group_path", "commodity", "rate", "note", "entry"])
        for r in raw:
            w.writerow([r.block, r.direction, r.group_path, r.commodity_cell, r.rate_text,
                        r.note, r.entry])

    rows = read_tsv_rows(args.lca) + rows_1604(raw)
    with (args.out / "rates.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    fields = list(asdict(rows[0]).keys())
    with (args.out / "rates.tsv").open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    write_report(rows, stats, args.out)
    tot = collections.Counter(r.parse_status for r in rows)
    print(f"{len(rows)} rows ({dict(tot)}); 1604: {len(raw)} entries; wrote {args.out}/",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
