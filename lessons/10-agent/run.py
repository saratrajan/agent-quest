"""Run the triage agent. From the project folder, with the service desk up (make desk) and Ollama running:

    python lessons/10-agent/run.py --incident INC0010404
    python lessons/10-agent/run.py --incident INC0010404 --note     (offers to post the triage on the ticket)
    python lessons/10-agent/run.py --eval                           (all 100 held-back incidents; about 20 minutes)
    python lessons/10-agent/run.py --eval --limit 10

Each run uses YOUR triage, traced and check_answer from agent.py, your tool
loop from session 9, your retrieval from session 8 and your scoring from
session 6. Every trace is saved in data/traces/ as JSON.
"""
import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import agentkit  # noqa: E402

try:
    import tools  # noqa: E402
except ModuleNotFoundError as err:
    if err.name != "chromadb":
        raise
    sys.exit("This session needs Chroma. Install it with: make setup-lessons")

agent = agentkit.load("10-agent", "agent")
scoring = agentkit.load("06-baseline", "scoring")


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def triage_one(incident: dict, services: list[str]) -> dict:
    """One incident through the agent, with timing and token counts added."""
    usage = {"model_turns": 0, "prompt_tokens": 0, "output_tokens": 0}

    def count(reply: dict) -> None:
        usage["model_turns"] += 1
        usage["prompt_tokens"] += reply.get("prompt_tokens", 0)
        usage["output_tokens"] += reply.get("output_tokens", 0)

    def step(messages, tools=None):
        reply = agentkit.step(messages, tools=tools, temperature=0, num_ctx=8192, num_predict=500)
        count(reply)
        return reply

    def commit(messages, schema):
        answer = agentkit.commit(messages, schema, temperature=0, num_ctx=8192, num_predict=600)
        count(agentkit.commit.last)
        return answer

    started = time.perf_counter()
    out = agent.triage(incident, tools.TOOLS, tools.specs(), services, step, commit)
    out["seconds"] = round(time.perf_counter() - started, 1)
    out["usage"] = usage
    seen = set(re.findall(r"INC\d{7}", json.dumps([t.get("result") for t in out["trace"]], default=str)))
    out["problems"] = agent.check_answer(out["answer"], services, seen)
    out["incident"] = incident["number"]
    path = Path("data/traces")
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{incident['number']}.json").write_text(json.dumps(out, indent=1, default=str))
    return out


def show(out: dict) -> None:
    thoughts = [m.get("thought", "") for m in out["messages"] if m["role"] == "assistant" and m.get("tool_calls")]
    print("Trace:")
    for n, (t, thought) in enumerate(zip(out["trace"], thoughts + [""] * len(out["trace"])), 1):
        if thought:
            print(f"  {n}. thought: {thought[:200]}")
        result = f"ERROR {t['error']}" if "error" in t else json.dumps(t["result"], default=str)
        print(f"     {t['tool']}({json.dumps(t['arguments'])})   {t['seconds']}s\n       -> {result[:230]}{' ...' if len(result) > 230 else ''}")
    u = out["usage"]
    print(f"\n{len(out['trace'])} tool calls, {u['model_turns']} model turns, {u['prompt_tokens']} tokens read, "
          f"{u['output_tokens']} written, {out['seconds']}s" + ("" if out["finished"] else "   (ran out of steps)"))
    print("\nAnswer:")
    if out["answer"] is None:
        print("  none")
    else:
        for key, value in out["answer"].items():
            print(f"  {key:<18} {value}")
    print("\nChecks: " + ("passed" if not out["problems"] else "; ".join(out["problems"])))


def note_text(answer: dict) -> str:
    steps = "\n".join(f"  {n}. {s}" for n, s in enumerate(answer.get("first_steps") or [], 1))
    return (f"Suggested triage (automated, not yet reviewed): P{answer.get('priority')} on {answer.get('service')}. "
            f"Confidence: {answer.get('confidence')}.\nProbable cause: {answer.get('probable_cause')}\n"
            f"Similar incidents: {', '.join(answer.get('similar_incidents') or []) or 'none found'}\nFirst steps:\n{steps}")


def one(number: str, offer_note: bool) -> None:
    incident = next((i for i in agentkit.eval_incidents() if i["number"] == number), None)
    if incident is None:
        incident = agentkit.desk(f"/api/now/table/incident/{number}")["result"]
    services = [s["id"] for s in agentkit.desk("/api/services")["result"]]
    print(f"{incident['number']}  {incident['short_description']}\n  {incident['description'][:200]}\n  "
          f"reported as P{incident.get('priority_at_open')} from {incident['source']}\n")
    out = triage_one(incident, services)
    show(out)
    print(f"\nFull trace saved to data/traces/{number}.json")
    if not offer_note or out["answer"] is None:
        return
    text = note_text(out["answer"])
    print("\nThe agent proposes this work note:\n" + "\n".join("  | " + line for line in text.splitlines()))
    if out["problems"]:
        print("  The answer failed its checks, so nothing will be posted.")
        return
    if not sys.stdin.isatty() or input("\nPost it on the ticket? Only 'yes' posts it. ").strip().lower() != "yes":
        print("Not posted.")
        return
    agentkit.desk(f"/api/now/table/incident/{number}/work_notes", {"author": "Triage agent", "role": "Automated suggestion", "text": text})
    print(f"Posted. See it at {agentkit.DESK}/incidents/{number}")


def evaluate(limit: int | None, name: str | None) -> None:
    held, labels = agentkit.eval_incidents(), agentkit.eval_labels()
    if limit:
        held = held[:limit]
        labels = {h["number"]: labels[h["number"]] for h in held}
    services = [s["id"] for s in agentkit.desk("/api/services")["result"]]
    print(f"Agent with tools: {len(held)} held-back incidents...", flush=True)
    outs = []
    for n, incident in enumerate(held, 1):
        outs.append(triage_one(incident, services))
        if n % 10 == 0:
            print(f"  {n} done", flush=True)
    usable = lambda o: o["answer"] if o["answer"] and "priority out of range" not in o["problems"] else None
    predictions = {o["incident"]: usable(o) for o in outs}
    s = scoring.score(predictions, labels)
    seconds = sum(o["seconds"] for o in outs) / len(outs)
    print(f"\n  priority exact {pct(s['priority_exact'])}   within one {pct(s['priority_within_one'])}   service {pct(s['service'])}   "
          f"usable answers {s['answered']}/{s['n']}")
    table = scoring.confusion(predictions, labels)
    print("\n  Rows are the true priority, columns what was predicted:")
    for i, row in enumerate(table):
        print(f"    really P{i + 1} " + "".join(f"{c:>6}" for c in row))
    calls = Counter(t["tool"] for o in outs for t in o["trace"])
    print(f"\n  per incident: {seconds:.1f}s, {sum(len(o['trace']) for o in outs) / len(outs):.1f} tool calls, "
          f"{sum(o['usage']['prompt_tokens'] for o in outs) // len(outs)} tokens read, "
          f"{sum(o['usage']['output_tokens'] for o in outs) // len(outs)} written")
    print("  tools used: " + ", ".join(f"{name} {n}" for name, n in calls.most_common()))
    print(f"  ran out of steps: {sum(not o['finished'] for o in outs)}.  failed tool calls: {sum('error' in t for o in outs for t in o['trace'])}.")
    flagged = [o for o in outs if o["problems"]]
    print(f"  answers that failed a check: {len(flagged)}" + (" (" + "; ".join(sorted({p for o in flagged for p in o['problems']}))[:200] + ")" if flagged else ""))
    related = sum(bool(set((o["answer"] or {}).get("similar_incidents") or []) & set(labels[o["incident"]]["related"])) for o in outs)
    print(f"  cited at least one truly related incident: {related} of {len(outs)}")
    by_number = {h["number"]: h for h in held}
    answered = [o for o in outs if o["answer"]]
    was_right = lambda o: by_number[o["incident"]]["priority_at_open"] == labels[o["incident"]]["priority"]
    now_right = lambda o: o["answer"].get("priority") == labels[o["incident"]]["priority"]
    kept = sum(o["answer"].get("priority") == by_number[o["incident"]]["priority_at_open"] for o in answered)
    print(f"\n  The agent saw the reporter's priority. It kept it on {kept} of {len(answered)} incidents.")
    print(f"  Where the reporter was wrong ({sum(not was_right(o) for o in answered)}), the agent corrected "
          f"{sum(now_right(o) for o in answered if not was_right(o))}. Where the reporter was right "
          f"({sum(was_right(o) for o in answered)}), the agent broke {sum(not now_right(o) for o in answered if was_right(o))}.")
    done, cut = [o for o in answered if o["finished"]], [o for o in answered if not o["finished"]]
    svc = lambda group: pct(sum(o["answer"].get("service") == labels[o["incident"]]["service"] for o in group) / len(group)) if group else "–"
    print(f"  Service right when the run finished within its steps: {svc(done)} of {len(done)}. When it ran out: {svc(cut)} of {len(cut)}.")
    print("\n  Does the stated confidence mean anything?")
    for level in agent.CONFIDENCE:
        group = [o for o in outs if (o["answer"] or {}).get("confidence") == level]
        if group:
            right = sum(o["answer"].get("priority") == labels[o["incident"]]["priority"] for o in group)
            svc = sum(o["answer"].get("service") == labels[o["incident"]]["service"] for o in group)
            print(f"    {level:<24} {len(group):>3} incidents   priority right {pct(right / len(group)):>4}   service right {pct(svc / len(group)):>4}")
    if limit:
        print("\nA partial run is not saved. Drop --limit to put this on the results board.")
    else:
        agentkit.save_result(name or "Agent with tools", {**s, "hit_at_5": related / len(outs), "seconds": round(seconds, 1)})
        print("\nSaved to the results board: http://localhost:8000/results")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--incident", metavar="NUMBER")
    ap.add_argument("--note", action="store_true", help="offer to post the triage as a work note; you must type yes")
    ap.add_argument("--eval", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--name")
    args = ap.parse_args()
    try:
        if args.incident:
            one(args.incident, args.note)
        elif args.eval:
            evaluate(args.limit, args.name)
        else:
            ap.print_help()
    except (RuntimeError, LookupError) as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
