"""Experiments for session 6. Run from the project folder, with the service desk up (make desk):

    python lessons/06-baseline/baseline.py --tour
    python lessons/06-baseline/baseline.py --floor
    python lessons/06-baseline/baseline.py --run            (needs Ollama; about 3 minutes)
    python lessons/06-baseline/baseline.py --run --rubric --reported

--run uses YOUR build_prompt, parse_triage, score and confusion from scoring.py.
Add --limit 20 for a quick look; only a full run is saved to the results board.
"""
import argparse
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import agentkit  # noqa: E402

scoring = agentkit.load("06-baseline", "scoring")

RUBRIC = """How Time Travel Inc. sets priority:
P1: most customers cannot search, book or pay, or money or personal data is at risk right now.
P2: a main function is failing for many customers, or for everyone on one region, supplier or app.
P3: something is degraded, slow or failing for some customers; most can still complete what they came to do.
P4: minor or cosmetic, a back-office delay, or a single customer; no one is blocked."""


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def show(name: str, s: dict, seconds: float | None = None) -> None:
    took = f"   {seconds:.1f}s per incident" if seconds is not None else ""
    print(f"  {name:<40} priority exact {pct(s['priority_exact']):>4}   within one {pct(s['priority_within_one']):>4}   "
          f"service {pct(s['service']):>4}   usable answers {s['answered']}/{s['n']}{took}")


def show_confusion(table: list[list[int]]) -> None:
    print("\n  Rows are the true priority, columns what was predicted:")
    print("             " + "".join(f"said P{p}  " for p in (1, 2, 3, 4)))
    for i, row in enumerate(table):
        print(f"    really P{i + 1} " + "".join(f"{n:>7}  " for n in row))
    over = sum(table[i][j] for i in range(4) for j in range(4) if j < i)
    under = sum(table[i][j] for i in range(4) for j in range(4) if j > i)
    print(f"  Called more severe than it was: {over}.  Called less severe than it was: {under}.")


def tour() -> None:
    resolved = agentkit.desk("/api/now/table/incident?limit=1")
    held = agentkit.eval_incidents()
    services = agentkit.desk("/api/services")["result"]
    print(f"The service desk holds {resolved['total']} resolved incidents and {len(held)} held-back ones.\n")
    one = resolved["result"][0]
    print("A resolved incident carries its answers:")
    for key in ("number", "short_description", "priority_at_open", "priority", "service", "assignment_group", "root_cause_category", "resolution"):
        print(f"    {key:<20} {one.get(key)}")
    full = agentkit.desk(f"/api/now/table/incident/{held[0]['number']}")["result"]
    print("\nA held-back incident does not. This is everything the desk will say about it:")
    for key, value in full.items():
        print(f"    {key:<20} {str(value)[:90]}")
    print(f"\nThe {len(services)} services to choose from:")
    for s in services:
        print(f"    {s['id']:<16} tier {s['tier']}   owned by {s['team']:<22} depends on {', '.join(s['depends_on']) or 'nothing'}")


def floor() -> None:
    held, labels = agentkit.eval_incidents(), agentkit.eval_labels()
    past = {r["number"]: r for r in agentkit.history()}
    lazy = scoring.majority_baseline(past)
    print(f"From the {len(past)} resolved incidents, the most common priority is P{lazy['priority']} "
          f"and the most common service is {lazy['service']}.\n")
    print("Two triagers with no intelligence at all, scored on the 100 held-back incidents:")
    always = scoring.score({i["number"]: lazy for i in held}, labels)
    show("Always the most common answer", always)
    reporter = scoring.score({i["number"]: {"priority": i["priority_at_open"], "service": ""} for i in held}, labels)
    show("Keep the reporter's priority", reporter)
    agentkit.save_result("Always the most common answer", {**always, "hit_at_5": None, "seconds": 0})
    agentkit.save_result("Keep the reporter's priority", {**reporter, "service": None, "hit_at_5": None, "seconds": 0})
    print("\nBoth rows are now on the results board. Any model has to beat these to be worth running.")


def run(limit: int | None, rubric: bool, reported: bool, name: str | None) -> None:
    held, labels = agentkit.eval_incidents(), agentkit.eval_labels()
    if limit:
        held = held[:limit]
        labels = {i["number"]: labels[i["number"]] for i in held}
    services = [s["id"] for s in agentkit.desk("/api/services")["result"]]
    label = name or {(False, False): "Model alone", (True, False): "Model with a rubric", (False, True): "Model with the reporter's priority",
                     (True, True): "Model with rubric and reporter's priority"}[(rubric, reported)]
    print(f"{label}: asking {agentkit.MODEL} to triage {len(held)} held-back incidents...")
    predictions, started = {}, time.perf_counter()
    for n, incident in enumerate(held, 1):
        prompt = scoring.build_prompt(incident, services)
        if rubric:
            prompt = RUBRIC + "\n\n" + prompt
        if reported:
            prompt += f"\nThe person who reported it marked it P{incident['priority_at_open']}. Reporters are usually, but not always, right."
        predictions[incident["number"]] = scoring.parse_triage(agentkit.ask(prompt, temperature=0, num_predict=200)["text"])
        if n % 20 == 0:
            print(f"  {n} done")
    seconds = (time.perf_counter() - started) / len(held)
    s = scoring.score(predictions, labels)
    print()
    show(label, s, seconds)
    show_confusion(scoring.confusion(predictions, labels))
    if reported:
        usable = [i for i in held if predictions[i["number"]]]
        right = [i for i in usable if i["priority_at_open"] == labels[i["number"]]["priority"]]
        wrong = [i for i in usable if i["priority_at_open"] != labels[i["number"]]["priority"]]
        kept = sum(predictions[i["number"]]["priority"] == i["priority_at_open"] for i in usable)
        fixed = sum(predictions[i["number"]]["priority"] == labels[i["number"]]["priority"] for i in wrong)
        broke = sum(predictions[i["number"]]["priority"] != labels[i["number"]]["priority"] for i in right)
        print(f"\n  The model kept the reporter's priority on {kept} of {len(usable)} incidents.")
        print(f"  Where the reporter was wrong ({len(wrong)}), the model corrected {fixed}. Where the reporter was right ({len(right)}), the model broke {broke}.")
    if limit:
        print("\nA partial run is not saved. Drop --limit to put this on the results board.")
    else:
        agentkit.save_result(label, {**s, "hit_at_5": None, "seconds": round(seconds, 1)})
        print("\nSaved to the results board: http://localhost:8000/results")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tour", action="store_true")
    ap.add_argument("--floor", action="store_true")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--rubric", action="store_true", help="put the company's priority definitions in front of the prompt")
    ap.add_argument("--reported", action="store_true", help="tell the model what priority the reporter chose")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--name")
    args = ap.parse_args()
    try:
        if args.tour:
            tour()
            print()
        if args.floor:
            floor()
        elif args.tour:
            pass
        elif args.run:
            run(args.limit, args.rubric, args.reported, args.name)
        else:
            ap.print_help()
    except (RuntimeError, LookupError) as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
