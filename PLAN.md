# HECTOR: working plan

*Started 2026-09-18. Derived from issue #2 (the assessment, 2026-09-15) plus checks made
since. Issue #2 holds the evidence and reasoning; this file holds the order of work and its
status. Update the status column as tasks land; record corrections in §5 rather than
rewriting history.*

**Goal for the remaining ~6 months (M1 ≈ mid-Sept 2026 → M6 ≈ mid-March 2027, estimate):**
Scenario B, HECTOR as the main publication venue for the glossary, by about M4; Scenario C,
an extensible framework others can build on, in M5–M6. Issue #2 §7 explains both.

Legend: **[E]** engineering · **[C]** curatorial · **[D]** decision (Stephen) · **[X]**
external. **Where** is the repo the work happens in: most inputs come from
London_Customs_Accounts (LCA), and the outputs land here.

---

## 1. Decisions needed first (Stephen)

| # | decision | recommendation | blocks |
|---|---|---|---|
| **1** [X] | **Jenks permission** for derived structured data (LCA `documentation/data_licensing_strategy.md` §1) | **Agreed informally (Stephen, 29 Sep 2026).** Before HECTOR's first publication, get a one-line written confirmation that covers CC BY 4.0 on the derived data (verbatim `original_text` held back). Building continues locally meanwhile | all publication |
| **2** [D] | **Flatten vs compose** qualified commodities (issue #2 §4) | **Decided 29 Sep: flatten only the combinations the Books of Rates price separately** (at most the 391 rate-bearing phrases, not issue #2's ~2,400). Each gets a commodity URI carrying its rates, linked to its base commodity by `skos:broader` *and* `hector:compoundOf`. Corpus cargo records keep composing (concept + qualifiers). No qualifier needs AAT before release. Slugs readable (`canvas-normandy`), per uri-policy open question 2 | 12, 14–17 |
| **3** [D] | **URI and versioning policy** | **adopted 2026-09-18** as drafted: `docs/uri-policy.md`; **amended 29 Sep for units** (below) | every export |
| **D4** [D] | **HECTOR URI vs LCA glossary URI.** Each concept already has `https://w3id.org/mlca/glossary/{key}`. Which is canonical? | **Decided 29 Sep: HECTOR canonical.** LCA keeps its glossary URIs and emits `skos:exactMatch` (not `owl:sameAs`, which would merge LCA-only statements into HECTOR's) to the HECTOR URI. LCA commits the ledger and resolves key → URI at publication; records (incl. pass-2) keep the glossary key | 12 |
| **D5** [D] | **Data licence for HECTOR output** | **Done 29 Sep: `LICENSE-DATA` (CC BY 4.0) + README "Licence".** Decided 29 Sep: CC BY 4.0, the same as LCA (share-alike removed there 22 Sep). Add `LICENSE-DATA` beside the MIT code `LICENSE`, crediting Stuart Jenks's transcriptions of the Books of Rates | 24, 25 |
| **D6** [D] | **Where do the 1604-only commodities live?** (C8: 255 BOR-only entries removed from LCA in e9b5c99) | **Decided 29 Sep: back in the LCA glossary with `scope: "bor1604"`.** Condition: the scope is enforced in ONE place, LCA's glossary loader, so the entries stay out of LCA's parser and public glossary/JSON-LD; and the restore must pass LCA's per-file no-anchor-loss check (adding forms has flipped fuzzy matches corpus-wide before). Curated in the concepts tool, filterable | 1604 half of 15 → 17 |
| **D7** [D] | **Units** (task 18 open questions) | **Done 29 Sep** (units now `unit/<slug>`; `unit/pound` + `unit/dimension/mass` in the repo, `unit/mass` and `unit/mass/pound` deprecation records; validator KIND rule and tests; `quantityKind` a set; `definedAs` adopted in context + vocabulary; ledger re-minted; every general reading in `definedAs`, second readings added for aum, wey, mark, skive, cast; 58 units with definedAs, staging site 0 errors). **Decided 29 Sep:** (a) **no dimension in unit URIs**: `…/unit/<slug>`; dimension is a property of the record, may be multi-valued (sack: mass *and* package) and correctable. The live exemplar `unit/mass/pound` gets a deprecation record → `unit/pound`; `unit/mass` likewise retired. (b) adopt **`definedAs`** and **`hector:each`** into the context and vocabulary. (c) **conflicting conversions are all published**, each a separate statement with source and scope, doubtful ones `exact: false` with a note; nothing is chosen between them. The wey and aum glossary descriptions go to the curators as defects. (d) **task 19 (QUDT/Noback) dropped** | 18, 20, first publication |

**D3, the URI policy.** Adopted 2026-09-18; the full text is `docs/uri-policy.md`. In short:
- entities are **path URIs**, never fragments: `https://w3id.org/hector/commodity/<slug>`,
  `…/unit/<slug>` (dimension dropped from the path 29 Sep, D7), `…/rate/<book>/<id>`;
- vocabulary terms (properties, classes) in **one** namespace shared by both repos. Recommend
  `https://w3id.org/hector/ontology#`, which LCA already emits for `hector:compoundOf`, so
  only HECTOR's context changes. Serve a vocabulary document at `ontology/ontology.json`;
- slugs are minted once and **never derived afresh from glossary keys** (keys are renamed and
  merged; see `metadata.rekey_history`). Keep a committed ledger `glossary key → slug`;
  merges produce a deprecation record that points at the survivor rather than a 404;
- releases are tagged (`vYYYY.MM`), and each entity carries `dcterms:modified` and, when
  retired, `owl:deprecated` + `dcterms:isReplacedBy`.

---

## 2. Phase 0: repair the foundation (this repo, M1), **new since issue #2**

Issue #2 assumed "the schema, the w3id redirects and the browser UI exist and work". The
redirects and UI do; the schema does not (CLAUDE.md §4, verified with PyLD on 2026-09-18).
Generating 2,452 files from the current exemplars would multiply every defect below, so this
phase comes before the exporter.

| # | task | status |
|---|---|---|
| **F1** [E] | Make `context/hector.jsonld` **valid**: remove `rdfs:label`/`rdfs:comment` from term definitions (move them to a vocabulary document); drop or correct the three `hector:role*` compact-IRI terms. Test: PyLD expands both exemplars with no error | **done 2026-09-18**: context is JSON-LD 1.1, HECTOR terms only, layered after the Linked Art context; term docs moved to `ontology/ontology.json`; role terms replaced by `hector:ModernLemma` etc. as `classified_as` concepts |
| **F2** [E] | Fix the **entity URIs** per D3: stop expanding `hector:commodity/…` to `https://w3id.org/hector#commodity/…`. Test: every `@id` expands to a URI that returns 200 through w3id with `Accept: application/ld+json` | **done 2026-09-18**: entity ids are path URIs (`https://w3id.org/hector/commodity/saffron`), rates embedded with fragment ids; `ENTITY-URI` and `DANGLING-REF` are errors in the validator |
| **F3** [E] | Fix the **Linked Art alignment**: either adopt the real Linked Art context (`https://linked.art/ns/v1/linked-art.json`, CIDOC-CRM terms) or stop claiming the alignment. Recommend adopting it: `Type`→`crm:E55_Type`, `identified_by`, `classified_as`, `Name`, `content`, `language` as an AAT language entity. **This is a remodel of the exemplars, not a prefix swap**: the Linked Art context redefines `id`, `type` and `_label` and implies a different document structure | **done 2026-09-18**: adopted. Documents use `[linked-art.json, hector context]`; exemplars remodelled as `Type` / `MeasurementUnit` / `Name` / `MonetaryAmount` / `Dimension` |
| **F4** [E] | **Unify the `hector:` namespace** with LCA (`https://w3id.org/hector/ontology#`); define `compoundOf` in HECTOR's vocabulary. Tell the LCA session if anything there has to change | **done 2026-09-18**: `hector` = `https://w3id.org/hector/ontology#` (as LCA), `hectorid` = `https://w3id.org/hector/`; `compoundOf` declared. LCA needs no change; LCA session told |
| **F5** [E] | Rewrite the **exemplars** without placeholder ids (`aat:300123456`, lexvo `eng-1234`, the fictional images, the 1574 book) and with a real role for the modern lemma. Also fix the saffron errors listed in CLAUDE.md §4.5: London mapped to the UK's GeoNames id, a Wikidata page URL used as an entity, the same AAT id as both sameAs and classified_as, duplicate validFrom terms, GBP for a pre-decimal rate, and a dimension typed as a unit. Saffron must be real data, or be marked as illustrative | **done 2026-09-18**: all three exemplars rewritten with ids checked against AAT/Wikidata/QUDT, flagged `illustrative`. The old AAT id `300010621` does not exist and `Q12057` is a spider family (see C6) |
| **21** [E] | Bring forward from issue #2: a **JSON Schema / SHACL shape and a CI validator**, proved able to fail (run it on the current, broken exemplars first: it must reject them) | **done 2026-09-18**: `tools/validate.py` (+ `--online`) and `shapes/hector.shacl.ttl`, CI in `.github/workflows/validate.yml`. Rejects the pre-Phase-0 files (`tests/fixtures/legacy/`); each check has a mutation test, and two were sabotaged to confirm the tests fail |

Phase 0 complete 2026-09-18.

---

## 3. The main line (issue #2 §8 numbering kept)

### Places (mostly LCA-side work; outputs referenced here)
| # | task | where | status |
|---|---|---|---|
| 4 [E] | Audit the 374 ship-port WHG matches by namespace; quarantine ODbL coordinates | LCA | in progress there (Abbaragh already re-identified in `whg_confirmed_matches.tsv`); check with the LCA session |
| 5 [E] | Re-source ODbL-derived coordinates from `wd`/`gn`, else drop the geometry | LCA | — |
| 6 [C] | Resolve the `ukhc` (4 rows) licence | LCA | — |
| 7 [C] | Re-audit the 281 matches scored ≥96 | LCA | — |
| 8 [E] | Reconcile the ship-port gazetteer (#46 LP-TSV). Contributes only ~27 rows to provenance | LCA | — |
| **9** [C] | **Complete the commodity-provenance place list**: the pending provenance pass over `qualifiers.json`. **Critical path to rates.** Size it first | LCA | — |
| 10 [E] | Reconcile commodity provenance (Wikidata/GeoNames only) | LCA | — |
| 11 [C] | Audit the existing 106 provenance ids: auto-confirmed? are `point`s from P625, not OSM? | LCA | — |

### The exporter (here)
| # | task | status |
|---|---|---|
| **12** [E] | `export_hector.py` (in this repo, reading `LCA/docs/data/glossary_data.json` by path): labels, forms with language tags, identifiers, groups, descriptions, attestation counts. **Map `aat` by kind** (see C1), **after first removing every item with id `300386154`** (it occurs with `match:'close'` in 18 entries and beside real concepts in 68, so a kind-based mapping would otherwise emit `closeMatch` to "unidentified"): exact → `equivalent` (Linked Art's identity link, as in the saffron exemplar); close → `closeMatch`; broader → `broader` (`skos:broader`; on a Linked Art Type, `classified_as` would mean "a kind of type", not "narrower than"); nothing left → no identifier, marked unidentified. State a precedence for items flagged both close and broader (`chest`). Emits the D3 key→slug ledger | **built 2026-09-18**, local only: `tools/export/export_hector.py` → `build/site/` (staging copy of the site, 2,452 commodity records) + `build/ledger/commodities.tsv`. The whole staging site validates (0 errors); identity counts reproduce C1 exactly. Forms carry no language in the glossary, so Names have none (not guessed). Not yet emitted: groups (no IRIs), qualifiers (decision 2), the `p` matching code (not IPA; task 13 gives IPA). **Publishing = copy `build/site/commodity/` + commit the ledger, after task 1** |
| 13 [E] | Phonetic keys from ~9% to 100% of 19,411 forms, reusing LCA `process/helpers/phonetic.py` | **built 29 Sep, local** (`tools/phonetics/ipa.py`, method `lme-letters-v1`): every form read with late Middle English letter values (how the clerks read both languages), ~50 ordered rules, pure Python, no stress; a phoneticKey on 20,933 of 20,935 Names (exporter + qualified records). Chosen by measurement (`tools/phonetics/compare.py`, 18,984 same-concept nearest-neighbour queries): 0.818 against 0.797 bare spelling, 0.797 Epitran lat, 0.769 Epitran eng, 0.777 LCA get_ipa, 0.774 routed by language guess, 0.719 phonemize.js (fra-Latn 0.832 rejected: it wins by silencing inflections). `--check` proven to fail (rule removed: 10 tests + 8,314 stale keys; shuffled rules: nondeterminism). Known weaknesses in the module docstring and PLAN history. Bump METHOD on any rule change |
| 14 [E] | Emit qualified commodities per decision 2 | **built 29 Sep, local** (`tools/rates/link_rates.py`): a combination gets its own record (`commodity/<concept>-<qualifier>`, skos:broader + compoundOf to the base, spellings as written as attested Names) only where the books price it apart -- the same concept at the same unit at different prices with different qualifiers. 680 records over 171 concepts (issue #2: 170 heads). Qualifier spellings joined through LCA qualifiers.json and a light fold (whit/whyte, spruse/sprewce, newcastell/neucastell); some remain split (neucastel/neuecastel). Slugs minted once into `build/ledger/qualified.tsv` |

### Rates
| # | task | where | status |
|---|---|---|---|
| **15** [E] | Parse `LCA/data/bor/*.tsv` into structured rates: split commodity/qualifier/unit out of the fused `commodity` cell; price £ s d → pence + currency; validFrom/validThrough per book; editorial `[…]` kept as a flag; source. 2,419 rows across 5 TSVs. **Also parse 1604** from `Jenks Book of Rates 1604.doc/.html`: LCA had extracted it and deliberately removed it (e9b5c99) as out of LCA's scope; **in scope for HECTOR** (Stephen, 2026-09-18) | here (reads LCA) | parser **done 2026-09-18** (`tools/rates/parse_bor.py`, output in ignored `build/rates/`): 4,063 rows incl. 1,644 from 1604; 3,905 ok / 69 partial / 89 failed (mostly genuine non-rates). Rates and units reliable on samples; the commodity/qualifier split is naive (~15–20% wrong), so match `commodity_text` against the glossary instead (task 16). Emitting waits on task 1; 1604 re-extraction cross-checked against LCA's removed PDF-derived TSVs: 99.6% of inward / 97.8% of outward rates align in sequence, differences are group prefixes, PDF line-break truncation and "see" rows |
| 16 [C] | Reconcile the 141 rate-bearing qualifier phrases that match nothing in `qualifiers.json` | LCA editors | — |
| 17 [E] | Emit `hector:taxation` linked to commodity and unit URIs | here | **built 29 Sep, local, 1507-1558** (1604 waits for D6's LCA-side restore): of 2,419 rows, 1,828 linked (1,540 by the goods at the head of the entry, 14 by a phrase, 274 by a single word elsewhere); 1,031 rates on base commodities, 797 on qualified ones, 341 qualifiers kept in sourceText as not priced apart; NOT linked and listed in `build/rates/link-report.md`: 314 with no glossary spelling (candidate spellings for LCA's curators: Annes sede, Appells, Beffe...), 170 on a spelling two concepts share, 59 no price, 48 no unit. Rate: pence + lsd, per quantity + unit (units ledger), validFrom the book, validThrough the next, the source line quoted in sourceText. Staging site 3,388 documents, 0 errors. Tests `tests/test_link_rates.py` (head-first proven to fail without its rule) |

### Units
| # | task | status |
|---|---|---|
| 18 [E] | Build the unit catalogue: 222 glossary entries in `Units, weights & measures` + 357 corpus-attested unit concepts (ladings `type: unit` spans) + `…_units.tsv` conversion statements | **built 2026-09-19**, local only: `tools/units/build_units.py` → `build/units/` (`catalogue.tsv`, `rates_join.tsv`, `conversions.tsv`, `report.md`) + `build/ledger/units.tsv`. 365 candidate concepts (222 in the group ∪ 353 attested, C9); **248 emitted as units** (212 of the group, 26 attested casks/packing units outside it, 10 rates-only incl. `hector:each`); 127 not units (the tagger types every vessel in `Containers & vessels` as a unit; 10 group entries are instruments/goods). All **79** units the rates parser recognises are joined (60 to glossary units, 19 to rates-only units/`each`), covering all 3,972 rate rows that have a unit. 288 conversion statements with sources: 64 general (52 exact), 224 commodity-specific (units.tsv 73, Books of Rates contents clauses 113, LCA value model 34, LCA duty ratios 4). Dimension assignment (mass/length/volume/count/package) is a hand proposal: see §4 |
| 19 [C] | Align to QUDT and the Digital Noback Project | todo (droppable). Only `pound` carries QUDT/Wikidata ids (kept from the exemplar); dimension documents align to QUDT quantity kinds. The one thing 19 would add that 20 lacks is SI factors for length and volume |
| 20 [E] | Emit `unit/<slug>/ontology.json` (D7; was `unit/<dimension>/<slug>`) with conversion factors where known | **built 2026-09-19** into `build/site/unit/` (run after the commodity export, which rebuilds `build/site/`): 248 MeasurementUnit records + dimension documents for length, volume, count, package. 48 carry `definedAs` (a Dimension: value + HECTOR unit, with its source), 12 mass units a `conversionToGram` chained to the pound avoirdupois. `definedAs` is a **proposed term**: it and a unit sense of `attestationCount` exist only in the staged `build/site/context` and `ontology`, not in the repo. Whole staging site: 0 errors (2,706 docs); units online: 0 errors, 0 warnings |

### Framework and publication
| # | task | status |
|---|---|---|
| 21 [E] | Schema + CI validator | **moved to Phase 0** |
| 22 [E] | Contribution route: PR template, validation on PR | todo |
| 23 [E] | UI for thousands of entities (Dexie + Fuse phonetic search, as `index.html` promises) | todo (droppable) |
| 24 [C] | Credits and licence pages for every source | todo |
| 25 [E] | Deposit + DOI (Zenodo via a GitHub release) | todo |

Critical path: **1 → 9 → 10 → 15 → 17 → 25**, with **F1–F5 → 12** in parallel. If time runs
short, drop 19 and 23 before 21 or 25.

---

## 3a. Parked 29 September 2026 (read this first)

Decisions 2, D4, D5, D6, D7 taken 29 Sep (§1). LIVE: D7 (units at unit/<slug>, deprecation
records for the old paths, definedAs adopted, every conflicting conversion published) and D5
(LICENSE-DATA). LOCAL in build/, Jenks-derived: rates 1507-1558 linked (tasks 14, 17),
680 qualified records, IPA keys (task 13). Run order: parse_bor, export_hector, build_units,
link_rates; staging 3,388 docs, 0 errors; 115 tests. **Blocker: Jenks's written confirmation
(task 1).** Next: the 314 unlinked rate spellings to LCA's curators; D6 (1604 commodities
back into the LCA glossary behind a loader filter); D4 on the LCA side once the ledger is
published; `ciste` needs an LCA history record (export exits 1 on it, by design).

## 4. Where things stand (handoff, 2026-09-18, end of session)

**Done and live on `main`** (CI green; verified over w3id): Phase 0 complete (F1–F5, 21). The
context is valid and layered on Linked Art, the vocabulary is at `/ontology`, and entity URIs
are path URIs that dereference to their own documents (D3 adopted). The validator
(`tools/validate.py`) and its tests prove each check can fail.

**Built locally, not published** (Jenks-derived, so it stays in git-ignored `build/` until
task 1):

| artefact | how to regenerate | state |
|---|---|---|
| `build/rates/` (rates.jsonl/tsv, 1604_raw.tsv, report.md) | `python -m tools.rates.parse_bor` | 4,063 rows incl. 1604; cross-checked against LCA's removed 1604 TSVs |
| `build/site/` (staging site, 2,452 commodity records) | `python -m tools.export.export_hector` | validates 0 errors; online: 3 bad ids, all LCA-side (C7) |
| `build/ledger/commodities.tsv` (slug ledger) | minted by the exporter | **not yet authoritative**: nothing published, so it can still be regenerated. From first publication it is committed and must never be regenerated (docs/uri-policy.md §3) |
| `build/units/`, `build/site/unit/` (unit catalogue + 248 unit records) | `python -m tools.units.build_units` **after** the export (the export wipes `build/site/`) | validates 0 errors; online 0 warnings. Reads `build/rates/rates.jsonl` |
| `build/ledger/units.tsv` (unit slug ledger, with `dimension`) | minted by `build_units` | **not yet authoritative**, as `commodities.tsv`. A minted dimension is kept even if the classification changes (reported), since the path contains it |
| `build/lca-removed-1604/` | `git -C LCA show e9b5c99^:<path>` | LCA's removed 1604 TSVs and pre-filter index, for reference |

**Decisions taken 29 Sep 2026** (see §1): 2, D4, D5, D6, D7 decided; 1 agreed informally.
**Waiting on Stephen:** only the written Jenks confirmation, which gates publication.
- C8 resolved 29 Sep: the 88 are curation, not loss (§5); `successor()` fixed.

**Told to the LCA session** (it may not have acted): the namespace is unified (no LCA change
needed); the three wrong ids (C7); LCA's glossary URIs contain raw spaces.

**Next, needing no decision** (all local, publish only after task 1):
1. ~~**13**~~ built 29 Sep (task row above): LCA's helpers measured WORSE than a purpose-built
   late-Middle-English letter reading, so they were not reused.
2. ~~**18**: the unit catalogue~~ built 2026-09-19 (with 20), local only. Open for Stephen:
   - ~~dimension classification, `definedAs`, `hector:each`~~ **decided 29 Sep (D7)**: no dimension
     in unit URIs (re-mint `build/ledger/units.tsv` as `unit/<slug>`, dimension a multi-valued
     property); adopt `definedAs` and `hector:each`. The unit sense of `attestationCount` rides
     with `definedAs`;
   - the hand lists `NOT_UNITS` (e.g. `weight`, ambiguous), `CONTAINER_GOODS`, `PACKING_INCLUDE`;
   - conflicts in `conversions.tsv` (wine **barrel** 1/6 vs the later statutory 1/8 tun; **butt**
     charged like a tun vs the glossary's ½ tun; **mark** 20 pieces vs 2 dozen; **wey**
     self-inconsistent; **aum** ⅓ vs ⅕): **decided 29 Sep (D7): publish every reading as its own
     sourced, scoped statement**, doubtful ones `exact: false` with a note; choose none. Send the
     wey and aum descriptions to LCA's curators as glossary defects;
   - ~~**19** (QUDT/Noback)~~ **dropped 29 Sep (D7)**.
3. ~~**17 (draft)**~~ built 29 Sep with 14 (above); run order: parse_bor, export_hector,
   build_units, link_rates. Next: review the 1,828 links (the report's sample first), and
   the 314 + 170 unlinked. Originally: emit Rate nodes into `build/site/` for commodities that already exist.
   1507–1558 rates can be linked by matching `commodity_text` against glossary forms; 1604
   needs the D6 restore on the LCA side first. Qualified rates follow decision 2 (flatten rated only).
4. When task 1 lands: copy `build/site/commodity/` into the repo and commit
   `build/ledger/commodities.tsv` as `ledger/commodities.tsv` **in the same commit**, run
   `tools/validate.py --online` locally (CI cannot reach Getty), then push.

Nothing Jenks-derived goes to `main` until task 1 is ticked: `main` is live on
`w3id.org/hector`.

---

## 5. Corrections to issue #2

Record here when a figure in issue #2 turns out to be wrong, with the date and how it was
measured. Consider posting a correction comment on the issue as well, since the issue is
where others read it.

- **C1 (2026-09-18, figures revised the same day): "100% AAT/Wikidata classification, all
  confirmed" overstates the identifications.** 2,451 of 2,452 entries have at least one `aat`
  item (`bacon` has none), and none is an unreviewed suggestion, which is what the issue
  measured. Rule: first drop every item whose id is `300386154` *unidentified (information
  indicator)*; then an entry counts as exact/close if any remaining item lacks `broader`,
  and otherwise as broader-only. Result: **1,334** exact/close, **722** broader-only,
  **395** unidentified-only, **1** empty. Scenario B still stands, but "100% sameAs" does
  not: about **54%** of entries can carry an identity link. Measured from
  `LCA/docs/data/glossary_data.json` (generated 2026-02-07 header, file dated 2026-08-17).
  *My first figures (1,345 / 711 / 396) came from a label-based rule that miscounted the 68
  entries mixing the placeholder with real concepts. The `hector-08` session caught it.*
- **C5 (2026-09-18): `hector:compoundOf` is used by 3 glossary entries, not 4.**
- **C2 (2026-09-18): "the schema … exist[s] and work[s]" is wrong for the schema.** The
  context is rejected by a conforming JSON-LD processor, entity ids expand to fragment URIs,
  and the `la:` namespace is not Linked Art's. Hence Phase 0. (CLAUDE.md §4.)
- **C3 (2026-09-18): "four Books of Rates … 2,419 entries".** The 2,419 are the five TSVs for
  1507, 1545 and 1558 only. 1604 *had* been extracted in LCA and was deliberately removed
  (e9b5c99, 2026-02-07) as out of LCA's scope; Stephen confirms it is in HECTOR's. HECTOR's
  parser now extracts it again (1,644 rows).
- **C4 (2026-09-18): licence position.** The issue says CC BY 4.0 "has been chosen for
  project-authored data". The glossary file's `metadata.licence` still declares CC BY-SA
  4.0, and the Jenks permission that governs the glossary is still pending. Hence D5.
- **C6 (2026-09-18): two of the exemplar's identifiers were not merely placeholders but wrong.**
  `aat:300010621` (saffron's `sameAs`, and "spice") returns 404 from AAT, so it does not exist;
  `wd:Q12057` is *Uloboridae*, a family of spiders. Saffron is AAT `300013073` (under
  "vegetable dye") and Wikidata `Q25434`. Found by dereferencing every id
  (`tools/validate.py --online`); the new exemplars pass that check.
- **C7 (2026-09-18): three wrong authority ids in the glossary**, found by dereferencing all
  1,250 ids the export uses: `meat` → AAT 300256775 does not exist (meat is 300389813);
  `ounce` → AAT 300379226 is *kilograms* (ounces: 300379229); `osnaburg`'s place → Q4024 is
  Frankfurt (Oder) (Osnabrück: Q2916). Reported to the LCA session; fix there, not here.
- **C8 (2026-09-18): the glossary lacks the 1604-only commodities.** Of the 3,296 entries in
  the pre-removal backup, 346 vanished without any rekey/merge/deletion record: 255 have only
  Books of Rates sources (the 1604 removal), 88 have Customs Account sources (disappeared for
  some other, unrecorded reason: ask Stephen/LCA), 3 have none. See decision D6.
  **Revised 2026-09-29: the 88 are curation, not loss.** Traced through all 527 LCA commits
  that touched the glossary (key sets diffed commit by commit): every one was removed between
  10 May and 21 Jul 2026 by Stephen's commits, 30 of them the browser editor's and the rest
  scripted consolidations (thread 2c6f5d87, "last" 1377d4bf, Eliot's duplicate queue 59a687fe,
  gun fb6f4546, gum 706e3a8b, and seven single-key commits). By history: **31** resolve to a
  live concept (hector's check was wrong, see below), **4** are recorded deletions (`cocket`,
  a customs seal, deliberately), **13** have chains ending at a split target such as
  "poke/pocket" or "lyneboard / line" (no single successor: correctly left for a human),
  **40** have no record at all because the scripted consolidations never wrote history. By
  forms: 64 keep all or most of their spellings under a live concept and 21 split cleanly into
  a live head plus a qualifier (`flaunders tile` → tile + q(flaunders)). The only loss of
  meaning is **`gunes vocati basis`**, the "base", the smallest cannon (OED base n.6): `gun`
  survives, "basis" exists nowhere; plus one unregistered variant, "pro toyles" of
  `toalys pro joyners`. Both sent to LCA's curators. A rerun today also counts `ciste`
  (removed 22 Sep by the container rule, forms intact), hence 89.
  **The check was wrong for 31 of them.** `successor()` ranked rekeys above merges whatever
  their time, and the browser editor writes a burst of rekeys just before a merge (`cradil` →
  `cradle_3` → `cradil`, then merged into `cradle_2`, 9 Jun), so it looped. Fixed 29 Sep: one
  time-ordered stream, the latest record per key wins, and at a tied instant a merge outranks
  the deletion scripted consolidations write beside it. Over all 1,983 keys gone since the
  backup, "missing" falls 347 → 307; the tests `cradil`, `tablys` and the reverse order each
  fail on the old code or pin the new rule.
- **C9 (2026-09-19): 353 corpus-attested unit concepts, not 357.** Distinct `matches[0].key` over
  spans typed `unit` (281 keys, 432,803 spans) or `commodity-unit` (72 keys, 16,987 spans) in
  `LCA/docs/data/ladings/*.json.gz`; all 353 are glossary keys. 210 of them are in the units group;
  the other 143 are mostly vessels the tagger types as units because of their group, so "corpus-
  attested" is not the same as "a unit" (task 18 row). The 357 of 2026-09-15 was measured on an
  earlier annotation.
