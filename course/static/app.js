// Course app behaviour: marking steps, saving answers, running tests, playing pre-work videos.
(() => {
  const page = document.querySelector("[data-session-number]");
  if (!page) return;
  const session = page.dataset.sessionNumber;
  const api = (stepId, action) => `/api/course/sessions/${session}/steps/${encodeURIComponent(stepId)}/${action}`;
  const post = (url, body) =>
    fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined })
      .then(async (r) => { const j = await r.json().catch(() => ({})); if (!r.ok) throw new Error(j.detail || "Something went wrong"); return j; });

  function setDone(stepId, done) {
    const step = document.getElementById(`step-${stepId}`);
    step.dataset.done = String(done);
    const toc = document.querySelector(`.toc a[data-step="${CSS.escape(stepId)}"]`);
    if (toc) toc.dataset.done = String(done);
    const btn = step.querySelector('[data-action="complete"]');
    if (btn) { btn.textContent = done ? "Mark as not done" : btn.dataset.label; btn.setAttribute("aria-pressed", String(done)); }
    const all = document.querySelectorAll(".step");
    const n = document.querySelectorAll('.step[data-done="true"]').length;
    document.querySelectorAll("[data-progress-text]").forEach((el) => (el.textContent = `${n} of ${all.length} steps done`));
    document.querySelectorAll("[data-progress-bar]").forEach((el) => (el.style.width = `${all.length ? (100 * n) / all.length : 0}%`));
  }

  function complete(stepId, done, source = "manual") {
    return post(api(stepId, "complete"), { done, source }).then(() => setDone(stepId, done));
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const step = btn.closest(".step");
    if (!step) return;  // not a lesson step (for example one of Buddy's buttons)
    const stepId = step.dataset.step;
    if (btn.dataset.action === "complete") {
      complete(stepId, step.dataset.done !== "true").catch((err) => (btn.textContent = err.message));
    } else if (btn.dataset.action === "check") {
      const out = step.querySelector("[data-result]");
      btn.disabled = true; btn.setAttribute("aria-busy", "true"); btn.textContent = "Running the tests…";
      post(api(stepId, "check")).then((r) => {
        out.hidden = false;
        out.className = `result ${r.passed ? "pass" : "fail"}`;
        out.querySelector("strong").textContent = r.passed ? "All tests passed." : "Not passing yet.";
        out.querySelector("pre").textContent = r.output;
        setDone(stepId, r.passed);
      }).catch((err) => { out.hidden = false; out.className = "result fail"; out.querySelector("strong").textContent = err.message; })
        .finally(() => { btn.disabled = false; btn.removeAttribute("aria-busy"); btn.textContent = "Run the tests"; });
    } else if (btn.dataset.action === "play") {
      play(step, btn);
    }
  });

  document.addEventListener("focusout", (e) => {
    const box = e.target.closest("textarea[data-answer]");
    if (!box || box.value === box.dataset.saved) return;
    const note = box.closest(".step").querySelector(".saved");
    post(api(box.closest(".step").dataset.step, "answer"), { text: box.value })
      .then(() => { box.dataset.saved = box.value; note.textContent = "Saved"; })
      .catch((err) => (note.textContent = `Not saved: ${err.message}`));
  });

  document.addEventListener("change", (e) => {
    const pick = e.target.closest("select[data-mark]");
    if (!pick || pick.value === "") return;
    const note = pick.closest(".selfmark").querySelector(".saved");
    post(api(pick.closest(".step").dataset.step, "mark"), { points: Number(pick.value) })
      .then(() => (note.textContent = "Saved")).catch((err) => (note.textContent = `Not saved: ${err.message}`));
  });

  // --- YouTube: nothing is requested from YouTube until the poster is clicked.
  let apiReady;
  function loadApi() {
    if (apiReady) return apiReady;
    apiReady = new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error("timeout")), 8000);
      window.onYouTubeIframeAPIReady = () => { clearTimeout(timer); resolve(window.YT); };
      const s = document.createElement("script");
      s.src = "https://www.youtube.com/iframe_api";
      s.onerror = () => { clearTimeout(timer); reject(new Error("blocked")); };
      document.head.appendChild(s);
    });
    apiReady.catch(() => (apiReady = null));
    return apiReady;
  }

  function playerFailed(step) {
    const box = step.querySelector(".player");
    box.hidden = true;
    step.querySelector(".player-error").hidden = false;
  }

  function play(step, poster) {
    const { youtube, start, end } = step.querySelector(".player").dataset;
    poster.querySelector("span").textContent = "Loading the player…";
    loadApi().then((YT) => {
      const holder = document.createElement("div");
      poster.replaceWith(holder);
      let marked = false;
      const finish = () => { if (!marked && step.dataset.done !== "true") { marked = true; complete(step.dataset.step, true, "auto").catch(() => {}); } };
      const player = new YT.Player(holder, {
        host: "https://www.youtube-nocookie.com",
        videoId: youtube,
        playerVars: { start: Number(start), end: Number(end), rel: 0, modestbranding: 1, autoplay: 1, origin: location.origin },
        events: {
          onError: () => playerFailed(step),
          onStateChange: (ev) => { if (ev.data === YT.PlayerState.ENDED) finish(); },
        },
      });
      setInterval(() => {
        if (typeof player.getCurrentTime === "function" && player.getCurrentTime() >= Number(end) - 2) finish();
      }, 1000);
    }).catch(() => playerFailed(step));
  }
})();
