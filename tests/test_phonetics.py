"""Tests for tools/phonetics/ipa.py (PLAN.md task 13). Offline; standard library only.

The pinned keys are repeated here on purpose rather than read from ipa.PINNED, so that
re-pinning the module does not silently re-pin its tests. The --check tests use a small
invented glossary, never Jenks-derived entries.
"""
import json
import string

import pytest

from tools.phonetics import ipa

PINNED = [
    # (form, expected key, what it exercises)
    ("saffron", "safron", "English; doubled consonant is orthographic"),
    ("shepe", "ʃepə", "Middle English sh and weak final -e"),
    ("hoppes", "hopəs", "Middle English plural -es"),
    ("wyne", "winə", "y as the vowel i"),
    ("yerde", "jerdə", "consonantal y"),
    ("knyght", "knixt", "gh as /x/"),
    ("cervisia", "servisia", "Latin: c before i is /s/"),
    ("avellanae", "avelane", "Latin ae"),
    ("gingiber", "dʒindʒiber", "soft g; Latin -er is not a weak ending"),
    ("hoggeshedes", "hogeʃedəs", "doubled g stays hard before e (sh across the compound: a known weakness)"),
    ("pfeltt", "pfelt", "Low German spelling: letters kept"),
    ("gardebrace", "gardebrasə", "Anglo-Norman"),
    ("ketelle bandes", "ketelə bandəs", "a phrase keeps its word boundaries"),
    ("cloþis", "kloθis", "thorn"),
    ("tiler pro alblastres", "tiler pro alblastrəs", "Latin-English phrase"),
    ("bolt_3", "bolt", "LCA key suffix dropped"),
]


@pytest.mark.parametrize("form,want,why", PINNED)
def test_pinned(form, want, why):
    assert ipa.transcribe(form) == want, why


@pytest.mark.parametrize("a,b", [("saffron", "saffran"), ("pannus", "pannis"), ("tin", "ten"),
                                 ("wyne", "wyte"), ("cervisia", "cervisio")])
def test_a_one_letter_mutation_changes_the_key(a, b):
    assert ipa.transcribe(a) != ipa.transcribe(b)


@pytest.mark.parametrize("a,b", [("wyne", "wine"), ("coton", "cotton"), ("shepe", "schepe"),
                                 ("cyrupi", "sirupi"), ("jesseron", "gesseron")])
def test_variant_spellings_of_one_sound_share_a_key(a, b):
    assert ipa.transcribe(a) == ipa.transcribe(b)


def test_no_letters_no_key():
    assert ipa.transcribe("") == ""
    assert ipa.transcribe("’ ., [..] 12") == ""


def test_every_letter_has_a_rule():
    for ch in string.ascii_lowercase:
        assert ipa.transcribe_word(ch)


def test_selftest_passes():
    assert ipa.selftest() == []


def test_selftest_fails_when_a_rule_is_removed(monkeypatch):
    """The selftest must be able to fail: drop the sh rule and it has to notice."""
    monkeypatch.setattr(ipa, "RULES", [r for r in ipa.RULES if r[0] != "sh"])
    fails = ipa.selftest()
    assert any("shepe" in f for f in fails), fails


def test_selftest_fails_when_a_rule_changes(monkeypatch):
    monkeypatch.setattr(ipa, "RULES", [("e", "i", ipa._always)] + ipa.RULES)
    assert ipa.selftest()


def test_deterministic_across_order():
    words = [f for f, _, _ in PINNED]
    first = [ipa.transcribe(w) for w in words]
    assert [ipa.transcribe(w) for w in reversed(words)] == first[::-1]


def test_language_guess_is_recorded_not_used():
    assert ipa.language_guess("avellanae") == "la"
    assert ipa.language_guess("hoppes") == "en"
    # the key does not depend on the guess: one convention for all
    assert ipa.table({"avellanae": ["x"], "hoppes": ["y"]})[0]["method"] == ipa.METHOD


def _lca(tmp_path, forms):
    lca = tmp_path / "lca"
    (lca / "docs/data").mkdir(parents=True)
    g = {"entries": {k: {"f": [{"t": t} for t in ts]} for k, ts in forms.items()}, "metadata": {}}
    (lca / "docs/data/glossary_data.json").write_text(json.dumps(g), encoding="utf-8")
    return lca


def test_check_passes_on_a_fresh_table_and_fails_on_a_stale_one(tmp_path):
    lca = _lca(tmp_path, {"widget": ["wyne", "wine"], "gadget": ["hoppes"]})
    out = tmp_path / "ipa.tsv"
    assert ipa.main(["--lca", str(lca), "--out", str(out)]) == 0
    rows = ipa.read_tsv(out)
    assert [(r["form"], r["ipa"], r["keys"]) for r in rows] == [
        ("hoppes", "hopəs", "gadget"), ("wine", "winə", "widget"), ("wyne", "winə", "widget")]
    assert ipa.check(lca, out) == []

    # a key edited by hand (or written by an older rule set) is caught
    rows[0]["ipa"] = "hopes"
    ipa.write_tsv(rows, out)
    assert any("differ from a fresh run" in f for f in ipa.check(lca, out))
    assert ipa.main(["--lca", str(lca), "--out", str(out), "--check"]) == 1


def test_check_fails_when_the_glossary_gains_a_form(tmp_path):
    lca = _lca(tmp_path, {"widget": ["wyne"]})
    out = tmp_path / "ipa.tsv"
    ipa.main(["--lca", str(lca), "--out", str(out)])
    lca = _lca(tmp_path / "later", {"widget": ["wyne", "wyn"]})
    assert any("form set differs" in f for f in ipa.check(lca, out))


def test_check_fails_when_the_table_is_missing(tmp_path):
    lca = _lca(tmp_path, {"widget": ["wyne"]})
    assert any("missing" in f for f in ipa.check(lca, tmp_path / "absent.tsv"))
