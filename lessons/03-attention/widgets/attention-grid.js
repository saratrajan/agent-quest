// Three tokens with editable 2-number queries and keys. Shows softmax(QK^T / sqrt(2)) as a grid.
(() => {
  const root = document.querySelector('[data-widget="attention-grid"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const names = ["position 1", "position 2", "position 3"];
  const start = { q: [[1, 0], [0, 1], [1, 1]], k: [[1, 0], [0, 1], [1, 1]] };
  let q, k, masked = false;
  root.innerHTML = `
    <style>
      .atg{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-4)}
      .atg .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:var(--space-5)}
      .atg table{border-collapse:collapse;font-size:var(--step-2)}
      .atg th{font:600 var(--step-1)/1.2 var(--font-sans);color:var(--text-muted);text-align:left;padding:.3rem .5rem .3rem 0}
      .atg td{padding:.2rem .5rem .2rem 0}
      .atg input[type=number]{width:3.6rem;font:inherit;padding:.3rem;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text)}
      .atg .grid{display:grid;grid-template-columns:5.5rem repeat(3,4rem);gap:4px;font:500 .85rem var(--font-mono);align-items:center}
      .atg .cell{height:3rem;border-radius:6px;display:grid;place-items:center;border:1px solid var(--border)}
      .atg .cell.off{border-style:dashed;color:var(--text-muted);background:transparent}
      .atg .head{color:var(--text-muted);font:600 var(--step-1) var(--font-sans);text-align:center}
      .atg .side{color:var(--text-muted);font:600 var(--step-1) var(--font-sans)}
      .atg .ctl{display:flex;gap:var(--space-4);flex-wrap:wrap;align-items:center}
    </style>
    <div class="atg">
      <div class="cols">
        <div><table><thead><tr><th></th><th colspan="2">Query</th><th colspan="2">Key</th></tr></thead><tbody data-at="inputs"></tbody></table></div>
        <div><div class="grid" data-at="grid" role="img" aria-label="Attention weights"></div></div>
      </div>
      <div class="ctl"><label><input type="checkbox" data-at="mask"> Causal mask (no looking ahead)</label>
      <button class="btn" type="button" data-at="reset">Reset to the lesson example</button>
      <span class="muted" data-at="note"></span></div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-at="${n}"]`);

  function build() {
    $("inputs").innerHTML = names.map((n, i) => `<tr><td>${n}</td>` +
      [0, 1].map((j) => `<td><input type="number" step="0.5" data-v="q" data-i="${i}" data-j="${j}" value="${q[i][j]}" aria-label="Query ${i + 1}, number ${j + 1}"></td>`).join("") +
      [0, 1].map((j) => `<td><input type="number" step="0.5" data-v="k" data-i="${i}" data-j="${j}" value="${k[i][j]}" aria-label="Key ${i + 1}, number ${j + 1}"></td>`).join("") + "</tr>").join("");
  }

  function weights() {
    return q.map((qi, i) => {
      const scores = k.map((kj, j) => (masked && j > i ? -Infinity : (qi[0] * kj[0] + qi[1] * kj[1]) / Math.SQRT2));
      const top = Math.max(...scores);
      const exps = scores.map((s) => (s === -Infinity ? 0 : Math.exp(s - top)));
      const total = exps.reduce((a, b) => a + b, 0);
      return exps.map((e) => e / total);
    });
  }

  function draw() {
    const w = weights();
    let html = '<span></span>' + names.map((_, j) => `<span class="head">looks at ${j + 1}</span>`).join("");
    w.forEach((row, i) => {
      html += `<span class="side">${names[i]}</span>`;
      row.forEach((val, j) => {
        const off = masked && j > i;
        const dark = val > 0.55;
        html += off ? '<span class="cell off">masked</span>'
          : `<span class="cell" style="background: color-mix(in srgb, var(--diagram-1) ${Math.round(val * 100)}%, var(--surface)); color: ${dark ? "#fff" : "var(--text)"}">${val.toFixed(3)}</span>`;
      });
    });
    $("grid").innerHTML = html;
    $("note").textContent = `Row 3 sums to ${w[2].reduce((a, b) => a + b, 0).toFixed(3)}.`;
  }

  function reset() {
    q = start.q.map((r) => [...r]); k = start.k.map((r) => [...r]);
    build(); draw();
  }
  root.addEventListener("input", (e) => {
    const el = e.target;
    if (el.dataset.v) { (el.dataset.v === "q" ? q : k)[Number(el.dataset.i)][Number(el.dataset.j)] = Number(el.value) || 0; draw(); }
    if (el.dataset.at === "mask") { masked = el.checked; draw(); }
  });
  $("reset").addEventListener("click", reset);
  reset();
})();
