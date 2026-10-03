/* HECTOR site: the landing page (search) and the human view of every record.
 *
 * w3id.org/hector sends every HTML request for /<path> to index.html?path=<path> (JSON requests
 * go straight to <path>/ontology.json), so this one page is also the human view of each record.
 * No libraries: records are fetched from the same site, and search/index.json (built by
 * tools/site/build_search_index.py) holds every record's label and attested spellings.
 */
(() => {
    "use strict";

    const BASE = new URL(".", document.baseURI);           // .../hector/
    const W3ID = "https://w3id.org/hector/";
    const PREFIX = {
        hectorid: W3ID, hector: W3ID + "ontology#",
        aat: "http://vocab.getty.edu/aat/", wd: "http://www.wikidata.org/entity/",
        qudtunit: "http://qudt.org/vocab/unit/", quantitykind: "http://qudt.org/vocab/quantitykind/",
        geonames: "https://sws.geonames.org/", skos: "http://www.w3.org/2004/02/skos/core#",
        owl: "http://www.w3.org/2002/07/owl#", rdfs: "http://www.w3.org/2000/01/rdf-schema#",
    };
    const KIND = {c: "Commodity", q: "Commodity, as priced in the Books of Rates", u: "Unit"};
    const AAT_PREFERRED = "aat:300404670";
    const AAT_NOTE = "aat:300435416";

    const $ = (sel, el = document) => el.querySelector(sel);
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

    function expand(id) {
        if (!id) return "";
        if (/^https?:\/\//.test(id)) return id;
        const m = /^([a-zA-Z]+):(.*)$/.exec(id);
        return m && PREFIX[m[1]] !== undefined ? PREFIX[m[1]] + m[2] : id;
    }

    /** A link to a referenced thing: HECTOR records open in this page, others go to their authority. */
    function ref(r) {
        if (typeof r === "string") r = {id: r};
        const url = expand(r.id);
        const label = esc(r._label || r.id);
        if (url.startsWith(W3ID) && !url.includes("#")) {
            const path = url.slice(W3ID.length);
            return `<a href="?path=${encodeURIComponent(path)}">${label}</a>`;
        }
        const src = url.includes("vocab.getty.edu") ? "AAT" : url.includes("wikidata.org") ? "Wikidata"
            : url.includes("qudt.org") ? "QUDT" : url.includes("w3id.org/mlca") ? "LCA glossary" : "";
        return `<a href="${esc(url)}">${label}</a>${src ? ` <span class="src">${src}</span>` : ""}`;
    }

    const list = (items) => (items || []).map(ref).join(", ");

    function normalise(s) {
        return String(s).toLowerCase().replace(/þ/g, "th").replace(/ȝ/g, "y").replace(/æ/g, "ae")
            .normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[’'".,]/g, "");
    }

    /* ------------------------------------------------------------------ record view */

    async function showRecord(path) {
        const el = $("#record");
        el.hidden = false;
        document.title = `${path} · HECTOR`;
        el.innerHTML = `<p class="muted">Loading <code>${esc(path)}</code>…</p>`;
        let doc;
        try {
            const res = await fetch(new URL(`${path}/ontology.json`, BASE));
            if (!res.ok) throw new Error(res.status);
            doc = await res.json();
        } catch (e) {
            el.innerHTML = `<h1>No record at this address</h1>
                <p>There is no HECTOR record at <code>${esc(W3ID + path)}</code>. It may have been renamed during the alpha
                (see the <a href="./ledger/commodities.tsv">ledgers</a>), or never existed.</p>
                <p><a href="./">Search HECTOR</a></p>`;
            return;
        }
        if (path === "ontology" || doc["@graph"]) return renderVocabulary(el, doc);
        renderEntity(el, path, doc);
    }

    function renderEntity(el, path, d) {
        const uri = d.id || W3ID + path;
        const label = d._label || path;
        document.title = `${label} · HECTOR`;
        const isUnit = d.type === "MeasurementUnit";
        const kind = isUnit ? "Unit" : d.compoundOf ? KIND.q : "Commodity";
        const h = [];
        h.push(`<p class="crumb"><a href="./">HECTOR</a> › ${esc(kind)}</p>`);
        h.push(`<h1>${esc(label)}</h1>`);
        h.push(`<p class="uri"><code>${esc(uri)}</code> <button type="button" class="copy" data-copy="${esc(uri)}">Copy URI</button>
                 <a class="json" href="./${esc(path)}/ontology.json">JSON-LD</a>
                 <a class="json" href="./${esc(path)}/ontology.ttl">Turtle</a>
                 <a class="json" href="./${esc(path)}/ontology.rdf">RDF/XML</a>
                 <a class="json" title="Opens a GitHub issue (GitHub account required)" href="https://github.com/ihr-digital/hector/issues/new?template=correction.yml&amp;uri=${encodeURIComponent(uri)}">Report a correction</a></p>`);

        if (d.deprecated) {
            const to = d.isReplacedBy ? ref(d.isReplacedBy) : "nothing";
            h.push(`<div class="callout"><strong>This record has been merged.</strong> It is replaced by ${to}.
                    The URI is kept so that existing links still resolve.</div>`);
        }

        const notes = (d.referred_to_by || []).filter((n) => n.content);
        if (notes.length) {
            h.push(`<section><h2>Description</h2>${notes.map((n) => {
                const isNote = (n.classified_as || []).some((c) => c.id === AAT_NOTE);
                return `<p class="${isNote ? "" : "muted small"}">${esc(n.content)}</p>`;
            }).join("")}</section>`);
        }

        const facts = [];
        const row = (k, v) => v && facts.push(`<dt>${k}</dt><dd>${v}</dd>`);
        row("Same as", list(d.equivalent));
        row("Close match", list(d.closeMatch));
        row("Broader", list(d.broader));
        row("Made up of", list(d.compoundOf));
        row("Material", list(d.material));
        row("Place of origin", list(d.originPlace));
        row("Classified as", list(d.classified_as));
        row("Related", list(d.related));
        row("In the LCA glossary", list(d.exactMatch));
        row("See also", list(d.seeAlso));
        if (isUnit) {
            row("Kind of quantity", (d.quantityKind || []).map((q) => {
                const p = expand(q).replace(W3ID, "");
                return `<a href="?path=${encodeURIComponent(p)}">${esc(p.split("/").pop())}</a>`;
            }).join(", "));
            row("Defined as", (d.definedAs || []).map((x) => `${esc(x.value)} × ${ref(x.unit)}`).join("; "));
            if (d.conversionToGram) row("In grams", `${esc(d.conversionToGram)} g <span class="muted small">(a modern reference value)</span>`);
        }
        if (d.attestationCount) row("Occurrences", `${Number(d.attestationCount).toLocaleString("en-GB")} in the London customs accounts, 1380–1560`);
        row("Last changed", esc(d.modified));
        if (facts.length) h.push(`<section><h2>Identification</h2><dl class="facts">${facts.join("")}</dl></section>`);

        const names = d.identified_by || [];
        if (names.length) {
            const rows = names.map((n) => {
                const pref = (n.classified_as || []).some((c) => c.id === AAT_PREFERRED);
                const dates = n.validFrom ? (n.validFrom === n.validThrough || !n.validThrough ? n.validFrom : `${n.validFrom}–${n.validThrough}`) : "";
                const ipa = (n.phoneticKey || []).map((k) => `/${esc(k)}/`).join(" ");
                return `<tr><td>${esc(n.content)}${pref ? ' <span class="tag">preferred</span>' : ""}</td><td>${esc(dates)}</td><td class="ipa">${ipa}</td></tr>`;
            }).join("");
            h.push(`<section><h2>Spellings <span class="count">${names.length}</span></h2>
                <p class="muted small">As written in the sources, with the years they are dated to where known. The IPA keys read each
                spelling with late Middle English letter values, for matching variants; they are not pronunciations.</p>
                <div class="scroll"><table><thead><tr><th>Spelling</th><th>Dated</th><th>Phonetic key</th></tr></thead>
                <tbody>${rows}</tbody></table></div></section>`);
        }

        const rates = d.taxation || [];
        if (rates.length) {
            const rows = rates.map((r) => {
                const per = r.perQuantity ? `${r.perQuantity.value !== 1 ? esc(r.perQuantity.value) + " " : ""}${ref(r.perQuantity.unit)}` : "";
                const when = r.validFrom ? `${esc(r.validFrom)}${r.validThrough ? "–" + esc(r.validThrough) : ""}` : "";
                return `<tr><td>${when}</td><td>${esc(r.amount?.lsd || "")}</td><td>${per}</td><td class="small">${esc(r.sourceText || r._label || "")}</td></tr>`;
            }).join("");
            h.push(`<section><h2>Customs rates <span class="count">${rates.length}</span></h2>
                <p class="muted small">The official valuation per unit, with the source of each.</p>
                <div class="scroll"><table><thead><tr><th>In force</th><th>Rate</th><th>Per</th><th>Source</th></tr></thead>
                <tbody>${rows}</tbody></table></div></section>`);
        }

        h.push(`<details class="raw"><summary>Show the JSON-LD</summary><pre><code>${esc(JSON.stringify(d, null, 2))}</code></pre></details>`);
        el.innerHTML = h.join("");
        wireCopy(el);
    }

    function renderVocabulary(el, doc) {
        document.title = "Vocabulary · HECTOR";
        const graph = doc["@graph"] || [];
        const head = graph.find((g) => g.type === "owl:Ontology") || {};
        const terms = graph.filter((g) => g !== head);
        el.innerHTML = `<p class="crumb"><a href="./">HECTOR</a> › Vocabulary</p>
            <h1>${esc(head._label || "HECTOR vocabulary")}</h1>
            <p class="uri"><code>https://w3id.org/hector/ontology</code> <a class="json" href="./ontology/ontology.json">JSON-LD</a>
            <a class="json" href="./ontology/ontology.ttl">Turtle</a> <a class="json" href="./ontology/ontology.rdf">RDF/XML</a></p>
            ${head["rdfs:comment"] ? `<p>${esc(head["rdfs:comment"])}</p>` : ""}
            ${head["owl:versionInfo"] ? `<p class="muted small">Status: ${esc(head["owl:versionInfo"])}</p>` : ""}
            <dl class="terms">${terms.map((t) => `<dt id="${esc(String(t.id).replace(/^hector:/, ""))}"><code>${esc(t.id)}</code>
                <span class="muted small">${esc(t.type)}</span></dt><dd>${esc(t["rdfs:comment"] || t._label || "")}</dd>`).join("")}</dl>`;
    }

    function wireCopy(el) {
        el.querySelectorAll("button.copy").forEach((b) => b.addEventListener("click", async () => {
            try { await navigator.clipboard.writeText(b.dataset.copy); b.textContent = "Copied"; }
            catch { b.textContent = "Copy failed"; }
            setTimeout(() => (b.textContent = "Copy URI"), 1500);
        }));
    }

    /* ------------------------------------------------------------------ landing + search */

    let INDEX = null;
    let kindFilter = "";
    let FUZZY = null, fuzzyLoading = null, searchSeq = 0;
    const FUZZY_MIN = 0.6, FUZZY_MAX = 15, FUZZY_WHEN_FEWER = 10;

    async function gzBytes(url) {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`${url}: ${r.status}`);
        return new Uint8Array(await new Response(r.body.pipeThrough(new DecompressionStream("gzip"))).arrayBuffer());
    }

    /* Similar spellings: the London Customs Accounts project's character bi-encoder
       (js/fuzzy_encoder.js; vectors from tools/site/build_fuzzy.mjs). Loaded only when a
       search finds few matches. */
    function loadFuzzy() {
        if (!fuzzyLoading) {
            fuzzyLoading = (async () => {
                const dec = (b) => JSON.parse(new TextDecoder().decode(b));
                const [meta, model, bytes] = await Promise.all([
                    gzBytes(new URL("search/fuzzy.json.gz", BASE)).then(dec),
                    gzBytes(new URL("search/encoder.json.gz", BASE)).then(dec),
                    gzBytes(new URL("search/fuzzy.i8.gz", BASE))]);
                const i8 = new Int8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
                if (i8.length !== meta.n * meta.dim) throw new Error("fuzzy.i8 does not match its index");
                const probe = meta.rows[meta.n - 1];
                const rec = INDEX[probe[0]];
                if (!rec || ![rec.label, ...rec.names].some((s) => FuzzyEncoder.norm0(s) === probe[1]))
                    throw new Error("fuzzy index was built from another search index");
                FUZZY = {meta, i8, enc: FuzzyEncoder.create(model)};
            })().catch((e) => { fuzzyLoading = null; throw e; });
        }
        return fuzzyLoading;
    }

    function fuzzy(q, exclude) {
        const f = FuzzyEncoder.norm0(q);
        if (Array.from(f).length < 3) return [];
        const {meta, i8, enc} = FUZZY;
        const cos = FuzzyEncoder.cosines(enc.embed(f), i8, meta.n, meta.dim, meta.scale);
        const best = new Map();
        for (let r = 0; r < meta.n; r++) {
            if (cos[r] < FUZZY_MIN) continue;
            const [ri, form] = meta.rows[r];
            const b = best.get(ri);
            if (!b || cos[r] > b.c) best.set(ri, {c: cos[r], form});
        }
        return [...best].map(([ri, b]) => ({r: INDEX[ri], c: b.c, form: b.form}))
            .filter((x) => x.r && !exclude.has(x.r.path) && (!kindFilter || x.r.kind === kindFilter))
            .sort((a, b) => b.c - a.c).slice(0, FUZZY_MAX);
    }

    async function loadIndex() {
        if (INDEX) return INDEX;
        const res = await fetch(new URL("search/index.json", BASE));
        if (!res.ok) throw new Error(res.status);
        INDEX = (await res.json()).map(([path, label, kind, names, dep]) => ({
            path, label, kind, names, dep, keys: [label, ...names].map(normalise),
        }));
        return INDEX;
    }

    function stats(index) {
        const n = (k) => index.filter((r) => r.kind === k && !r.dep).length;
        const spellings = index.reduce((a, r) => a + r.names.length + 1, 0);
        $("#stats").innerHTML = [
            `<li><strong>${n("c").toLocaleString("en-GB")}</strong> commodities</li>`,
            `<li><strong>${n("q").toLocaleString("en-GB")}</strong> commodities as priced in the Books of Rates, with their rates</li>`,
            `<li><strong>${n("u").toLocaleString("en-GB")}</strong> units of measure</li>`,
            `<li><strong>${spellings.toLocaleString("en-GB")}</strong> spellings, searchable here</li>`,
        ].join("");
    }

    function search(q) {
        const status = $("#search-status"), out = $("#results");
        const nq = normalise(q.trim());
        if (!nq) { searchSeq++; status.textContent = ""; out.innerHTML = ""; return; }
        const hits = [];
        for (const r of INDEX) {
            if (kindFilter && r.kind !== kindFilter) continue;
            let best = -1, via = "";
            r.keys.forEach((k, i) => {
                const score = k === nq ? 3 : k.startsWith(nq) ? 2 : k.includes(nq) ? 1 : -1;
                if (score > best || (score === best && i === 0)) { best = score; via = i === 0 ? "" : r.names[i - 1]; }
            });
            if (best >= 0) hits.push({r, best: best + (via ? 0 : 0.5) - (r.dep ? 2 : 0), via});
        }
        hits.sort((a, b) => b.best - a.best || a.r.label.localeCompare(b.r.label));
        const shown = hits.slice(0, 60);
        status.textContent = hits.length ? `${hits.length.toLocaleString("en-GB")} match${hits.length === 1 ? "" : "es"}${hits.length > shown.length ? `, first ${shown.length} shown` : ""}`
            : "No matches. Try a shorter part of the word.";
        const item = ({r, via}) => `<li><a href="?path=${encodeURIComponent(r.path)}">${esc(r.label)}</a>
            <span class="kind">${esc(KIND[r.kind])}${r.dep ? " · merged" : ""}</span>
            ${via ? `<span class="via">spelled “${esc(via)}”</span>` : ""}</li>`;
        out.innerHTML = shown.map(item).join("");
        if (hits.length >= FUZZY_WHEN_FEWER || Array.from(nq).length < 3) return;
        const mine = ++searchSeq;
        if (!FUZZY) status.textContent += hits.length ? " · looking for similar spellings…" : " Looking for similar spellings…";
        loadFuzzy().then(() => {
            if (mine !== searchSeq) return;
            const near = fuzzy(q, new Set(hits.map((h) => h.r.path)));
            status.textContent = status.textContent.replace(/ ·? ?[Ll]ooking for similar spellings…$/, "");
            if (!near.length) return;
            if (!hits.length) status.textContent = "No exact matches.";
            out.insertAdjacentHTML("beforeend", `<li class="near-head">Similar spellings</li>` + near.map((x) =>
                `<li><a href="?path=${encodeURIComponent(x.r.path)}">${esc(x.r.label)}</a>
                <span class="kind">${esc(KIND[x.r.kind])}</span>
                <span class="via" title="${Math.round(x.c * 100)}% alike, by the London Customs Accounts project's spelling encoder">≈ “${esc(x.form)}”, ${Math.round(x.c * 100)}% alike</span></li>`).join(""));
        }).catch(() => {
            if (mine === searchSeq) status.textContent = status.textContent.replace(/ ·? ?[Ll]ooking for similar spellings…$/, "");
        });
    }

    async function showLanding() {
        $("#landing").hidden = false;
        const q = $("#q");
        try {
            stats(await loadIndex());
        } catch {
            $("#stats").innerHTML = `<li class="muted">The search index could not be loaded.</li>`;
            q.disabled = true;
            return;
        }
        const run = () => search(q.value);
        q.addEventListener("input", run);
        document.querySelectorAll(".filters button").forEach((b) => b.addEventListener("click", () => {
            kindFilter = b.dataset.kind;
            document.querySelectorAll(".filters button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
            run();
        }));
        const initial = new URLSearchParams(location.search).get("q");
        if (initial) { q.value = initial; run(); }
    }

    const path = (new URLSearchParams(location.search).get("path") || "").replace(/^\/+|\/+$/g, "");
    if (path) showRecord(path); else showLanding();
})();
