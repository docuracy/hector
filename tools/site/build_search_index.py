#!/usr/bin/env python3
"""Build the search index the landing page (index.html) reads: search/index.json.

    .venv/bin/python -m tools.site.build_search_index                  # build/site/ (after link_rates)
    .venv/bin/python -m tools.site.build_search_index --root .         # the published repo

One row per record under commodity/ and unit/:
    [path, label, kind, [other names...], deprecated]
kind: "c" commodity, "q" qualified commodity (has compoundOf), "u" unit. The names are every
attested spelling in the record's identified_by, so the page can find "nottes" under nut. It is
derived entirely from the records, so rebuild it whenever they change (it is part of the
republish steps in PLAN.md).
"""
import argparse
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def build(root: Path) -> int:
    rows = []
    for doc in sorted(list(root.glob("commodity/*/ontology.json")) + list(root.glob("unit/**/ontology.json"))):
        d = json.loads(doc.read_text(encoding="utf-8"))
        if d.get("type") not in ("Type", "MeasurementUnit"):
            continue
        path = doc.parent.relative_to(root).as_posix()
        if path.startswith("unit/dimension"):
            continue
        label = d.get("_label") or path.rsplit("/", 1)[-1]
        names = sorted({n["content"] for n in d.get("identified_by", []) if n.get("content")} - {label})
        kind = "u" if d["type"] == "MeasurementUnit" else ("q" if d.get("compoundOf") else "c")
        rows.append([path, label, kind, names, 1 if d.get("deprecated") else 0])
    out = root / "search" / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO / "build" / "site")
    a = ap.parse_args(argv)
    n = build(a.root.resolve())
    print(f"{n} records -> {a.root / 'search' / 'index.json'}")


if __name__ == "__main__":
    main()
