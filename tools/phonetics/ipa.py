"""IPA phonetic keys for every glossary form (PLAN.md task 13; `hector:phoneticKey`).

`hector:phoneticKey` is "a phonetic transcription (IPA) of a Name, used to match variant
spellings across sources". This module gives every form (`f[].t`) of every LCA glossary entry
one such key.

The method: ONE convention for every form
-----------------------------------------
The forms are Middle English (about three quarters), medieval Latin (about 15%), and a few
Anglo-Norman/French, Low German/Dutch and mixed Latin-English phrases (measured on a
hand-labelled sample of 200, see the task-13 report). They carry no language tag, and HECTOR
does not guess one for its Names (CLAUDE.md). So every form is read with one convention,
**late Middle English letter values**: the values the English clerks who wrote both the Latin
and the English of the accounts gave the letters. Medieval Latin in England was read with the
same values (soft c and g before front vowels, v as /v/), and Middle English vowels, spelt
before the Great Vowel Shift, have their "continental" values. The result is a broad
(phonemic) transcription without stress, a key for matching, not a reconstruction of any one
speaker's pronunciation. It is deterministic, has no dependencies, and is small enough to port
to the browser so that a search box can transcribe a query the same way (task 23).

Why not Epitran, LCA's `process/helpers/phonetic.py` or the site's `js/phonemize.js`: all were
measured on the whole glossary (nearest-neighbour: is the key closest to a form's key that of
a form of the same concept?). Epitran eng-Latn (flite, modern American English) and LCA's
`get_ipa` (eng-Latn after `normalize_medieval_spelling`, which also deletes word spaces and
leaves 42 forms without a key) did worse than the plain spelling; phonemize.js spells unknown
words out letter by letter ("cervicia" -> "ˈtʃɛɹviˈsiaɪeɪ"); routing each form by a language
guess to Epitran lat-Latn or eng-Latn put a form and its variants in different conventions
and matched worse than either alone. Epitran lat-Latn (classical Latin) matched well but reads
English with classical values (c always /k/, v as /w/, sh as /sh/), and scored the same as the
bare spelling. This convention scored better than all of these and than the spelling. Only
Epitran fra-Latn scored higher, because French rules silence final consonants and -e and so
erase the Latin and English inflections; a French reading of English and Latin words is not a
transcription of them. Reproduce with `python3 -m tools.phonetics.compare`.

Usage
-----
    python -m tools.phonetics.ipa            # write build/phonetics/ipa.tsv (+ report)
    python -m tools.phonetics.ipa --check    # selftest + TSV is current; exit 1 on failure
    python -m tools.phonetics.ipa saffron "wyne of gascoigne"   # transcribe arguments

`transcribe(text)` is the function the exporter calls for each Name.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LCA = Path("/home/stephen/PycharmProjects/London_Customs_Accounts")
OUT = REPO / "build" / "phonetics" / "ipa.tsv"

METHOD = "lme-letters-v1"   # bump when any rule changes: the keys change with it
LANGUAGE = "enm"            # the convention (ISO 639-3 Middle English), not the form's language
TSV_FIELDS = ["form", "language", "ipa", "method", "lang_guess", "keys"]

VOWELS = set("aeiouy")

# --------------------------------------------------------------------------- normalising


def clean(text: str) -> str:
    """The letters of a form, lower case, words separated by single spaces.

    Thorn and eth are "th", yogh "y"; abbreviation marks (’ '), punctuation, editorial
    brackets, digits and LCA's key suffixes (`bolt_3`) are dropped; hyphens separate words.
    Accents are removed. Nothing else is changed: the spelling is the evidence.
    """
    t = unicodedata.normalize("NFKD", text.lower())
    t = t.replace("þ", "th").replace("ð", "th").replace("ȝ", "y")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    t = re.sub(r"[-_/]", " ", t)
    t = re.sub(r"[^a-z ]", "", t)
    return re.sub(r"\s+", " ", t).strip()


# --------------------------------------------------------------------------- rules
# Each rule: (letters, ipa, condition). At each position the FIRST rule whose letters start
# there and whose condition holds is applied, so longer and conditional rules come first.
# A condition gets (word, start, end) and sees the degeminated word.


def _next(w, e):
    return w[e] if e < len(w) else ""


def _prev(w, s):
    return w[s - 1] if s > 0 else ""


def _front(w, s, e):          # before e, i, y: soft c
    return _next(w, e) in ("e", "i", "y")


def _front_ei(w, s, e):       # before e, i: soft g (not y: gyrfalcon, gyrdel)
    return _next(w, e) in ("e", "i")


def _initial(w, s, e):
    return s == 0


def _after_vowel(w, s, e):
    return s > 0 and w[s - 1] in VOWELS


def _consonantal_y(w, s, e):  # y before a vowel, word-initially or after a vowel: yerde
    return _next(w, e) in "aeiou" and _next(w, e) != "" and (s == 0 or w[s - 1] in VOWELS)


def _ng_final(w, s, e):       # ring, ringes, sheling: velar nasal alone
    return _next(w, e) not in VOWELS


def _ng_back(w, s, e):        # ...ngo, ...nga: nasal + g
    return _next(w, e) in ("a", "o", "u")


def _weak_e(w, s, e):
    """Unstressed final -e and -es after a consonant, when an earlier vowel carries the
    word: the Middle English schwa of shepe, hoppes. (Not -en/-er/-el: Latin piper, gingiber.)"""
    rest = w[e:]
    if rest not in ("", "s"):
        return False
    if s == 0 or w[s - 1] in VOWELS:
        return False
    return any(ch in VOWELS for ch in w[: s - 1])


def _always(w, s, e):
    return True


RULES: list[tuple[str, str, object]] = [
    # consonant clusters and digraphs
    ("sch", "ʃ", _always),
    ("sh", "ʃ", _always),
    ("tch", "tʃ", _always),
    ("ch", "tʃ", _always),
    ("th", "θ", _always),
    ("ph", "f", _always),
    ("gh", "g", _initial),
    ("gh", "x", _always),
    ("wh", "w", _always),
    ("ck", "k", _always),
    ("qu", "kw", _always),
    ("qw", "kw", _always),
    ("sc", "s", _front),
    ("ng", "ŋ", _ng_final),
    ("ng", "ŋg", _ng_back),
    ("nk", "ŋk", _always),
    # vowel digraphs (long vowels and diphthongs, pre-Great-Vowel-Shift values)
    ("aw", "au", _always),
    ("au", "au", _always),
    ("ay", "ai", _always),
    ("ai", "ai", _always),
    ("ey", "ei", _always),
    ("ei", "ei", _always),
    ("ew", "eu", _always),
    ("eu", "eu", _always),
    ("ow", "uː", _always),
    ("ou", "uː", _always),
    ("oy", "oi", _always),
    ("oi", "oi", _always),
    ("oo", "oː", _always),
    ("ee", "eː", _always),
    ("ea", "ɛː", _always),
    ("ie", "iː", _always),
    ("aa", "aː", _always),
    ("ae", "e", _always),    # Latin ae, read e
    ("oe", "e", _always),    # Latin oe, read e
    ("ii", "i", _always),    # Latin -ii
    # single letters
    ("y", "j", _consonantal_y),
    ("c", "s", _front),
    ("c", "k", _always),
    ("g", "dʒ", _front_ei),
    ("g", "g", _always),
    ("G", "g", _always),
    ("j", "dʒ", _always),
    ("q", "k", _always),
    ("x", "ks", _always),
    ("e", "ə", _weak_e),
    ("a", "a", _always),
    ("e", "e", _always),
    ("i", "i", _always),
    ("y", "i", _always),
    ("o", "o", _always),
    ("u", "u", _always),
] + [(ch, ch, _always) for ch in "bdfhklmnprstvwz"]

_GEMINATE = re.compile(r"([bcdfgklmnprstvwxz])\1+")


def transcribe_word(word: str) -> str:
    # doubled consonant letters are orthographic in these spellings (ketelle, hoppes); but a
    # doubled g stays hard before e/i (hogge, egges), so it is marked G before degeminating
    w = _GEMINATE.sub(r"\1", word.replace("gg", "G"))
    out, i = [], 0
    while i < len(w):
        for letters, ipa, cond in RULES:
            if w.startswith(letters, i) and cond(w, i, i + len(letters)):
                out.append(ipa)
                i += len(letters)
                break
        else:  # clean() leaves only a-z, and every letter has an unconditional rule
            raise ValueError(f"no rule for {w[i]!r} in {word!r}")
    return "".join(out)


def transcribe(text: str) -> str:
    """The phonetic key of a form: its IPA, words separated by spaces; '' if it has no letters."""
    return " ".join(transcribe_word(w) for w in clean(text).split())


# --------------------------------------------------------------------------- language guess
# Recorded in the TSV only, to describe the population; it does NOT choose the transcription.
# A port of LCA process/concept_retrieval.py language_guess() (read, not imported: CLAUDE.md §7).

_LA_STRONG = re.compile(r"(orum|arum|ibus|ium|ius|um|us|ae|ii|a)$")
_LA_WEAK = re.compile(r"(is|i|em|ibus|o)$")
_EN_ORTH = re.compile(r"w|k|sh|gh")
_EN_WEAK = re.compile(r"y|th|(ing|yng|es|ys|e|er|ez)$")
_LA_FUNCTION = {"de", "pro", "cum", "sine", "vocat", "vocata", "et"}
_EN_FUNCTION = {"of", "and", "the", "called", "for", "with"}


def load_vernacular(lca: Path = LCA) -> set:
    p = lca / "data" / "pos_vernacular.json"
    try:
        return set(json.loads(p.read_text(encoding="utf-8")).get("vernacular", []))
    except (OSError, ValueError):
        return set()


def language_guess(text: str, vernacular: set = frozenset()) -> str:
    """'la', 'en' or 'und': LCA's word-voting heuristic (English orthography or an attested
    vernacular form says English, Latin case endings say Latin)."""
    n0 = clean(text)
    if n0 in vernacular:
        return "en"
    score = 0
    for w in n0.split():
        if w in vernacular or w in _EN_FUNCTION:
            score -= 1
        elif w in _LA_FUNCTION:
            score += 1
        elif _EN_ORTH.search(w):
            score -= 1
        elif _LA_STRONG.search(w):
            score += 1
        elif _EN_WEAK.search(w):
            score -= 1
        elif _LA_WEAK.search(w):
            score += 1
    return "la" if score > 0 else "en" if score < 0 else "und"


# --------------------------------------------------------------------------- table


def glossary_forms(lca: Path = LCA) -> dict[str, list[str]]:
    """{form text: sorted glossary keys that carry it}, over every f[].t of every entry."""
    g = json.loads((lca / "docs" / "data" / "glossary_data.json").read_text(encoding="utf-8"))
    forms: dict[str, set] = collections.defaultdict(set)
    for key, e in g["entries"].items():
        for f in e.get("f") or []:
            forms[f["t"]].add(key)
    return {t: sorted(ks) for t, ks in forms.items()}


def table(forms: dict[str, list[str]], vernacular: set = frozenset()) -> list[dict]:
    rows = []
    for t in sorted(forms):
        ipa = transcribe(t)
        rows.append({"form": t, "language": LANGUAGE if ipa else "",
                     "ipa": ipa, "method": METHOD if ipa else "none",
                     "lang_guess": language_guess(t, vernacular),
                     "keys": " | ".join(forms[t])})
    return rows


def write_tsv(rows: list[dict], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TSV_FIELDS, delimiter="\t", lineterminator="\n",
                           quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(rows)


def read_tsv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))


# --------------------------------------------------------------------------- selftest
# Pinned keys: common words in each of the glossary's languages. A change to any rule that
# alters one of these must be deliberate (bump METHOD and re-pin).
PINNED = {
    "saffron": "safron",                 # English
    "shepe": "ʃepə",                     # Middle English: sh, weak final -e
    "hoppes": "hopəs",                   # ME plural, geminate spelling
    "wyne": "winə",                      # y as i
    "yerde": "jerdə",                    # consonantal y
    "knyght": "knixt",                   # gh as x (ME)
    "cervisia": "servisia",              # Latin: soft c
    "avellanae": "avelane",              # Latin ae
    "unciis": "unsis",                   # Latin -ii
    "gingiber": "dʒindʒiber",            # soft g before e, i
    "egges": "egəs",                     # ... but doubled g stays hard
    "qwisshon": "kwiʃon",                # qw, ssh
    "ketelle bandes": "ketelə bandəs",   # phrase: words kept apart
    "cloþis": "kloθis",                  # thorn
    "pfeltt": "pfelt",                   # Low German spelling, letters kept
    "gardebrace": "gardebrasə",          # Anglo-Norman
    "bolt_3": "bolt",                    # LCA key suffix dropped
}
# Spellings the key must merge (variant spellings of one sound) ...
SAME = [("wyne", "wine"), ("coton", "cotton"), ("cyrupi", "sirupi"), ("fardel", "fardell"),
        ("shepe", "schepe"), ("qwisshon", "quisshon"), ("jesseron", "gesseron"),
        ("phisik", "fisik"), ("kanvas", "canvas")]
# ... and single-letter mutations it must NOT merge (it would be a spelling fold, not a key).
DIFFERENT = [("saffron", "saffran"), ("pannus", "pannis"), ("tin", "ten"), ("bolt", "bold"),
             ("pipe", "pike"), ("wyne", "wyte"), ("cervisia", "cervisio"), ("gunne", "gonne")]


def selftest(forms: dict[str, list[str]] | None = None) -> list[str]:
    """Return a list of failures ([] = pass)."""
    fails = []
    for form, want in PINNED.items():
        got = transcribe(form)
        if got != want:
            fails.append(f"pinned: {form!r} -> {got!r}, expected {want!r}")
    for a, b in SAME:
        if transcribe(a) != transcribe(b):
            fails.append(f"same: {a!r} {transcribe(a)!r} != {b!r} {transcribe(b)!r}")
    for a, b in DIFFERENT:
        if transcribe(a) == transcribe(b):
            fails.append(f"different: {a!r} and {b!r} both {transcribe(a)!r}")
    if transcribe("") != "" or transcribe("’ , .") != "":
        fails.append("no letters must give an empty key")
    if forms:
        texts = sorted(forms)
        first = [transcribe(t) for t in texts]
        shuffled = texts[:]
        random.Random(20260929).shuffle(shuffled)
        again = dict(zip(shuffled, (transcribe(t) for t in shuffled)))
        diff = [t for t, k in zip(texts, first) if again[t] != k]
        if diff:
            fails.append(f"nondeterministic on {len(diff)} forms, e.g. {diff[:3]}")
        bad = [t for t, k in zip(texts, first) if k and not re.fullmatch(r"[a-zæðŋəɛɔʃʒθχxːʊ ]+", k)]
        if bad:
            fails.append(f"{len(bad)} keys contain characters outside the rule outputs, e.g. {bad[:3]}")
    return fails


def check(lca: Path, path: Path) -> list[str]:
    forms = glossary_forms(lca)
    fails = selftest(forms)
    if not path.exists():
        return fails + [f"{path} missing: run python -m tools.phonetics.ipa"]
    on_disk = read_tsv(path)
    fresh = table(forms, load_vernacular(lca))
    if [r["form"] for r in on_disk] != [r["form"] for r in fresh]:
        a, b = {r["form"] for r in on_disk}, {r["form"] for r in fresh}
        fails.append(f"{path}: form set differs from the glossary ({len(b - a)} new, {len(a - b)} gone)")
    else:
        stale = [f["form"] for f, d in zip(fresh, on_disk)
                 if (f["ipa"], f["method"]) != (d["ipa"], d["method"])]
        if stale:
            fails.append(f"{path}: {len(stale)} keys differ from a fresh run, e.g. {stale[:3]}")
    return fails


# --------------------------------------------------------------------------- report


def summary(rows: list[dict]) -> dict:
    c = collections.Counter()
    for r in rows:
        c[("method", r["method"])] += 1
        c[("lang_guess", r["lang_guess"])] += 1
    return {"forms": len(rows), "with key": sum(1 for r in rows if r["ipa"]),
            "without key": sum(1 for r in rows if not r["ipa"]),
            "distinct keys": len({r["ipa"] for r in rows if r["ipa"]}),
            "by method": {k[1]: v for k, v in sorted(c.items()) if k[0] == "method"},
            "by lang_guess": {k[1]: v for k, v in sorted(c.items()) if k[0] == "lang_guess"}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("text", nargs="*", help="transcribe these and print, instead of the glossary")
    ap.add_argument("--lca", type=Path, default=LCA)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true",
                    help="selftest, determinism over the glossary, and the TSV is current")
    a = ap.parse_args(argv)
    if a.text:
        for t in a.text:
            print(f"{t}\t{transcribe(t)}")
        return 0
    if a.check:
        fails = check(a.lca, a.out)
        for f in fails:
            print("FAIL", f)
        print("phonetics check:", "FAILED" if fails else "ok")
        return 1 if fails else 0
    fails = selftest()
    if fails:
        for f in fails:
            print("FAIL", f)
        return 1
    rows = table(glossary_forms(a.lca), load_vernacular(a.lca))
    write_tsv(rows, a.out)
    print(json.dumps(summary(rows), ensure_ascii=False), f"-> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
