"""
Link the Books of Rates to commodities and units, and emit the rates (PLAN.md tasks 14 and 17,
decision 2). Local only: writes into build/ like the other Jenks-derived steps.

    .venv/bin/python -m tools.rates.parse_bor            # build/rates/rates.jsonl
    .venv/bin/python -m tools.export.export_hector       # build/site/commodity, ledger
    .venv/bin/python -m tools.units.build_units          # build/site/unit, units ledger, rates_join
    .venv/bin/python -m tools.rates.link_rates           # this: rates into build/site

WHAT IT DOES, per rate row of the 1507, 1545 and 1558 books (1604 waits for decision D6: its
commodities are to return to the LCA glossary first):

1. LINK THE COMMODITY by matching `commodity_text` against every glossary spelling (the
   glossary's forms, normalised), LONGEST MATCH FIRST, anywhere in the text. The parser's own
   head/qualifier split is 15-20% wrong (PLAN.md task 15), so it is not used. A spelling that
   belongs to two concepts is ambiguous and is not used alone.
2. DECISION 2 (29 Sep 2026): flatten ONLY what the books price separately. Words left over
   after the matched spelling -- "canvas" + "Normandy browne" -- are the qualifier, and that
   combination becomes a commodity record of its own (commodity/<concept>-<qualifier>),
   linked to the base by skos:broader AND hector:compoundOf, with the rate on it. A rate with
   no leftover words goes on the base commodity. Slugs for combinations are minted once into
   build/ledger/qualified.tsv, never re-derived (URI policy §3).
3. THE RATE: a Rate node in the record's `taxation`, id <record>#rate-<book>-<direction>-<line>:
   the amount in pence and as written (£ s d), per <quantity> <unit> (the unit through
   build/units/rates_join.tsv and the units ledger), valid from the book's year to the next
   book's, and the source line quoted in `sourceText`.

Rows that cannot be linked -- no spelling found, only an ambiguous one, no unit, no price --
are listed in build/rates/link-report.md, never guessed.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import json
import re
import sys
import unicodedata
from pathlib import Path

from tools.phonetics.ipa import transcribe as phonetic_key

REPO = Path(__file__).resolve().parents[2]
LCA = REPO.parent / "London_Customs_Accounts"
BUILD = REPO / "build"
W3ID = "https://w3id.org/hector/"
CONTEXT = ["https://linked.art/ns/v1/linked-art.json", "https://w3id.org/hector/context"]
AAT_PREFERRED = {"id": "aat:300404670", "type": "Type", "_label": "preferred terms"}
AAT_BRIEF = {"id": "aat:300418049", "type": "Type", "_label": "brief texts"}
ATTESTED = {"id": "hector:AttestedVariant", "type": "Type", "_label": "attested variant"}
STERLING = {"id": "aat:300411998", "type": "Currency", "_label": "pound sterling (system of money)"}
BOOKS = ["1507", "1545", "1558", "1604"]
LINKED_BOOKS = ("1507", "1545", "1558")        # 1604 after D6
# Words that join a commodity to its qualifier or its measure, and say nothing of either.
FILLER = {"the", "of", "de", "and", "et", "called", "voc", "vocat", "vocatur", "cont", "conteyning",
          "conteynynge", "conteininge", "conteyninge", "containing", "for", "or", "a", "an", "in",
          "with", "wt", "le", "la", "les", "du", "des", "pro", "per", "every", "each",
          # the books' formulae: "that ys to saye", "whether ytt be", "of all sortes"
          "that", "ys", "is", "to", "saye", "say", "whether", "ytt", "it", "be", "all", "sorte",
          "sortes", "sortte", "manare", "maner", "manner", "one", "another", "on", "by", "at"}
# Glossary spellings that are ordinary words in the books' English, and so never link on
# their own away from the head: "every" is a spelling of ivory, "made" and "called" of others.
COMMON = FILLER | {"made", "small", "smalle", "great", "grett", "white", "whyte", "black", "blake",
                   "rede", "red", "browne", "new", "old", "fyne", "fine", "course", "coarse"}
QUAL_LEDGER_FIELDS = ["slug", "glossary_key", "qualifier", "minted", "status"]


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace("þ", "th").replace("ð", "th").replace("ſ", "s").replace("æ", "ae")
    s = re.sub(r"[’'`‘ʼ]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-") or "x"


def load_tsv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def form_index(entries: dict) -> dict[str, set]:
    """normalised spelling -> glossary keys that carry it (keys themselves count as spellings)."""
    idx = collections.defaultdict(set)
    for key, e in entries.items():
        for t in [re.sub(r"_\d+$", "", key)] + [f.get("t") for f in e.get("f", [])]:
            n = norm(t or "")
            if n and len(n) >= 3:
                idx[n].add(key)
    return idx


def link(text: str, idx: dict, max_len: int) -> tuple[str | None, str, str, str]:
    """(glossary key, matched spelling, qualifier, how). The books name the goods FIRST
    ("Canvas called Normandy..."), so, in order: the longest unique spelling at the start;
    then the longest unique phrase (2+ words) anywhere; then a single unique word anywhere
    that is not an ordinary word (COMMON). A spelling shared by several concepts is ambiguous
    and never used. Anywhere-matches linked the wrong word when tried first: "Buckroms in
    paperes, every paper" -> ivory (a spelling of which is "every"), "Corke made in
    barrelles" -> barrel."""
    toks = norm(text).split()

    def hit(i, n):
        keys = idx.get(" ".join(toks[i:i + n]))
        return next(iter(keys)) if keys and len(keys) == 1 else None

    def result(i, n, how):
        spelling = toks[i:i + n]
        rest = [t for t in toks[:i] + toks[i + n:]
                if t not in FILLER and not t.isdigit() and t not in spelling]
        return hit(i, n), " ".join(spelling), " ".join(rest), how

    for n in range(min(max_len, len(toks)), 0, -1):          # 1. at the head
        if hit(0, n):
            return result(0, n, "head")
    for n in range(min(max_len, len(toks)), 1, -1):          # 2. a phrase anywhere
        for i in range(1, len(toks) - n + 1):
            if hit(i, n):
                return result(i, n, "phrase")
    for i in range(1, len(toks)):                            # 3. a word anywhere
        if toks[i] not in COMMON and len(toks[i]) >= 4 and hit(i, 1):
            return result(i, 1, "word")
    amb = [t for t in toks if len(idx.get(t, ())) > 1]
    return None, "", "", ("ambiguous: " + ", ".join(amb)) if amb else "no glossary spelling"


def qualifier_canon(lca: Path):
    """One qualifier however it is spelt: "whit"/"whyte" -> white, "spruse"/"sprewce" -> prussia,
    "parrys" -> paris, through LCA's docs/data/qualifiers.json (a word whose spelling it lists
    under exactly one canonical); other words by a light spelling fold (y as i, w and v as u,
    doubled letters single, a final e dropped), which also joins newcastell and neucastell.
    Without this, one combination spelt three ways across the books became three records."""
    q = json.loads((lca / "docs/data/qualifiers.json").read_text(encoding="utf-8"))["canonicals"]
    form2c = collections.defaultdict(set)
    for k, v in q.items():
        for f in [k, v.get("label", ""), *v.get("forms", [])]:
            n = norm(f)
            if n:
                form2c[n].add(v.get("label") or k)

    def fold(t: str) -> str:
        t = t.replace("y", "i").replace("w", "u").replace("v", "u")
        t = re.sub(r"(.)\1+", r"\1", t)
        return t[:-1] if len(t) > 3 and t.endswith("e") else t

    def canon(qual: str) -> str:
        out = []
        for t in qual.split():
            c = form2c.get(t)
            out.append(norm(next(iter(c))) if c and len(c) == 1 else fold(t))
        return " ".join(dict.fromkeys(out))          # a word said twice counts once
    return canon


def next_year(book: str) -> str:
    i = BOOKS.index(book)
    return BOOKS[i + 1] if i + 1 < len(BOOKS) else book


def _num(v):
    """The per-quantity as a number (the parser gives "100"); 1 when the rate is per one."""
    if v in (None, ""):
        return 1
    f = float(v)
    return int(f) if f.is_integer() else f


def rate_node(rec_uri: str, r: dict, unit_ref: dict) -> dict:
    lsd = (r.get("rate_raw") or "").strip()
    return {
        "id": f"{rec_uri}#rate-{r['book']}-{r['direction']}-{r['source_line']}",
        "type": "Rate",
        "_label": f"{r['book']}{' ' + r['direction'] if r['direction'] != 'none' else ''}: "
                  f"{r['commodity_raw']} {lsd}",
        "amount": {"type": "MonetaryAmount", "currency": STERLING,
                   "valueInPence": str(r["pence"]), "lsd": lsd.strip("[]")},
        "perQuantity": {"type": "Dimension", "value": _num(r.get("unit_quantity")), "unit": unit_ref},
        "validFrom": r["book"],
        "validThrough": next_year(r["book"]),
        "sourceText": (f"Book of Rates {r['book']}"
                       + (f", {r['direction']}" if r["direction"] != "none" else "")
                       + f", line {r['source_line']} (transcribed by Stuart Jenks): "
                       + f"'{r['commodity_raw']}' {r['rate_raw']}"
                       + (" [the rate is an editorial supply]" if r.get("editorial") else "")),
    }


def run(lca: Path = LCA, today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    site = BUILD / "site"
    g = json.loads((lca / "docs/data/glossary_data.json").read_text(encoding="utf-8"))
    entries = g["entries"]
    idx = form_index(entries)
    max_len = max(len(k.split()) for k in idx)
    com = {r["glossary_key"]: r["slug"] for r in load_tsv(BUILD / "ledger/commodities.tsv")
           if r["status"] == "active"}
    all_slugs = {r["slug"] for r in load_tsv(BUILD / "ledger/commodities.tsv")}
    units = {r["key"]: r["slug"] for r in load_tsv(BUILD / "ledger/units.tsv") if r["status"] == "active"}
    join = {r["rates_unit"]: r["key"] for r in load_tsv(BUILD / "units/rates_join.tsv")}
    qpath = BUILD / "ledger/qualified.tsv"
    qledger = load_tsv(qpath)
    qslug = {(r["glossary_key"], r["qualifier"]): r["slug"] for r in qledger if r["status"] == "active"}
    all_slugs |= {r["slug"] for r in qledger}

    rows = [json.loads(l) for l in (BUILD / "rates/rates.jsonl").open(encoding="utf-8")]
    canon = qualifier_canon(lca)
    rep = collections.Counter()
    # DECISION 2 (29 Sep): a qualified combination gets its own record only where the books
    # PRICE it separately -- where, for the same concept and the same unit, rates differ with
    # the qualifier (issue #2: 170 heads, 391 phrases). Elsewhere the rate sits on the base
    # commodity and its wording is kept in sourceText. First pass: prices per (concept, unit).
    prices = collections.defaultdict(set)
    for r in rows:
        if r["book"] in LINKED_BOOKS and r.get("pence") and join.get(r.get("unit") or "") in units:
            k, _sp, q, _how = link(r.get("commodity_text") or r.get("commodity_raw") or "", idx, max_len)
            if k:
                prices[(k, join[r["unit"]])].add((canon(q) if q else "", str(r["pence"])))
    priced_apart = {kq for kq, ps in prices.items()
                    if len({p for _q, p in ps}) > 1 and len({q for q, _p in ps}) > 1}
    unlinked = collections.defaultdict(list)
    by_record = collections.defaultdict(list)          # slug -> rate nodes
    qual_docs = {}                                     # slug -> (key, qualifier, [attested texts])
    sample = []
    for r in rows:
        if r["book"] not in LINKED_BOOKS:
            rep["1604 rows held for D6"] += 1
            continue
        rep["rows considered"] += 1
        if not r.get("pence"):
            unlinked["no price"].append(r); continue
        ukey = join.get(r.get("unit") or "")
        if not ukey or ukey not in units:
            unlinked["no unit"].append(r); continue
        key, spelling, qual, why = link(r.get("commodity_text") or r.get("commodity_raw") or "", idx, max_len)
        if not key:
            unlinked[why.split(":")[0]].append(r); continue
        rep[f"linked at the {why}"] += 1
        qual = canon(qual) if qual else ""
        if qual and (key, ukey) not in priced_apart:
            rep["qualifier kept in sourceText (not priced apart)"] += 1
            qual = ""
        if key not in com:
            unlinked["concept has no HECTOR record"].append(r); continue
        unit_ref = {"id": f"{W3ID}unit/{units[ukey]}", "type": "MeasurementUnit",
                    "_label": re.sub(r"_\d+$", "", re.sub(r"^(bor|hector):", "", ukey))}
        if qual:
            slug = qslug.get((key, qual))
            if not slug:
                base = slugify(f"{com[key]} {qual}")
                slug, n = base, 2
                while slug in all_slugs:
                    slug, n = f"{base}-{n}", n + 1
                qslug[(key, qual)] = slug
                all_slugs.add(slug)
                qledger.append({"slug": slug, "glossary_key": key, "qualifier": qual,
                                "minted": today, "status": "active"})
            qd = qual_docs.setdefault(slug, (key, qual, []))
            if r["commodity_text"] not in qd[2]:
                qd[2].append(r["commodity_text"])
            rep["rates on a qualified commodity"] += 1
        else:
            slug = com[key]
            rep["rates on a base commodity"] += 1
        by_record[slug].append(rate_node(f"{W3ID}commodity/{slug}", r, unit_ref))
        if len(sample) < 400:
            sample.append((r["commodity_raw"], key, spelling, qual, why))
    for why, rs in unlinked.items():
        rep[f"not linked: {why}"] += len(rs)

    # qualified records (decision 2)
    for slug, (key, qual, texts) in qual_docs.items():
        base_uri, base_label = f"{W3ID}commodity/{com[key]}", re.sub(r"_\d+$", "", key)
        doc = {"@context": CONTEXT, "id": f"{W3ID}commodity/{slug}", "type": "Type",
               "_label": f"{base_label} ({qual})",
               "referred_to_by": [{"type": "LinguisticObject", "classified_as": [AAT_BRIEF],
                                   "content": f"{base_label}, qualified as ‘{qual}’: a commodity as the "
                                              "Books of Rates price it separately (HECTOR decision 2, 29 Sep 2026)."}],
               "identified_by": [{"type": "Name", "content": f"{base_label} ({qual})",
                                  "classified_as": [AAT_PREFERRED]}]
                                + [{"type": "Name", "content": t, "classified_as": [ATTESTED]} for t in texts],
               "broader": [{"id": base_uri, "type": "Type", "_label": base_label}],
               # task 13: the same IPA key the exporter gives every Name (tools/phonetics/ipa.py)
               "compoundOf": [{"id": base_uri, "type": "Type", "_label": base_label}],
               "modified": today}
        for n in doc["identified_by"]:
            k = phonetic_key(n["content"])
            if k:
                n["phoneticKey"] = [k]
        p = site / "commodity" / slug / "ontology.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rep["qualified commodity records"] = len(qual_docs)

    # rates onto the records
    for slug, rates in by_record.items():
        p = site / "commodity" / slug / "ontology.json"
        doc = json.loads(p.read_text(encoding="utf-8"))
        doc["taxation"] = sorted(rates, key=lambda x: x["id"])
        p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rep["records with rates"] = len(by_record)

    qpath.parent.mkdir(parents=True, exist_ok=True)
    with qpath.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, QUAL_LEDGER_FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in sorted(qledger, key=lambda r: r["slug"]):
            w.writerow({k: r.get(k, "") for k in QUAL_LEDGER_FIELDS})

    out = BUILD / "rates/link-report.md"
    lines = ["# Books of Rates: linking report", "", f"Built {today} by tools/rates/link_rates.py.", ""]
    lines += [f"- {k}: {v:,}" for k, v in sorted(rep.items())]
    for why, rs in sorted(unlinked.items()):
        lines += ["", f"## Not linked: {why} ({len(rs)})", ""]
        lines += [f"- {r['book']} l.{r['source_line']}: {r['commodity_raw']}" for r in rs[:60]]
    lines += ["", "## Sample of links (commodity as written -> concept, spelling, qualifier)", ""]
    lines += [f"- {a} -> **{k}** via '{s}' ({h})" + (f", qualifier '{q}'" if q else "") for a, k, s, q, h in sample[:160]]
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dict(rep)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--lca", type=Path, default=LCA)
    a = ap.parse_args(argv)
    print(json.dumps(run(a.lca), indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
