"""Tests for tools/validate.py (PLAN.md task 21).

Every check is shown able to fail: each mutation test asserts that the unmutated document is
free of the code AND that the mutated one reports it, so a check that silently stopped looking
would fail here rather than pass. The legacy fixtures are the repo's files as they stood before
Phase 0 (commit 7e6d932), which the validator must reject.
"""
import copy
import json
import os
import shutil
from pathlib import Path

import pytest

from tools import validate as V

REPO = Path(__file__).resolve().parent.parent
LEGACY = REPO / "tests" / "fixtures" / "legacy"
SAFFRON = "commodity/saffron/ontology.json"


@pytest.fixture(autouse=True)
def _restore_root():
    yield
    V.set_root(REPO)


def make_repo(tmp_path: Path, overrides: dict[str, object] | None = None, legacy: bool = False) -> Path:
    """A copy of the repo's data files in tmp_path, with some files replaced."""
    root = tmp_path / "repo"
    for rel in ["context/hector.jsonld", "ontology/ontology.json", "shapes/hector.shacl.ttl",
                "tools/contexts/linked-art.json", SAFFRON, "unit/mass/ontology.json",
                "unit/mass/pound/ontology.json"]:
        src = (LEGACY / rel) if legacy and (LEGACY / rel).exists() else REPO / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    for rel, content in (overrides or {}).items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if content is None:
            dst.unlink()
        else:
            dst.write_text(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False),
                           encoding="utf-8")
    V.set_root(root)
    return root


def codes(issues, level="ERROR", path=None):
    return {i.code for i in issues if i.level == level and (path is None or i.path == path)}


def load(rel):
    return json.loads((REPO / rel).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ the real repo

def test_repo_is_valid_and_was_actually_checked():
    V.set_root(REPO)
    checked = []
    issues = V.validate(checked=checked)
    assert [str(i) for i in issues if i.level == "ERROR"] == []
    # presence: every entity document was reached
    reached = {c.resolve().relative_to(REPO).as_posix() for c in checked}
    assert {SAFFRON, "unit/mass/ontology.json", "unit/mass/pound/ontology.json",
            "ontology/ontology.json"} <= reached


# ------------------------------------------------------------------ legacy files (pre Phase 0)

def test_legacy_repo_is_rejected(tmp_path):
    make_repo(tmp_path, legacy=True, overrides={"ontology/ontology.json": None})
    issues = V.validate()
    assert "JSONLD" in codes(issues, path="context/hector.jsonld")
    for doc in (SAFFRON, "unit/mass/ontology.json", "unit/mass/pound/ontology.json"):
        assert "JSONLD" in codes(issues, path=doc), doc


def test_legacy_documents_fail_the_deeper_checks_once_the_context_parses(tmp_path):
    """Fix only F1 in the legacy context; the legacy documents must still fail on F3/F5 defects."""
    ctx = json.loads((LEGACY / "context/hector.jsonld").read_text())
    c = ctx["@context"]
    for k in ("hector:roleAttestedVariant", "hector:roleModernLemma", "hector:roleArchaicForm"):
        del c[k]
    for v in c.values():
        if isinstance(v, dict):
            v.pop("rdfs:label", None)
            v.pop("rdfs:comment", None)
    make_repo(tmp_path, legacy=True, overrides={"context/hector.jsonld": ctx})
    issues = V.validate()
    saffron = codes(issues, path=SAFFRON)
    assert "JSONLD" not in saffron            # the context now parses...
    assert "RELATIVE-IRI" in saffron          # ..."modern_lemma"
    assert "UNKNOWN-NAMESPACE" in saffron     # http://linked.art/ns/v1/
    assert "EXTERNAL-IRI-FORM" in saffron     # wikidata /wiki/Q84, museum.org, finds.org.uk
    assert "EXTERNAL-UNLABELLED" in saffron   # bare sameAs strings
    assert "KIND" in saffron                  # not a crm:E55_Type
    assert "ENTITY-URI" in saffron            # hector#commodity/saffron, a fragment URI
    pound = codes(issues, path="unit/mass/pound/ontology.json")
    assert "UNKNOWN-NAMESPACE" in pound       # hector:Unit, in the retired https://w3id.org/hector#
    assert "KIND" in codes(issues, path="unit/mass/ontology.json")


# ------------------------------------------------------------------ one mutation per check

def mutate(fn, rel=SAFFRON):
    doc = copy.deepcopy(load(rel))
    fn(doc)
    return {rel: doc}


MUTATIONS = {
    "UNIDENTIFIED-IDENTITY": mutate(lambda d: d["equivalent"].append(
        {"id": "aat:300386154", "type": "Type", "_label": "unidentified (information indicator)"})),
    "IDENTITY-CLASS": mutate(lambda d: d["broader"].append(
        {"id": "aat:300013073", "type": "Type", "_label": "saffron"})),
    "RELATIVE-IRI": mutate(lambda d: d["identified_by"][0].__setitem__("language", "en")),
    "EXTERNAL-IRI-FORM": mutate(lambda d: d["equivalent"].append(
        {"id": "https://www.wikidata.org/wiki/Q25434", "_label": "saffron"})),
    "EXTERNAL-UNLABELLED": mutate(lambda d: d["equivalent"][1].pop("_label")),
    "UNDEFINED-TERM": mutate(lambda d: d.__setitem__("hector:notInTheVocabulary", "x")),
    "UNKNOWN-NAMESPACE": mutate(lambda d: d.__setitem__("http://linked.art/ns/v1/label", "x")),
    "KIND": mutate(lambda d: d["identified_by"][1]["classified_as"].append(
        {"id": "aat:300404670", "type": "Type", "_label": "preferred terms"})),
    "SHACL": mutate(lambda d: d["taxation"][0]["amount"].__setitem__("valueInPence", "-1")),
    "ENTITY-URI": mutate(lambda d: d.__setitem__("id", "hector:commodity/saffron")),
    "DANGLING-REF": mutate(lambda d: d["taxation"][0]["perQuantity"]["unit"].__setitem__(
        "id", "hectorid:unit/mass/no-such-unit")),
    "JSONLD": mutate(lambda d: d.__setitem__("@context", [*d["@context"], {"bad": {"rdfs:label": "x"}}])),
}


@pytest.mark.parametrize("code", sorted(MUTATIONS))
def test_each_check_fires_on_its_defect(tmp_path, code):
    make_repo(tmp_path)
    assert code not in codes(V.validate(), path=SAFFRON), "control: clean saffron must not report it"
    make_repo(tmp_path / "m", overrides=MUTATIONS[code])
    assert code in codes(V.validate(), path=SAFFRON)


def test_dimension_typed_as_unit_is_rejected(tmp_path):
    over = mutate(lambda d: d.__setitem__("type", "MeasurementUnit"), "unit/mass/ontology.json")
    make_repo(tmp_path, overrides=over)
    assert "KIND" in codes(V.validate(), path="unit/mass/ontology.json")


def test_name_language_given_as_string_violates_shacl(tmp_path):
    # "@value" object: a literal where the language entity belongs
    make_repo(tmp_path, overrides=mutate(lambda d: d["identified_by"][0].__setitem__(
        "language", [{"@value": "English"}])))
    msgs = [i.message for i in V.validate() if i.code == "SHACL"]
    assert any("language" in m for m in msgs), msgs


def test_name_without_language_is_allowed(tmp_path):
    make_repo(tmp_path, overrides=mutate(lambda d: d["identified_by"][0].pop("language")))
    assert codes(V.validate(), path=SAFFRON) == set()


def test_missing_vocabulary_is_an_error(tmp_path):
    make_repo(tmp_path, overrides={"ontology/ontology.json": None})
    assert "UNDEFINED-TERM" in codes(V.validate())


def test_remote_contexts_are_never_fetched(tmp_path):
    over = mutate(lambda d: d.__setitem__("@context", "https://example.net/context.jsonld"))
    make_repo(tmp_path, overrides=over)
    assert "JSONLD" in codes(V.validate(), path=SAFFRON)


# ------------------------------------------------------------------ online (network)

online = pytest.mark.skipif(not os.environ.get("HECTOR_ONLINE"), reason="set HECTOR_ONLINE=1")


def _getty_reachable() -> bool:
    """Positive control for the AAT half: can a known-good AAT id be checked from here?"""
    import requests
    s = requests.Session()
    s.headers["User-Agent"] = "HECTOR validator tests"
    res = V.authority_labels("http://vocab.getty.edu/aat/300013073", s, {})
    return res is not None and res[0] == 200


@online
def test_online_wikidata_catches_a_mislabelled_id(tmp_path):
    make_repo(tmp_path)
    assert not codes(V.validate(online=True)) & {"ONLINE-NOTFOUND", "ONLINE-LABEL"}
    # the legacy Q-id: a spider family, not saffron
    make_repo(tmp_path / "m", overrides=mutate(lambda d: d["equivalent"].__setitem__(
        1, {"id": "wd:Q12057", "type": "Type", "_label": "saffron"})))
    issues = V.validate(online=True)
    assert any(i.code == "ONLINE-LABEL" and "Q12057" in i.message for i in issues)


@online
def test_online_aat_catches_a_nonexistent_id(tmp_path):
    if not _getty_reachable():
        pytest.skip("Getty AAT cannot be reached from this network (neither the web front "
                    "end nor SPARQL); AAT ids were NOT checked")
    make_repo(tmp_path)
    assert not codes(V.validate(online=True)) & {"ONLINE-NOTFOUND", "ONLINE-LABEL"}
    # the legacy AAT id, which does not exist
    make_repo(tmp_path / "m", overrides=mutate(lambda d: d["equivalent"].__setitem__(
        0, {"id": "aat:300010621", "type": "Type", "_label": "saffron"})))
    issues = V.validate(online=True)
    assert any(i.code == "ONLINE-NOTFOUND" and "300010621" in i.message for i in issues)
