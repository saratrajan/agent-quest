// One real run of the triage agent, step by step. Recorded with run.py --incident INC0010404.
(() => {
  const root = document.querySelector('[data-widget="trace-viewer"]');
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const steps = [
    { kind: "tool", name: "search_incidents", args: '{"query": "cruise deposit amount calculated wrongly after release"}', seconds: 0.621,
      thought: "I need to find similar past incidents to understand the priority and resolution patterns.",
      result: 'Five incidents. INC0010308 "Cruise deposit amount calculated wrongly", final priority 3, cruises, root cause bad-deploy. Resolution: rolled back the cruise service; refunded the difference to affected customers. Four more like it, priorities 3 and 4.' },
    { kind: "tool", name: "recent_deploys", args: '{"service_id": "cruises", "before": "2026-07-27T23:59:12Z"}', seconds: 0.006,
      thought: "All five have the root cause bad-deploy, most ended at priority 3. Check whether there was a recent deploy to the cruises service around the time the incident opened.",
      result: "One deploy: DEP00237, cruises-v3.24.0, at 22:45:12, 74 minutes before the incident opened." },
    { kind: "tool", name: "get_service", args: '{"service_id": "cruises"}', seconds: 0.005,
      thought: "The deploy just before the incident confirms the likely cause. Check the runbooks for the cruises service.",
      result: "Team Cruise, tier 2, depends on payments, identity and supplier-sync. Runbooks: none listed." },
    { kind: "tool", name: "list_runbooks", args: "{}", seconds: 0.003,
      thought: "The cruises service has no runbooks listed. Look at all runbooks to see whether another one is relevant.",
      result: 'Twelve runbooks, among them rb-rollback-deploy, "Roll back a bad deploy", filed under web-frontend.' },
    { kind: "summary", name: "summary",
      thought: "The pattern from past incidents is clear and the recent deploy confirms it. No further tool is needed.",
      result: "Caused by a recent faulty deploy (cruises-v3.24.0). Past incidents were resolved by rolling back and refunding overcharged customers. Priority 3, as most similar incidents ended there." },
    { kind: "commit", name: "commit",
      result: '{"priority": 3, "service": "cruises", "similar_incidents": ["INC0010308", "INC0010263", "INC0010226"], "probable_cause": "bad-deploy", "first_steps": ["Roll back the cruises service deploy (cruises-v3.24.0)", "Refund overcharged customers"], "confidence": "high"}' },
  ];
  const title = { tool: (s) => `calls ${s.name}`, summary: () => "stops and summarises", commit: () => "commits to a structured answer" };
  root.innerHTML = `
    <style>
      .trx{border:1px solid var(--border);border-radius:var(--radius);padding:var(--space-4);background:var(--bg);display:grid;grid-template-columns:minmax(200px,260px) minmax(0,1fr);gap:var(--space-4)}
      @media (max-width:680px){.trx{grid-template-columns:1fr}}
      .trx ol{margin:0;padding:0;list-style:none;display:flex;flex-direction:column;gap:.35rem}
      .trx button{width:100%;text-align:left;display:grid;grid-template-columns:1.4rem minmax(0,1fr) auto;gap:.5rem;align-items:center;padding:.45rem .6rem;border:1px solid var(--border);border-radius:6px;background:var(--surface);color:var(--text);font:500 var(--step-2) inherit;cursor:pointer}
      .trx button[aria-current="true"]{border-color:var(--diagram-1);border-width:2px}
      .trx .n,.trx .t{font-family:var(--font-mono);color:var(--text-muted);font-size:.78rem}
      .trx .detail{display:flex;flex-direction:column;gap:.6rem;font-size:var(--step-2);min-width:0}
      .trx .lab{font:600 var(--step-1)/1.2 var(--font-mono);letter-spacing:.06em;text-transform:uppercase;color:var(--text-muted)}
      .trx code{font-family:var(--font-mono);font-size:.82rem;overflow-wrap:anywhere}
      .trx .thought{font-style:italic}
      .trx .totals{grid-column:1/-1;border-top:1px solid var(--border);padding-top:var(--space-3);color:var(--text-muted);font-size:var(--step-2)}
    </style>
    <div class="trx">
      <ol data-t="list"></ol>
      <div class="detail" data-t="detail" role="status"></div>
      <div class="totals">Incident INC0010404, "Cruise deposit amount calculated wrongly", reported as P3. Whole run: 4 tool calls, 6 model turns, 10,458 tokens read, 1,173 written, 31.3 seconds. The tools took 0.6 seconds of that; the model took the rest. The answer was correct: P3, cruises.</div>
    </div>`;
  const $ = (n) => root.querySelector(`[data-t="${n}"]`);
  const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  let at = 0;
  function draw() {
    $("list").innerHTML = steps.map((s, i) => `<li><button type="button" data-i="${i}" aria-current="${i === at}">
      <span class="n">${i + 1}</span><span>${title[s.kind](s)}</span><span class="t">${s.seconds !== undefined ? s.seconds + "s" : ""}</span></button></li>`).join("");
    const s = steps[at];
    $("detail").innerHTML =
      (s.thought ? `<span class="lab">The model's stated thought</span><span class="thought">${esc(s.thought)}</span>` : "")
      + (s.kind === "tool" ? `<span class="lab">The call it wrote</span><code>${esc(s.name)}(${esc(s.args)})</code><span class="lab">What your code returned (shortened)</span><span>${esc(s.result)}</span>` : "")
      + (s.kind === "summary" ? `<span class="lab">Its summary, in words</span><span>${esc(s.result)}</span>` : "")
      + (s.kind === "commit" ? `<span class="lab">One more model turn, constrained to your schema</span><code>${esc(s.result)}</code><span class="lab">Your checks</span><span>Priority in range, service exists, all three cited incidents appeared in a tool result: passed.</span>` : "");
  }
  root.addEventListener("click", (e) => {
    const b = e.target.closest("button[data-i]");
    if (!b) return;
    at = Number(b.dataset.i);
    draw();
  });
  draw();
})();
