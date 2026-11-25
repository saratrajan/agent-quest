// Reciprocal rank fusion on two short rankings. Same arithmetic as rrf().
(() => {
  const root = document.querySelector('[data-widget="fusion-explorer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const names = {
    A: "Refunds taking more than 10 days", B: "Refund queue backlog growing", C: "Customers chasing pending refunds",
    D: "Card payments declined at checkout", E: "Loyalty points missing after refund", F: "Refund policy page shows old text",
  };
  const lists = { keyword: ["F", "A", "B", "E", "D"], vector: ["B", "C", "A", "D", "E"] };
  root.innerHTML = `
    <style>
      .fsx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .fsx .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:var(--space-4)}
      .fsx h4{margin:0 0 .4rem;font:600 var(--step-1)/1.2 var(--font-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
      .fsx ol{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:.3rem;font-size:var(--step-2)}
      .fsx li{display:grid;grid-template-columns:1.4rem minmax(0,1fr) auto;gap:.5rem;align-items:center;padding:.3rem .5rem;border:1px solid var(--border);border-radius:6px;background:var(--surface)}
      .fsx li .n{font-family:var(--font-mono);color:var(--text-muted)}
      .fsx li button{font:600 .75rem var(--font-mono);border:1px solid var(--border);background:var(--bg);color:var(--text);border-radius:4px;cursor:pointer;padding:.1rem .35rem}
      .fsx li button:disabled{opacity:.35;cursor:default}
      .fsx .fused li{grid-template-columns:1.4rem minmax(0,1fr);border-color:var(--diagram-1)}
      .fsx .fused .body{display:flex;flex-direction:column;gap:.15rem;min-width:0}
      .fsx .mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums;text-align:right;color:var(--text-muted);font-size:.78rem}
      .fsx label{display:flex;flex-direction:column;gap:.3rem;font-size:var(--step-2);font-weight:600;max-width:320px}
      .fsx label span{font:500 var(--step-2) var(--font-mono);color:var(--diagram-1)}
    </style>
    <div class="fsx">
      <p class="muted">Query: "refund still not received". Two searches disagree. Move items up in either list and watch the merged order.</p>
      <div class="cols">
        <div><h4>Keyword ranking</h4><ol data-f="keyword"></ol></div>
        <div><h4>Vector ranking</h4><ol data-f="vector"></ol></div>
        <div><h4>Merged</h4><ol class="fused" data-f="fused"></ol></div>
      </div>
      <label>k, the constant in 1 / (k + rank) <span data-f="kv"></span><input type="range" data-f="k" min="1" max="100" step="1" value="60" aria-label="The constant k"></label>
      <span class="muted" data-f="note" role="status"></span>
    </div>`;
  const $ = (n) => root.querySelector(`[data-f="${n}"]`);
  function draw() {
    const k = Number($("k").value);
    for (const key of ["keyword", "vector"]) {
      $(key).innerHTML = lists[key].map((id, i) => `<li><span class="n">${i + 1}</span><span>${names[id]}</span>
        <button type="button" data-list="${key}" data-i="${i}" ${i === 0 ? "disabled" : ""} aria-label="Move ${names[id]} up in the ${key} ranking">↑</button></li>`).join("");
    }
    const total = {}, parts = {};
    for (const key of ["keyword", "vector"]) lists[key].forEach((id, i) => {
      total[id] = (total[id] || 0) + 1 / (k + i + 1);
      (parts[id] = parts[id] || []).push(`1/${k + i + 1}`);
    });
    const order = Object.keys(total).sort((a, b) => total[b] - total[a]);
    $("fused").innerHTML = order.map((id, i) => `<li><span class="n">${i + 1}</span><span class="body"><span>${names[id]}</span>
      <span class="mono" style="text-align:left">${parts[id].join(" + ")} = ${total[id].toFixed(4)}</span></span></li>`).join("");
    $("kv").textContent = k;
    const place = (id) => order.indexOf(id) + 1;
    $("note").textContent = `The policy page, first by keywords but absent from the vector list, is at position ${place("F")}. `
      + (k < 5 ? "With a small k, first place in one list counts for a lot." : "With a large k, being found by both searches matters more than being first in one.");
  }
  root.addEventListener("click", (e) => {
    const { list, i } = e.target.dataset || {};
    if (!list) return;
    const n = Number(i);
    [lists[list][n - 1], lists[list][n]] = [lists[list][n], lists[list][n - 1]];
    draw();
  });
  root.addEventListener("input", draw);
  draw();
})();
