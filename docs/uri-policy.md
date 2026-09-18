# HECTOR URI and versioning policy (decision D3)

*Status: **adopted 2026-09-18** by Stephen, as drafted, including the recommendations on the
three open questions at the end. Applied the same day (PLAN.md F2, F4): the context, the
exemplars and the validator follow it, and `tools/validate.py` enforces §1 (`ENTITY-URI`,
`DANGLING-REF`). The "problem" section below describes the state before adoption.*

## The problem, in one example

`commodity/saffron/ontology.json` says `"id": "hector:commodity/saffron"`, and the context
maps `hector` to `https://w3id.org/hector#`. So saffron's identifier is

    https://w3id.org/hector#commodity/saffron

HTTP never sends the part after `#`, so anyone who looks that identifier up gets
`https://w3id.org/hector`, the site root, and not saffron. The file itself is reachable, but only
at a *different* URI (`https://w3id.org/hector/commodity/saffron`), which is not the one the data
uses. `tools/validate.py` reported this as `ENTITY-URI` on every document.

## Proposal

### 1. Entities get path URIs, never fragments

    https://w3id.org/hector/commodity/<slug>
    https://w3id.org/hector/unit/<dimension>/<slug>          e.g. unit/mass/pound
    https://w3id.org/hector/unit/<dimension>                 the dimension itself
    https://w3id.org/hector/rate/<book>/<id>                 e.g. rate/1558-inward/0412

These already resolve through the existing w3id rules: with a JSON `Accept` header they
redirect to `<path>/ontology.json`, and with anything else to the viewer. **No change to w3id is
needed.** (Rates would need either one file per rate or a rule change; see Open questions.)

### 2. Vocabulary terms live in one namespace, shared with LCA

    https://w3id.org/hector/ontology#<term>        e.g. hector:phoneticKey, hector:Rate

- LCA's `docs/api/context.json` already uses this namespace for `hector:compoundOf`, so LCA
  would need **no change**. HECTOR's context changes one line.
- Term IRIs dereference: `https://w3id.org/hector/ontology#phoneticKey` → (fragment dropped)
  `/hector/ontology` → `ontology/ontology.json`, the vocabulary document added in Phase 0.
  Again, no w3id change.
- The alternative, keeping `https://w3id.org/hector#`, means changing LCA and leaves term IRIs
  resolving to the site root.

In the context this becomes two prefixes, so that entities and terms cannot be confused:

```json
"hector":   "https://w3id.org/hector/ontology#",
"hectorid": "https://w3id.org/hector/"
```

Documents then write `"id": "hectorid:commodity/saffron"`, or simply the full URI. The
exporter writes full URIs.

### 3. Slugs are minted once, recorded in a ledger, and never recomputed

Glossary keys are renamed and merged over time (`metadata.rekey_history`, `merge_history` in
LCA's `glossary_data.json`). A URI computed from the current key would change whenever the key
does. So:

- the exporter keeps a ledger with columns
  `slug, glossary_key, minted, status, replaced_by, content_sha256, modified`. *Until first
  publication it lives at `build/ledger/commodities.tsv` (git-ignored), because its keys are
  Jenks-derived headwords. Nothing has been published, so no URI has been cited and nothing can
  break. It is committed as `ledger/commodities.tsv` in the same commit as the first published
  export, and never regenerated after that* (implementation: `tools/export/export_hector.py`);
- a slug is minted the first time a key is exported, and is looked up from then on;
- slugs are lowercase ASCII: diacritics are stripped, spaces and punctuation become `-`, and a
  collision takes a numeric suffix. They are never reused;
- when two concepts are merged, the loser's URI keeps resolving to a small deprecation document
  (`owl:deprecated true`, `dcterms:isReplacedBy <survivor>`), not a 404.

### 4. Versions

- Releases are tagged `vYYYY.MM` (e.g. `v2026.11`) and deposited on Zenodo (task 25), so a
  citation can name a fixed version.
- Every entity carries `dcterms:modified`.
- URIs are not versioned: `https://w3id.org/hector/commodity/saffron` always means the current
  description of saffron, and a tagged release gives the historical one.

## What adopting it changes

| where | change |
|---|---|
| `context/hector.jsonld` | `hector` → `…/ontology#`; add `hectorid` (F4, F2) |
| entity documents | `id` becomes the path URI; `ENTITY-URI` is an error in `tools/validate.py` |
| `ontology/ontology.json` | term ids follow automatically, since they are written `hector:…` |
| LCA | nothing (it already uses `…/ontology#`); tell the LCA session once it is done |
| w3id `.htaccess` | nothing, for commodities and units |

## Open questions (resolved 2026-09-18: each recommendation adopted)

1. **Rates:** is each rate its own document (`rate/1558-inward/0412/ontology.json`, about 4,000
   files), or embedded in its commodity with a fragment id (`…/commodity/saffron#rate-1558`)?
   A fragment id is fine *inside* a document, because the document is what gets looked up.
   **Recommend embedding**, which also keeps the file count down.
2. **Qualified commodities (decision 2):** if flattened, do their slugs follow the qualifier
   (`canvas-normandy`), or are they opaque? **Recommend readable slugs**, since the ledger makes
   them stable anyway.
3. **Units:** is the `<dimension>` path level wanted? It makes URIs longer, and a unit that
   changes dimension (rare) would need a redirect. **Recommend keeping it**: it is already public
   and it groups units usefully.
