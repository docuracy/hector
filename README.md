# HECTOR
## Historical Economic Commodities: Terminologies, Ontologies, & Rates

## Objectives

- Facilitate the work of the [IHR AHRC/DFG London Customs Accounts Project](https://www.history.ac.uk/research/history-policy/unlocking-upcycled-medieval-data) by building a digital catalogue of historical traded commodities. This will be based initially on Tudor Books of Rates transcripts (ed. Stuart Jenks), but should be extensible to other sources including the medieval London Customs Accounts.
- Represent weights and measures (units, including currencies) used in taxation, linked and categorised.
- For permanent, stable URIs, and dereferenceable, interoperable terms, use **w3id.org** redirects, e.g.:  `https://w3id.org/hector/` as the namespace base.
- Develop an extensible schema in the form of a JSON-LD Context Document  
    - Namespace custom terms as `hector:`.  
    - Extend the LinkedArt schema for alignment with CIDOC-CRM (museum/heritage standard).
    - Include attested forms in English and Latin, extensible to other languages.
    - Record normalised phonetic keys (arrays) for variant spellings to aid matching.
    - Allow temporal scoping for all terms.
    - Link commodities, units, images, and names to external authorities and vocabularies (for example Wikidata, Lexvo, Getty AAT, QUDT).
    - Commodities will be implicitly linked to **categories** and **subcategories** from reputable LOD vocabularies (Getty AAT, Wikidata).
    - Enable linking to images with persistent identifiers (museum collections, UK Portable Antiquities Scheme).
- Build phonetically-searchable interface.

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
