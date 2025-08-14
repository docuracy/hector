# HECTOR
## Historical Economic Commodities: Terminologies, Ontologies, & Rates

## Objectives

- Facilitate the [IHR AHRC/DFG London Customs Accounts Project](https://www.history.ac.uk/research/history-policy/unlocking-upcycled-medieval-data) by building a **digital catalogue** and **controlled vocabulary** of historical traded commodities. This will be based initially on Tudor Books of Rates transcripts (ed. Stuart Jenks), but should be extensible to other sources including the medieval London Customs Accounts.
- Build a parallel catalogue of historical weights and measures (i.e. units, including currencies) used in trade and taxation, linked and categorised.
- Embed a **glossary** of definitions in the structured catalogue.
- Record customs Rates (cost per unit of commodity) with full temporal metadata, linking each rate to the relevant commodity and unit.
- Associate commodities and units with external authorities (e.g. Wikidata, Lexvo, Getty AAT, QUDT) and persistent image identifiers (e.g. museum collections, UK Portable Antiquities Scheme).
- Provide permanent, stable URIs for all terms through **w3id.org** redirects, using `"hector": "https://w3id.org/hector#"` as the namespace base.
- Build a phonetically-searchable and dynamically-linked browser interface, hosted sustainably beyond the life of the project on GitHub Pages.


![hector_model_diagram](https://github.com/user-attachments/assets/1b61207b-0101-43c9-b905-f42ef3f78400)


## Design Principles

- **Stable Identification** – Each entity has a permanent URI and machine-readable definition.
- **Interoperability** – JSON-LD data aligned with LinkedArt and CIDOC-CRM, extended via a dedicated hector: namespace.
- **Context Richness** – Entities may carry temporal scope, language variants (English, Latin, others), phonetic keys for matching, and implicit links to categories and subcategories from reputable LOD vocabularies (e.g. Getty AAT, Wikidata).
- **Discoverability** – Phonetic indexing and variant forms support cross-source matching.
- **Dual Catalogue Coherence** – Commodities, units, and rates are linked and cross-referenced to ensure consistent navigation and data integration.
- **Extensibility** – Schema and controlled vocabulary designed to accommodate additional geographic zones, time periods, currencies, languages, and measurement systems.
- **Sustainability** – Namespace anchored at w3id.org, static resources hosted on GitHub Pages.

## _Conceptual Inspiration_

_The acronym **HECTOR** is a respectful nod to the philosopher [**Héctor-Neri Castañeda**](https://en.wikipedia.org/wiki/H%C3%A9ctor-Neri_Casta%C3%B1eda), known for his work on formal semantics, reference, and context-sensitive meaning._

_While unrelated in scope, HECTOR’s approach to precise, dereferenceable identifiers for commodities and units parallels Castañeda’s interest in rigorous systems for identifying and distinguishing entities across contexts. Just as quasi-indexicals in philosophy track identity across shifting perspectives, HECTOR accommodates historical and linguistic variation, ensuring that “saffron” in one manuscript can be linked unambiguously to “croco” or “crocos” elsewhere._

---

### Test Persistent URLs using a Browser

- **Root**: [https://w3id.org/hector/](https://w3id.org/hector/) - User Interface (searchable index)
- **About**: [https://w3id.org/hector/about/](https://w3id.org/hector/about/) - links back here
- **Context**: [https://w3id.org/hector/context](https://w3id.org/hector/context) - JSON-LD Context Document
- **Commodity Example**: [https://w3id.org/hector/commodity/saffron](https://w3id.org/hector/commodity/saffron) - pre-loaded in the User Interface
- **Unit Example**: [https://w3id.org/hector/unit/mass/pound](https://w3id.org/hector/unit/mass/pound) - pre-loaded in the User Interface

### Programmatic JSON Request Examples

#### Context Document

```bash
curl -H "Accept: application/ld+json" -L "https://w3id.org/hector/context/"

```

#### Commodity

```bash
curl -H "Accept: application/ld+json" -L "https://w3id.org/hector/commodity/saffron"

```

#### Unit

```bash
curl -H "Accept: application/ld+json" -L "https://w3id.org/hector/unit/mass/pound"

```
