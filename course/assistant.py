"""Buddy, the course assistant.

Three rules shape this file:
  1. Facts about progress are computed by code and never generated.
  2. Questions about the material are answered by a local model that is shown
     only matching lesson text, and only from sessions the learner has unlocked.
  3. Worked answers, model answers and solutions are never read at all.
Nothing here reaches the internet: the model runs on this machine under Ollama.
"""
import ast
import html
import json
import math
import os
import random
import re
import urllib.error
import urllib.request
from datetime import date, datetime

MILESTONES = [("M1", "fundamentals done", 5), ("M2", "RAG measured", 8), ("M3", "agent usable", 10), ("M4", "production-ready", 14)]
STOP = set("a an and are as at be but by can could do does for from has have how i if in into is it its me my of on or our "
           "so than that the their them then there these this to us was we what when where which who why will with would you your "
           "about tell explain please need needs want mean means work works use used like get got give say said".split())
SYSTEM = ("You are Buddy, a friendly learning sidekick inside a hands-on course on language models, retrieval and agents. "
          "Answer using ONLY the CONTEXT you are given. If the context does not contain the answer, say you cannot find it "
          "in the course. Be concrete, use the context's own numbers and terms, and keep to 120 words or fewer. "
          "Never write solution code for an exercise.")
MARKER = ("You mark one quiz answer for a course, using ONLY the CONTEXT you are given. Reply with a verdict and nothing else. "
          "If the learner's answer agrees with the context, reply with the single word CORRECT. Otherwise reply with "
          "INCORRECT: followed by the correct answer from the context in one short sentence. "
          "Accept an answer that is right but worded differently; a number or name that differs from the context is wrong. Do not explain your marking and do not mention the learner or the context.")
OFF_TOPIC = ("I can only help with this course: what a session teaches, your progress, and questions about the lessons "
             "you have unlocked. I couldn't match that to anything in them.")


def ollama_llm(system: str, user: str) -> str:
    """The default model call: a short, direct, structured answer from the local model."""
    host = os.environ.get("OLLAMA_HOST_URL", "http://localhost:11434")
    body = {"model": os.environ.get("BUDDY_MODEL", "qwen3:4b"), "system": system, "stream": False, "think": False,
            "format": "json", "prompt": user + '\n\nReply as JSON: {"answer": "<your reply as plain text>"}',
            "options": {"temperature": 0.2, "num_predict": 400, "num_ctx": 4096}}
    request = urllib.request.Request(f"{host}/api/generate", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            text = (json.loads(response.read()).get("response") or "").strip()
    except (urllib.error.URLError, OSError, ValueError) as err:
        raise RuntimeError(f"The local model is not available ({err})") from None
    return parse_reply(text)


def parse_reply(text: str) -> str:
    """The model is asked for {"answer": "..."}. Accept that or plain prose;
    anything else (an echo of the prompt, an empty answer) counts as no reply."""
    text = text.strip()
    try:
        data = json.loads(text)
    except ValueError:
        if text:
            return text
        raise RuntimeError("The local model returned nothing") from None
    answer = data.get("answer") if isinstance(data, dict) else None
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError("The local model did not give a usable answer")
    return answer.strip()


def plain_text(markup: str) -> list[str]:
    """Lesson HTML as a list of plain paragraphs."""
    markup = re.sub(r"<(script|style)\b.*?</\1>", " ", markup, flags=re.S | re.I)
    markup = re.sub(r"</(p|li|tr|h[1-6]|pre|table|ol|ul|div)>", "\n", markup, flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", " ", markup))
    return [re.sub(r"\s+", " ", line).strip() for line in text.split("\n") if len(line.strip()) > 20]


def terms(text: str) -> list[str]:
    out = []
    for word in re.findall(r"[a-z0-9][a-z0-9\-]*", text.lower()):
        word = word[:-1] if len(word) > 3 and word.endswith("s") else word
        if word not in STOP and len(word) > 1:
            out.append(word)
    return out


def plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


class Assistant:
    def __init__(self, course, llm=None):
        self.course = course
        self.llm = llm or ollama_llm

    # ---- what Buddy can see

    def _overview(self) -> dict:
        return self.course.overview()

    def _status(self, n: int) -> str | None:
        return next((s["status"] for s in self._overview()["sessions"] if s["number"] == n), None)

    def _chunks(self) -> list[dict]:
        """Concept pages of every released session, cut into passages of a few sentences."""
        status = {s["number"]: s["status"] for s in self._overview()["sessions"]}
        out = []
        for s in self.course.sessions():
            if not s.released:
                continue
            for st in s.steps:
                if st["kind"] != "concept":
                    continue
                path = self.course.lessons_dir / s.folder / st["file"]
                if not path.is_file():
                    continue
                buf, k = "", 0
                for para in plain_text(path.read_text()) + [""]:
                    if para and len(buf) + len(para) < 700:
                        buf = f"{buf} {para}".strip()
                        continue
                    if buf:
                        out.append({"session": s.number, "step_id": st["id"], "title": st["title"], "index": k,
                                    "text": buf, "locked": status[s.number] == "locked"})
                        k += 1
                    buf = para
        return out

    def _search(self, question: str, chunks: list[dict]) -> list[tuple[float, dict]]:
        query = list(dict.fromkeys(terms(question)))
        if not query or not chunks:
            return []
        bags = [terms(c["text"] + " " + c["title"]) for c in chunks]
        df = {t: sum(t in bag for bag in bags) for t in query}
        known = [t for t in query if df[t]]
        if len(known) < max(1, math.ceil(len(query) / 2)):  # most of the question must be about the course
            return []
        scored = []
        for chunk, bag in zip(chunks, bags):
            score = sum(math.log(1 + len(chunks) / df[t]) * (1 + math.log(bag.count(t))) for t in known if t in bag)
            if score:
                scored.append((score, chunk))
        return sorted(scored, key=lambda pair: -pair[0])

    def _ask_model(self, system: str, user: str) -> str | None:
        try:
            return self.llm(system, user).strip() or None
        except RuntimeError:
            return None

    @staticmethod
    def _source(chunk_or_step: dict, session: int | None = None) -> dict:
        return {"session": chunk_or_step.get("session", session), "step_id": chunk_or_step.get("step_id") or chunk_or_step["id"],
                "title": chunk_or_step["title"]}

    @staticmethod
    def _out(reply: str, sources=(), used_model=False, **extra) -> dict:
        unique = list({(s["session"], s["step_id"]): s for s in sources}.values())
        return {"reply": reply, "sources": unique, "used_model": used_model, **extra}

    # ---- facts, computed

    def _done_today(self) -> list[str]:
        state, today, titles = self.course.store.get(), date.today(), {}
        for s in self.course.sessions():
            for st in s.steps:
                titles[f"{s.number}/{st['id']}"] = st["title"]
        out = []
        for key, entry in state["steps"].items():
            try:
                when = datetime.fromisoformat(entry.get("at", "")).astimezone().date()
            except ValueError:
                continue
            if entry.get("done") and when == today and key in titles:
                out.append(titles[key])
        return out

    def _next(self) -> tuple[str, list]:
        nxt = self._overview()["continue"]
        if not nxt:
            return "You have finished everything released so far.", []
        s = self.course.find(nxt["session"])
        step = next(st for st in s.steps if st["id"] == nxt["step_id"])
        return (f"Next up: \"{step['title']}\" in session {s.number}, {s.title} ({step['section']}).",
                [self._source(step, s.number)])

    def today(self) -> dict:
        done = self._done_today()
        nxt, sources = self._next()
        if not done:
            return self._out(f"You haven't completed anything in the course today yet. {nxt}", sources)
        shown = ", ".join(f'"{t}"' for t in done[:5]) + (" and more" if len(done) > 5 else "")
        return self._out(f"You've completed {plural(len(done), 'lesson step')} today: {shown}. {nxt}", sources)

    def overall(self) -> dict:
        o = self._overview()
        done, total = o["overall"]["done"], o["overall"]["total"]
        lines = [f"You've done {done} of {total} lesson steps in the sessions built so far ({round(100 * done / total) if total else 0}%)."]
        for s in o["sessions"]:
            if s["status"] in ("in-progress", "done"):
                lines.append(f"Session {s['number']}, {s['title']}: {s['done']} of {s['total']}.")
        nxt, sources = self._next()
        return self._out(" ".join(lines + [nxt]), sources)

    def next_step(self) -> dict:
        return self._out(*self._next())

    def streak(self) -> dict:
        n = self.course.streak()
        tail = "Complete a lesson step today to keep it going." if n else "Complete a lesson step to start one."
        return self._out(f"Your learning streak is {plural(n, 'day')}. {tail}")

    def milestone(self) -> dict:
        o = self._overview()
        status = {s["number"]: s for s in o["sessions"]}
        for code, name, last in MILESTONES:
            if not all(status[n]["status"] == "done" for n in range(1, last + 1)):
                built = [status[n] for n in range(1, last + 1) if status[n]["status"] != "not-released"]
                left = sum(s["total"] - s["done"] for s in built)
                unbuilt = last - len(built)
                more = f" {plural(unbuilt, 'session')} before it {'is' if unbuilt == 1 else 'are'} not built yet." if unbuilt else ""
                return self._out(f"The next milestone is {code}, {name}, reached when you finish session {last}. "
                                 f"You have {plural(left, 'lesson step')} left in the sessions built so far.{more}")
        return self._out("You have reached every milestone. Congratulations.")

    def outline(self, n: int) -> dict:
        s = self.course.find(n)
        if s is None:
            return self._out(f"There is no session {n}. The course has 14 sessions.")
        if not s.released:
            return self._out(f"Session {n}, {s.title}, has not been released yet. In short: {s.summary}")
        points = "\n".join(f"- {o}" for o in s.outcomes) if s.outcomes else s.summary
        lock = f"\n\nIt is locked until you finish session {n - 1}." if self._status(n) == "locked" else ""
        return self._out(f"Session {n}, {s.title}, teaches you to:\n{points}\n\nIt has {plural(len(s.steps), 'lesson step')}.{lock}")

    def feedback(self) -> dict:
        state = self.course.store.get()
        lines, first_try, retried = [], [], []
        for s in self.course.sessions():
            earned = possible = 0
            for st in s.steps:
                key = f"{s.number}/{st['id']}"
                tries = state["attempts"].get(key, [])
                if st["kind"] == "exercise" and tries:
                    passed_at = next((i + 1 for i, t in enumerate(tries) if t["passed"]), None)
                    if passed_at == 1:
                        first_try.append(st["title"])
                    elif passed_at:
                        retried.append(f'"{st["title"]}" ({passed_at} attempts)')
                    else:
                        retried.append(f'"{st["title"]}" ({plural(len(tries), "attempt")}, not passing yet)')
                if st["kind"] == "problem" and key in state["marks"]:
                    earned += state["marks"][key]["points"]
                    possible += st["points"]
            if possible:
                lines.append(f"Session {s.number} problem set: you gave yourself {earned} of {possible} points.")
        if first_try:
            lines.insert(0, "Passed first time: " + ", ".join(f'"{t}"' for t in first_try) + ".")
        if retried:
            lines.insert(0, "Took more than one go: " + ", ".join(retried) + ". Worth revisiting the concept step before each.")
        notes = []
        reviews = self.course.data_dir / "reviews"
        if reviews.is_dir():
            for path in sorted(reviews.glob("*.md")):
                notes.append(f"Reviewer's note, session {path.stem.lstrip('0') or '0'}: {path.read_text().strip()[:600]}")
        done = self._overview()["overall"]["done"]
        if not lines and not notes and not done:
            return self._out("Nothing to give feedback on yet. Once you run an exercise's tests or mark a problem, "
                             "I can tell you what went smoothly and what took a few goes.")
        head = f"So far you've completed {plural(done, 'lesson step')} and your streak is {plural(self.course.streak(), 'day')}."
        if not lines and not notes:
            lines = ["No exercise attempts or problem marks yet, so there is little to judge beyond that."]
        return self._out("\n".join([head] + lines + notes))

    # ---- lesson questions, answered by the local model from matching text

    def answer(self, question: str, history=()) -> dict:
        ranked = self._search(question, self._chunks())
        if not ranked:
            return self._out(OFF_TOPIC)
        top_score, top = ranked[0]
        open_hits = [(sc, c) for sc, c in ranked if not c["locked"]]
        if top["locked"] and (not open_hits or open_hits[0][0] < 0.6 * top_score):
            s = self.course.find(top["session"])
            return self._out(f"That is covered in session {s.number}, {s.title}, which is still locked. "
                             f"Finish session {s.number - 1} to unlock it.")
        picked = [c for _, c in open_hits[:3]]
        context = "\n\n".join(f"[Session {c['session']}, {c['title']}]\n{c['text']}" for c in picked)
        recent = "\n".join(f"{t['role']}: {t['text'][:300]}" for t in list(history)[-4:])
        user = f"CONTEXT:\n{context}\n\n" + (f"EARLIER IN THIS CHAT:\n{recent}\n\n" if recent else "") + f"QUESTION: {question}"
        sources = [self._source(c) for c in picked[:2]]
        reply = self._ask_model(SYSTEM, user)
        if reply is None:
            return self._out("The local model isn't running, so here is the passage from the lesson that best matches:\n\n"
                             f"{picked[0]['text'][:600]}\n\nStart Ollama for a fuller answer.", sources)
        return self._out(reply, sources, used_model=True)

    # ---- quick actions on a session

    def _open_session(self, n: int | None):
        s = self.course.find(n) if n else None
        if s is None:
            return None, self._out("Open a session first, then I can help with it.")
        if not s.released:
            return None, self._out(f"Session {s.number} has not been released yet.")
        if self._status(s.number) == "locked":
            return None, self._out(f"Session {s.number} is locked. Finish session {s.number - 1} to unlock it.")
        return s, None

    def _session_chunks(self, n: int) -> list[dict]:
        return [c for c in self._chunks() if c["session"] == n]

    def explain(self, n) -> dict:
        s, refusal = self._open_session(n)
        if refusal:
            return refusal
        chunks = self._session_chunks(s.number)[:3]
        context = "\n\n".join(c["text"] for c in chunks) + "\n\nBy the end the learner can: " + "; ".join(s.outcomes)
        reply = self._ask_model(SYSTEM, f"CONTEXT:\n{context}\n\nQUESTION: In plain words, what is {s.title} and why does it matter here?")
        sources = [self._source(c) for c in chunks[:1]]
        if reply is None:
            return self._out(self.outline(s.number)["reply"] + "\n\n(The local model isn't running, so this is the outline.)", sources)
        return self._out(reply, sources, used_model=True)

    def hint(self, n) -> dict:
        s, refusal = self._open_session(n)
        if refusal:
            return refusal
        state = self.course.session(s.number)
        step = next((st for st in state["steps"] if st["kind"] == "exercise" and not st["done"]), None)
        if step is None:
            return self._out("There is no unfinished exercise in this session.")
        docs = []
        try:
            tree = ast.parse((self.course.lessons_dir / s.folder / step["file"]).read_text())
            named = [(node.name, ast.get_docstring(node)) for node in ast.walk(tree)
                     if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node)]
            wanted = [d for name, d in named if name in step["brief"]] or [d for _, d in named]
            docs = wanted[:3]
        except (SyntaxError, OSError):
            pass
        context = f"Exercise: {step['title']}\nWhat to do: {step['brief']}\n" + "\n".join(f"Notes in the file: {d[:500]}" for d in docs)
        system = SYSTEM + " Give ONE hint that helps the learner take the next step themselves. Do not write the code."
        reply = self._ask_model(system, f"CONTEXT:\n{context}\n\nQUESTION: I am stuck on this exercise. Give me a hint.")
        source = [self._source(step, s.number)]
        if reply is None:
            return self._out(f"{step['brief']}\n\n(The local model isn't running, so this is the exercise's own brief.)", source)
        return self._out(reply, source, used_model=True)

    def example(self, n) -> dict:
        s, refusal = self._open_session(n)
        if refusal:
            return refusal
        chunks = self._session_chunks(s.number)
        if not chunks:
            return self._out("This session has no worked example yet.")
        best = max(chunks, key=lambda c: len(re.findall(r"\d", c["text"])))  # the passage with the most numbers
        whole = " ".join(c["text"] for c in chunks if c["step_id"] == best["step_id"])[:2400]  # its whole lesson step
        reply = self._ask_model(SYSTEM, f"CONTEXT:\n{whole}\n\nQUESTION: Walk me through the worked example in this lesson step by step, using its numbers.")
        if reply is None:
            return self._out(f"{best['text'][:700]}\n\n(I couldn't get an answer from the local model, so this is the lesson's own text.)", [self._source(best)])
        return self._out(reply, [self._source(best)], used_model=True)

    def quiz(self, n) -> dict:
        s, refusal = self._open_session(n)
        if refusal:
            return refusal
        read = {st["id"] for st in self.course.session(s.number)["steps"] if st["kind"] == "concept" and st["done"]}
        chunks = [c for c in self._session_chunks(s.number) if c["step_id"] in read]
        if not chunks:
            return self._out("Finish a concept step in this session first, then I can quiz you on it.")
        chunk = random.choice(chunks)
        system = SYSTEM + " Write ONE short question that can be answered from the context. Give only the question."
        question = self._ask_model(system, f"CONTEXT:\n{chunk['text']}\n\nQUESTION: Ask me one question about this.")
        if question is None:
            return self._out("Quizzes need the local model. Start Ollama and try again.")
        return self._out(question, [self._source(chunk)], used_model=True,
                         quiz={"question": question, "session": chunk["session"], "step_id": chunk["step_id"], "chunk": chunk["index"]})

    def mark_quiz(self, answer: str, quiz: dict) -> dict:
        chunk = next((c for c in self._chunks() if (c["session"], c["step_id"], c["index"]) ==
                      (quiz["session"], quiz["step_id"], quiz["chunk"]) and not c["locked"]), None)
        if chunk is None:
            return self._out("I've lost track of that question. Ask me for another quiz.")
        verdict = self._ask_model(MARKER, f"CONTEXT:\n{chunk['text']}\n\nQUIZ QUESTION: {quiz['question']}\nLEARNER'S ANSWER: {answer}\n\n"
                                          "QUESTION: Is the learner's answer correct? Reply CORRECT, or INCORRECT: and the correct answer.")
        if verdict is None:
            return self._out("I can't mark that without the local model. Start Ollama and try again.", [self._source(chunk)])
        # The model gives only the verdict; the sentence the learner reads is written here.
        found = re.match(r"\W*(incorrect|correct)\b[\s:.,\-]*(.*)", verdict, flags=re.I | re.S)
        if not found:
            return self._out("I couldn't mark that answer. Try answering again, or ask me for another quiz.", [self._source(chunk)])
        if found.group(1).lower() == "correct":
            return self._out("Your answer is correct.", [self._source(chunk)], used_model=True)
        right = " ".join(found.group(2).split()).rstrip(".")
        right = re.sub(r"^(the correct answer is|(the|according to the) context (states|says)?)[\s,:]*(that )?", "", right, flags=re.I)
        ending = f"The correct answer is: {right}." if right else "Read the step again for the correct answer."
        return self._out(f"Your answer is incorrect. {ending}", [self._source(chunk)], used_model=True)

    # ---- routing

    def reply(self, message: str, session: int | None = None, action: str | None = None, history=(), quiz: dict | None = None) -> dict:
        text = message.strip()
        if action:
            return {"explain": self.explain, "hint": self.hint, "example": self.example, "quiz": self.quiz}[action](session)
        if quiz and text:
            return self.mark_quiz(text, quiz)
        low = text.lower()
        if not low:
            return self._out("Ask me what a session teaches, how much you've done today, what to do next, or anything about a lesson you've unlocked.")
        if re.fullmatch(r"(hi|hello|hey|yo|good (morning|afternoon|evening))\b[ !.]*", low):
            return self._out("Hi, I'm Buddy, your learning sidekick. " + self._next()[0])
        if re.search(r"\bquiz\b|\b(test|question) me\b|\bask me (a|some|another) questions?\b", low):
            # Typed instead of pressed: the same quiz as the "Quiz me" button, on the open session or the current one.
            return self.quiz(session or (self._overview()["continue"] or {}).get("session", 1))
        named = re.search(r"\b(?:session|module|lesson)\s*(\d{1,2})\b", low)
        if re.search(r"\b(teach|teaches|learn|cover|covers|about|outcomes?)\b", low) and (named or re.search(r"\b(this|the) (module|session|lesson)\b", low)):
            current = self._overview()["continue"]
            return self.outline(int(named.group(1)) if named else session or (current or {}).get("session", 1))
        if re.search(r"\bfeedback\b|how am i doing|how('m| am) i getting on|strengths?|weak", low):
            return self.feedback()
        if "streak" in low:
            return self.streak()
        if "milestone" in low:
            return self.milestone()
        if "today" in low and re.search(r"progress|done|logged|complete|finish|did i", low):
            return self.today()
        if re.search(r"what('s| is| should i do)? next|where (do|should) i (start|continue|go)|what should i do|continue where", low):
            return self.next_step()
        if re.search(r"\bprogress\b|how far|how much.*(done|left|complete)|steps? (done|left)", low):
            return self.overall()
        return self.answer(text, history)
