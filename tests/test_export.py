"""Tests for tools/export/export_hector.py (PLAN.md task 12).

The unit tests use a small invented glossary, never Jenks-derived entries. The integration test
reads the real LCA glossary at test time and is skipped when that checkout is absent.
"""
import copy
import json
from pathlib import Path

import pytest

from tools import validate as V
from tools.export import export_hector as X

REPO = Path(__file__).resolve().parent.parent
REAL_LCA = X.LCA

SOURCES = [{"name": "Account A", "date_from": 1400, "date_to": 1410},
           {"name": "Account B", "date_from": 1450, "date_to": 1455},
           {"name": "Book, undated", "date_from": None, "date_to": None}]


def entry(forms=(("widget", [0], 1),), aat=(), **kw):
    e = {"d": "an invented commodity", "f": [{"t": t, "s": s, "w": w} for t, s, w in forms],
         "aat": list(aat), "groups": []}
    e.update(kw)
    return e


def glossary(entries, **meta):
    m = {"source_registry": {"sources": SOURCES}, "rekey_history": [], "merge_history": [],
         "deletion_history": []}
    m.update(meta)
    return {"entries": entries, "metadata": m}


def run(tmp_path, g, attest=None, today="2026-01-01"):
    lca = tmp_path / "lca"
    (lca / "docs/data").mkdir(parents=True, exist_ok=True)
    (lca / "docs/data/glossary_data.json").write_text(json.dumps(g), encoding="utf-8")
    (lca / "docs/data/concept_attestation.json").write_text(json.dumps(attest or {}), encoding="utf-8")
    site, ledger = tmp_path / "site", tmp_path / "ledger.tsv"
    report = X.export(lca, site, ledger, today=today)
    return site, ledger, report


def doc(site, slug):
    return json.loads((site / "commodity" / slug / "ontology.json").read_text(encoding="utf-8"))


def ledger_rows(path):
    return {r["slug"]: r for r in X.load_ledger(path)}


@pytest.fixture(autouse=True)
def _restore_root():
    yield
    V.set_root(REPO)


# ------------------------------------------------------------------ slugs

@pytest.mark.parametrize("key,slug", [
    ("canvas", "canvas"), ("bay oil", "bay-oil"), ("gad’jet", "gadjet"),
    ("widgetry lath_2", "widgetry-lath-2"), ("Éstaing", "estaing"), ("þred", "thred"), ("—", "x"),
])
def test_slugify(key, slug):
    assert X.slugify(key) == slug


def test_slug_collisions_are_suffixed_not_merged(tmp_path):
    site, ledger, report = run(tmp_path, glossary({"a b": entry(), "a-b": entry()}))
    rows = X.load_ledger(ledger)
    assert sorted(r["slug"] for r in rows) == ["a-b", "a-b-2"]
    assert len(report["slug_collisions"]) == 1


# ------------------------------------------------------------------ identifier mapping

def ids(d, role):
    return [r["id"] for r in d.get(role, [])]


def test_identifier_mapping(tmp_path):
    g = glossary({
        "exact": entry(aat=[{"id": "300000001", "label": "a"}]),
        "close": entry(aat=[{"id": "300000002", "label": "b", "match": "close"}]),
        "uncertain": entry(aat=[{"id": "300000003", "label": "c", "uncertain": True}]),
        "broad": entry(aat=[{"id": "300000004", "label": "d", "broader": True}]),
        "closebroad": entry(aat=[{"id": "300000005", "label": "e", "broader": True, "match": "close"}]),
        "wikidata": entry(aat=[{"id": "Q42", "label": "f", "source": "wikidata"}]),
        "suggested": entry(aat=[{"id": "300000006", "label": "g", "suggested": True}]),
        # the placeholder, bare, marked close, and beside a broader concept
        "unid": entry(aat=[{"id": "300386154", "label": "unidentified"}]),
        "unidclose": entry(aat=[{"id": "300386154", "label": "unidentified", "match": "close"}]),
        "unidbroad": entry(aat=[{"id": "300386154", "label": "u", "broader": True},
                                {"id": "300000007", "label": "cloth", "broader": True}]),
        "unidexact": entry(aat=[{"id": "300386154", "label": "u", "match": "close"},
                                {"id": "300000008", "label": "h"}]),
    })
    site, _, report = run(tmp_path, g)
    assert ids(doc(site, "exact"), "equivalent") == ["aat:300000001"]
    assert ids(doc(site, "close"), "closeMatch") == ["aat:300000002"]
    assert ids(doc(site, "uncertain"), "closeMatch") == ["aat:300000003"]
    assert ids(doc(site, "broad"), "broader") == ["aat:300000004"]
    assert ids(doc(site, "closebroad"), "broader") == ["aat:300000005"]
    assert ids(doc(site, "closebroad"), "closeMatch") == []
    assert ids(doc(site, "wikidata"), "equivalent") == ["wd:Q42"]
    assert "equivalent" not in doc(site, "suggested") and report["skipped_suggested"] == ["suggested"]
    for slug in ("unid", "unidclose", "unidbroad"):
        d = doc(site, slug)
        assert ids(d, "classified_as") == ["aat:300386154"], slug
        assert not d.get("equivalent") and not d.get("closeMatch"), slug
    assert ids(doc(site, "unidbroad"), "broader") == ["aat:300000007"]
    d = doc(site, "unidexact")  # identified after all: no unidentified marker
    assert ids(d, "equivalent") == ["aat:300000008"] and "classified_as" not in d


def test_names_dates_and_preferred(tmp_path):
    g = glossary({"widget": entry(forms=[("widget", [0, 1], 1), ("wydget", [2], 0), ("wigit", [], 0)]),
                  "gizmo": entry(forms=[("gysmo", [1], 1)])})
    site, _, _ = run(tmp_path, g)
    names = {n["content"]: n for n in doc(site, "widget")["identified_by"]}
    assert names["widget"]["validFrom"] == "1400" and names["widget"]["validThrough"] == "1455"
    assert "validFrom" not in names["wydget"]  # undated source
    pref = [n for n in names.values() if any(c["id"] == "aat:300404670" for c in n["classified_as"])]
    assert [n["content"] for n in pref] == ["widget"]
    # the key is not among gizmo's forms: it still gets the single preferred Name
    gn = doc(site, "gizmo")["identified_by"]
    assert [n["content"] for n in gn if n["classified_as"][0]["id"] == "aat:300404670"] == ["gizmo"]


def test_links_places_and_attestation(tmp_path):
    g = glossary({
        "a": entry(related=["b"], x=["gone"], compoundOf=["b"],
                   geo=[{"id": "whg:place:wd:Q2634", "label": "Naples"}, {"id": "osm:123", "label": "x"}]),
        "b": entry(geo={"id": "Q90", "label": "Paris"}),
    })
    site, _, report = run(tmp_path, g, attest={"a": 7})
    a = doc(site, "a")
    assert ids(a, "related") == ids(a, "compoundOf") == ["https://w3id.org/hector/commodity/b"]
    assert "seeAlso" not in a and report["dangling_link"] == ["a: x -> 'gone' (not in glossary)"]
    assert ids(a, "originPlace") == ["wd:Q2634"] and report["geo_skipped"] == ["a: osm:123"]
    assert ids(doc(site, "b"), "originPlace") == ["wd:Q90"]
    assert a["attestationCount"] == 7 and "attestationCount" not in doc(site, "b")
    assert ids(a, "exactMatch") == ["https://w3id.org/mlca/glossary/a"]


# ------------------------------------------------------------------ ledger over time

def test_rerun_is_stable_and_modified_tracks_content(tmp_path):
    g = glossary({"widget": entry(), "gizmo": entry()})
    site, ledger, _ = run(tmp_path, g, today="2026-01-01")
    first = ledger_rows(ledger)
    g2 = copy.deepcopy(g)
    g2["entries"]["gizmo"]["d"] = "a changed description"
    site, ledger, _ = run(tmp_path, g2, today="2026-02-01")
    second = ledger_rows(ledger)
    assert set(first) == set(second) == {"widget", "gizmo"}
    assert second["widget"]["modified"] == "2026-01-01" == doc(site, "widget")["modified"]
    assert second["gizmo"]["modified"] == "2026-02-01" == doc(site, "gizmo")["modified"]
    assert second["gizmo"]["minted"] == "2026-01-01"


def test_rekey_keeps_the_slug(tmp_path):
    run(tmp_path, glossary({"wydgetry": entry(forms=[("wydgetry", [0], 1)])}))
    site, ledger, report = run(tmp_path, glossary(
        {"widgetry": entry(forms=[("wydgetry", [0], 1)])},
        rekey_history=[{"old_key": "wydgetry", "new_key": "widgetry"}]))
    rows = ledger_rows(ledger)
    assert set(rows) == {"wydgetry"} and rows["wydgetry"]["glossary_key"] == "widgetry"
    assert doc(site, "wydgetry")["_label"] == "widgetry"
    assert not (site / "commodity/widgetry").exists() and report["rekeyed"]


def test_merge_and_delete_leave_deprecation_records(tmp_path):
    run(tmp_path, glossary({"gadjet": entry(), "gadget": entry(), "thingum": entry()}))
    site, ledger, report = run(tmp_path, glossary(
        {"gadget": entry()},
        merge_history=[{"primary": "gadget", "merged": ["gadjet"]}],
        deletion_history=[{"key": "thingum"}]))
    rows = ledger_rows(ledger)
    assert rows["gadjet"]["status"] == "deprecated" and rows["gadjet"]["replaced_by"] == "gadget"
    assert rows["thingum"]["status"] == "deleted"
    d = doc(site, "gadjet")
    assert d["deprecated"] is True and d["isReplacedBy"]["id"] == "https://w3id.org/hector/commodity/gadget"
    assert doc(site, "thingum")["deprecated"] is True and "isReplacedBy" not in doc(site, "thingum")
    # and the deprecation records are valid documents
    V.set_root(site)
    issues = V.validate([site / "commodity/gadjet/ontology.json", site / "commodity/thingum/ontology.json"])
    assert [str(i) for i in issues if i.level == "ERROR"] == []


def test_both_lca_history_record_shapes_are_understood(tmp_path):
    run(tmp_path, glossary({"gizmo": entry(), "gadjet": entry(), "gadget": entry(), "doohicky_2": entry()}))
    site, ledger, report = run(tmp_path, glossary(
        {"gizmos": entry(), "gadget": entry()},
        rekey_history=[{"from": "gizmo", "to": "gizmos", "when": "2026-06-18T09:00:00Z"}],
        merge_history=[{"from": "gadjet", "into": "gadget", "when": "2026-06-18T09:00:00Z", "reason": "x"}],
        deletion_history=[{"key": "doohicky_2", "when": "2026-06-18T09:00:00Z", "reason": "x"}]))
    rows = ledger_rows(ledger)
    assert rows["gizmo"]["glossary_key"] == "gizmos" and rows["gizmo"]["status"] == "active"
    assert rows["gadjet"]["status"] == "deprecated" and rows["gadjet"]["replaced_by"] == "gadget"
    assert rows["doohicky-2"]["status"] == "deleted"
    assert report["missing"] == []


def test_later_rename_wins_whatever_the_record_order(tmp_path):
    run(tmp_path, glossary({"gizmo": entry()}))
    _, ledger, _ = run(tmp_path, glossary(
        {"gizmo-final": entry()},
        rekey_history=[{"from": "gizmo", "to": "gizmo-final", "when": "2026-06-02T00:00:00Z"},
                       {"old_key": "gizmo", "new_key": "gizmo-draft", "timestamp": "2026-06-01T00:00:00Z"}]))
    assert ledger_rows(ledger)["gizmo"]["glossary_key"] == "gizmo-final"


def test_a_key_that_vanishes_without_history_is_reported_not_dropped(tmp_path):
    run(tmp_path, glossary({"widget": entry(), "gizmo": entry()}))
    site, ledger, report = run(tmp_path, glossary({"widget": entry()}))
    assert report["missing"] == ["gizmo"]
    assert ledger_rows(ledger)["gizmo"]["status"] == "active"


def test_synthetic_export_validates(tmp_path):
    g = glossary({"widget": entry(aat=[{"id": "300000001", "label": "a"}], related=["gizmo"]),
                  "gizmo": entry(aat=[{"id": "300386154", "label": "u"}])})
    site, _, _ = run(tmp_path, g)
    V.set_root(site)
    checked = []
    issues = V.validate(checked=checked)
    assert [str(i) for i in issues if i.level == "ERROR"] == []
    assert {"commodity/widget/ontology.json", "commodity/gizmo/ontology.json"} <= {
        p.resolve().relative_to(site.resolve()).as_posix() for p in checked}


# ------------------------------------------------------------------ the real glossary

@pytest.mark.skipif(not (REAL_LCA / "docs/data/glossary_data.json").exists(),
                    reason="LCA checkout not present")
def test_real_export_reconciles_with_plan_c1(tmp_path):
    site, ledger, report = X.export(REAL_LCA, tmp_path / "site", tmp_path / "ledger.tsv"), None, None
    docs = [json.loads(p.read_text()) for p in (tmp_path / "site/commodity").glob("*/ontology.json")]
    real = [d for d in docs if not d.get("illustrative")]
    ident = sum(1 for d in real if d.get("equivalent") or d.get("closeMatch"))
    broader_only = sum(1 for d in real if d.get("broader") and not (d.get("equivalent") or d.get("closeMatch")))
    unid_only = sum(1 for d in real if d.get("classified_as") and not d.get("broader"))
    # PLAN.md C1, measured 2026-09-18; re-measure if the glossary has moved on
    assert len(real) >= 2400
    assert abs(ident - 1334) < 50 and abs(broader_only - 722) < 50 and abs(unid_only - 395) < 50
    assert not any(r["id"].endswith("300386154") for d in real for k in ("equivalent", "closeMatch")
                   for r in d.get(k, []))
