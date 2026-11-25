// Step through one real tool-calling conversation and watch what the model re-reads each turn.
(() => {
  const root = document.querySelector('[data-widget="conversation-stepper"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  // Recorded from explore.py --chain with qwen3:4b. "read" is the prompt tokens of the model turn that follows.
  const steps = [
    { who: "you", text: "Incident INC0010404 was opened at 2026-07-27T23:59:12Z: \"Cruise deposit amount calculated wrongly\". Was anything deployed to the cruises service shortly before, and which runbook would apply?" },
    { who: "model", read: 559, thought: "I need to check recent deploys to the cruises service around the time the incident was opened.", call: 'recent_deploys({"service_id": "cruises", "before": "2026-07-27T23:59:12Z"})' },
    { who: "code", text: '{"result": [{"id": "DEP00237", "service": "cruises", "deployed_at": "2026-07-27T22:45:12Z", "version": "cruises-v3.24.0", "summary": "Dependency updates"}], "total": 1}' },
    { who: "model", read: 772, thought: "There was a deploy 1 hour 14 minutes before the incident. Now I need the runbooks for the cruises service.", call: 'get_service({"service_id": "cruises"})' },
    { who: "code", text: '{"id": "cruises", "team": "Cruise", "tier": 2, "depends_on": ["payments", "identity", "supplier-sync"], "runbooks": []}' },
    { who: "model", read: 943, answer: "A deploy (DEP00237) went to the cruises service 1 hour 14 minutes before the incident. The cruises service has no runbooks defined." },
  ];
  const label = { you: "You", model: "Model writes", code: "Your code runs it and returns" };
  root.innerHTML = `
    <style>
      .cvx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:flex;flex-direction:column;gap:var(--space-3)}
      .cvx .bar{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap}
      .cvx button{font:600 var(--step-2) inherit;padding:.4rem .9rem;border-radius:999px;border:1px solid var(--border);background:var(--surface);color:var(--text);cursor:pointer}
      .cvx button:disabled{opacity:.45;cursor:default}
      .cvx .msg{border-left:3px solid var(--border);padding:.2rem 0 .2rem .8rem;display:flex;flex-direction:column;gap:.25rem;font-size:var(--step-2)}
      .cvx .msg.model{border-color:var(--diagram-1)}
      .cvx .msg.code{border-color:var(--text-muted)}
      .cvx .who{font:600 var(--step-1)/1.2 var(--font-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
      .cvx code{font-family:var(--font-mono);font-size:.82rem;overflow-wrap:anywhere}
      .cvx .thought{font-style:italic;color:var(--text-muted)}
      .cvx .meter{display:grid;grid-template-columns:9rem minmax(0,1fr) 4.5rem;gap:.6rem;align-items:center;font-size:var(--step-2)}
      .cvx .track{height:14px;background:var(--border);border-radius:4px;overflow:hidden}
      .cvx .fill{height:100%;background:var(--diagram-1);border-radius:4px}
      .cvx .mono{font-family:var(--font-mono);text-align:right;font-variant-numeric:tabular-nums}
    </style>
    <div class="cvx">
      <div class="bar"><button type="button" data-c="next">Next message</button><button type="button" data-c="reset">Start again</button>
        <span class="muted" data-c="count" role="status"></span></div>
      <div data-c="log" style="display:flex;flex-direction:column;gap:var(--space-3)"></div>
      <div data-c="meters" style="display:flex;flex-direction:column;gap:.35rem"></div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-c="${n}"]`);
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  let shown = 1;
  function draw() {
    $("log").innerHTML = steps.slice(0, shown).map((s) => `
      <div class="msg ${s.who}"><span class="who">${label[s.who]}</span>
        ${s.thought ? `<span class="thought">${esc(s.thought)}</span>` : ""}
        ${s.call ? `<code>${esc(s.call)}</code>` : ""}
        ${s.answer ? `<span>${esc(s.answer)}</span>` : ""}
        ${s.text ? (s.who === "code" ? `<code>${esc(s.text)}</code>` : `<span>${esc(s.text)}</span>`) : ""}</div>`).join("");
    const turns = steps.slice(0, shown).filter((s) => s.read);
    $("meters").innerHTML = turns.map((s, i) => `
      <div class="meter"><span>Model turn ${i + 1} read</span><span class="track"><span class="fill" style="display:block;width:${(s.read / 943) * 100}%"></span></span><span class="mono">${s.read} tok</span></div>`).join("")
      + (turns.length ? `<span class="muted">Total read so far: ${turns.reduce((a, s) => a + s.read, 0)} tokens. Each turn re-reads everything before it.</span>` : "");
    $("count").textContent = `${shown} of ${steps.length} messages`;
    $("next").disabled = shown >= steps.length;
  }
  root.addEventListener("click", (e) => {
    const c = e.target.dataset && e.target.dataset.c;
    if (c === "next" && shown < steps.length) shown += 1;
    else if (c === "reset") shown = 1;
    else return;
    draw();
  });
  draw();
})();
