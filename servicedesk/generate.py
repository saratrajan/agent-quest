"""Builds the incident history. Everything comes from one seeded random
generator, so the same seed always gives byte-identical data.

Run `python -m servicedesk.generate` (or `make data`) to write the database,
the training corpus and the held-back answers into data/.
"""
import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from servicedesk.catalog import PATTERNS, REGIONS, SERVICES, SUPPLIERS
from servicedesk.troubleshooting import build_thread

SEED = 20261124
START = datetime(2025, 5, 20, tzinfo=UTC)
END = datetime(2026, 11, 19, tzinfo=UTC)
TOTAL, HISTORY = 500, 400
PRIORITY_COUNTS = {1: 25, 2: 75, 3: 225, 4: 175}
PER_PATTERN = {1: 7, 2: 8, 3: 17}  # incidents per pattern by typical priority; priority-4 patterns share the rest
ANCHORS_PER_PATTERN, ANCHOR_SLOTS = 5, 360
N_WRONG_PRIORITY, N_DUPLICATES, N_VAGUE, N_DEPLOYS = 75, 40, 50, 300

ERROR_CODES = ["HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504", "ERR_TIMEOUT", "ERR_CONN_RESET", "E4012", "E5031"]
PEOPLE = ["Asha Verma", "Tomás Ibarra", "Mei-Lin Zhou", "Jonas Eriksen", "Farah Haddad", "Kwame Osei",
          "Elena Petrova", "Diego Santoro", "Hana Kobayashi", "Luca Moretti"]
VAGUE_SHORT = ["Site is broken", "Customers are complaining", "Something wrong with bookings", "Urgent: please look",
               "Problem reported by customer", "Not working properly", "Getting errors again", "Issue since this morning"]
VAGUE_DESC = [
    "A customer called to say it is not working. They tried twice. No screenshot. Please investigate.",
    "Several people have mentioned problems today. Not sure which part is affected. It was fine yesterday.",
    "Getting complaints on chat. Customers say they cannot finish what they were doing. Details to follow.",
    "Something looks wrong since earlier today. Passing this on from the front-line team, who had no more detail.",
    "Reported in the team channel: things are slow or failing for some users in {region}. Unclear how many.",
]
DEPLOY_SUMMARIES = ["Dependency updates", "Performance tuning", "New feature behind a flag", "Bug fixes", "Logging changes",
                    "Refactor of request handling", "Configuration loader update", "Library upgrade", "Retry handling change"]
RESOLVE_MINUTES = {1: (20, 180), 2: (60, 480), 3: (240, 2880), 4: (1440, 14400)}


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fill(rng: random.Random, template: str) -> str:
    return template.format(region=rng.choice(REGIONS), supplier=rng.choice(SUPPLIERS),
                           error_code=rng.choice(ERROR_CODES), pct=rng.randint(12, 85))


def _pattern_counts() -> dict:
    counts = {p.id: PER_PATTERN[p.typical_priority] for p in PATTERNS if p.typical_priority in PER_PATTERN}
    p4 = [p.id for p in PATTERNS if p.typical_priority == 4]
    left = TOTAL - sum(counts.values())
    for k, pid in enumerate(p4):
        counts[pid] = left // len(p4) + (1 if k < left % len(p4) else 0)
    return counts


def _records(seed: int) -> list[dict]:
    """Incidents with real datetimes and object links, before numbering."""
    rng = random.Random(seed)
    teams = {s.id: s.team for s in SERVICES}
    span = int((END - START).total_seconds())
    times = sorted(START + timedelta(seconds=rng.randrange(span)) for _ in range(TOTAL))

    # Each pattern gets five early time slots, so it always recurs in the searchable history.
    early = list(range(ANCHOR_SLOTS))
    rng.shuffle(early)
    recs, counts = [], _pattern_counts()
    for p in PATTERNS:
        for k in range(counts[p.id]):
            recs.append({"pattern": p, "anchor": k < ANCHORS_PER_PATTERN})
    anchors = [r for r in recs if r["anchor"]]
    for r, slot in zip(anchors, early):
        r["opened"] = times[slot]
    used = set(early[:len(anchors)])
    free = [s for s in range(TOTAL) if s not in used]
    rng.shuffle(free)
    for r, slot in zip((r for r in recs if not r["anchor"]), free):
        r["opened"] = times[slot]

    # Final priority: the pattern's typical level or one step less severe, in exact overall proportions.
    need = dict(PRIORITY_COUNTS)
    for level in (1, 2, 3, 4):
        group = [r for r in recs if r["pattern"].typical_priority == level]
        rng.shuffle(group)
        keep = min(need[level], len(group))
        for r in group[:keep]:
            r["priority"] = level
        for r in group[keep:]:
            r["priority"] = level + 1
        need[level] -= keep
        if level < 4:
            need[level + 1] -= len(group) - keep
    assert all(v == 0 for v in need.values()), need

    # Duplicates: a second report of the same problem within six hours of the first.
    movable = [r for r in recs if not r["anchor"]]
    dups = rng.sample(movable, N_DUPLICATES)
    dup_ids = {id(r) for r in dups}
    for r in recs:
        r["parent"] = None
    for d in dups:
        originals = [r for r in recs if r["pattern"] is d["pattern"] and id(r) not in dup_ids]
        d["parent"] = rng.choice(originals)
        d["opened"] = d["parent"]["opened"] + timedelta(minutes=rng.randint(5, 300))

    wrong = {id(r) for r in rng.sample(recs, N_WRONG_PRIORITY)}
    vague = {id(r) for r in rng.sample(recs, N_VAGUE)}
    for r in recs:
        p, pr = r["pattern"], r["priority"]
        step = {1: 1, 4: -1}.get(pr) or rng.choice([-1, 1])
        r["at_open"] = pr + step if id(r) in wrong else pr
        r["vague"] = id(r) in vague
        r["source"] = rng.choice(p.sources)
        if r["vague"]:
            r["short"] = rng.choice(VAGUE_SHORT)
            r["desc"] = _fill(rng, rng.choice(VAGUE_DESC))
        else:
            r["short"] = _fill(rng, rng.choice(p.short_templates))
            r["desc"] = _fill(rng, rng.choice(p.description_templates))
        r["fix"] = _fill(rng, rng.choice(p.resolution_templates))
        lo, hi = RESOLVE_MINUTES[pr]
        r["resolved"] = r["opened"] + timedelta(minutes=rng.randint(lo, hi))
        r["team"] = teams[p.service]
        r["people"] = [rng.choice(PEOPLE), rng.choice(PEOPLE)]
        r["note_delays"] = [rng.randint(3, 15), rng.randint(16, 40)]
        r["deploy_lead"] = rng.randint(5, 110)
    recs.sort(key=lambda r: r["opened"])
    for k, r in enumerate(recs):
        r["number"] = f"INC{10001 + k:07d}"
        r["split"] = "history" if k < HISTORY else "eval"
    return recs


def build_incidents(seed: int = SEED) -> list[dict]:
    out = []
    for r in _records(seed):
        p = r["pattern"]
        notes, resolution, close_code = build_thread(r, seed)
        out.append({
            "number": r["number"], "short_description": r["short"], "description": r["desc"], "source": r["source"],
            "opened_at": _iso(r["opened"]), "resolved_at": _iso(r["resolved"]),
            "priority_at_open": r["at_open"], "priority": r["priority"], "service": p.service,
            "assignment_group": r["team"], "root_cause_category": p.root_cause, "pattern_id": p.id,
            "duplicate_of": r["parent"]["number"] if r["parent"] else None, "state": "Resolved",
            "resolution": resolution, "close_code": close_code, "work_notes": notes, "is_vague": r["vague"],
            "split": r["split"],
        })
    return out


def build_deploys(seed: int = SEED) -> list[dict]:
    recs = _records(seed)
    rng = random.Random(seed + 1)
    raw = [(r["opened"] - timedelta(minutes=r["deploy_lead"]), r["pattern"].service)
           for r in recs if r["pattern"].deploy_related]
    span = int((END - START).total_seconds())
    ids = [s.id for s in SERVICES]
    while len(raw) < N_DEPLOYS:
        raw.append((START + timedelta(seconds=rng.randrange(span)), rng.choice(ids)))
    raw.sort()
    seen: dict = {}
    out = []
    for k, (when, service) in enumerate(raw):
        seen[service] = seen.get(service, 0) + 1
        out.append({"id": f"DEP{k + 1:05d}", "service": service, "deployed_at": _iso(when),
                    "version": f"{service}-v3.{seen[service]}.0", "summary": rng.choice(DEPLOY_SUMMARIES),
                    "author": rng.choice(PEOPLE)})
    return out


def export_corpus(incidents: list[dict]) -> str:
    blocks = []
    for i in incidents:
        if i["split"] != "history":
            continue
        notes = "\n".join(f"[{n['at']}] {n['author']} ({n['role']}): {n['text']}" for n in i["work_notes"])
        blocks.append(f"{i['number']} P{i['priority']} {i['service']}\n{i['short_description']}\n"
                      f"{i['description']}\n{notes}\nClose code: {i['close_code']}\n")
    return "\n".join(blocks)


def eval_labels(incidents: list[dict]) -> dict:
    """The answers for the held-back incidents, plus, for each, the history
    incidents that had the same underlying cause (used to score retrieval)."""
    by_pattern: dict[str, list[str]] = {}
    for i in incidents:
        if i["split"] == "history":
            by_pattern.setdefault(i["pattern_id"], []).append(i["number"])
    return {i["number"]: {**{k: i[k] for k in ("priority", "service", "assignment_group", "root_cause_category", "pattern_id")},
                          "related": by_pattern.get(i["pattern_id"], [])}
            for i in incidents if i["split"] == "eval"}


def _write_labels(out: Path, incidents: list[dict]) -> None:
    (out / "eval_labels.json").write_text(json.dumps(eval_labels(incidents), indent=2, sort_keys=True))


def main(data_dir: str = "data", if_missing: bool = False) -> None:
    from servicedesk import db

    out = Path(data_dir)
    out.mkdir(parents=True, exist_ok=True)
    if if_missing and (out / "timetravel.db").exists():
        print(f"{out}/timetravel.db already exists; leaving it alone")
        labels = out / "eval_labels.json"
        if not labels.exists() or '"related"' not in labels.read_text():
            _write_labels(out, build_incidents())  # same seed, same incidents: only the answer file is refreshed
            print(f"Refreshed {labels}")
        return
    incidents, deploys = build_incidents(), build_deploys()
    path = out / "timetravel.db"
    if path.exists():
        path.unlink()
    conn = db.connect(str(path))
    db.load(conn, incidents, deploys)
    conn.close()
    (out / "corpus.txt").write_text(export_corpus(incidents))
    _write_labels(out, incidents)
    print(f"Wrote {len(incidents)} incidents and {len(deploys)} deploys to {out}/")


if __name__ == "__main__":
    import sys

    main(if_missing="--if-missing" in sys.argv)
