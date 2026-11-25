// Temperature, top-k and top-p on one fixed distribution. Same order as sample_next.
(() => {
  const root = document.querySelector('[data-widget="sampling-explorer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const tokens = ["failing", "down", "slow", "timing", "degraded", "unavailable", "offline", "healthy", "on", "purple"];
  const logits = [3.2, 2.6, 2.1, 1.7, 1.2, 0.8, 0.3, -0.4, -1.0, -2.5];
  root.innerHTML = `
    <style>
      .spx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .spx .ctl{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:var(--space-4)}
      .spx label{display:flex;flex-direction:column;gap:.3rem;font-size:var(--step-2);font-weight:600}
      .spx label span{font:500 var(--step-2) var(--font-mono);color:var(--diagram-1)}
      .spx .rowx{display:grid;grid-template-columns:7rem minmax(0,1fr) 3.4rem;gap:.7rem;align-items:center;font-size:var(--step-2)}
      .spx .track{height:16px;background:var(--border);border-radius:4px;position:relative;overflow:hidden}
      .spx .fill{position:absolute;inset:0 auto 0 0;background:var(--diagram-1);border-radius:4px}
      .spx .ghost{position:absolute;top:0;bottom:0;width:2px;background:var(--text-muted)}
      .spx .rowx.out{color:var(--text-muted);text-decoration:line-through}
      .spx .rowx.out .fill{background:transparent}
      .spx .mono{font-family:var(--font-mono);text-align:right;font-variant-numeric:tabular-nums}
    </style>
    <div class="spx">
      <p class="muted">Next word after "The payment gateway is". The thin mark on each bar is the model's own probability, before any control.</p>
      <div class="ctl">
        <label>Temperature <span data-s="tv"></span><input type="range" data-s="t" min="0.1" max="2" step="0.1" value="1"></label>
        <label>Top-k <span data-s="kv"></span><input type="range" data-s="k" min="1" max="10" step="1" value="10"></label>
        <label>Top-p <span data-s="pv"></span><input type="range" data-s="p" min="0.1" max="1" step="0.05" value="1"></label>
      </div>
      <div data-s="rows"></div>
      <span class="muted" data-s="note" role="status"></span>
    </div>`;
  const $ = (n) => root.querySelector(`[data-s="${n}"]`);
  const softmax = (z) => { const m = Math.max(...z.filter(Number.isFinite)); const e = z.map((v) => (Number.isFinite(v) ? Math.exp(v - m) : 0)); const s = e.reduce((a, b) => a + b, 0); return e.map((v) => v / s); };
  const base = softmax(logits);

  function draw() {
    const t = Number($("t").value), k = Number($("k").value), p = Number($("p").value);
    let z = logits.map((v) => v / t);
    const kth = [...z].sort((a, b) => b - a)[k - 1];
    z = z.map((v) => (v < kth ? -Infinity : v));
    const probs = softmax(z);
    const order = probs.map((v, i) => [v, i]).sort((a, b) => b[0] - a[0]);
    let before = 0;
    order.forEach(([v, i]) => { if (before >= p) z[i] = -Infinity; before += v; });
    const final = softmax(z);
    $("tv").textContent = t.toFixed(1); $("kv").textContent = k === 10 ? "off (10)" : k; $("pv").textContent = p === 1 ? "off (1.00)" : p.toFixed(2);
    $("rows").innerHTML = tokens.map((name, i) => `
      <div class="rowx ${final[i] === 0 ? "out" : ""}"><span>${name}</span>
      <span class="track"><span class="fill" style="width:${(final[i] * 100).toFixed(1)}%"></span><span class="ghost" style="left:${(base[i] * 100).toFixed(1)}%"></span></span>
      <span class="mono">${final[i] === 0 ? "0" : final[i].toFixed(3)}</span></div>`).join("");
    const left = final.filter((v) => v > 0).length;
    $("note").textContent = `${left} of 10 tokens can still be chosen. The favourite has ${(Math.max(...final) * 100).toFixed(0)}% of the probability.`;
  }
  root.addEventListener("input", draw);
  draw();
})();
