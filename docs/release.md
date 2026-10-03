# Releasing HECTOR

The first tagged release ends the **alpha** (docs/uri-policy.md §0): from then on URIs are
stable and the ledgers are frozen. Prepared 3 October 2026; nothing here has been done yet.

## Alpha pre-releases

`vYYYY.MM-alpha.N`, published as a GitHub **pre-release**: a snapshot for discussion that
promises nothing persistent. No DOI (Zenodo's integration, once enabled, must not be triggered
by these: publish them as pre-releases only), nothing frozen, alpha notices left in place. Bump
`version` and `date-released` in CITATION.cff and `owl:versionInfo`, add a CHANGELOG entry, tag.
First: v2026.10-alpha.1, 3 Oct 2026.

## Before tagging (the first full release)

1. **Decide the version and date** (`vYYYY.MM`, docs/uri-policy.md §4) and what is in it
   (the 1604 Book of Rates and Sound Toll harmonisation are deferred to later versions: PLAN.md).
2. **Republish from the current glossary** and check everything (PLAN.md §0, "To republish"):
   `tools/validate.py --online` 0 errors; `pytest`; `build_rdf --check`; `build_fuzzy.mjs --check`.
3. **Freeze the ledgers.** From this release a slug is never renamed or withdrawn; a merge
   gives a deprecation record. Remove the alpha clause from docs/uri-policy.md §0 (keep it as
   history: "alpha until vYYYY.MM").
4. **Remove the alpha notices**, all of them:
   - README.md (status banner; "please do not cite"), index.html (yellow notice, heading,
     "Not yet" list), LICENSE-DATA (Status), CREDITS.md (alpha line), CITATION.cff (`message`);
   - `owl:versionInfo` in ontology/ontology.json (make it the version);
   - CHANGELOG.md: turn "Unreleased (alpha)" into the release heading, with its date.
5. **CITATION.cff**: add `version` and `date-released`; validate (`cffconvert --validate`).
   **.zenodo.json**: check creators and contributors, and their roles (CREDITS.md); Zenodo
   reads this file in preference to CITATION.cff.
6. **Credits**: confirm the CRediT roles with everyone named, and add anyone missing.

## Tagging and the DOI

7. **Zenodo**: in Zenodo, enable the GitHub integration for `docuracy/hector` (Stephen; once).
   A GitHub *release* (not just a tag) then triggers a deposit and mints a DOI.
8. Create the release `vYYYY.MM` on GitHub with the CHANGELOG entry as its notes.
9. When Zenodo has minted the DOI: add it to CITATION.cff (`doi`, and an `identifiers` entry),
   to the README (a "How to cite" section and DOI badge), and to the landing page; record the
   concept DOI (all versions) as well as the version DOI.

## After

10. Tell the London Customs Accounts project the DOI, so its documentation can cite HECTOR.
11. Announce on issue #2 and close what the release settles.
