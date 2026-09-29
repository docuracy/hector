"""tools/rates/link_rates.py: how a Book of Rates entry is linked to a glossary concept and
its qualifier (PLAN.md tasks 14 and 17, decision 2). An invented glossary; nothing Jenks-derived."""
import json

from tools.rates import link_rates as L

ENTRIES = {
    "ivory": {"f": [{"t": "ivory"}, {"t": "every"}]},     # a real glossary spelling of ivory
    "buckram": {"f": [{"t": "buckroms"}, {"t": "buckram"}]},
    "canvas": {"f": [{"t": "canvas"}]},
    "cork": {"f": [{"t": "corke"}]},
    "barrel": {"f": [{"t": "barrelles"}]},
    "pan": {"f": [{"t": "pans"}]},
    "pan_2": {"f": [{"t": "pans"}]},                       # one spelling, two concepts
    "wax": {"f": [{"t": "wax"}]},
}


def linked(text):
    idx = L.form_index(ENTRIES)
    return L.link(text, idx, max(len(k.split()) for k in idx))


def test_the_goods_at_the_head_win_over_a_word_later_on():
    # anywhere-first linked this to ivory, through "every"
    key, spelling, qual, how = linked("Buckroms in paperes, every paper 1 with another")
    assert (key, how) == ("buckram", "head")
    key, *_ = linked("Corke made in barrelles the laste")
    assert key == "cork"                                   # not the barrel it came in


def test_an_ambiguous_spelling_is_never_used():
    key, _s, _q, how = linked("Droppyn pans of yerne")
    assert key is None and how.startswith("ambiguous")


def test_an_ordinary_word_does_not_link_on_its_own():
    idx = L.form_index({"ivory": {"f": [{"t": "every"}]}})
    assert L.link("Thynges every one", idx, 1)[0] is None


def test_the_qualifier_loses_formula_words_and_the_head_again():
    # commodity_text as the parser gives it: the measure ("the bale") is already split off
    key, spelling, qual, _ = linked("Canvas called Vytory canvas that ys to saye")
    assert (key, qual) == ("canvas", "vytory")


def test_one_qualifier_however_it_is_spelt(tmp_path):
    q = {"canonicals": {"white": {"label": "white", "forms": ["whit", "whyte"]},
                        "prussia": {"label": "Prussia", "forms": ["spruse", "sprewce"]}}}
    (tmp_path / "docs/data").mkdir(parents=True)
    (tmp_path / "docs/data/qualifiers.json").write_text(json.dumps(q), encoding="utf-8")
    canon = L.qualifier_canon(tmp_path)
    a, b = canon("normandy whit"), canon("normandy whyte")
    assert a == b and a.endswith(" white")                 # "normandy" itself is folded
    assert canon("spruse") == canon("sprewce") == "prussia"
    assert canon("newcastell") == canon("neucastell")      # the spelling fold
    assert canon("normandy") != canon("paris")             # CONTROL: different places stay apart


def test_the_quantity_is_a_number():
    assert L._num("100") == 100 and L._num("2.5") == 2.5 and L._num(None) == 1
