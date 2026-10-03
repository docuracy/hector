// Similar-spelling search for the site: every attested spelling embedded with the London Customs
// Accounts project's character bi-encoder.
//
//   node tools/site/build_fuzzy.mjs build/site          # after build_search_index (writes search/fuzzy.*)
//   node tools/site/build_fuzzy.mjs . --check           # is the published index current? (exit 1)
//   node tools/site/build_fuzzy.mjs --parity [--break]  # the encoder agrees with its Python original
//
// WHY THIS ENCODER. LCA measured every candidate on 2,825 held-out glossary spellings (its
// documentation/search_plan.md, 29 Sep 2026): this bi-encoder ranks the right concept first 0.881
// of the time, against 0.853 for Symphonym v8 + trigrams and 0.790 for Symphonym alone (110
// wins to 28), and it is ~100k weights of plain JavaScript, no ONNX runtime. Stephen chose it
// for HECTOR on that evidence (3 Oct 2026). Symphonym stays LCA's matcher for person names.
//
// ASSETS, copied unmodified from LCA (commit bbc1e91d): js/fuzzy_encoder.js (the encoder in
// plain JavaScript), search/encoder.json.gz (its trained weights), and
// tests/fixtures/encoder/encoder_fixture.json (Python inputs and embeddings, for --parity).
// The vectors are made here with the same JavaScript the page runs, so build and browser agree
// by construction; --parity proves that JavaScript still matches the Python model.
//
// Writes search/fuzzy.json.gz {sources, n, dim, scale, rows: [[index row, spelling]]} and
// search/fuzzy.i8.gz (n x dim int8: round-half-to-even(x * 127) of each unit vector), where
// "index row" is the record's position in search/index.json (tools/site/build_search_index.py).
import {readFileSync, writeFileSync, existsSync} from "node:fs";
import {gunzipSync, gzipSync} from "node:zlib";
import {createHash} from "node:crypto";
import {createRequire} from "node:module";
import {resolve} from "node:path";

const require = createRequire(import.meta.url);
const REPO = new URL("../../", import.meta.url).pathname;
const FE = require(REPO + "js/fuzzy_encoder.js");
const SCALE = 127;
const sha = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");
const model = () => JSON.parse(gunzipSync(readFileSync(REPO + "search/encoder.json.gz")));

function parity(breakIt) {
    const m = model();
    if (breakIt) {                                       // must FAIL: proves the check can fail
        const w = m.weights["proj.bias"];
        const buf = Buffer.from(w.b64, "base64"); buf.writeFloatLE(buf.readFloatLE(0) + 0.5, 0);
        w.b64 = buf.toString("base64");
    }
    const enc = FE.create(m);
    const fx = JSON.parse(readFileSync(REPO + "tests/fixtures/encoder/encoder_fixture.json", "utf8"));
    let worst = 0; const bad = [];
    for (const c of fx.cases) {
        const n = FE.norm0(c.input);
        if (n !== c.norm0) bad.push(`norm0(${JSON.stringify(c.input)}) = ${JSON.stringify(n)}, Python ${JSON.stringify(c.norm0)}`);
        const z = enc.embed(c.norm0 || c.input.toLowerCase());
        let d = 0;
        for (let i = 0; i < z.length; i++) d = Math.max(d, Math.abs(z[i] - c.embedding[i]));
        worst = Math.max(worst, d);
        if (d > 1e-4) bad.push(`embed(${JSON.stringify(c.input)}) differs by ${d.toExponential(2)}`);
    }
    if (bad.length) { console.log("FAIL\n  " + bad.slice(0, 12).join("\n  ")); return 1; }
    console.log(`ok: ${fx.cases.length} cases, norm0 identical, worst |JS - Python| ${worst.toExponential(2)}`);
    return 0;
}

function roundHalfEven(x) {
    const r = Math.round(x);
    return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

function build(root, check) {
    const indexPath = resolve(root, "search/index.json");
    const sources = {"index.json": sha(indexPath), "encoder.json.gz": sha(REPO + "search/encoder.json.gz")};
    const metaPath = resolve(root, "search/fuzzy.json.gz");
    if (check) {
        if (!existsSync(metaPath)) { console.log("STALE: search/fuzzy.json.gz missing"); return 1; }
        const have = JSON.parse(gunzipSync(readFileSync(metaPath))).sources;
        if (JSON.stringify(have) !== JSON.stringify(sources)) {
            console.log(`STALE: built from ${JSON.stringify(have)}, current ${JSON.stringify(sources)}`); return 1;
        }
        console.log("ok: built from the current index and encoder"); return 0;
    }
    if (parity(false)) return 1;
    const index = JSON.parse(readFileSync(indexPath, "utf8"));
    const enc = FE.create(model());
    const rows = [], seen = new Set();
    index.forEach(([_path, label, _kind, names, dep], i) => {
        if (dep) return;                                 // merged records are not offered
        for (const s of [label, ...names]) {
            const f = FE.norm0(s);
            if (Array.from(f).length < 2 || seen.has(i + "\u0000" + f)) continue;
            seen.add(i + "\u0000" + f);
            rows.push([i, f]);
        }
    });
    const dim = enc.dim, i8 = new Int8Array(rows.length * dim);
    rows.forEach(([_i, f], r) => {
        const z = enc.embed(f);
        for (let d = 0; d < dim; d++) i8[r * dim + d] = Math.max(-127, Math.min(127, roundHalfEven(z[d] * SCALE)));
    });
    const meta = {sources, n: rows.length, dim, scale: SCALE, rows,
                  measured: "LCA bi-encoder: 0.881 top-1 / 0.934 top-5 on 2,825 held-out glossary spellings (29 Sep 2026)"};
    writeFileSync(metaPath, gzipSync(Buffer.from(JSON.stringify(meta)), {level: 9}));
    writeFileSync(resolve(root, "search/fuzzy.i8.gz"), gzipSync(Buffer.from(i8.buffer), {level: 9}));
    console.log(`${rows.length.toLocaleString("en-GB")} spellings of ${index.length.toLocaleString("en-GB")} records embedded (dim ${dim})`);
    return 0;
}

const args = process.argv.slice(2);
if (args.includes("--parity")) process.exit(parity(args.includes("--break")));
const root = args.find((a) => !a.startsWith("--")) || resolve(REPO, "build/site");
process.exit(build(root, args.includes("--check")));
