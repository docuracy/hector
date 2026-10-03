# Contributing to HECTOR

Thank you for looking. HECTOR is an **alpha**: comments and corrections are exactly what it
needs now, before the first release fixes its URIs.

## The records are generated: please do not edit them by hand

Every file under `commodity/`, `unit/`, `ledger/`, `search/` and `dump/`, and the `.ttl` and
`.rdf` beside each record, is **built** from two sources and overwritten at every republish:

- the curated glossary of the [London Customs Accounts](https://docuracy.github.io/London_Customs_Accounts/)
  project (commodities, units, spellings, descriptions, identifiers);
- Stuart Jenks's transcriptions of the Tudor Books of Rates (the rates).

A change made directly to a record would be lost. A correction has to reach the source it came
from, so the way to make one is an **issue**.

## Reporting a correction

[Open an issue](https://github.com/docuracy/hector/issues/new?template=correction.yml) with:

- the record's URI (`https://w3id.org/hector/commodity/...` or `.../unit/...`);
- what is wrong: a misidentified commodity, a wrong or missing AAT or Wikidata identifier, a
  spelling that belongs elsewhere, two records that are the same thing, a rate linked to the
  wrong goods, a mistaken conversion;
- your evidence: a source, a dictionary entry, an identifier.

Corrections to commodities and spellings are made in the London Customs Accounts glossary by its
curators and reach HECTOR at the next republish; corrections to rates, units and the vocabulary
are made here.

## Pull requests

Welcome for what is *not* generated: the tools (`tools/`), the validator and its tests, the site
(`index.html`, `js/`, `css/`), the documentation, and HECTOR's own vocabulary
(`ontology/ontology.json`, `context/hector.jsonld`). Every pull request is checked by CI: every
document validated against the context, the vocabulary and the URI policy; external identifiers
dereferenced (Getty's AAT cannot be reached from GitHub's runners, so those are checked only in
local runs); the test suite, which proves each check can fail; and the Turtle, RDF/XML and search
files checked as current. Run the same locally before opening one:

```bash
.venv/bin/python tools/validate.py --online
HECTOR_ONLINE=1 .venv/bin/python -m pytest tests/ -q
.venv/bin/python -m tools.site.build_rdf --root . --check
node tools/site/build_fuzzy.mjs . --check
```

A new term in the vocabulary must be declared in `ontology/ontology.json` before a record uses it
(the validator enforces this). URIs follow [docs/uri-policy.md](docs/uri-policy.md): slugs are
minted once, recorded in the ledger and never recomputed.

## Licence

By contributing you agree that data contributions are published under CC BY 4.0
([LICENSE-DATA](LICENSE-DATA)) and code under MIT ([LICENSE](LICENSE)). See [CREDITS.md](CREDITS.md)
for the sources HECTOR draws on.
