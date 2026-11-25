"""Progress lives in one JSON file. It is never rewritten in place: every
write goes to a temporary file first, and an unreadable file is set aside."""
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _empty() -> dict:
    return {"steps": {}, "answers": {}, "checks": {}, "attempts": {}, "marks": {}}


class ProgressStore:
    def __init__(self, path):
        self.path = Path(path)

    def get(self) -> dict:
        if not self.path.exists():
            return _empty()
        try:
            state = json.loads(self.path.read_text())
            if not isinstance(state, dict) or not all(isinstance(state.get(k, {}), dict) for k in _empty()):
                raise ValueError("unexpected shape")
        except (ValueError, OSError):
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            self.path.rename(self.path.with_name(f"{self.path.name}.corrupt-{stamp}"))
            return _empty()
        return {**_empty(), **state}

    def _save(self, state: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
        os.replace(tmp, self.path)

    def set_done(self, session: int, step_id: str, done: bool, source: str) -> None:
        state = self.get()
        state["steps"][f"{session}/{step_id}"] = {"done": bool(done), "source": source, "at": _now()}
        self._save(state)

    def set_answer(self, session: int, step_id: str, text: str) -> None:
        state = self.get()
        state["answers"][f"{session}/{step_id}"] = text
        self._save(state)

    def set_check(self, session: int, step_id: str, passed: bool, output: str) -> None:
        state = self.get()
        key = f"{session}/{step_id}"
        state["checks"][key] = {"passed": bool(passed), "output": output, "at": _now()}
        state["attempts"].setdefault(key, []).append({"passed": bool(passed), "at": _now()})  # history, for feedback
        self._save(state)

    def set_mark(self, session: int, step_id: str, points: int) -> None:
        """The learner's own score for a problem, after comparing with the worked answer."""
        state = self.get()
        state["marks"][f"{session}/{step_id}"] = {"points": int(points), "at": _now()}
        self._save(state)


def is_done(state: dict, session: int, step_id: str) -> bool:
    return bool(state["steps"].get(f"{session}/{step_id}", {}).get("done"))


def summarise(sessions, state: dict, unlock_all: bool = False) -> dict:
    """Per-session counts and status. A released session is locked until the
    session before it is done; its progress is kept, just not reachable."""
    per, overall, nxt, previous_done = {}, {"done": 0, "total": 0}, None, True
    for s in sessions:
        if not s.released:
            per[s.number] = {"done": 0, "total": 0, "status": "not-released"}
            previous_done = False
            continue
        done = sum(is_done(state, s.number, st["id"]) for st in s.steps)
        total = len(s.steps)
        complete = bool(total) and done == total
        if not previous_done and not unlock_all:
            status = "locked"
        else:
            status = "done" if complete else "in-progress" if done else "not-started"
        per[s.number] = {"done": done, "total": total, "status": status}
        overall["done"] += done
        overall["total"] += total
        if nxt is None and status in ("in-progress", "not-started"):
            first = next((st["id"] for st in s.steps if not is_done(state, s.number, st["id"])), None)
            if first:
                nxt = {"session": s.number, "step_id": first}
        previous_done = complete
    return {"sessions": per, "overall": overall, "continue": nxt}


def streak(state: dict, today: date) -> int:
    """Consecutive days with at least one step completed, counting back from
    today. A streak stays alive through the day after its last active day."""
    days = set()
    for entry in state["steps"].values():
        if not entry.get("done"):
            continue
        try:  # times are stored in UTC; a day is the learner's own local day
            days.add(datetime.fromisoformat(entry.get("at", "")).astimezone().date().isoformat())
        except ValueError:
            continue
    day = today if today.isoformat() in days else today - timedelta(days=1)
    count = 0
    while day.isoformat() in days:
        count += 1
        day -= timedelta(days=1)
    return count
