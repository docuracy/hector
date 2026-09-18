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
| **1** [X] | **Jenks permission** for derived structured data, ideally CC BY 4.0 (LCA `documentation/data_licensing_strategy.md` §1) | put it in writing now; offer the split (open licence on derived data, verbatim `original_text` held back) | all publication |
| **2** [D] | **Flatten vs compose** qualified commodities (issue #2 §4) | **flatten**: `Normandy canvas` gets its own commodity URI with the rate attached, linked by `hector:compoundOf`. Works with the schema today, avoids AAT for ~400 qualifiers | 12, 14–17 |
| **3** [D] | **URI and versioning policy** | **adopted 2026-09-18** as drafted: `docs/uri-policy.md` | every export |
| **D4** [D] | **HECTOR URI vs LCA glossary URI.** Each concept already has `https://w3id.org/mlca/glossary/{key}`. Which is canonical? | HECTOR canonical; LCA's JSON-LD emits `skos:exactMatch` (or `owl:sameAs`) to it. Keeps LCA URIs working | 12 |
| **D5** [D] | **Data licence for HECTOR output** (repo `LICENSE` is MIT, code only; glossary metadata says CC BY-SA; strategy prefers CC BY) | follows task 1; add a `LICENSE-DATA` once decided | 24, 25 |

**D3, the URI policy.** Adopted 2026-09-18; the full text is `docs/uri-policy.md`. In short:
- entities are **path URIs**, never fragments: `https://w3id.org/hector/commodity/<slug>`,
  `…/unit/<dimension>/<slug>`, `…/rate/<book>/<id>`;
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
| 13 [E] | Phonetic keys from ~9% to 100% of 19,411 forms, reusing LCA `process/helpers/phonetic.py` | todo |
| 14 [E] | Emit qualified commodities per decision 2 | todo, needs 2 |

### Rates
| # | task | where | status |
|---|---|---|---|
| **15** [E] | Parse `LCA/data/bor/*.tsv` into structured rates: split commodity/qualifier/unit out of the fused `commodity` cell; price £ s d → pence + currency; validFrom/validThrough per book; editorial `[…]` kept as a flag; source. 2,419 rows across 5 TSVs. **Also parse 1604** from `Jenks Book of Rates 1604.doc/.html` (issue #1 says done; no TSV exists) | here (reads LCA) | parser **done 2026-09-18** (`tools/rates/parse_bor.py`, output in ignored `build/rates/`): 4,063 rows incl. 1,644 from 1604; 3,905 ok / 69 partial / 89 failed (mostly genuine non-rates). Rates and units reliable on samples; the commodity/qualifier split is naive (~15–20% wrong), so match `commodity_text` against the glossary instead (task 16). Emitting waits on task 1 |
| 16 [C] | Reconcile the 141 rate-bearing qualifier phrases that match nothing in `qualifiers.json` | LCA editors | — |
| 17 [E] | Emit `hector:taxation` linked to commodity and unit URIs | here | todo |

### Units
| # | task | status |
|---|---|---|
| 18 [E] | Build the unit catalogue: 222 glossary entries in `Units, weights & measures` + 357 corpus-attested unit concepts (ladings `type: unit` spans) + `…_units.tsv` conversion statements | todo |
| 19 [C] | Align to QUDT and the Digital Noback Project | todo (droppable) |
| 20 [E] | Emit `unit/<dimension>/<slug>/ontology.json` with conversion factors where known | todo |

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

## 4. What the HECTOR session can do now, without waiting on anyone

1. ~~F1, F3, F5~~ done 2026-09-18.
2. ~~21~~ done 2026-09-18.
3. ~~15 (parsing only)~~ done 2026-09-18; output local in `build/rates/`.
4. ~~Draft the D3 URI policy~~: adopted 2026-09-18 (`docs/uri-policy.md`); F2, F4 done.
Next without a decision: 13 (phonetic keys, computed locally) and 18 (unit catalogue, built
locally); both publish only after task 1.

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
  1507, 1545 and 1558 only; the fourth book, 1604, is unparsed.
- **C4 (2026-09-18): licence position.** The issue says CC BY 4.0 "has been chosen for
  project-authored data". The glossary file's `metadata.licence` still declares CC BY-SA
  4.0, and the Jenks permission that governs the glossary is still pending. Hence D5.
- **C6 (2026-09-18): two of the exemplar's identifiers were not merely placeholders but wrong.**
  `aat:300010621` (saffron's `sameAs`, and "spice") returns 404 from AAT, so it does not exist;
  `wd:Q12057` is *Uloboridae*, a family of spiders. Saffron is AAT `300013073` (under
  "vegetable dye") and Wikidata `Q25434`. Found by dereferencing every id
  (`tools/validate.py --online`); the new exemplars pass that check.
