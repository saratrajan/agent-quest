// Softmax and cross-entropy on three scores. Same arithmetic as cross_entropy_by_hand.
(() => {
  const root = document.querySelector('[data-widget="softmax-explorer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const tokens = ["failing", "timing", "resolved"];
  const start = [2.0, 1.0, 0.1];
  root.innerHTML = `
    <style>
      .smx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .smx .rowx{display:grid;grid-template-columns:5.5rem 9rem 3rem minmax(0,1fr) 3.5rem;gap:.7rem;align-items:center;font-size:var(--step-2)}
      .smx .track{height:18px;background:var(--border);border-radius:4px;overflow:hidden}
      .smx .fill{height:100%;background:var(--diagram-1);border-radius:4px}
      .smx .rowx.target .fill{background:var(--diagram-3)}
      .smx .rowx.target .name{font-weight:700}
      .smx .mono{font-family:var(--font-mono);font-variant-numeric:tabular-nums;text-align:right}
      .smx .out{display:flex;gap:var(--space-5);flex-wrap:wrap;align-items:baseline;border-top:1px solid var(--border);padding-top:var(--space-3)}
      .smx .out b{font:700 1.5rem var(--font-mono);color:var(--diagram-3)}
      .smx input[type=range]{width:100%}
      @media (max-width:560px){.smx .rowx{grid-template-columns:5rem minmax(0,1fr) 3rem}.smx .track,.smx .p{grid-column:1/-1}}
    </style>
    <div class="smx">
      <div class="rows"></div>
      <div class="out"><span>Loss for the chosen target: <b data-out="loss"></b></span><span class="muted" data-out="note"></span>
      <button class="btn" type="button" data-out="reset">Reset to the lesson example</button></div>
    </div>`;
  const rows = root.querySelector(".rows");
  let z = [...start], target = 0;
  rows.innerHTML = tokens.map((t, i) => `
    <div class="rowx" data-i="${i}">
      <label class="name"><input type="radio" name="smx-target" value="${i}" ${i === 0 ? "checked" : ""}> ${t}</label>
      <input type="range" min="-3" max="5" step="0.1" value="${start[i]}" aria-label="Score for ${t}">
      <span class="mono z"></span><span class="track"><span class="fill" style="display:block"></span></span><span class="mono p"></span>
    </div>`).join("");

  function draw() {
    const top = Math.max(...z);
    const exps = z.map((v) => Math.exp(v - top));
    const total = exps.reduce((a, b) => a + b, 0);
    const probs = exps.map((e) => e / total);
    rows.querySelectorAll(".rowx").forEach((row, i) => {
      row.classList.toggle("target", i === target);
      row.querySelector(".z").textContent = z[i].toFixed(1);
      row.querySelector(".fill").style.width = `${(probs[i] * 100).toFixed(1)}%`;
      row.querySelector(".p").textContent = probs[i].toFixed(3);
    });
    const loss = -Math.log(probs[target]);
    root.querySelector('[data-out="loss"]').textContent = loss.toFixed(3);
    root.querySelector('[data-out="note"]').textContent =
      `A uniform guess over three tokens would score ${Math.log(3).toFixed(3)}.` + (loss > Math.log(3) ? " This is worse than guessing." : "");
  }
  rows.addEventListener("input", (e) => {
    const row = e.target.closest(".rowx");
    if (e.target.type === "range") z[Number(row.dataset.i)] = Number(e.target.value);
    if (e.target.type === "radio") target = Number(e.target.value);
    draw();
  });
  root.querySelector('[data-out="reset"]').addEventListener("click", () => {
    z = [...start]; target = 0;
    rows.querySelectorAll("input[type=range]").forEach((el, i) => (el.value = start[i]));
    rows.querySelector('input[type=radio][value="0"]').checked = true;
    draw();
  });
  draw();
})();
