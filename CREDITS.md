# Credits

HECTOR (Historical Economic Commodities: Terminologies, Ontologies & Rates) is built and
maintained by Stephen Gadd ([docuracy](https://docuracy.co.uk)). Its data are published under
[CC BY 4.0](LICENSE-DATA) and its code under the [MIT licence](LICENSE). It draws on the sources
below; each is credited here, with the terms on which it is used.

**HECTOR is an alpha**: please do not cite it yet (see the [README](README.md)).

## The transcriptions: Stuart Jenks

Every commodity, spelling and rate in HECTOR derives from **Stuart Jenks's transcriptions** of
the London customs accounts (1380–1560) and of the Tudor Books of Rates of 1507, 1545 and 1558,
with his index of subjects to the Books of Rates. He has licensed the transcriptions as
reproduced in these datasets, and all data derived from them, under CC BY 4.0. His editions are
published by the [Hansischer Geschichtsverein](https://www.hansischergeschichtsverein.de/london-customs-accounts);
the editions themselves, as publications, are not part of that licence or of HECTOR.

Credit, as he asked: *"Derived from Stuart Jenks's transcriptions of the London customs accounts
and the Tudor books of rates. Licensed CC BY 4.0."*

## The glossary: the London Customs Accounts project

HECTOR's commodities and units, their descriptions, groupings and qualifiers, and the counts of
how often each occurs, come from the curated glossary of the
[London Customs Accounts](https://docuracy.github.io/London_Customs_Accounts/) project
(Institute of Historical Research, University of London; AHRC/DFG *Unlocking Upcycled Medieval
Data*): Colson, J., Scheltjens, W., Benbow, E., Gadd, S., & Grove-Gordillo, M. The glossary's
curation, by Eliot Benbow and Maria Grove-Gordillo among others, is what makes the commodities usable. Its data are CC BY
4.0. Each HECTOR record links back to its glossary entry (`exactMatch`), and the glossary links
to HECTOR in return.

The site's similar-spelling search uses that project's **character encoder** (its weights,
`search/encoder.json.gz`, and its JavaScript, `js/fuzzy_encoder.js`), copied unmodified.

## External identifiers

Records quote identifiers and labels from these vocabularies, which keep their own terms:

- **Getty Art & Architecture Thesaurus (AAT).** *Contains information from the J. Paul Getty
  Trust, Getty Research Institute, Art & Architecture Thesaurus, which is made available under
  the ODC Attribution License.* ([ODC-By 1.0](https://opendatacommons.org/licenses/by/1-0/))
- **Wikidata**: [CC0](https://creativecommons.org/publicdomain/zero/1.0/).
- **QUDT** (units and quantity kinds): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/),
  [qudt.org](https://qudt.org/).

No OpenStreetMap or OpenHistoricalMap data (ODbL) are included.

## Models and infrastructure

- **[Linked Art](https://linked.art/)**, on **[CIDOC-CRM](https://cidoc-crm.org/)**: the data
  model and JSON-LD context HECTOR's records are written in.
- **[w3id.org](https://w3id.org/)** (the Permanent Identifier Community Group): HECTOR's
  persistent URIs.
- **GitHub Pages**: hosting.

The phonetic keys on every spelling are HECTOR's own (`tools/phonetics/ipa.py`, a reading with
late Middle English letter values).

## Descriptions and dictionaries

Many descriptions, inherited from the glossary, quote or summarise standard reference works
(the *Oxford English Dictionary*, the *Middle English Dictionary*, the Getty AAT's scope notes,
and others), each cited in the description where it is used. They are quoted for reference; the
works themselves are not part of HECTOR's data or licence.
