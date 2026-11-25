// A 4 x 4 confusion table you can edit. Same arithmetic as score() and confusion().
(() => {
  const root = document.querySelector('[data-widget="confusion-explorer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  // Rows: true P1..P4. The row totals are the real mix of the 100 held-back incidents: 2, 6, 51, 41.
  const presets = {
    "Always P3": [[0, 0, 2, 0], [0, 0, 6, 0], [0, 0, 51, 0], [0, 0, 41, 0]],
    "Leans severe": [[2, 0, 0, 0], [3, 3, 0, 0], [9, 24, 18, 0], [1, 9, 21, 10]],
    "Leans mild": [[0, 1, 1, 0], [0, 2, 3, 1], [0, 1, 30, 20], [0, 0, 4, 37]],
    "Perfect": [[2, 0, 0, 0], [0, 6, 0, 0], [0, 0, 51, 0], [0, 0, 0, 41]],
  };
  let table = presets["Leans severe"].map((r) => [...r]);
  root.innerHTML = `
    <style>
      .cfx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .cfx .presets{display:flex;flex-wrap:wrap;gap:.5rem}
      .cfx button{font:600 var(--step-2) var(--font-sans, inherit);padding:.35rem .8rem;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer}
      .cfx button[aria-pressed="true"]{border-color:var(--diagram-1);color:var(--diagram-1)}
      .cfx .grid{display:grid;grid-template-columns:5.5rem repeat(4,minmax(3.2rem,5rem)) 4rem;gap:.35rem;align-items:center;font-size:var(--step-2)}
      .cfx .h{font:600 var(--step-1)/1.2 var(--font-mono);color:var(--text-muted);text-align:center}
      .cfx .h.l{text-align:left}
      .cfx input{width:100%;box-sizing:border-box;text-align:center;font:500 var(--step-2) var(--font-mono);padding:.45rem .2rem;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text)}
      .cfx input.diag{border-color:var(--diagram-1);border-width:2px}
      .cfx input.near{border-style:dashed;border-color:var(--text-muted)}
      .cfx .sum{font-family:var(--font-mono);text-align:right;color:var(--text-muted)}
      .cfx .out{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--space-3)}
      .cfx .stat{display:flex;flex-direction:column;gap:.15rem}
      .cfx .stat b{font:600 1.5rem/1.1 var(--font-mono);color:var(--diagram-1);font-variant-numeric:tabular-nums}
      .cfx .stat span{font-size:var(--step-2);color:var(--text-muted)}
    </style>
    <div class="cfx">
      <p class="muted">Each cell counts incidents. The row is the true priority, the column is what the triager said. Solid boxes are exact; dashed boxes are one level out. Pick a triager, or type your own counts.</p>
      <div class="presets" data-c="presets"></div>
      <div class="grid" data-c="grid"></div>
      <div class="out" data-c="out" role="status"></div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-c="${n}"]`);
  let active = "Leans severe";

  function draw(rebuild) {
    if (rebuild) {
      $("presets").innerHTML = Object.keys(presets).map((n) => `<button type="button" data-p="${n}" aria-pressed="${n === active}">${n}</button>`).join("");
      let html = `<span class="h l">true ↓ said →</span>` + [1, 2, 3, 4].map((p) => `<span class="h">P${p}</span>`).join("") + `<span class="h">total</span>`;
      table.forEach((row, i) => {
        html += `<span class="h l">really P${i + 1}</span>`;
        row.forEach((v, j) => {
          const cls = i === j ? "diag" : Math.abs(i - j) === 1 ? "near" : "";
          html += `<input class="${cls}" type="number" min="0" max="999" value="${v}" data-i="${i}" data-j="${j}" aria-label="really P${i + 1}, said P${j + 1}">`;
        });
        html += `<span class="sum" data-row="${i}"></span>`;
      });
      $("grid").innerHTML = html;
    }
    let n = 0, exact = 0, near = 0, over = 0, under = 0;
    table.forEach((row, i) => {
      root.querySelector(`[data-row="${i}"]`).textContent = row.reduce((a, b) => a + b, 0);
      row.forEach((v, j) => { n += v; if (i === j) exact += v; if (Math.abs(i - j) <= 1) near += v; if (j < i) over += v; if (j > i) under += v; });
    });
    const pct = (x) => (n ? `${Math.round((100 * x) / n)}%` : "–");
    const p1 = table[0].reduce((a, b) => a + b, 0);
    $("out").innerHTML = `
      <div class="stat"><b>${pct(exact)}</b><span>priority exact</span></div>
      <div class="stat"><b>${pct(near)}</b><span>within one level</span></div>
      <div class="stat"><b>${over}</b><span>called more severe than it was</span></div>
      <div class="stat"><b>${under}</b><span>called less severe than it was</span></div>
      <div class="stat"><b>${p1 ? `${table[0][0]} of ${p1}` : "–"}</b><span>real P1s caught as P1</span></div>`;
  }
  root.addEventListener("click", (e) => {
    const name = e.target.dataset && e.target.dataset.p;
    if (!name) return;
    active = name; table = presets[name].map((r) => [...r]); draw(true);
  });
  root.addEventListener("input", (e) => {
    const { i, j } = e.target.dataset;
    if (i === undefined) return;
    table[Number(i)][Number(j)] = Math.max(0, Math.floor(Number(e.target.value) || 0));
    active = ""; root.querySelectorAll("[data-p]").forEach((b) => b.setAttribute("aria-pressed", "false"));
    draw(false);
  });
  draw(true);
})();
