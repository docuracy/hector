"""Tests for tools/rates/parse_bor.py (PLAN.md task 15).

Unit tests use hand-written synthetic strings shaped like the sources. The integration tests
read the real Jenks files from the LCA checkout at test time and are skipped when it is
absent: no transcribed row is embedded here, because nothing Jenks-derived may be committed
until the Jenks permission (PLAN.md task 1) is granted.
"""
import csv
from pathlib import Path

import pytest

from tools.rates import parse_bor as pb

LCA = pb.DEFAULT_LCA
BOR = LCA / pb.BOR_DIR
needs_lca = pytest.mark.skipif(not BOR.is_dir(), reason="LCA checkout not present")


# ---------------------------------------------------------------- £ s d

@pytest.mark.parametrize("text, pence, status, editorial", [
    ("£3 6s 8d", "800", "ok", False),
    ("13s 4d", "160", "ok", False),
    ("20s", "240", "ok", False),
    ("10d", "10", "ok", False),
    ("£4", "960", "ok", False),
    ("[13s 4d]", "160", "ok", True),
    ("33[s] 4d", "400", "ok", True),
    ("5¾d", "5.75", "ok", False),
    ("2s ob.", "24.5", "ok", False),
    ("26 8d", "320", "ok", False),              # shilling sign omitted in the source
    ("10s or 12s", "120", "partial", False),     # alternatives: leading value only, flagged
    ("50s at 3d þe lb.", "600", "partial", False),
    ("[no valuation]", None, "failed", True),
    ("4", None, "failed", False),
    ("", None, "failed", False),
])
def test_parse_rate(text, pence, status, editorial):
    r = pb.parse_rate(text)
    assert (r.pence, r.status, r.editorial) == (pence, status, editorial)


def test_parse_rate_components():
    r = pb.parse_rate("£1 2s 3d")
    assert (r.pounds, r.shillings, r.pennies, r.pence) == ("1", "2", "3", str(240 + 24 + 3))


# ---------------------------------------------------------------- commodity / unit split

def test_split_count_unit_with_counted_thing():
    sp = pb.split_commodity("Wydgets of Flaunders the hundreth elles")
    assert sp.commodity_text == "Wydgets of Flaunders"
    assert (sp.unit.unit, sp.unit.quantity, sp.unit.of) == ("hundred", "100", "ell")
    assert sp.status == "ok"


def test_split_hundredweight_and_contents():
    sp = pb.split_commodity("Frobs grene þe C waight cont’ 112 lb.")
    assert sp.commodity_text == "Frobs grene"
    assert sp.head == "Frobs" and sp.qualifier == "grene"
    assert sp.unit.unit == "hundredweight"
    assert sp.contents_text == "cont’ 112 lb."
    assert (sp.contents_quantity, sp.contents_unit) == ("112", "pound")


def test_split_contents_in_words():
    sp = pb.split_commodity("Blicks the C cont’ five score")
    assert (sp.unit.unit, sp.contents_quantity, sp.contents_unit) == ("hundred", "5", "score")


def test_split_variety_after_voc():
    sp = pb.split_commodity("Grommets voc’ small grommets the dozen")
    assert sp.head == "Grommets" and sp.variety == "small grommets"
    assert (sp.unit.unit, sp.unit.quantity) == ("dozen", "12")


def test_split_numbered_unit():
    sp = pb.split_commodity("Pelts the 40 skynes")
    assert (sp.unit.unit, sp.unit.quantity, sp.unit.of) == ("skin", "40", "skin")


def test_split_great_gross():
    sp = pb.split_commodity("Beads of bone the great groce")
    assert (sp.unit.unit, sp.unit.quantity) == ("gross", "1728")


def test_split_the_whole_and_thelle():
    assert pb.split_commodity("Blorps thole pece").unit.unit == "piece"
    assert pb.split_commodity("Silk of Lucca makyng thelle").unit.unit == "ell"


def test_split_unknown_unit_is_partial_not_ok():
    sp = pb.split_commodity("Zorkes the zork")
    assert sp.unit is not None and sp.unit.unit is None and sp.unit.unit_text == "zork"
    assert sp.status == "partial"


def test_split_no_unit_fails():
    sp = pb.split_commodity("Zorkes of Spayne")
    assert sp.unit is None and sp.status == "failed"
    assert sp.commodity_text == "Zorkes of Spayne"


# ---------------------------------------------------------------- 1604 HTML flattening

SYNTHETIC_1604 = """<html><body>
<p>Preamble that must be ignored 6s 8d</p>
<p>Rates for the subsidy of poundage inwardes</p>
<p>– A –</p>
<p>Anvils the dozen 6s</p>
<p>Drugges voc’</p>
<p>Zorkroot the pound 12d</p>
<p>– B –</p>
<p>Bolts the pece 2s</p>
<table><tbody>
<tr><td rowspan="3">Fishe vocat’</td><td colspan="2">cod the barrell 13s 4d</td></tr>
<tr><td rowspan="2">herring</td><td>white the barrell 6s 8d</td></tr>
<tr><td>red the cade cont’ 500 8s 4d</td></tr>
</tbody></table>
<p>Wydgets see Frobs</p>
<p><sup>a‑a </sup>Interlined L.</p>
<p>Rates for the subsydy of poundage outwardes</p>
<p>Blorps the flitche 6s 8d</p>
<p>Custome and subsidy of wollen clothes</p>
<p>Everie Englishman ... the some of 6s 8d</p>
</body></html>"""


def test_extract_1604_structure(tmp_path):
    f = tmp_path / "b.html"
    f.write_text(SYNTHETIC_1604, encoding="utf-8")
    raw, stats = pb.extract_1604(f)
    got = [(r.direction, r.commodity_cell, r.rate_text) for r in raw]
    assert got == [
        ("inward", "Anvils the dozen", "6s"),
        ("inward", "Drugges voc’ Zorkroot the pound", "12d"),
        ("inward", "Bolts the pece", "2s"),
        ("inward", "Fishe vocat’ cod the barrell", "13s 4d"),
        ("inward", "Fishe vocat’ herring white the barrell", "6s 8d"),
        ("inward", "Fishe vocat’ herring red the cade cont’ 500", "8s 4d"),
        ("inward", "Wydgets see Frobs", ""),
        ("outward", "Blorps the flitche", "6s 8d"),
    ]
    assert raw[6].note == "cross-reference"
    assert stats["letter headings skipped"] == 2
    assert stats["footnote paragraphs skipped"] == 1


# ---------------------------------------------------------------- the real files

def _data_lines(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE))[1:]
    return [r for r in rows if any(x.strip() for x in r)]


@needs_lca
def test_tsv_rows_round_trip_verbatim():
    rows = pb.read_tsv_rows(LCA)
    assert rows, "no rows read"          # presence, before any absence claim
    for suffix, (book, direction) in pb.TSV_BOOKS.items():
        path = BOR / f"{pb.TSV_PREFIX}{suffix}.tsv"
        expected = _data_lines(path)
        got = [r for r in rows if r.source_file == path.name]
        assert len(got) == len(expected) > 0, path.name
        assert all(r.book == book and r.direction == direction for r in got)
        assert [(r.commodity_raw, r.rate_raw) for r in got] == [(e[0], e[1]) for e in expected]


@needs_lca
def test_real_parse_quality_floor():
    rows = pb.read_tsv_rows(LCA)
    raw, _ = pb.extract_1604(BOR / pb.HTML_1604)
    rows += pb.rows_1604(raw)
    by_book = {b: [r for r in rows if r.book == b] for b in ("1507", "1545", "1558", "1604")}
    for b, sub in by_book.items():
        assert sub, b
        with_pence = sum(r.pence is not None for r in sub) / len(sub)
        with_unit = sum(r.unit is not None for r in sub) / len(sub)
        assert with_pence >= 0.85, (b, with_pence)
        assert with_unit >= 0.85, (b, with_unit)
    # both directions of 1604 were found, and the woollen-cloth section was not parsed as rates
    assert {r.direction for r in by_book["1604"]} == {"inward", "outward"}
    assert not any(r.commodity_raw.startswith("Everie Englishman") for r in by_book["1604"])
    assert any(r.commodity_raw.startswith("Drugges voc’ ") for r in by_book["1604"])


def test_split_half_unit():
    u = pb.split_commodity("Blicks the di’ cheste").unit
    assert (u.unit, u.quantity) == ("chest", "0.5")
