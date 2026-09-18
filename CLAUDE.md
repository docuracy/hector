# CLAUDE.md — HECTOR

**HECTOR** (Historical Economic Commodities: Terminologies, Ontologies, & Rates) is a Linked
Data catalogue of historical traded commodities, units of measure and customs rates, served as
static JSON-LD from GitHub Pages behind the persistent namespace `https://w3id.org/hector/`.
It is the intended publication venue for the commodity glossary built in the sister project,
the **London Customs Accounts** (LCA), at `/home/stephen/PycharmProjects/London_Customs_Accounts`.

Owner: Stephen Gadd (`docuracy` on GitHub). Remote: `github.com/docuracy/hector`, public,
default branch `main`.

---

## 1. Start here: the plan

- **`PLAN.md`** (this repo) is the working plan: ordered tasks, owners, status, what to do
  next. Keep it current as work lands; it is the file to update, not the issue.
- **Issue #2** — <https://github.com/docuracy/hector/issues/2> — *"How far can HECTOR get in
  the remaining six months? Assessment, task list and timetable"* (2026-09-15). The evidence
  and reasoning behind the plan: the state of the glossary against HECTOR's model, why rates
  force a decision on qualified commodities, the two-gazetteer problem, the licensing audit,
  scenarios, 25 numbered tasks, timetable, risks.
  - The issue **body was revised in place** to absorb the correction comment beneath it. The
    body is authoritative. The comment's tasks **8a–8d are the body's tasks 8–11**; do not
    treat them as additional tasks.
  - Several of its numbers have since been corrected; see `PLAN.md` §"Corrections to issue
    #2". Where the two disagree, `PLAN.md` wins, and the reason is recorded there.
- **Issue #1** — *"Parse Books of Rates"* (2025-08-17): the original rates checklist. Its
  ticked item "Parse tabular Rates for 1604 from `.doc` into TSV" has **no TSV on disk** in
  the LCA repo (verified 2026-09-18).

The one-line version: the glossary content is largely ready; HECTOR's own foundation (the
JSON-LD context and URI scheme) is broken and must be fixed before anything is exported at
scale; the critical path then runs through the Jenks licence, an exporter, rate extraction and
a commodity-provenance place list.

---

## 2. What is in this repo (as of 2026-09-18)

46 commits 2025-08-13 → 2025-08-17 (the proof of concept), then Phase 0 from 2026-09-18.

```
index.html                 SPA: shows ?path=, fetches the JSON for it, renders with a JSON viewer
js/phonemize.js            5.6 MB UMD build of hans00/phonemize (English G2P for the IPA display)
css/index.css              5 lines
context/hector.jsonld      JSON-LD 1.1 context: HECTOR's terms only, used AFTER the Linked Art
                           context (documents: "@context": [linked-art.json, hector context])
ontology/ontology.json     the vocabulary: every hector: term with _label + rdfs:comment
commodity/saffron/ontology.json   the only commodity: an ILLUSTRATIVE Linked Art Type
unit/mass/ontology.json           unit dimension (a Type)
unit/mass/pound/ontology.json     the only unit (MeasurementUnit, illustrative)
shapes/hector.shacl.ttl    SHACL shapes the validator applies to the expanded graph
tools/validate.py          the validator (task 21); tests/test_validate.py proves each check fires
tools/contexts/linked-art.json    vendored Linked Art context, so validation is offline/deterministic
tools/rates/parse_bor.py   Books of Rates parser (task 15); writes ONLY to build/rates/ (ignored)
docs/uri-policy-draft.md   draft of decision D3, for Stephen
.github/workflows/validate.yml    CI: validator --online + pytest, on push/PR and weekly
LICENSE                    MIT (code). The DATA licence is undecided; see §6
```

`index.html` loads Bootstrap and a JSON viewer from jsDelivr, Roboto from Google Fonts. It
describes a Dexie + Fuse.js phonetic search that does not exist yet.

### Convention: one entity = one directory with an `ontology.json`

`<kind>/<path>/ontology.json`. The URI `https://w3id.org/hector/<kind>/<path>` resolves to it
(next section). New entities must follow this, or they will not dereference.

---

## 3. How it is served (the w3id redirect)

GitHub Pages serves `main` at the repo root → `https://docuracy.github.io/hector/`.

**Pushing to `main` publishes immediately**, to a persistent namespace others may cite.
Stephen is content for Phase 0 work to go straight to `main` (2026-09-18). Anything
Jenks-derived stays in `build/` (git-ignored) until the permission lands; see §6.

The redirect rules are **not in this repo**. They live in `perma-id/w3id.org` at
`ids/hector/.htaccess` (read it with
`gh api repos/perma-id/w3id.org/contents/ids/hector/.htaccess --jq .content | base64 -d`).
Changing them needs a PR to that repository. Current behaviour (probed 2026-09-18):

| request | goes to |
|---|---|
| `/about` | the GitHub repo |
| `/context` | `context/hector.jsonld` |
| any path, `Accept: application/json` or `application/ld+json` | `<path>/ontology.json` (404 if absent) |
| any path, anything else | `index.html?path=<path>` (always 200, even for entities that do not exist) |

RDF/XML (`ontology.owl`) is commented out in the `.htaccess`. `/hector/` itself with a JSON
Accept header 404s (`//ontology.json`).

---

## 4. Known defects in the foundation (verified 2026-09-18, with PyLD)

Fix these before generating thousands of files from the exemplars, or every generated file
inherits them. They are tasks F1–F5 in `PLAN.md`. **Status 2026-09-18: 1, 3 and 5 are fixed;
2 and 4 wait on decision D3** (`docs/uri-policy-draft.md`). The description below is kept as the
record of what was wrong; `tests/fixtures/legacy/` holds the original files, and the validator
must keep rejecting them.

1. **`context/hector.jsonld` is invalid JSON-LD.** A conforming processor rejects it
   outright, so nothing HECTOR serves can be processed as JSON-LD today:
   - term definitions contain `rdfs:label` / `rdfs:comment` keys, which are not allowed in a
     term definition (*"a term definition must not contain rdfs:label"*). Documentation of
     terms belongs in a separate vocabulary document, not in the context;
   - `hector:roleAttestedVariant` / `roleModernLemma` / `roleArchaicForm` are compact-IRI
     terms mapped to *different* IRIs (`…#attested_variant`, …). JSON-LD 1.1 forbids that
     (*"term in form of IRI must expand to definition"*).
2. **Entity URIs do not dereference.** The prefix is `"hector": "https://w3id.org/hector#"`,
   so `"@id": "hector:commodity/saffron"` expands to `https://w3id.org/hector#commodity/saffron`
   — a fragment. HTTP drops the fragment, so the identifier resolves to the site root, not
   to saffron. The same applies to units and to `hector:taxation/...`.
3. **The Linked Art alignment exists only in name.** The context declares
   `"la": "http://linked.art/ns/v1/"` and the data uses `la:Type`, `la:label`,
   `la:identified_by`, `la:classified_as`, `la:Name`, `la:content`, `la:language`. Real Linked
   Art maps these to CIDOC-CRM (`Type` → `crm:E55_Type`, `identified_by` →
   `crm:P1_is_identified_by`, `classified_as` → `crm:P2_has_type`, `Name` →
   `crm:E33_E41_Linguistic_Appellation`, `content` → `crm:P190_has_symbolic_content`,
   `_label` → `rdfs:label`), and its own `la:` prefix is `https://linked.art/ns/terms/`.
   HECTOR's `la:` IRIs are made-up URIs that no one else uses. Linked Art also expects
   `language` to be an entity (an AAT language concept), not the string `"la"`.
4. **Two namespaces for one vocabulary.** LCA's `docs/api/context.json` declares
   `"hector": "https://w3id.org/hector/ontology#"` and already publishes `hector:compoundOf`
   under it (3 glossary entries: `arblast threde`, `awl blade`, `crossbow lath_2`; issue #2
   says 4). HECTOR's own context uses `https://w3id.org/hector#` and does
   not define `compoundOf` at all.
5. **The exemplars contain placeholder identifiers**: `aat:300123456` ("foodstuff"),
   `lexvo eng-1234` / `lat-5678`, `finds.org.uk/images/12345.jpg`,
   `collection.museum.org/object/6789`, and a 1574 Book of Rates (the project holds 1507,
   1545, 1558 and 1604). Treat `saffron` as a **shape**, never as data. One role is the bare
   string `"modern_lemma"`, which expands to the relative IRI
   `https://w3id.org/hector/commodity/modern_lemma`. Also wrong in saffron:
   - `originPlace` is labelled London but uses GeoNames `2635167`, which is the **United
     Kingdom** (Wikidata Q145); London is `2643743` (Q84). Its `sameAs` is a Wikidata *page*
     URL (`www.wikidata.org/wiki/Q84`), not the entity URI (`www.wikidata.org/entity/Q84`);
   - `aat:300010621` is both saffron's `sameAs` and its `classified_as` "spice": one of the
     two is wrong;
   - the rate uses `schema:validFrom` although `hector:validFrom` is also defined, and
     `priceCurrency: GBP` (an ISO 4217 code for modern sterling) for a pre-decimal rate.
   In `unit/`, `unit/mass` is a dimension but is typed `hector:Unit`.
   - Found when the ids were dereferenced (2026-09-18): `aat:300010621` **does not exist** (AAT
     returns 404), and `wd:Q12057` is **Uloboridae, a spider family**, not saffron. Saffron is
     AAT `300013073` and Wikidata `Q25434`. Nothing in the old files carried a label to
     compare against, so neither was detectable; the validator now requires a `_label` on
     every external reference and `--online` compares it with the authority's.

   (Checked 2026-09-18 by the `hector-08` session, and the GeoNames ids by this one, via
   Wikidata P1566.)

To check a context/document yourself, PyLD (`pip install PyLD`) and
`jsonld.expand(doc, {'base': 'https://w3id.org/hector/<path>'})` reproduce all of the above.

---

## 5. What HECTOR needs from the LCA repo, and where it is

LCA path: `/home/stephen/PycharmProjects/London_Customs_Accounts` (below: `LCA/`). Its own
`CLAUDE.md` describes that project in depth; read it before relying on any file there.

**Read from LCA; do not write to it.** Several Claude sessions share that one checkout (stage
explicit paths only, never rewrite history there). If something in LCA needs changing, message
its session (see §8) or ask Stephen. HECTOR tooling should read LCA files by path and write
only inside this repo.

### Commodities: the glossary

`LCA/docs/data/glossary_data.json` (tracked, 5.5 MB). Top-level keys: `version`, `generated`,
`metadata`, `entries`, `qa_identifiers`.

- `entries` — **2,452** concepts, keyed by headword. Field reference in LCA `CLAUDE.md`
  ("Entry Data Model"). The ones that map onto HECTOR:
  - `f` forms `[{t, p, s, w, v}]` → `identified_by` names (`t` text, `p` phonetic, `s`
    source ids, `w=1` headword). 19,411 forms; `p` is filled on only ~9%.
  - `d` description → gloss.
  - `aat` `[{id, label, source?, broader?, match?, uncertain?, note?}]` → `sameAs` /
    `classified_as` / `closeMatch`. **Not all of these are identifications** (`PLAN.md`
    correction C1). AAT `300386154` *unidentified (information indicator)* is a placeholder
    meaning "not identified". It appears on its own, beside real concepts (68 entries), and
    even with `match: 'close'` (18 entries). **Drop every item with that id before mapping
    by kind.** After that: 1,334 entries have an exact/close concept, 722 broader-only (a
    classification, never `sameAs`), 395 nothing, and 1 (`bacon`) has `aat: []`.
    `chest` has an item with both `match: 'close'` and `broader: true`, so the mapping needs
    a stated precedence. `source: 'wikidata'` marks a Wikidata Q-id rather than an AAT id.
  - `groups` — 33 AAT-derived commodity groups (e.g. `Textiles & cloth`,
    `Units, weights & measures` = 222 entries, `Unidentified` = 407).
  - `q` qualifiers, `materials`, `geo` (entry provenance, 24 entries, ids like
    `whg:place:wd:Q2634`), `compoundOf`, `related`, `x` cross-references.
- `metadata.rekey_history` / `merge_history` / `deletion_history` / `duplicate_history`:
  **glossary keys are not stable**, they get renamed and merged. A HECTOR URI minted from a
  key needs a ledger mapping old keys to URIs, or merges will break citations.
- `metadata.licence` states **CC BY-SA 4.0**; this conflicts with the licensing strategy
  (§6). Do not copy it into HECTOR output.

Related LCA files:

| file | what |
|---|---|
| `docs/data/concept_attestation.json` | `{concept_key: count}` corpus attestations; 1,907 of 2,452 attested |
| `docs/data/qualifiers.json` | canonical qualifier store: `{schemaVersion, _note, canonicals}`, 548 canonicals `{label, lang, forms, gloss, memo, reviewed, helpWanted, …}`. `_note`: colours/weaves/sizes/quality/materials reviewed; **provenance pending** |
| `docs/data/qualifier_attestation.json` | per-qualifier corpus counts |
| `docs/data/concept_definitions.json` | harvested external definitions. **Mixed licences (CC BY-SA, CC0, two scraped sources with no licence): do not export into HECTOR** |
| `process/generate_jsonld.py` + `docs/api/context.json` | LCA's own JSON-LD for glossary entries at `https://w3id.org/mlca/glossary/{key}`; the only current use of `hector:` |
| `process/commodity_parser/` | the machine tagger that annotates cargo text against the glossary |

### Rates: the Books of Rates (Jenks transcriptions)

`LCA/data/bor/` (tracked):

| file | rows | columns |
|---|---|---|
| `Jenks Books of Rates final 3 June 2024_1507.tsv` | 335 | `commodity`, `rate` |
| `…_1545-Inward.tsv` / `…_1545-Outward.tsv` | 810 / 49 | same |
| `…_1558-Inward.tsv` / `…_1558-Outward.tsv` | 1,154 / 71 | same |
| `Jenks Book of Rates 1604.doc` / `.html` | — | **not yet parsed to TSV** |
| `Jenks index of subjects English books of rates_commodities.tsv` | 1,376 | `commodity`, `definition`, `pages` |
| `…_crossrefs.tsv` | 5 | `commodity`, `target`, `pages` |
| `…_units.tsv` | 73 | `unit`, `commodity`, `amount` (e.g. `bale / comyn / 3 cwt at 112 lb./cwt`) |

Total rated rows in the five TSVs: 2,419. The `commodity` cell fuses commodity, qualifier and
unit (`Canvas Normandy whyte the hundreth elles`); `rate` is £ s d text, sometimes bracketed
(`[13s 4d]`, an editorial supply). Nothing parses these into price/unit yet; the glossary
builder (`process/bor_phonetic_glossary.py`, `process/glossary_parser.py`,
`process/bor_extraction.py`) mines them for headwords only.

### Units

No unit catalogue exists anywhere yet. Sources:
- the 222 glossary entries in group `Units, weights & measures`;
- corpus unit annotations in `LCA/docs/data/ladings/<vol>.json.gz`: spans with
  `"type": "unit"` and `matches: [{key, headword, groups}]`, where `key` is a glossary key
  (357 distinct unit concepts matched, measured 2026-09-15);
- `…_units.tsv` above for conversion statements.

### Places

Two largely disjoint populations (issue #2 §5):
- **Ship home ports** (LCA issue #46 gazetteer): `docs/data/index_places_lp.tsv` (350 rows,
  WHG LP-TSV), `whg_confirmed_matches.tsv` (374 matches), `whg_match_coordinates.tsv`
  (368 coordinate rows; `source` column and identifier prefix tell you the licence:
  `wd` CC0, `gn` CC BY, `iv` project's own, `ohm`/`osm` ODbL). This work is **active in LCA
  sessions** and has moved since 2026-09-15; re-read before relying on counts. Stephen's
  standing rule there: nobody edits `index_places_lp.tsv` without his say-so.
- **Commodity provenance**: `geo` on glossary entries and qualifier canonicals (Wikidata
  Q-ids). Incomplete; this is the list the rates need.

### Phonetics

`LCA/process/helpers/phonetic.py` (Epitran, PanPhon, Symphonym singletons),
`process/build_ipa.py`, `process/ipa_index.py`, `process/symphonym/`. Reuse these to fill
`hector:phoneticKey` rather than building a second stack.

---

## 6. Licensing: the binding constraint

`LCA/documentation/data_licensing_strategy.md` is the reference. As of 2026-09-14:

- **§1, permission from Stuart Jenks, is unticked.** The glossary, the rates and every form
  are derived from his transcriptions. Until it is granted **nothing Jenks-derived is
  published**, which here means: not pushed to `main`.
- The preferred data licence is **CC BY 4.0** (option 2 of §1a); CC BY-SA is still open.
  The glossary file's own `metadata.licence` says CC BY-SA. The repo `LICENSE` is MIT, which
  covers code. The data licence is a decision for Stephen, not something to infer.
- **ODbL (OSM, OpenHistoricalMap) must not enter HECTOR data**: share-alike would make CC BY
  indefensible (LCA issue #43 removed OSM geometry for this reason). Place coordinates come
  from Wikidata P625 (CC0) or GeoNames (CC BY), or are omitted.

---

## 7. Working here

- Python: `.venv/` (ignored) from `requirements.txt`: `python3 -m venv .venv &&
  .venv/bin/pip install -r requirements.txt`. Stephen has standing permission for package
  installs (say afterwards what went where). Do not import from LCA as a package; read its files.
- Before committing any `ontology.json`, context or vocabulary change:
  `.venv/bin/python tools/validate.py --online` (0 errors; the `ENTITY-URI` warnings are D3)
  and `HECTOR_ONLINE=1 .venv/bin/python -m pytest tests/ -q`. CI runs both.
- New data documents use `"@context": ["https://linked.art/ns/v1/linked-art.json",
  "https://w3id.org/hector/context"]`, put a `_label` on every external reference, and declare
  any new `hector:` term in `ontology/ontology.json` first (the validator enforces all three).
- Rates: `.venv/bin/python -m tools.rates.parse_bor` → `build/rates/` (`rates.jsonl`,
  `rates.tsv`, `1604_raw.tsv`, `report.md`). Never commit that output (§6).
- British English in prose and documentation.
- Commits: stage explicit paths, never `git add -A` (`.idea/` is untracked and should stay
  out). Never amend/rebase/reset shared history; fix mistakes in the next commit.
- Numbers in this file, `PLAN.md` and issue #2 were measured on the dates given. Re-measure
  before building on one. Where a number comes from issue #2 and was not re-checked, say so.
- A generated catalogue of thousands of files is a public, citable artefact. Before any
  bulk export: a valid context (F1), a URI policy (task 3) and a validator (task 21) that
  has been shown to *fail* on a bad document.

---

## 8. Contact with the LCA side

Other Claude sessions work in the LCA checkout; `ListAgents` lists them (names like
`london-customs-accounts-NN`). For an LCA-side change, a question about a file's meaning, or
news that something there has moved: message that session, or ask Stephen. When you finish
something that changes what the LCA side should do (e.g. the namespace decision, which
changes LCA's `docs/api/context.json`), tell it rather than editing its files.
