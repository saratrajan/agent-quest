// Buddy: the chat panel. Everything is sent to this app's own /api/course/assistant and nowhere else.
(() => {
  const root = document.getElementById("buddy");
  if (!root) return;
  const $ = (id) => document.getElementById(id);
  const panel = $("buddy-panel"), opener = $("buddy-open"), log = $("buddy-log"), form = $("buddy-form");
  const input = $("buddy-input"), stage = $("buddy-stage"), pose = $("buddy-pose"), nudge = $("buddy-nudge");
  const session = root.dataset.session ? Number(root.dataset.session) : null;
  const store = (kind) => { try { return window[kind]; } catch { return null; } };
  let history = [], quiz = null, busy = false;

  ["a", "b", "c"].forEach((sheet) => { new Image().src = `/static/buddy/sheet-${sheet}.jpg`; });  // so pose changes are instant

  function setPose(name, mood) {
    stage.classList.remove("thinking", "hello");
    if (mood) stage.classList.add(mood);
    if (pose.dataset.pose === name) return;
    pose.classList.add("swap");
    setTimeout(() => { pose.dataset.pose = name; pose.classList.remove("swap"); }, 180);
  }

  function open() {
    panel.hidden = false;
    opener.setAttribute("aria-expanded", "true");
    if (nudge) nudge.hidden = true;
    setPose("wave", "hello");
    store("sessionStorage")?.setItem("buddy-open", "1");
    input.focus();
  }
  function close() {
    panel.hidden = true;
    opener.setAttribute("aria-expanded", "false");
    store("sessionStorage")?.removeItem("buddy-open");
    opener.focus();
  }

  function bubble(text, who, extra = "") {
    const el = document.createElement("div");
    el.className = `bmsg from-${who} ${extra}`.trim();
    el.textContent = text;
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return el;
  }

  function sources(list) {
    if (!list || !list.length) return;
    const row = document.createElement("div");
    row.className = "bsrc";
    const label = document.createElement("span");
    label.textContent = "From:";
    row.appendChild(label);
    list.forEach((s) => {
      const a = document.createElement("a");
      a.href = `/sessions/${Number(s.session)}#step-${encodeURIComponent(s.step_id)}`;
      a.textContent = `Session ${Number(s.session)} · ${s.title}`;
      row.appendChild(a);
    });
    log.appendChild(row);
    log.scrollTop = log.scrollHeight;
  }

  async function send(message, action, shown) {
    if (busy) return;
    busy = true;
    form.querySelector("button").disabled = true;
    if (shown) bubble(shown, "you");
    const wait = bubble(action === "quiz" ? "Thinking of a question…" : "Thinking…", "buddy", "wait");
    setPose("curious", "thinking");
    const body = { message: message || "", session, history: history.slice(-8) };
    if (action) body.action = action;
    if (quiz && !action) body.quiz = quiz;
    quiz = null;
    try {
      const res = await fetch("/api/course/assistant", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === "string" ? data.detail : "I couldn't read that. Try a shorter question.");
      wait.remove();
      bubble(data.reply, "buddy");
      sources(data.sources);
      if (shown) history.push({ role: "you", text: shown.slice(0, 4000) });
      history.push({ role: "buddy", text: data.reply.slice(0, 4000) });
      quiz = data.quiz || null;
      input.placeholder = quiz ? "Type your answer…" : "Ask Buddy about the course…";
      setPose(quiz ? "paw" : "happy");
    } catch (err) {
      wait.remove();
      bubble(err.message || "Something went wrong. Is the course app still running?", "buddy");
      setPose("sit");
    } finally {
      busy = false;
      form.querySelector("button").disabled = false;
      input.focus();
    }
  }

  opener.addEventListener("click", open);
  $("buddy-close").addEventListener("click", close);
  panel.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = "";
    send(text, null, text);
  });
  root.addEventListener("click", (e) => {
    const chip = e.target.closest(".buddy-chip, .buddy-nudge [data-action]");
    if (!chip) return;
    if (panel.hidden) open();
    if (chip.dataset.action) send("", chip.dataset.action, chip.textContent.replace("→", "").trim());
    else send(chip.dataset.ask, null, chip.dataset.ask);
  });

  // A little depth: Buddy leans toward the pointer.
  stage.addEventListener("pointermove", (e) => {
    const box = stage.getBoundingClientRect();
    pose.style.setProperty("--ry", `${(((e.clientX - box.left) / box.width) - 0.5) * 22}deg`);
    pose.style.setProperty("--rx", `${(0.5 - ((e.clientY - box.top) / box.height)) * 12}deg`);
  });
  stage.addEventListener("pointerleave", () => { pose.style.setProperty("--ry", "0deg"); pose.style.setProperty("--rx", "0deg"); });

  if (nudge) {
    const key = `buddy-nudge-${session}-${new Date().toISOString().slice(0, 10)}`;
    if (store("localStorage")?.getItem(key)) nudge.hidden = true;
    $("buddy-nudge-close").addEventListener("click", () => { nudge.hidden = true; store("localStorage")?.setItem(key, "1"); });
    nudge.querySelector("[data-action]").addEventListener("click", () => store("localStorage")?.setItem(key, "1"));
  }
  if (store("sessionStorage")?.getItem("buddy-open")) { panel.hidden = false; opener.setAttribute("aria-expanded", "true"); if (nudge) nudge.hidden = true; }
})();
