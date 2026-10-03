#!/usr/bin/env python3
"""Write Turtle and RDF/XML beside every JSON-LD record: <dir>/ontology.ttl and <dir>/ontology.rdf.

    .venv/bin/python -m tools.site.build_rdf                  # build/site/ (after link_rates)
    .venv/bin/python -m tools.site.build_rdf --root .         # the published repo
    .venv/bin/python -m tools.site.build_rdf --check          # stale or missing files? (exit 1)

Each graph is made exactly as tools/validate.py makes it (the same local copies of the HECTOR and
Linked Art contexts, so nothing is fetched), then serialised; every file is re-parsed and must give
the same number of triples as the JSON-LD, or the run fails. Blank nodes are canonicalised, so the Turtle
of an unchanged record is byte-identical; RDF/XML is compared as a graph (its bytes follow the
Python version), and a file is rewritten only when its graph changes. Also writes dump/hector.ttl.gz, every
record in one file. The JSON-LD stays the source: rebuild these whenever the records change (part
of the republish steps in PLAN.md).
"""
import argparse
import gzip
import json
import sys
from pathlib import Path

import re

from rdflib import BNode, Graph
from rdflib.compare import isomorphic, to_canonical_graph

from tools import validate as V

REPO = Path(__file__).resolve().parents[2]
PREFIXES = {
    "crm": "http://www.cidoc-crm.org/cidoc-crm/", "la": "https://linked.art/ns/terms/",
    "skos": "http://www.w3.org/2004/02/skos/core#", "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "owl": "http://www.w3.org/2002/07/owl#", "dcterms": "http://purl.org/dc/terms/",
    "xsd": "http://www.w3.org/2001/XMLSchema#", "schema": "http://schema.org/",
    "aat": "http://vocab.getty.edu/aat/", "wd": "http://www.wikidata.org/entity/",
    "qudtunit": "http://qudt.org/vocab/unit/", "quantitykind": "http://qudt.org/vocab/quantitykind/",
    "hector": "https://w3id.org/hector/ontology#", "hectorid": "https://w3id.org/hector/",
}


def graph_for(doc_path: Path) -> Graph:
    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    raw = V.to_graph(V.jsonld.expand(doc, {"base": V.entity_uri(doc_path)}))
    # Canonical blank-node labels, so a rebuild is byte-identical (rdflib's are random per run),
    # prefixed with the record's path so that no two records share one: canonical labels alone
    # repeat from record to record, and merged into the dump they fused (228,115 -> 188,628).
    tag = re.sub(r"[^A-Za-z0-9]", "_", doc_path.resolve().parent.relative_to(V.ROOT).as_posix())
    rename = lambda n: BNode(f"{tag}_{n}") if isinstance(n, BNode) else n
    g = Graph()
    for t in sorted(tuple(rename(x) for x in t) for t in to_canonical_graph(raw)):   # sorted: stable RDF/XML
        g.add(t)
    for p, ns in PREFIXES.items():
        g.bind(p, ns, override=True)
    return g


def documents(root: Path):
    yield from sorted(root.glob("commodity/*/ontology.json"))
    yield from sorted(root.glob("unit/**/ontology.json"))
    if (root / "ontology" / "ontology.json").exists():
        yield root / "ontology" / "ontology.json"


def build(root: Path, check: bool) -> int:
    V.set_root(root)
    problems, written, dump = [], 0, Graph()
    for p, ns in PREFIXES.items():
        dump.bind(p, ns, override=True)
    for doc in documents(root):
        g = graph_for(doc)
        dump += g
        for fmt, name in (("turtle", "ontology.ttl"), ("xml", "ontology.rdf")):
            text = g.serialize(format=fmt)
            back = Graph().parse(data=text, format=fmt)
            if len(back) != len(g):
                problems.append(f"{doc.parent.relative_to(root)}/{name}: {len(back)} triples, JSON-LD has {len(g)}")
                continue
            out = doc.parent / name
            if fmt == "xml":
                # rdflib's RDF/XML writer orders subjects through a set, so its bytes vary with the
                # Python version's string hashing (3.10 here, 3.12 in CI): compare graphs, not bytes,
                # and rewrite only when the graph has changed, so a republish does not churn every .rdf
                current = out.exists() and isomorphic(Graph().parse(out, format="xml"), back)
            else:
                current = out.exists() and out.read_text(encoding="utf-8") == text
            if check:
                if not current:
                    problems.append(f"{out.relative_to(root)}: missing or stale")
            elif not current:
                out.write_text(text, encoding="utf-8")
                written += 1
    out = root / "dump" / "hector.ttl.gz"
    if not check:
        out.parent.mkdir(parents=True, exist_ok=True)
        with gzip.GzipFile(out, "wb", mtime=0) as fh:
            fh.write(dump.serialize(format="turtle").encode("utf-8"))
    for p in problems[:20]:
        print("PROBLEM", p, file=sys.stderr)
    print(f"{written} files written; {len(dump):,} triples in the dump; {len(problems)} problems")
    return 1 if problems else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", type=Path, default=REPO / "build" / "site")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    sys.exit(build(a.root.resolve(), a.check))


if __name__ == "__main__":
    main()
