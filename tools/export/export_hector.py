#!/usr/bin/env python3
"""Export the LCA commodity glossary as HECTOR commodity records (PLAN.md task 12).

    .venv/bin/python -m tools.export.export_hector            # writes build/site/, build/ledger/
    .venv/bin/python tools/validate.py --root build/site      # then validate what was written

Reads `LCA/docs/data/glossary_data.json` and `concept_attestation.json` by path (never writes
to LCA). Writes a staging copy of the site to `build/site/`: this repo's static files plus one
`commodity/<slug>/ontology.json` per glossary entry. Everything here is derived from Jenks's
transcriptions, so it stays in `build/` (git-ignored) until the Jenks permission (task 1).

URIs follow docs/uri-policy.md: a slug is minted once per glossary key and kept in the ledger
`build/ledger/commodities.tsv`. It is never recomputed. When LCA renames a key, the ledger row
follows the rename. When a key is merged away or deleted, its slug gets a deprecation record,
not a 404. The ledger stays in build/ until first publication: until something is published,
no URI has been cited, so nothing can break. From first publication it must be committed.

AAT/Wikidata mapping (PLAN.md task 12, corrections C1/C5):
  1. drop every item with id 300386154 "unidentified (information indicator)";
  2. `suggested` items (unreviewed machine proposals) are skipped;
  3. broader:true -> `broader` (wins over match:'close' on the same item, e.g. `chest`:
     "close to something broader" is still only a broader claim);
     match:'close' -> `closeMatch`; `uncertain` exact -> `closeMatch` (an uncertain identity
     is not an identity); otherwise -> `equivalent`;
  4. an entry left with no equivalent/closeMatch that carried 300386154 is
     `classified_as` aat:300386154, which marks it unidentified without claiming identity.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import sys
import unicodedata
from pathlib import Path
from urllib.parse import quote

REPO = Path(__file__).resolve().parents[2]
LCA = Path("/home/stephen/PycharmProjects/London_Customs_Accounts")
W3ID = "https://w3id.org/hector/"
MLCA = "https://w3id.org/mlca/glossary/"
CONTEXT = ["https://linked.art/ns/v1/linked-art.json", "https://w3id.org/hector/context"]

UNIDENTIFIED = "300386154"
AAT_PREFERRED = {"id": "aat:300404670", "type": "Type", "_label": "preferred terms"}
AAT_DESCRIPTION = {"id": "aat:300435416", "type": "Type", "_label": "descriptive note"}
AAT_UNIDENTIFIED = {"id": "aat:" + UNIDENTIFIED, "type": "Type",
                    "_label": "unidentified (information indicator)"}
ATTESTED = {"id": "hector:AttestedVariant", "type": "Type", "_label": "attested variant"}

# Files of this repo copied into the staging site (what is served besides the export)
STATIC = ["context", "ontology", "unit", "commodity", "shapes", "tools/contexts", "index.html",
          "css", "js"]

LEDGER_FIELDS = ["slug", "glossary_key", "minted", "status", "replaced_by", "content_sha256",
                 "modified"]


# --------------------------------------------------------------------------- slugs & ledger

def slugify(key: str) -> str:
    s = unicodedata.normalize("NFKD", key)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("þ", "th").replace("ð", "th").replace("æ", "ae").replace("œ", "oe")
    s = re.sub(r"[’'`‘ʼ]", "", s)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


def load_ledger(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


def save_ledger(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, LEDGER_FIELDS, delimiter="\t", lineterminator="\n")
        w.writeheader()
        for r in sorted(rows, key=lambda r: r["slug"]):
            w.writerow({k: r.get(k, "") for k in LEDGER_FIELDS})


def history(meta: dict) -> tuple[dict, dict, set]:
    """LCA's rekey/merge/deletion history as {old: new}, {merged: primary}, {deleted}.

    LCA writes two record shapes (both seen 2026-09-18): {timestamp, old_key, new_key} /
    {when, from, to} for rekeys; {timestamp, primary, merged: [...]} / {when, from, into} for
    merges; {timestamp, key, ...} / {when, key, reason} for deletions. Records are applied in
    time order, so a later rename of the same key wins.
    """
    def when(r):
        return r.get("timestamp") or r.get("when") or ""

    rekeys, merged_into, deleted = {}, {}, set()
    for r in sorted(meta.get("rekey_history", []), key=when):
        old, new = r.get("old_key", r.get("from")), r.get("new_key", r.get("to"))
        if old and new:
            rekeys[old] = new
    for r in sorted(meta.get("merge_history", []), key=when):
        if "primary" in r:
            for k in r.get("merged", []):
                merged_into[k] = r["primary"]
        elif r.get("from") and r.get("into"):
            merged_into[r["from"]] = r["into"]
    for r in meta.get("deletion_history", []):
        if r.get("key"):
            deleted.add(r["key"])
    return rekeys, merged_into, deleted


def successor(key: str, meta: dict, entries: dict) -> tuple[str, str | None]:
    """Follow LCA's history for a key that has left the glossary.

    Returns (kind, new_key): ('rekey', k) if renamed to a live key k; ('merge', k) if merged
    into live key k; ('delete', None) if deleted; ('missing', None) if there is no record.
    """
    rekeys, merged_into, deleted = history(meta)

    kind, k, seen = None, key, set()
    while k not in entries and k not in seen:
        seen.add(k)
        if k in rekeys:
            kind = kind or "rekey"
            k = rekeys[k]
        elif k in merged_into:
            kind = "merge"
            k = merged_into[k]
        elif k in deleted:
            return "delete", None
        else:
            return "missing", None
    return (kind or "rekey", k) if k in entries else ("missing", None)


def reconcile(ledger: list[dict], entries: dict, meta: dict, today: str, report: dict) -> dict[str, dict]:
    """Bring the ledger up to date with the glossary. Returns {glossary_key: row} for live keys."""
    by_key = {r["glossary_key"]: r for r in ledger if r["status"] == "active"}
    slugs = {r["slug"] for r in ledger}

    # 1. keys that have left the glossary
    for key, row in list(by_key.items()):
        if key in entries:
            continue
        kind, new = successor(key, meta, entries)
        if kind == "rekey" and new not in by_key:
            row["glossary_key"] = new
            by_key[new] = row
            report["rekeyed"].append(f"{key} -> {new} (slug {row['slug']} kept)")
        elif kind in ("rekey", "merge"):
            row["status"] = "deprecated"
            row["replaced_by"] = ""  # filled below, once the survivor has a slug
            row["_successor"] = new
            report["deprecated"].append(f"{key} -> merged into {new}")
        elif kind == "delete":
            row["status"] = "deleted"
            report["deprecated"].append(f"{key} -> deleted in LCA")
        else:
            report["missing"].append(key)  # left alone, still active: needs a human
            continue
        del by_key[key]

    # 2. mint slugs for new keys (sorted, so a first run is deterministic)
    for key in sorted(entries):
        if key in by_key:
            continue
        base = slugify(key)
        slug, n = base, 2
        while slug in slugs:
            slug, n = f"{base}-{n}", n + 1
        row = {"slug": slug, "glossary_key": key, "minted": today, "status": "active",
               "replaced_by": "", "content_sha256": "", "modified": ""}
        ledger.append(row)
        by_key[key] = row
        slugs.add(slug)
        if slug != base:
            report["slug_collisions"].append(f"{key!r} -> {slug}")

    for row in ledger:
        if row.get("_successor"):
            row["replaced_by"] = by_key[row.pop("_successor")]["slug"]
    return by_key


# --------------------------------------------------------------------------- records

def uri(slug: str) -> str:
    return f"{W3ID}commodity/{slug}"


def authority(item: dict) -> str:
    return ("wd:" if item.get("source") == "wikidata" else "aat:") + str(item["id"])


def map_identifiers(aat: list[dict], report: dict, key: str) -> dict[str, list[dict]]:
    out = collections.defaultdict(list)
    had_unidentified = False
    for it in aat:
        if str(it.get("id")) == UNIDENTIFIED:
            had_unidentified = True
            continue
        if it.get("suggested"):
            report["skipped_suggested"].append(key)
            continue
        ref = {"id": authority(it), "type": "Type", "_label": it.get("label") or str(it["id"])}
        if it.get("broader"):
            out["broader"].append(ref)
        elif it.get("match") == "close" or it.get("uncertain"):
            out["closeMatch"].append(ref)
        else:
            out["equivalent"].append(ref)
    # one IRI, one role: identity outranks match outranks broader
    seen = set()
    for role in ("equivalent", "closeMatch", "broader"):
        kept = []
        for r in out[role]:
            if r["id"] in seen:
                report["duplicate_identifier"].append(f"{key}: {r['id']} dropped from {role}")
                continue
            seen.add(r["id"])
            kept.append(r)
        out[role] = kept
    if had_unidentified and not out["equivalent"] and not out["closeMatch"]:
        out["classified_as"].append(AAT_UNIDENTIFIED)
    return {k: v for k, v in out.items() if v}


def names(key: str, entry: dict, sources: list[dict]) -> list[dict]:
    def span(src_ids):
        years = [(sources[i].get("date_from"), sources[i].get("date_to")) for i in src_ids
                 if 0 <= i < len(sources)]
        froms = [a for a, _ in years if a]
        tos = [b for _, b in years if b]
        return (min(froms) if froms else None), (max(tos) if tos else None)

    by_text: dict[str, set] = collections.OrderedDict()
    for f in entry.get("f", []):
        by_text.setdefault(f["t"], set()).update(f.get("s") or [])
    out = []
    if key not in by_text:
        out.append({"type": "Name", "content": key, "classified_as": [AAT_PREFERRED]})
    for text, srcs in by_text.items():
        n = {"type": "Name", "content": text,
             "classified_as": [AAT_PREFERRED, ATTESTED] if text == key else [ATTESTED]}
        a, b = span(sorted(srcs))
        if a:
            n["validFrom"] = f"{a:04d}"
        if b:
            n["validThrough"] = f"{b:04d}"
        out.append(n)
    return out


def links(keys, by_key: dict, key: str, field: str, report: dict) -> list[dict]:
    out = []
    for k in keys or []:
        row = by_key.get(k)
        if row is None:
            report["dangling_link"].append(f"{key}: {field} -> {k!r} (not in glossary)")
            continue
        out.append({"id": uri(row["slug"]), "type": "Type", "_label": k})
    return out


def origin_places(geo, key: str, report: dict) -> list[dict]:
    items = geo if isinstance(geo, list) else [geo] if geo else []
    out = []
    for g in items:
        m = re.fullmatch(r"(?:(?:whg:place:)?wd:)?(Q[1-9]\d*)", str(g.get("id", "")))
        if m:
            out.append({"id": "wd:" + m.group(1), "type": "Place", "_label": g.get("label") or m.group(1)})
        else:
            # only CC0 Wikidata places; anything else (GeoNames needs its licence recorded,
            # OSM/OHM are ODbL and barred, CLAUDE.md §6) is left out and reported
            report["geo_skipped"].append(f"{key}: {g.get('id')}")
    return out


def record(key: str, entry: dict, row: dict, by_key: dict, attest: dict, sources: list, report: dict) -> dict:
    doc = {"@context": CONTEXT, "id": uri(row["slug"]), "type": "Type", "_label": key}
    if entry.get("d"):
        doc["referred_to_by"] = [{"type": "LinguisticObject", "classified_as": [AAT_DESCRIPTION],
                                  "content": entry["d"]}]
    doc["identified_by"] = names(key, entry, sources)
    doc.update(map_identifiers(entry.get("aat") or [], report, key))
    doc["exactMatch"] = [{"id": MLCA + quote(key, safe=""), "type": "Type",
                          "_label": f"{key} (London Customs Accounts glossary)"}]
    if entry.get("materials"):
        doc["material"] = [{"id": "aat:" + str(m["id"]), "type": "Material", "_label": m.get("label") or str(m["id"])}
                           for m in entry["materials"]]
    places = origin_places(entry.get("geo"), key, report)
    if places:
        doc["originPlace"] = places
    for field, prop in (("compoundOf", "compoundOf"), ("related", "related"), ("x", "seeAlso")):
        ls = links(entry.get(field), by_key, key, field, report)
        if ls:
            doc[prop] = ls
    if key in attest:
        doc["attestationCount"] = int(attest[key])
    return doc


def deprecation(row: dict, today: str) -> dict:
    doc = {"@context": CONTEXT, "id": uri(row["slug"]), "type": "Type",
           "_label": row["glossary_key"], "deprecated": True, "modified": row.get("modified") or today}
    if row.get("replaced_by"):
        doc["isReplacedBy"] = {"id": uri(row["replaced_by"]), "type": "Type"}
    return doc


def content_hash(doc: dict) -> str:
    d = {k: v for k, v in doc.items() if k != "modified"}
    return hashlib.sha256(json.dumps(d, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# --------------------------------------------------------------------------- main

def export(lca: Path, out_site: Path, ledger_path: Path, today: str | None = None) -> dict:
    today = today or dt.date.today().isoformat()
    g = json.loads((lca / "docs/data/glossary_data.json").read_text(encoding="utf-8"))
    attest_path = lca / "docs/data/concept_attestation.json"
    attest = json.loads(attest_path.read_text(encoding="utf-8")) if attest_path.exists() else {}
    entries, meta = g["entries"], g["metadata"]
    sources = meta.get("source_registry", {}).get("sources", [])

    report = collections.defaultdict(list)
    ledger = load_ledger(ledger_path)
    by_key = reconcile(ledger, entries, meta, today, report)

    if out_site.exists():
        shutil.rmtree(out_site)
    for rel in STATIC:
        src = REPO / rel
        if src.is_dir():
            shutil.copytree(src, out_site / rel)
        elif src.exists():
            (out_site / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, out_site / rel)

    counts = collections.Counter()
    for row in ledger:
        key = row["glossary_key"]
        if row["status"] == "active" and key in entries:
            doc = record(key, entries[key], row, by_key, attest, sources, report)
            counts["commodity"] += 1
            for role in ("equivalent", "closeMatch", "broader", "classified_as"):
                if doc.get(role):
                    counts[f"with {role}"] += 1
        elif row["status"] in ("deprecated", "deleted"):
            doc = deprecation(row, today)
            counts["deprecation record"] += 1
        else:
            continue
        h = content_hash(doc)
        if h != row.get("content_sha256"):
            row["content_sha256"], row["modified"] = h, today
        doc["modified"] = row["modified"]
        path = out_site / "commodity" / row["slug"] / "ontology.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save_ledger(ledger_path, ledger)
    report["counts"] = dict(counts)
    return report


def write_report(report: dict, path: Path, glossary: Path):
    c = report["counts"]
    lines = ["# HECTOR commodity export report", "",
             f"Source: `{glossary}`. **Derived from Jenks's transcriptions: local only, do not "
             "commit or publish** (PLAN.md task 1).", "", "| | count |", "|---|---:|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(c.items())]
    for section, title in [("missing", "Ledger keys with no LCA history (left active; need a human)"),
                           ("rekeyed", "Keys renamed in LCA (slug kept)"),
                           ("deprecated", "Deprecated slugs"),
                           ("slug_collisions", "Slug collisions (suffixed)"),
                           ("duplicate_identifier", "Identifier given twice (lower role dropped)"),
                           ("dangling_link", "Links to keys not in the glossary (dropped)"),
                           ("geo_skipped", "Places left out (not a Wikidata id)"),
                           ("skipped_suggested", "Unreviewed suggested identifiers (skipped)")]:
        items = report.get(section) or []
        lines += ["", f"## {title}: {len(items)}", ""] + [f"- {x}" for x in items[:200]]
        if len(items) > 200:
            lines.append(f"- … and {len(items) - 200} more")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--lca", type=Path, default=LCA)
    ap.add_argument("--site", type=Path, default=REPO / "build" / "site")
    ap.add_argument("--ledger", type=Path, default=REPO / "build" / "ledger" / "commodities.tsv")
    ap.add_argument("--report", type=Path, default=REPO / "build" / "export-report.md")
    a = ap.parse_args(argv)
    report = export(a.lca, a.site, a.ledger)
    write_report(report, a.report, a.lca / "docs/data/glossary_data.json")
    print(json.dumps(report["counts"]), f"-> {a.site}; report {a.report}; ledger {a.ledger}")
    return 1 if report.get("missing") else 0


if __name__ == "__main__":
    sys.exit(main())
