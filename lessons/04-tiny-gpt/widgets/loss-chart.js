// Training (solid) and validation (dashed) loss for every run saved by train.py.
(() => {
  const root = document.querySelector('[data-widget="loss-chart"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const colors = ["--diagram-1", "--diagram-3", "--diagram-2", "--diagram-4", "--diagram-5"];
  root.innerHTML = `
    <style>
      .lch{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .lch svg{width:100%;height:auto;background:var(--surface);border:1px solid var(--border);border-radius:8px}
      .lch text{font:500 11px var(--font-sans);fill:var(--text-muted)}
      .lch .legend{display:flex;flex-direction:column;gap:.35rem;font-size:var(--step-2)}
      .lch .legend span{display:inline-block;width:.8rem;height:.8rem;border-radius:3px;margin-right:.5rem;vertical-align:-1px}
      .lch .legend b{font-variant-numeric:tabular-nums}
      .lch .ctl{display:flex;gap:var(--space-3);align-items:center;flex-wrap:wrap}
    </style>
    <div class="lch">
      <div class="ctl"><button class="btn" type="button" data-l="refresh">Refresh</button><span class="muted" data-l="status" role="status"></span></div>
      <div data-l="plot"></div><div class="legend" data-l="legend"></div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-l="${n}"]`);
  const W = 720, H = 300, L = 44, R = 14, T = 14, B = 30;

  function draw(runs) {
    runs = runs.filter((r) => Array.isArray(r.steps) && r.steps.length > 1 && Array.isArray(r.train_loss));
    if (!runs.length) {
      $("plot").innerHTML = "";
      $("legend").innerHTML = "";
      $("status").textContent = "No runs yet. Run the training script from the first experiment, then press Refresh.";
      return;
    }
    $("status").textContent = `${runs.length} run${runs.length === 1 ? "" : "s"} found.`;
    const maxStep = Math.max(...runs.map((r) => r.steps[r.steps.length - 1]));
    const all = runs.flatMap((r) => [...r.train_loss, ...(r.val_loss || [])]);
    const top = Math.ceil(Math.max(...all));
    const x = (s) => L + ((W - L - R) * s) / maxStep;
    const y = (v) => T + (H - T - B) * (1 - v / top);
    let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Loss against training step for ${runs.length} runs">`;
    for (let v = 0; v <= top; v++) {
      svg += `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--border)"/><text x="${L - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    [0, 0.5, 1].forEach((f) => (svg += `<text x="${x(maxStep * f)}" y="${H - 8}" text-anchor="${f === 0 ? "start" : f === 1 ? "end" : "middle"}">step ${Math.round(maxStep * f).toLocaleString()}</text>`));
    const line = (r, vals) => vals.map((v, i) => `${i ? "L" : "M"}${x(r.steps[i]).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
    let legend = "";
    runs.forEach((r, k) => {
      const c = `var(${colors[k % colors.length]})`;
      svg += `<path d="${line(r, r.train_loss)}" fill="none" stroke="${c}" stroke-width="2.2"/>`;
      const val = r.val_loss && r.val_loss.length === r.steps.length ? r.val_loss : null;
      if (val) svg += `<path d="${line(r, val)}" fill="none" stroke="${c}" stroke-width="2.2" stroke-dasharray="6 5"/>`;
      const last = r.steps.length - 1;
      svg += `<circle cx="${x(r.steps[last])}" cy="${y((val || r.train_loss)[last])}" r="4" fill="${c}"/>`;
      const row = document.createElement("div");
      const sw = document.createElement("span");
      sw.style.background = c;
      const text = document.createElement("b");
      text.textContent = r.name;
      row.append(sw, text, document.createTextNode(
        `  training ${r.train_loss[last].toFixed(3)}` + (val ? `, validation ${val[last].toFixed(3)}` : "") +
        (r.config && r.config.parameters ? ` · ${Number(r.config.parameters).toLocaleString()} parameters` : "") +
        (r.seconds ? ` · ${Math.round(r.seconds)}s` : "")));
      legend += row.outerHTML;
    });
    $("plot").innerHTML = svg + "</svg>";
    $("legend").innerHTML = legend;
  }

  function load() {
    $("status").textContent = "Loading…";
    fetch("/api/course/runs").then((r) => r.json()).then((d) => draw(d.runs || []))
      .catch(() => ($("status").textContent = "Could not load the runs. Is the course app running?"));
  }
  $("refresh").addEventListener("click", load);
  load();
})();
