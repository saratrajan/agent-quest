// Interactive byte-pair encoding stepper. Follows the same rules as bpe.py:
// start from UTF-8 bytes, merge the most frequent pair, first pair seen wins a tie.
(() => {
  const root = document.querySelector('[data-widget="bpe-stepper"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const DEFAULT = "aaabdaaabac";
  const colors = ["--diagram-1", "--diagram-2", "--diagram-3", "--diagram-4", "--diagram-5"];
  root.innerHTML = `
    <style>
      .bpe{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);display:flex;flex-direction:column;gap:var(--space-3);background:var(--bg)}
      .bpe .row{display:flex;gap:var(--space-2);flex-wrap:wrap;align-items:center}
      .bpe input{flex:1;min-width:12rem;font:inherit;padding:.55rem .7rem;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--text)}
      .bpe .toks{display:flex;flex-wrap:wrap;gap:4px;min-height:2.4rem}
      .bpe .tok{font:500 .85rem/1 var(--font-mono);padding:.45rem .5rem;border-radius:5px;border:1.5px solid var(--border);background:var(--surface);white-space:pre}
      .bpe .tok.merged{border-color:var(--c);color:var(--c)}
      .bpe .tok.next{outline:2px dashed var(--warning);outline-offset:1px}
      .bpe .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:var(--space-4)}
      .bpe h4{font:600 var(--step-1)/1 var(--font-mono);letter-spacing:.08em;text-transform:uppercase;color:var(--text-muted);margin:0 0 .5rem}
      .bpe table{border-collapse:collapse;font:400 .85rem/1.5 var(--font-mono);width:100%}
      .bpe td{padding:.1rem .5rem .1rem 0;white-space:pre}
      .bpe tr.best td{color:var(--warning);font-weight:600}
      .bpe .stat{font:500 var(--step-2)/1.4 var(--font-mono);color:var(--text-muted)}
    </style>
    <div class="bpe">
      <div class="row"><label class="eyebrow" for="bpe-text">Text</label><input id="bpe-text" value="${DEFAULT}" maxlength="160" spellcheck="false"></div>
      <div class="row"><button class="btn primary" type="button" data-bpe="step">Merge the top pair</button><button class="btn" type="button" data-bpe="reset">Start again</button><span class="stat" data-bpe="stat" role="status"></span></div>
      <div class="toks" data-bpe="toks" aria-label="Current token sequence"></div>
      <div class="cols">
        <div><h4>Pair counts now</h4><table data-bpe="counts"></table></div>
        <div><h4>Merges learned</h4><table data-bpe="merges"></table></div>
      </div>
    </div>`;
  const $ = (name) => root.querySelector(`[data-bpe="${name}"]`);
  const input = root.querySelector("#bpe-text");
  const decoder = new TextDecoder("utf-8", { fatal: false });
  let ids, vocab, merges, nBytes;

  const label = (id) => decoder.decode(vocab.get(id)).replace(/ /g, "␣").replace(/\n/g, "⏎");

  function pairCounts() {
    const counts = new Map(); // insertion order = order first seen
    for (let i = 0; i + 1 < ids.length; i++) {
      const key = ids[i] + "," + ids[i + 1];
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    return counts;
  }

  function topPair(counts) {
    let best = null;
    for (const [key, count] of counts) {
      if (best === null || count > best.count) best = { key, count }; // strictly greater: first seen wins a tie
    }
    return best;
  }

  function reset() {
    const bytes = new TextEncoder().encode(input.value);
    ids = Array.from(bytes);
    nBytes = ids.length;
    vocab = new Map();
    for (let i = 0; i < 256; i++) vocab.set(i, new Uint8Array([i]));
    merges = [];
    draw();
  }

  function step() {
    const best = topPair(pairCounts());
    if (!best || best.count < 2) return;
    const [a, b] = best.key.split(",").map(Number);
    const id = 256 + merges.length;
    const joined = new Uint8Array(vocab.get(a).length + vocab.get(b).length);
    joined.set(vocab.get(a));
    joined.set(vocab.get(b), vocab.get(a).length);
    vocab.set(id, joined);
    const out = [];
    for (let i = 0; i < ids.length; ) {
      if (i + 1 < ids.length && ids[i] === a && ids[i + 1] === b) { out.push(id); i += 2; }
      else { out.push(ids[i]); i += 1; }
    }
    ids = out;
    merges.push({ a, b, id, count: best.count });
    draw();
  }

  function draw() {
    const counts = pairCounts();
    const best = topPair(counts);
    const canStep = best && best.count >= 2;
    const [na, nb] = canStep ? best.key.split(",").map(Number) : [null, null];
    const toks = $("toks");
    toks.textContent = "";
    ids.forEach((id, i) => {
      const el = document.createElement("span");
      el.className = "tok" + (id >= 256 ? " merged" : "");
      if (id >= 256) el.style.setProperty("--c", `var(${colors[(id - 256) % colors.length]})`);
      const inNext = canStep && ((id === na && ids[i + 1] === nb) || (id === nb && ids[i - 1] === na));
      if (inNext) el.classList.add("next");
      el.textContent = label(id);
      el.title = `token ${id}`;
      toks.appendChild(el);
    });
    const rows = [...counts].sort((x, y) => y[1] - x[1]).slice(0, 8);
    $("counts").innerHTML = "";
    rows.forEach(([key, count]) => {
      const [a, b] = key.split(",").map(Number);
      const tr = document.createElement("tr");
      if (canStep && key === best.key) tr.className = "best";
      tr.innerHTML = "<td></td><td></td>";
      tr.children[0].textContent = `'${label(a)}' + '${label(b)}'`;
      tr.children[1].textContent = `× ${count}`;
      $("counts").appendChild(tr);
    });
    $("merges").innerHTML = "";
    merges.forEach((m) => {
      const tr = document.createElement("tr");
      tr.innerHTML = "<td></td><td></td>";
      tr.children[0].textContent = `${m.id}`;
      tr.children[1].textContent = `'${label(m.a)}' + '${label(m.b)}' → '${label(m.id)}'`;
      $("merges").appendChild(tr);
    });
    if (!merges.length) $("merges").innerHTML = "<tr><td>None yet</td></tr>";
    $("stat").textContent = `${nBytes} bytes → ${ids.length} tokens · vocabulary ${256 + merges.length}` + (canStep ? "" : " · no pair occurs twice, finished");
    $("step").disabled = !canStep;
  }

  $("step").addEventListener("click", step);
  $("reset").addEventListener("click", reset);
  input.addEventListener("input", reset);
  reset();
})();
