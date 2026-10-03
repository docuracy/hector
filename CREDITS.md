# Credits

HECTOR (Historical Economic Commodities: Terminologies, Ontologies & Rates) was conceived and
built by Stephen Gadd ([docuracy](https://docuracy.co.uk)). Its data are published under
[CC BY 4.0](LICENSE-DATA) and its code under the [MIT licence](LICENSE). It draws on the sources
below; each is credited here, with the terms on which it is used.

**HECTOR is an alpha**: please do not cite it yet (see the [README](README.md)).

## Funding

HECTOR was developed within the project **[Unlocking Upcycled Medieval Data: North Sea
Networks, People, and Commodities in the London Customs Accounts 1380–1560](https://www.history.ac.uk/research/centre-history-people-place-community/unlocking-upcycled-medieval-data)**,
funded by the Arts and Humanities Research Council (AHRC) and the Deutsche
Forschungsgemeinschaft (DFG) under the AHRC–DFG bilateral scheme, as a collaboration between the
Institute of Historical Research, School of Advanced Study, University of London, and
Otto-Friedrich-Universität Bamberg: AHRC grant [AH/Z507179/1](https://gtr.ukri.org/projects?ref=AH%2FZ507179%2F1);
DFG project number [547507634](https://gepris.dfg.de/project/547507634).

## Contributor roles (CRediT)

Roles in the [Contributor Roles Taxonomy](https://credit.niso.org/):

| contributor | roles |
|---|---|
| Stephen Gadd | Conceptualization, Methodology, Software, Data curation, Validation, Visualization, Writing – original draft |
| Stuart Jenks | Resources (the transcriptions every record derives from) |
| Eliot Benbow | Data curation (the London Customs Accounts glossary) |
| María Grove-Gordillo | Data curation (the London Customs Accounts glossary) |
| Justin Colson | Funding acquisition, Supervision |
| Werner Scheltjens | Funding acquisition, Supervision |

## The transcriptions: Stuart Jenks

Every commodity, spelling and rate in HECTOR derives from **Stuart Jenks's transcriptions** of
the London customs accounts (1380–1560) and of the Tudor Books of Rates of 1507, 1545 and 1558,
with his index of subjects to the Books of Rates: his own, otherwise unpublished, transcript
files. He has licensed the transcriptions as reproduced in these datasets, and all data derived
from them, under CC BY 4.0. His printed and online editions are not a source of HECTOR, nor part
of that licence.

Credit, as he asked: *"Derived from Stuart Jenks's transcriptions of the London customs accounts
and the Tudor books of rates. Licensed CC BY 4.0."*

## The glossary: the London Customs Accounts project

HECTOR's commodities and units, their descriptions, groupings and qualifiers, and the counts of
how often each occurs, come from the curated glossary of the
[London Customs Accounts](https://docuracy.github.io/London_Customs_Accounts/) project
(Institute of Historical Research, University of London; AHRC/DFG *Unlocking Upcycled Medieval
Data*): Colson, J., Scheltjens, W., Benbow, E., Gadd, S., & Grove-Gordillo, M. The glossary's
curation, by Eliot Benbow and María Grove-Gordillo among others, is what makes the commodities usable. Its data are CC BY
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
