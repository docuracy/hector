#!/usr/bin/env python3
"""Validate HECTOR's JSON-LD: the context, the vocabulary and every entity document.

PLAN.md task 21. Run from the repo root:

    .venv/bin/python tools/validate.py            # offline checks
    .venv/bin/python tools/validate.py --online   # also dereference AAT / Wikidata / QUDT ids
    .venv/bin/python tools/validate.py path/to/ontology.json ...   # specific files

Exit status is 1 if any ERROR is reported, else 0. WARNINGs do not fail the run.

Remote contexts are never fetched: HECTOR's own context URLs resolve to
`context/hector.jsonld` in this checkout, and the Linked Art context to the copy vendored in
`tools/contexts/linked-art.json` (fetched from https://linked.art/ns/v1/linked-art.json on
2026-09-18, sha256 3017421203aba8ea...). Any other remote context is an error, so a run is
deterministic and tests the files in the working tree, not whatever is live.

Checks (codes appear in the output):
  JSON-PARSE            file is not JSON
  JSONLD                a conforming processor (PyLD) rejects the document or its context
  RELATIVE-IRI          an IRI that only resolves against the document's own URL
                        (e.g. a bare "modern_lemma" in an @id-typed term)
  UNKNOWN-NAMESPACE     a predicate or class outside the known vocabularies (catches made-up
                        namespaces such as the old http://linked.art/ns/v1/)
  UNDEFINED-TERM        a hector: predicate, class or concept not declared in the vocabulary
                        document (ontology/ontology.json)
  EXTERNAL-IRI-FORM     a malformed authority IRI: Wikidata page URL instead of entity URI,
                        AAT id not 9 digits, GeoNames id without trailing slash, placeholder hosts
  EXTERNAL-UNLABELLED   an external reference with no rdfs:label (_label) in the document, so
                        no human or --online check can tell whether it is the right one
  UNIDENTIFIED-IDENTITY AAT 300386154 "unidentified (information indicator)" used as an
                        identity or match (equivalent / sameAs / exactMatch / closeMatch)
  IDENTITY-CLASS        the same IRI is both an identity/match and a class/broader of one node
  KIND                  document shape wrong for its path (commodity/, unit/<dim>/, unit/<dim>/<u>)
  SHACL                 violations of shapes/hector.shacl.ttl on the expanded graph
  ENTITY-URI            (WARNING until decision D3; ERROR with --strict-uris) the document's
                        subject is not https://w3id.org/hector/<its path>, so it cannot
                        dereference to this file
  ONLINE-NOTFOUND       (--online) the authority returns 404 for the id
  ONLINE-LABEL          (--online) the document's _label matches none of the authority's labels
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from pyld import jsonld
from rdflib import BNode, Graph, Literal, Namespace, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

ROOT = Path(__file__).resolve().parent.parent
CONTEXT_FILE = ROOT / "context" / "hector.jsonld"
VOCAB_FILE = ROOT / "ontology" / "ontology.json"
SHAPES_FILE = ROOT / "shapes" / "hector.shacl.ttl"
LINKED_ART_FILE = ROOT / "tools" / "contexts" / "linked-art.json"
CACHE_FILE = ROOT / "build" / "validate-online-cache.json"

W3ID = "https://w3id.org/hector/"
HECTOR_NAMESPACES = ("https://w3id.org/hector#", "https://w3id.org/hector/ontology#")

LOCAL_CONTEXTS: dict[str, Path] = {}


def set_root(root: Path):
    """Point the validator at a checkout (the tests use temporary copies of the repo)."""
    global ROOT, CONTEXT_FILE, VOCAB_FILE, SHAPES_FILE, LINKED_ART_FILE, CACHE_FILE
    ROOT = Path(root).resolve()
    CONTEXT_FILE = ROOT / "context" / "hector.jsonld"
    VOCAB_FILE = ROOT / "ontology" / "ontology.json"
    SHAPES_FILE = ROOT / "shapes" / "hector.shacl.ttl"
    LINKED_ART_FILE = ROOT / "tools" / "contexts" / "linked-art.json"
    CACHE_FILE = ROOT / "build" / "validate-online-cache.json"
    LOCAL_CONTEXTS.clear()
    LOCAL_CONTEXTS.update({
        "https://w3id.org/hector/context": CONTEXT_FILE,
        "https://w3id.org/hector/context/": CONTEXT_FILE,
        "https://docuracy.github.io/hector/context/hector.jsonld": CONTEXT_FILE,
        "https://linked.art/ns/v1/linked-art.json": LINKED_ART_FILE,
    })
    # PyLD caches resolved contexts by URL; a new root must not be served the old ones
    jsonld._resolved_context_cache.clear()

# Namespaces a predicate or class may come from.
KNOWN_NAMESPACES = (
    *HECTOR_NAMESPACES,
    "http://www.cidoc-crm.org/cidoc-crm/",
    "https://linked.art/ns/terms/",
    "http://www.w3.org/2004/02/skos/core#",
    "http://www.w3.org/2000/01/rdf-schema#",
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "http://www.w3.org/2002/07/owl#",
    "http://purl.org/dc/terms/",
    "http://schema.org/",
    "https://schema.org/",
    "http://qudt.org/schema/qudt/",
)

CRM = Namespace("http://www.cidoc-crm.org/cidoc-crm/")
LA = Namespace("https://linked.art/ns/terms/")
SCHEMA = Namespace("http://schema.org/")
UNIDENTIFIED = URIRef("http://vocab.getty.edu/aat/300386154")

IDENTITY_PREDICATES = {
    LA.equivalent, OWL.sameAs, SCHEMA.sameAs, URIRef("https://schema.org/sameAs"),
    SKOS.exactMatch, SKOS.closeMatch,
}
CLASS_PREDICATES = {CRM.P2_has_type, SKOS.broader, RDF.type}

EXTERNAL_PATTERNS = {
    # host marker: regex the whole IRI must match
    "wikidata.org": re.compile(r"^http://www\.wikidata\.org/entity/Q[1-9]\d*$"),
    "vocab.getty.edu/aat": re.compile(r"^http://vocab\.getty\.edu/aat/3\d{8}$"),
    "geonames.org": re.compile(r"^https://sws\.geonames\.org/[1-9]\d*/$"),
    "qudt.org/vocab": re.compile(r"^http://qudt\.org/vocab/(unit|quantitykind)/[A-Za-z0-9_-]+$"),
    "lexvo.org": re.compile(r"^http://lexvo\.org/id/(iso639-3|term/[a-z]{3})/[^/]+$"),
}
PLACEHOLDER_HOSTS = ("example.org", "example.com", "museum.org", "finds.org.uk/images/")


@dataclass
class Issue:
    path: str
    level: str  # ERROR | WARNING
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.level:7} {self.code:22} {self.path}: {self.message}"


# --------------------------------------------------------------------------- JSON-LD plumbing

def document_loader(url, options=None):
    target = LOCAL_CONTEXTS.get(url)
    if target is None:
        raise jsonld.JsonLdError(
            f"remote document {url!r} is not mapped to a local file; the validator does not "
            "fetch contexts from the network", "jsonld.LoadDocumentError",
            code="loading document failed")
    return {"contentType": "application/ld+json", "contextUrl": None, "documentUrl": url,
            "document": json.loads(target.read_text(encoding="utf-8"))}


jsonld.set_document_loader(document_loader)
set_root(ROOT)


def root_cause(exc: BaseException) -> str:
    msgs = []
    while exc is not None:
        m = getattr(exc, "message", None) or str(exc).split("\n")[0]
        msgs.append(str(m))
        exc = getattr(exc, "cause", None)
    return msgs[-1] if msgs else "unknown error"


def entity_uri(path: Path) -> str | None:
    """https://w3id.org/hector/<dir> for <dir>/ontology.json, per the w3id redirect."""
    try:
        rel = path.resolve().relative_to(ROOT)
    except ValueError:
        return None
    if rel.name != "ontology.json":
        return None
    return W3ID + rel.parent.as_posix()


def walk_iris(node, found: list[str]):
    """Every IRI in an expanded document: @id, @type and @vocab-typed values."""
    if isinstance(node, list):
        for n in node:
            walk_iris(n, found)
    elif isinstance(node, dict):
        for k, v in node.items():
            if k == "@id" and isinstance(v, str):
                found.append(v)
            elif k == "@type" and "@value" not in node:
                found.extend(v if isinstance(v, list) else [v])
            elif not k.startswith("@"):
                found.append(k)
                walk_iris(v, found)
            elif k in ("@list", "@set", "@graph", "@reverse"):
                walk_iris(v, found)


def to_graph(expanded) -> Graph:
    nquads = jsonld.to_rdf(expanded, {"format": "application/n-quads"})
    g = Graph()
    g.parse(data=nquads, format="nt")
    # nquads parsing puts triples in named graphs of a Dataset-like store; flatten
    flat = Graph()
    for t in g:
        flat.add(t)
    return flat


# --------------------------------------------------------------------------- vocabulary

def load_vocabulary(issues: list[Issue]) -> set[str] | None:
    """IRIs declared in ontology/ontology.json (classes, properties, concepts)."""
    if not VOCAB_FILE.exists():
        issues.append(Issue(rel(VOCAB_FILE), "ERROR", "UNDEFINED-TERM",
                            "no vocabulary document; hector: terms are declared nowhere"))
        return None
    try:
        doc = json.loads(VOCAB_FILE.read_text(encoding="utf-8"))
        g = to_graph(jsonld.expand(doc, {"base": entity_uri(VOCAB_FILE)}))
    except Exception as e:  # reported again, with detail, when the file itself is validated
        issues.append(Issue(rel(VOCAB_FILE), "ERROR", "JSONLD", f"vocabulary unusable: {root_cause(e)}"))
        return None
    declared = set()
    for cls in (RDF.Property, OWL.ObjectProperty, OWL.DatatypeProperty, RDFS.Class, OWL.Class,
                SKOS.Concept, CRM.E55_Type):
        declared.update(str(s) for s in g.subjects(RDF.type, cls) if isinstance(s, URIRef))
    return declared


# --------------------------------------------------------------------------- checks

def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def is_hector(iri: str) -> bool:
    return iri.startswith(HECTOR_NAMESPACES)


def is_external(iri: str) -> bool:
    return any(h in iri for h in EXTERNAL_PATTERNS) or any(h in iri for h in PLACEHOLDER_HOSTS)


def check_context(issues: list[Issue]):
    p = rel(CONTEXT_FILE)
    try:
        ctx = json.loads(CONTEXT_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        issues.append(Issue(p, "ERROR", "JSON-PARSE", str(e)))
        return
    try:
        jsonld.expand({"@context": ctx["@context"], "@id": "urn:x", "urn:p": "x"})
    except Exception as e:
        issues.append(Issue(p, "ERROR", "JSONLD", root_cause(e)))


def check_document(path: Path, vocab: set[str] | None, strict_uris: bool) -> tuple[list[Issue], Graph | None]:
    issues: list[Issue] = []
    p = rel(path)
    add = lambda level, code, msg: issues.append(Issue(p, level, code, msg))
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        add("ERROR", "JSON-PARSE", str(e))
        return issues, None

    own = entity_uri(path) or ("file://" + str(path.resolve()))
    try:
        expanded = jsonld.expand(doc, {"base": own})
    except Exception as e:
        add("ERROR", "JSONLD", root_cause(e))
        return issues, None

    # Relative IRIs: expand again against a sentinel base; anything carrying it was relative.
    sentinel = "http://relative-iri.invalid/"
    iris: list[str] = []
    walk_iris(jsonld.expand(doc, {"base": sentinel + "x/y"}), iris)
    for iri in sorted(set(i for i in iris if i.startswith(sentinel))):
        add("ERROR", "RELATIVE-IRI", f"{iri[len(sentinel):]!r} is a relative IRI (resolves to "
            f"{own.rsplit('/', 1)[0]}/{iri[len(sentinel):].split('/')[-1]})")

    g = to_graph(expanded)

    # Namespaces of predicates and classes
    for pred in sorted(set(map(str, g.predicates()))):
        if not pred.startswith(KNOWN_NAMESPACES):
            add("ERROR", "UNKNOWN-NAMESPACE", f"predicate <{pred}>")
    for cls in sorted(set(str(o) for o in g.objects(None, RDF.type))):
        if not cls.startswith(KNOWN_NAMESPACES):
            add("ERROR", "UNKNOWN-NAMESPACE", f"class <{cls}>")

    # hector: terms must be declared in the vocabulary (the vocabulary itself declares them)
    if vocab is not None and path.resolve() != VOCAB_FILE.resolve():
        used = set(map(str, g.predicates())) | set(str(o) for o in g.objects(None, RDF.type))
        used |= {str(o) for o in g.objects() if isinstance(o, URIRef) and is_hector(str(o))
                 and "#" in str(o) and "/" not in str(o).split("#", 1)[1]}
        for term in sorted(t for t in used if is_hector(t) and t not in vocab):
            add("ERROR", "UNDEFINED-TERM", f"<{term}> is not declared in {rel(VOCAB_FILE)}")

    # External references: well-formed, not placeholders, labelled
    for o in sorted(set(x for x in g.all_nodes() if isinstance(x, URIRef)), key=str):
        s = str(o)
        if any(h in s for h in PLACEHOLDER_HOSTS):
            add("ERROR", "EXTERNAL-IRI-FORM", f"<{s}> is a placeholder / fictional host")
            continue
        for marker, rx in EXTERNAL_PATTERNS.items():
            if marker in s and not rx.match(s):
                add("ERROR", "EXTERNAL-IRI-FORM", f"<{s}> does not match {rx.pattern}")
        if is_external(s) and (None, None, o) in g and not any(True for _ in g.objects(o, RDFS.label)):
            add("ERROR", "EXTERNAL-UNLABELLED", f"<{s}> has no _label / rdfs:label in the document")

    # AAT "unidentified" is never an identity; identity and class must not coincide
    for s_, p_, o_ in g.triples((None, None, UNIDENTIFIED)):
        if p_ in IDENTITY_PREDICATES:
            add("ERROR", "UNIDENTIFIED-IDENTITY", f"{p_.n3(g.namespace_manager)} aat:300386154")
    for subj in set(g.subjects()):
        ident = {o for p_ in IDENTITY_PREDICATES for o in g.objects(subj, p_)}
        klass = {o for p_ in CLASS_PREDICATES for o in g.objects(subj, p_)}
        for both in sorted(ident & klass, key=str):
            add("ERROR", "IDENTITY-CLASS", f"<{both}> is both an identity/match and a class/broader")

    if path.resolve() == VOCAB_FILE.resolve():
        check_vocabulary(g, add)
        return issues, g

    # Subject URI and kind
    subjects = top_subjects(expanded)
    if len(subjects) != 1:
        add("ERROR", "KIND", f"expected exactly one top-level entity, found {len(subjects)}")
    else:
        subj = subjects[0]
        if entity_uri(path) and subj != entity_uri(path):
            add("ERROR" if strict_uris else "WARNING", "ENTITY-URI",
                f"subject is <{subj}>, which does not dereference to this file "
                f"(expected <{entity_uri(path)}>; see PLAN.md F2/D3)")
        check_kind(path, g, URIRef(subj), add)

    return issues, g


def top_subjects(expanded) -> list[str]:
    return [n.get("@id", "_:blank") for n in expanded]


def check_vocabulary(g: Graph, add):
    """The vocabulary declares an owl:Ontology and documents every hector: term it declares."""
    if not any(True for _ in g.subjects(RDF.type, OWL.Ontology)):
        add("ERROR", "KIND", "the vocabulary document declares no owl:Ontology")
    terms = {s for s in g.subjects(RDF.type, None) if isinstance(s, URIRef) and is_hector(str(s))}
    if not terms:
        add("ERROR", "KIND", "the vocabulary document declares no hector: terms")
    for t in sorted(terms, key=str):
        if not any(True for _ in g.objects(t, RDFS.label)) or not any(True for _ in g.objects(t, RDFS.comment)):
            add("ERROR", "KIND", f"<{t}> needs both a _label and an rdfs:comment")


def check_kind(path: Path, g: Graph, subj: URIRef, add):
    try:
        parts = path.resolve().relative_to(ROOT).parts[:-1]
    except ValueError:
        return
    types = set(g.objects(subj, RDF.type))
    labels = list(g.objects(subj, RDFS.label))
    if not labels:
        add("ERROR", "KIND", "entity has no _label / rdfs:label")
    if parts[:1] == ("commodity",):
        if CRM.E55_Type not in types:
            add("ERROR", "KIND", "a commodity must be a Linked Art Type (crm:E55_Type)")
        names = [n for n in g.objects(subj, CRM.P1_is_identified_by)
                 if (n, RDF.type, CRM.E33_E41_Linguistic_Appellation) in g]
        if not names:
            add("ERROR", "KIND", "a commodity needs at least one Name in identified_by")
        preferred = [n for n in names if (n, CRM.P2_has_type, URIRef("http://vocab.getty.edu/aat/300404670")) in g]
        if names and len(preferred) != 1:
            add("ERROR", "KIND", f"a commodity needs exactly one Name classified as preferred "
                f"term (aat:300404670), found {len(preferred)}")
    elif parts[:1] == ("unit",) and len(parts) == 2:
        if CRM.E58_Measurement_Unit in types or CRM.E55_Type not in types:
            add("ERROR", "KIND", f"unit/{parts[1]} is a dimension: it must be a Type (crm:E55_Type), "
                "not a MeasurementUnit")
    elif parts[:1] == ("unit",) and len(parts) >= 3:
        if CRM.E58_Measurement_Unit not in types:
            add("ERROR", "KIND", "a unit must be a Linked Art MeasurementUnit (crm:E58_Measurement_Unit)")


def run_shacl(path: Path, g: Graph) -> list[Issue]:
    if not SHAPES_FILE.exists():
        return [Issue(rel(SHAPES_FILE), "ERROR", "SHACL", "shapes file missing")]
    from pyshacl import validate
    shapes = Graph().parse(SHAPES_FILE, format="turtle")
    conforms, results, _ = validate(g, shacl_graph=shapes, inference="none", allow_warnings=True)
    out = []
    if not conforms:
        SH = Namespace("http://www.w3.org/ns/shacl#")
        for r in results.subjects(RDF.type, SH.ValidationResult):
            sev = results.value(r, SH.resultSeverity)
            msg = results.value(r, SH.resultMessage)
            focus = results.value(r, SH.focusNode)
            level = "WARNING" if sev == SH.Warning else "ERROR"
            focus_s = focus.n3() if not isinstance(focus, BNode) else "(blank node)"
            out.append(Issue(rel(path), level, "SHACL", f"{focus_s}: {msg}"))
    return out


# --------------------------------------------------------------------------- online

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"\s*[(<].*?[)>]\s*", " ", s).strip(" <>")
    s = re.sub(r"\s+", " ", s)
    return s[:-1] if s.endswith("s") and len(s) > 3 else s


def authority_labels(iri: str, session, cache: dict) -> tuple[int, list[str]] | None:
    if iri in cache:
        return tuple(cache[iri])
    try:
        if "vocab.getty.edu/aat/" in iri:
            aid = iri.rsplit("/", 1)[1]
            r = session.get(f"https://vocab.getty.edu/aat/{aid}.jsonld", timeout=30,
                            headers={"Accept": "application/ld+json"})
            labels = []
            if r.status_code not in (200, 404):
                # Getty's web front end refuses some networks (HTTP 403 from GitHub Actions,
                # seen 2026-09-18); its SPARQL endpoint is a second route to the same data.
                r = aat_via_sparql(aid, session)
                labels = r.labels if r.status_code == 200 else []
            elif r.status_code == 200:
                for n in r.json().get("@graph", []):
                    for key in ("http://www.w3.org/2004/02/skos/core#prefLabel",
                                "http://www.w3.org/2004/02/skos/core#altLabel",
                                "http://www.w3.org/2008/05/skos-xl#literalForm"):
                        v = n.get(key)
                        for x in (v if isinstance(v, list) else [v] if v else []):
                            labels.append(x["@value"] if isinstance(x, dict) else x)
        elif "wikidata.org/entity/" in iri:
            qid = iri.rsplit("/", 1)[1]
            r = session.get(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", timeout=30)
            labels = []
            if r.status_code == 200:
                e = next(iter(r.json()["entities"].values()))
                labels = [v["value"] for v in e.get("labels", {}).values()]
                labels += [a["value"] for al in e.get("aliases", {}).values() for a in al]
        elif "qudt.org/vocab/" in iri:
            r = session.get(iri, timeout=30, headers={"Accept": "text/turtle"})
            labels = re.findall(r'rdfs:label\s+"([^"]+)"', r.text) if r.status_code == 200 else []
        else:
            return None
    except Exception:
        return None
    cache[iri] = [r.status_code, labels]
    return r.status_code, labels


@dataclass
class _Answer:
    status_code: int
    labels: list


def aat_via_sparql(aid: str, session) -> _Answer:
    q = ("SELECT ?l WHERE { ?s dc:identifier \"%s\" ; skos:inScheme aat: . "
         "{ ?s skos:prefLabel ?l } UNION { ?s skos:altLabel ?l } }" % aid)
    r = session.get("https://vocab.getty.edu/sparql.json", params={"query": q}, timeout=60)
    if r.status_code != 200:
        return _Answer(r.status_code, [])
    labels = [b["l"]["value"] for b in r.json()["results"]["bindings"]]
    return _Answer(200 if labels else 404, labels)


def check_online(path: Path, g: Graph, session, cache: dict) -> list[Issue]:
    out = []
    for o in sorted({x for x in g.all_nodes() if isinstance(x, URIRef) and is_external(str(x))}, key=str):
        if (None, None, o) not in g:
            continue
        res = authority_labels(str(o), session, cache)
        if res is None:
            if "geonames.org" not in str(o):
                out.append(Issue(rel(path), "WARNING", "ONLINE-NOTFOUND", f"<{o}> could not be checked"))
            continue
        status, labels = res
        if status == 404:
            out.append(Issue(rel(path), "ERROR", "ONLINE-NOTFOUND", f"<{o}> does not exist (HTTP 404)"))
            continue
        if status != 200:
            out.append(Issue(rel(path), "WARNING", "ONLINE-NOTFOUND", f"<{o}> returned HTTP {status}"))
            continue
        auth = {norm(l) for l in labels}
        for lab in g.objects(o, RDFS.label):
            if norm(str(lab)) not in auth:
                out.append(Issue(rel(path), "ERROR", "ONLINE-LABEL",
                                 f"<{o}> is labelled {str(lab)!r} here, but the authority's labels "
                                 f"include none that match (e.g. {sorted(labels)[:3]})"))
    return out


# --------------------------------------------------------------------------- main

def find_documents() -> list[Path]:
    return sorted(p for p in ROOT.rglob("ontology.json")
                  if not any(part in (".venv", "build", "node_modules", "tests") for part in p.relative_to(ROOT).parts))


def validate(paths: list[Path] | None = None, online: bool = False, strict_uris: bool = False,
             shacl: bool = True) -> list[Issue]:
    issues: list[Issue] = []
    check_context(issues)
    vocab = load_vocabulary(issues)
    docs = paths or find_documents()
    if not docs:
        issues.append(Issue(".", "ERROR", "KIND", "no ontology.json documents found"))
    session = cache = None
    if online:
        import requests
        session = requests.Session()
        session.headers["User-Agent"] = "HECTOR validator (https://github.com/docuracy/hector)"
        cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    for path in docs:
        doc_issues, g = check_document(path, vocab, strict_uris)
        issues += doc_issues
        if g is not None and shacl:
            issues += run_shacl(path, g)
        if g is not None and online:
            issues += check_online(path, g, session, cache)
    if online:
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(cache, indent=1, ensure_ascii=False))
    return issues


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("paths", nargs="*", type=Path)
    ap.add_argument("--online", action="store_true", help="dereference AAT / Wikidata / QUDT ids")
    ap.add_argument("--strict-uris", action="store_true", help="ENTITY-URI is an error, not a warning")
    ap.add_argument("--no-shacl", action="store_true")
    a = ap.parse_args(argv)
    issues = validate(a.paths or None, a.online, a.strict_uris, not a.no_shacl)
    for i in issues:
        print(i)
    n_err = sum(i.level == "ERROR" for i in issues)
    n_warn = sum(i.level == "WARNING" for i in issues)
    n_docs = len(a.paths or find_documents())
    print(f"\n{n_docs} document(s): {n_err} error(s), {n_warn} warning(s)")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
