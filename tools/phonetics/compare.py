"""Measure how well candidate phonetic keys match variant spellings (task 13's evidence).

For every (concept, form) whose concept has at least two forms: is the nearest other key
(normalised Levenshtein over the key, stress marks and spaces removed) a key of the SAME
concept? Ties count half. Also: exact-key precision/recall over pairs of distinct forms.
Scores are split by LCA's language guess (la / en / und).

Needs rapidfuzz and numpy. Optional methods are measured only when available and skipped
with a note otherwise: Epitran (lat/fra/deu/nld/eng-Latn; eng needs flite's lex_lookup) and
node for the site's js/phonemize.js. Nothing here feeds the export; it is the record of why
`ipa.py` uses the convention it does.

    python3 -m tools.phonetics.compare          # system python3 (has epitran), ~1 min
"""
from __future__ import annotations

import collections
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from tools.phonetics import ipa

PHONEMIZE_JS = r"""
const fs=require('fs'), vm=require('vm'); const ctx={}; vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[1],'utf8')+';this.p=phonemize;', ctx);
const ts=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(ts.map(t=>ctx.p.phonemize(t,{language:'en',strip:true}))));
"""


def methods(texts: list[str]) -> dict[str, list[str]]:
    out = {ipa.METHOD: [ipa.transcribe(t) for t in texts],
           "spelling (clean(), not IPA)": [ipa.clean(t) for t in texts]}
    try:
        import epitran
        for code in ["lat-Latn", "fra-Latn", "deu-Latn", "nld-Latn", "eng-Latn"]:
            if code == "eng-Latn" and not shutil.which("lex_lookup"):
                print("skip eng-Latn: flite lex_lookup not installed", file=sys.stderr)
                continue
            e = epitran.Epitran(code)
            out["epitran " + code] = [e.transliterate(ipa.clean(t)) for t in texts]
    except ImportError:
        print("skip Epitran methods: epitran not installed", file=sys.stderr)
    js = ipa.REPO / "js" / "phonemize.js"
    if shutil.which("node") and js.exists():
        r = subprocess.run(["node", "-e", PHONEMIZE_JS, str(js)], text=True, capture_output=True,
                           input=json.dumps([ipa.clean(t) for t in texts]), check=True)
        out["phonemize.js (en)"] = json.loads(r.stdout)
    else:
        print("skip phonemize.js: node or js/phonemize.js missing", file=sys.stderr)
    return out


def score(pairs, keys_by_text, lang_of) -> dict:
    import numpy as np
    from rapidfuzz.distance import Levenshtein
    from rapidfuzz.process import cdist

    concepts = [c for c, _ in pairs]
    K = [re.sub(r"[ˈˌ ]", "", keys_by_text[t]) for _, t in pairs]
    uk = sorted(set(K))
    ui = {k: i for i, k in enumerate(uk)}
    kid = [ui[k] for k in K]
    by_c = collections.defaultdict(list)
    k2c = collections.defaultdict(set)
    for j, c in enumerate(concepts):
        by_c[c].append(j)
        k2c[kid[j]].add(c)
    cid = {c: i for i, c in enumerate(sorted(by_c))}
    only = np.array([cid[next(iter(k2c[u]))] if len(k2c[u]) == 1 else -1 for u in range(len(uk))])
    qs = [j for j, c in enumerate(concepts) if len(by_c[c]) >= 2]
    qk = sorted({kid[j] for j in qs})
    rows = {}
    for s in range(0, len(qk), 800):
        ch = qk[s:s + 800]
        D = cdist([uk[i] for i in ch], uk, scorer=Levenshtein.normalized_distance,
                  workers=-1, dtype=np.float32)
        rows.update(zip(ch, D))
    hit = collections.defaultdict(lambda: [0.0, 0])
    for j in qs:
        c = concepts[j]
        row = rows[kid[j]]
        d_same = min(row[kid[o]] for o in by_c[c] if o != j)
        d_other = row[only != cid[c]].min()
        h = 1.0 if d_same < d_other else 0.5 if d_same == d_other else 0.0
        for cls in ("all", lang_of[pairs[j][1]]):
            hit[cls][0] += h
            hit[cls][1] += 1
    groups = collections.defaultdict(list)
    for j, (c, t) in enumerate(pairs):
        groups[K[j]].append((c, t))
    tp = fp = 0
    for g in groups.values():
        for a in range(len(g)):
            for b in range(a + 1, len(g)):
                if g[a][1] != g[b][1]:
                    tp, fp = (tp + 1, fp) if g[a][0] == g[b][0] else (tp, fp + 1)
    same = sum(len(v) * (len(v) - 1) // 2 for v in by_c.values())
    return {"nn": {k: round(v[0] / v[1], 4) for k, v in hit.items()},
            "queries": hit["all"][1], "distinct keys": len(uk),
            "exact precision": round(tp / (tp + fp), 4) if tp + fp else None,
            "exact recall": round(tp / same, 4), "empty": sum(1 for k in K if not k)}


def main() -> int:
    forms = ipa.glossary_forms()
    texts = sorted(forms)
    pairs = sorted({(k, t) for t, ks in forms.items() for k in ks})
    vern = ipa.load_vernacular()
    lang_of = {t: ipa.language_guess(t, vern) for t in texts}
    print("forms", len(texts), "concept-form pairs", len(pairs),
          "language guess", dict(collections.Counter(lang_of.values())))
    print("| method | NN all | NN la | NN en | NN und | exact precision | exact recall | distinct keys | empty |")
    print("|---|---|---|---|---|---|---|---|---|")
    for name, keys in methods(texts).items():
        r = score(pairs, dict(zip(texts, keys)), lang_of)
        nn = r["nn"]
        print(f"| {name} | {nn['all']} | {nn.get('la')} | {nn.get('en')} | {nn.get('und')} | "
              f"{r['exact precision']} | {r['exact recall']} | {r['distinct keys']} | {r['empty']} |",
              flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
