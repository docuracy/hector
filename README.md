# HECTOR
## Historical Economic Commodities: Terminologies, Ontologies, & Rates

> **Status: alpha (since 3 October 2026). Published for discussion; please do not cite yet.**
> Every record, identifier and URI may change or be withdrawn without notice until the first
> tagged release (`vYYYY.MM`, deposited on Zenodo). Until then URIs are not stable, and
> nothing here should be treated as a reference. Comments are very welcome as
> [issues](https://github.com/docuracy/hector/issues). See
> [docs/uri-policy.md](docs/uri-policy.md#0-alpha-until-the-first-release).

HECTOR is an open Linked Data vocabulary of historical traded **commodities**, the **units**
they were measured and packed in, and the **customs rates** charged on them. Each record gathers
the spellings the sources actually use, with dates and a phonetic key, links to the Getty Art &
Architecture Thesaurus and Wikidata where an equivalent exists, and is published as JSON-LD
aligned with [Linked Art](https://linked.art/). It is designed to grow to the goods of any trade,
period and language; its first content comes from the London customs accounts (1380–1560) and the
English Books of Rates of 1507, 1545 and 1558.

**Browse and search it at <https://w3id.org/hector/>**, by any spelling the sources use or a near
miss: similar spellings are found with the London Customs Accounts project's character encoder,
which LCA measured best for this material (0.881 top-1 on held-out glossary spellings, against
0.853 for Symphonym v8 with trigrams).

## What is published

| | records | where |
|---|---:|---|
| Commodities | 2,452 | `commodity/<slug>/ontology.json` |
| Commodities as the Books of Rates price them ("looking glasses of steel, large"), each linked to its commodity | 688 | `commodity/<slug>/ontology.json` |
| Customs rates, 1507–1558, with the source line quoted | 1,834 | inside the commodity records (`taxation`) |
| Units of measure, with definitions and conversions where the sources give them | 248 | `unit/<slug>/ontology.json` |
| Kinds of quantity (mass, length, volume, count, package) | 5 | `unit/dimension/<kind>/ontology.json` |
| Merged or moved records, kept so their URIs still resolve | 3 | deprecation records (`deprecated`, `isReplacedBy`) |

Every record is also published as **Turtle** (`ontology.ttl`) and **RDF/XML** (`ontology.rdf`) beside its
JSON-LD, the same graph in each, and all of HECTOR in one file as `dump/hector.ttl.gz` (Turtle,
gzipped; 228,272 triples). Also published: the JSON-LD context (`context/hector.jsonld`), the vocabulary of HECTOR's own
terms (`ontology/ontology.json`), the slug ledgers that record how each URI was minted and what
replaced it (`ledger/`), and the index the site searches (`search/index.json`). Counts as of
3 October 2026.

## Using it

Every record has a URI. A browser gets a readable page; a request for JSON gets the record:

```bash
curl -L -H "Accept: application/ld+json" https://w3id.org/hector/commodity/saffron
curl -L -H "Accept: application/ld+json" https://w3id.org/hector/unit/pound
curl -L https://w3id.org/hector/context          # the JSON-LD context
```

| URI | gives |
|---|---|
| <https://w3id.org/hector/> | the site: search by any attested spelling |
| <https://w3id.org/hector/commodity/saffron> | a commodity |
| <https://w3id.org/hector/unit/pound> | a unit |
| <https://w3id.org/hector/ontology> | HECTOR's own terms |
| <https://w3id.org/hector/context> | the JSON-LD context, layered on Linked Art's |
| <https://w3id.org/hector/about> | this repository |

**Shape of a record.** Commodities are Linked Art `Type`s and units `MeasurementUnit`s. A record
carries its names (`identified_by`: the preferred term and every attested spelling, with
`validFrom` / `validThrough` where dated and a `phoneticKey` in IPA, read with late Middle English
letter values for matching variants); its description (`referred_to_by`); its identifiers
(`equivalent` for an exact AAT or Wikidata match, `closeMatch`, `broader`, `classified_as`); links
to related records (`related`, `compoundOf`, `material`, `originPlace`) and to the London Customs
Accounts glossary (`exactMatch`); a count of occurrences in the London customs accounts
(`attestationCount`); and, for priced goods, `taxation`: each rate in pence and £ s d, per a
quantity of a unit, with the book's dates and the source line quoted. Units add `quantityKind`,
`definedAs` and, where it can be stated, `conversionToGram` (a modern reference value). The
worked example of the shape is `tests/fixtures/exemplar/commodity/saffron/ontology.json`.

## Sources and how it is built

- **Commodities and units** come from the curated glossary of the
  [London Customs Accounts](https://docuracy.github.io/London_Customs_Accounts/) project (IHR),
  read from that repository by path.
- **Rates** are parsed from Stuart Jenks's transcriptions of the Tudor Books of Rates.

The pipeline (Python, in `tools/`; everything is written to the git-ignored `build/` first):

```bash
.venv/bin/python -m tools.rates.parse_bor           # Books of Rates -> build/rates/
.venv/bin/python -m tools.export.export_hector      # LCA glossary -> build/site/commodity/, build/ledger/
.venv/bin/python -m tools.units.build_units         # -> build/site/unit/, build/ledger/units.tsv
.venv/bin/python -m tools.rates.link_rates          # rates onto commodities and units; qualified records
.venv/bin/python -m tools.site.build_search_index   # -> build/site/search/index.json
.venv/bin/python -m tools.site.build_rdf            # -> ontology.ttl / ontology.rdf beside each record, dump/
node tools/site/build_fuzzy.mjs build/site          # -> build/site/search/fuzzy.*, similar-spelling vectors
.venv/bin/python tools/validate.py --root build/site --online --no-shacl
```

Publishing copies `build/site/{commodity,unit,context,ontology,search,dump}` and `build/ledger/*.tsv`
into the repository root (PLAN.md §3 has the steps). Pushing to `main` publishes.

**Validation.** `tools/validate.py` checks every document against the context, the vocabulary and
the URI policy, and with `--online` dereferences every external identifier (Getty refuses
GitHub's runners, so AAT is checked only in local runs). `pytest tests/` proves each check can
fail. CI runs both on every push and pull request, and weekly, to catch identifiers that stop resolving.

## Not yet

- No tagged release or DOI: please do not cite.
- The URIs negotiate JSON-LD only: Turtle and RDF/XML are files to fetch directly
  (`https://docuracy.github.io/hector/commodity/saffron/ontology.ttl`) until the w3id redirect
  rules are extended.
- The 1604 Book of Rates is parsed but not published (it waits on its commodities being restored
  to the LCA glossary).
- Sources beyond London: other trades, places and languages. HECTOR is built to take them, and
  proposals are welcome. Images from museum and Portable Antiquities collections remain an aim.
- **No links to [QUDT](https://qudt.org/) or other vocabularies of modern units, by design**: those define today's
  standard units, whereas historical units varied from place to place and over time, so a link
  would assert an equivalence the sources do not support. Each unit gives its own sourced
  definitions and conversions instead.

Plans and decisions: [PLAN.md](PLAN.md) and [issue #2](https://github.com/docuracy/hector/issues/2).

## Citing HECTOR

Not yet, please: HECTOR is an alpha. From the first tagged release, cite its Zenodo DOI;
[CITATION.cff](CITATION.cff) supplies the metadata (GitHub's "Cite this repository"), and
[CREDITS.md](CREDITS.md) lists contributor roles (CRediT). Release steps: [docs/release.md](docs/release.md);
changes: [CHANGELOG.md](CHANGELOG.md).

## Contributing and credits

Corrections are welcome as [issues](https://github.com/docuracy/hector/issues/new?template=correction.yml)
(a GitHub account is required; every record on the site has a link that opens one with its URI
filled in). The records are
generated, so please read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a change to one.
[CREDITS.md](CREDITS.md) credits every source HECTOR draws on, with its terms.

## Licence

- **Data** (commodity, unit and rate records, ledgers, vocabulary): **CC BY 4.0**, see
  [LICENSE-DATA](LICENSE-DATA), which says whom to credit (HECTOR, Stuart Jenks's
  transcriptions, and the London Customs Accounts project).
- **Code**: MIT, see [LICENSE](LICENSE).

## Design principles

- **Stable identification**: each entity has a URI that dereferences to its own description
  (stable from the first tagged release; during the alpha, URIs may still change).
- **Interoperability**: JSON-LD aligned with Linked Art and CIDOC-CRM, extended by a small
  `hector:` vocabulary.
- **Variation kept, not normalised away**: every attested spelling stays on its record, dated
  where the source allows, with a phonetic key for matching.
- **Linked catalogues**: commodities, units and rates refer to one another by URI.
- **Sustainability**: namespace anchored at w3id.org, static files on GitHub Pages, no server.

![hector_model_diagram](https://github.com/user-attachments/assets/1b61207b-0101-43c9-b905-f42ef3f78400)

## _Conceptual Inspiration_

_The acronym **HECTOR** is a respectful nod to the philosopher [**Héctor-Neri Castañeda**](https://en.wikipedia.org/wiki/H%C3%A9ctor-Neri_Casta%C3%B1eda), known for his work on formal semantics, reference, and context-sensitive meaning._

_While unrelated in scope, HECTOR’s approach to precise, dereferenceable identifiers for commodities and units parallels Castañeda’s interest in rigorous systems for identifying and distinguishing entities across contexts. Just as quasi-indexicals in philosophy track identity across shifting perspectives, HECTOR accommodates historical and linguistic variation, so that “saffron” in one source is linked unambiguously to “crocus”, “zaffranus” or “seferone” in others._
