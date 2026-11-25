// Two vectors you can turn and stretch. Cosine follows the angle and ignores the length.
(() => {
  const root = document.querySelector('[data-widget="cosine-explorer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const a = [3, 1.5];
  root.innerHTML = `
    <style>
      .csx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:grid;grid-template-columns:minmax(220px,300px) minmax(0,1fr);gap:var(--space-4);align-items:center}
      @media (max-width:640px){.csx{grid-template-columns:1fr}}
      .csx svg{width:100%;height:auto;background:var(--surface);border:1px solid var(--border);border-radius:8px}
      .csx .side{display:flex;flex-direction:column;gap:var(--space-3)}
      .csx label{display:flex;flex-direction:column;gap:.3rem;font-size:var(--step-2);font-weight:600}
      .csx label span{font:500 var(--step-2) var(--font-mono);color:var(--diagram-1)}
      .csx table{border-collapse:collapse;font-size:var(--step-2);width:100%}
      .csx td{padding:.3rem 0;border-bottom:1px solid var(--border)}
      .csx td:last-child{text-align:right;font-family:var(--font-mono);font-variant-numeric:tabular-nums}
      .csx tr.key td{font-weight:700;color:var(--diagram-1)}
    </style>
    <div class="csx">
      <svg viewBox="-5 -5 10 10" role="img" aria-label="Two vectors drawn from the same origin">
        <line x1="-5" y1="0" x2="5" y2="0" stroke="var(--border)" stroke-width="0.04"/>
        <line x1="0" y1="-5" x2="0" y2="5" stroke="var(--border)" stroke-width="0.04"/>
        <line data-v="la" x1="0" y1="0" stroke="var(--text-muted)" stroke-width="0.12" stroke-linecap="round"/>
        <line data-v="lb" x1="0" y1="0" stroke="var(--diagram-1)" stroke-width="0.12" stroke-linecap="round"/>
        <line data-v="ld" stroke="var(--text-muted)" stroke-width="0.05" stroke-dasharray="0.15 0.15"/>
        <text data-v="ta" font-size="0.5" fill="var(--text-muted)">a</text>
        <text data-v="tb" font-size="0.5" fill="var(--diagram-1)">b</text>
      </svg>
      <div class="side">
        <label>Direction of b <span data-v="av"></span><input type="range" data-v="angle" min="-180" max="180" step="1" value="60" aria-label="Direction of b in degrees from a"></label>
        <label>Length of b <span data-v="lv"></span><input type="range" data-v="len" min="0.5" max="4.5" step="0.1" value="2" aria-label="Length of b"></label>
        <table>
          <tr><td>a · b (dot product)</td><td data-v="dot"></td></tr>
          <tr><td>length of a × length of b</td><td data-v="prod"></td></tr>
          <tr class="key"><td>cosine similarity</td><td data-v="cos"></td></tr>
          <tr><td>straight-line distance (dashed)</td><td data-v="dist"></td></tr>
        </table>
        <span class="muted" data-v="note" role="status"></span>
      </div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-v="${n}"]`);
  const base = Math.atan2(a[1], a[0]);
  function draw() {
    const deg = Number($("angle").value), len = Number($("len").value);
    const t = base + (deg * Math.PI) / 180;
    const b = [len * Math.cos(t), len * Math.sin(t)];
    const dot = a[0] * b[0] + a[1] * b[1], la = Math.hypot(...a), lb = Math.hypot(...b);
    const cos = dot / (la * lb), dist = Math.hypot(a[0] - b[0], a[1] - b[1]);
    const set = (el, x, y) => { $(el).setAttribute("x2", x); $(el).setAttribute("y2", -y); };
    set("la", a[0], a[1]); set("lb", b[0], b[1]);
    $("ld").setAttribute("x1", a[0]); $("ld").setAttribute("y1", -a[1]); set("ld", b[0], b[1]);
    $("ta").setAttribute("x", a[0] + 0.15); $("ta").setAttribute("y", -a[1] - 0.15);
    $("tb").setAttribute("x", b[0] + 0.15); $("tb").setAttribute("y", -b[1] - 0.15);
    $("av").textContent = `${deg}° from a`; $("lv").textContent = len.toFixed(1);
    $("dot").textContent = dot.toFixed(2); $("prod").textContent = (la * lb).toFixed(2);
    $("cos").textContent = cos.toFixed(3); $("dist").textContent = dist.toFixed(2);
    $("note").textContent = Math.abs(deg) < 1 ? "Same direction: cosine is 1 whatever the length."
      : Math.abs(Math.abs(deg) - 90) < 1 ? "At right angles: cosine is 0. Unrelated."
      : Math.abs(deg) > 179 ? "Opposite directions: cosine is -1."
      : "Move the length slider: the distance changes, the cosine does not.";
  }
  root.addEventListener("input", draw);
  draw();
})();
