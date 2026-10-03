## What this changes

<!-- One or two sentences. -->

## Checks

- [ ] This does **not** edit generated files by hand (`commodity/`, `unit/`, `ledger/`, `search/`,
      `dump/`, `*.ttl`, `*.rdf`): those are rebuilt from their sources at every republish
      (see CONTRIBUTING.md). Corrections to records go in an issue.
- [ ] `tools/validate.py --online` reports 0 errors, and the tests pass
      (`HECTOR_ONLINE=1 .venv/bin/python -m pytest tests/ -q`).
- [ ] Any new vocabulary term is declared in `ontology/ontology.json`.
- [ ] Any change to how URIs are minted follows `docs/uri-policy.md`.
