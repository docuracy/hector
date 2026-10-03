// fuzzy_encoder.js
//
// The project's character bi-encoder (process/concept_retrieval.py), in plain JavaScript,
// for fuzzy search of goods, measures and qualities. Step 4 of search_plan.md: measured
// best of every candidate on held-out glossary spellings (0.881 top-1 against 0.853 for
// Symphonym + trigram), and small enough (~100k weights) to need no ONNX runtime.
//
// Weights and the precomputed int8 vectors of every vocabulary spelling come from
// process/build_search_encoder.py. tools/search/parity.mjs runs this file under Node
// against that script's fixture: norm0 must match exactly and every embedding to 1e-4.
//
// Works as a browser global (FuzzyEncoder) and as a CommonJS module (for the parity test).

(function (root, factory) {
    const api = factory();
    if (typeof module === "object" && module.exports) module.exports = api;
    else root.FuzzyEncoder = api;
})(typeof self !== "undefined" ? self : this, function () {
    const PAD = 0, UNK = 1, BOS = 2, EOS = 3;

    // process/commodity_parser/normalize.py norm0: lower-case, strip diacritics, drop
    // abbreviation marks, trim non-word edges, collapse whitespace. Python's \w is
    // Unicode letters, digits, marks and underscore.
    const DROP = /['’ʼ….]/g;
    const EDGE = /^[^\p{L}\p{N}\p{M}_]+|[^\p{L}\p{N}\p{M}_]+$/gu;
    function norm0(text) {
        if (!text) return "";
        let s = String(text).toLowerCase().normalize("NFD").replace(/\p{Mn}/gu, "");
        s = s.replace(DROP, "").replace(EDGE, "");
        return s.replace(/\s+/g, " ").trim();
    }

    function decodeF32(b64) {
        const bin = typeof atob === "function" ? atob(b64) : Buffer.from(b64, "base64").toString("binary");
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
        return new Float32Array(bytes.buffer);
    }

    // model = the parsed encoder.json.gz
    function create(model) {
        const vocab = model.vocab, cfg = model.cfg, MAX_LEN = model.max_len || 48;
        const W = {};
        for (const [k, v] of Object.entries(model.weights)) W[k] = {shape: v.shape, d: decodeF32(v.b64)};
        const C = cfg.char_dim, F = cfg.filters, D = cfg.out_dim, widths = cfg.widths;
        const emb = W["emb.weight"].d;                        // V x C
        const convs = widths.map((w, j) => ({w, W: W[`convs.${j}.weight`].d, b: W[`convs.${j}.bias`].d}));
        const P = W["proj.weight"].d, Pb = W["proj.bias"].d;  // D x (F * widths)

        function embed(s) {
            const chars = Array.from(s);                       // code points, as Python str
            const L = Math.max(Math.min(MAX_LEN, chars.length + 2), 7);
            const ids = [BOS, ...chars.slice(0, L - 2).map(c => (c in vocab ? vocab[c] : UNK)), EOS];
            const x = new Int32Array(L);                       // PAD beyond the string
            ids.forEach((v, i) => { x[i] = v; });
            // e[c * L + t] = emb[x[t], c]
            const e = new Float32Array(C * L);
            for (let t = 0; t < L; t++) for (let c = 0; c < C; c++) e[c * L + t] = emb[x[t] * C + c];
            const pooled = new Float32Array(F * widths.length);
            convs.forEach(({w, W: Wc, b}, j) => {
                const npos = L - w + 1;
                const valid = Math.max(ids.length - w + 1, 1);
                const lim = Math.min(valid, npos);
                for (let f = 0; f < F; f++) {
                    let best = -Infinity;
                    for (let p = 0; p < lim; p++) {
                        let h = b[f];
                        const wf = f * C * w;
                        for (let c = 0; c < C; c++) {
                            const wc = wf + c * w, ec = c * L + p;
                            for (let k = 0; k < w; k++) h += Wc[wc + k] * e[ec + k];
                        }
                        if (h < 0) h = 0;                      // relu
                        if (h > best) best = h;
                    }
                    pooled[j * F + f] = best;
                }
            });
            const z = new Float32Array(D);
            const IN = F * widths.length;
            let norm = 0;
            for (let d = 0; d < D; d++) {
                let v = Pb[d];
                const row = d * IN;
                for (let i = 0; i < IN; i++) v += P[row + i] * pooled[i];
                z[d] = v; norm += v * v;
            }
            norm = Math.max(Math.sqrt(norm), 1e-12);
            for (let d = 0; d < D; d++) z[d] /= norm;
            return z;
        }

        return {embed, norm0, dim: D};
    }

    // Cosine of a float query against every row of an int8 matrix (rows = unit vectors
    // times `scale`). Returns a Float32Array of n cosines.
    function cosines(q, i8, n, dim, scale) {
        const out = new Float32Array(n);
        for (let r = 0; r < n; r++) {
            let s = 0;
            const o = r * dim;
            for (let d = 0; d < dim; d++) s += q[d] * i8[o + d];
            out[r] = s / scale;
        }
        return out;
    }

    return {create, norm0, cosines};
});
