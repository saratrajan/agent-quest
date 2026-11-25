"""Experiments for session 9. Run from the project folder, with the service desk up (make desk) and Ollama running:

    python lessons/09-tool-calling/explore.py --one
    python lessons/09-tool-calling/explore.py --one --native
    python lessons/09-tool-calling/explore.py --chain
    python lessons/09-tool-calling/explore.py --break
    python lessons/09-tool-calling/explore.py --ask "your own question"

Every run prints the whole conversation: what the model asked for, what YOUR
loop ran, and what went back. Nothing is hidden between the lines you see.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import agentkit  # noqa: E402
import desk_tools  # noqa: E402

loop = desk_tools.loop
SYSTEM = ("You help the on-call engineer at Time Travel Inc., a travel booking company. "
          "Use the tools to look things up; do not answer from memory. Answer briefly once you have what you need.")


def show(messages: list[dict]) -> None:
    for m in messages:
        if m["role"] == "system":
            continue
        if m["role"] == "user":
            print(f"\nYOU      {m['content']}")
        elif m["role"] == "tool":
            print(f"  RESULT   {m['content'][:300]}{' ...' if len(m['content']) > 300 else ''}")
        elif m.get("tool_calls"):
            if m.get("thought"):
                print(f"MODEL    thinks: {m['thought']}")
            for c in m["tool_calls"]:
                print(f"MODEL    calls {c['function']['name']}({json.dumps(c['function'].get('arguments') or {})})")
        else:
            print(f"MODEL    {m.get('content', '')}")


NATIVE = False


def converse(question: str, tools: dict | None = None, specs: list | None = None, max_steps: int = 6) -> None:
    usage = []

    def chat(messages, tools=None):
        if NATIVE:
            r = agentkit.chat(messages, tools=tools, think=True, temperature=0, num_ctx=8192)
        else:
            r = agentkit.step(messages, tools=tools, temperature=0, num_ctx=8192, num_predict=500)
        usage.append((r["prompt_tokens"], r["output_tokens"], r["seconds"]))
        return r

    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": question}]
    answer = loop.tool_loop(messages, tools or desk_tools.TOOLS, specs if specs is not None else desk_tools.specs(), chat, max_steps)
    show(messages)
    if answer is None:
        print(f"\nStopped: {max_steps} model turns without a final answer.")
    print("\nWhat each model turn cost:")
    for n, (prompt, out, seconds) in enumerate(usage, 1):
        print(f"  turn {n}: read {prompt:>5} tokens, wrote {out:>4}, {seconds:>5.1f}s")
    print(f"  total: {sum(u[0] for u in usage)} tokens read across {len(usage)} turns, {sum(u[2] for u in usage):.1f}s")


def one() -> None:
    converse("Which team owns the payments service, and which services does it depend on?")


def chain() -> None:
    held = agentkit.eval_incidents()
    incident = next(i for i in held if "deposit" in i["short_description"].lower())
    converse(f"Incident {incident['number']} was opened at {incident['opened_at']}: \"{incident['short_description']}\". "
             "It looks like the cruises service. Was anything deployed to that service shortly before, "
             "and which runbook would apply if a deploy is the cause?")


def breakit() -> None:
    print("1. A tool that fails: the desk has no such incident.\n" + "-" * 60)
    converse("What was the resolution of incident INC0099999?")
    print("\n\n2. A question the tools cannot answer.\n" + "-" * 60)
    converse("How many incidents did the payments service have in total last year? Give me the exact number.")
    print("\n\n3. A tool that never satisfies the model, with a limit of 3 turns.\n" + "-" * 60)
    stubborn = {"check_status": lambda service_id: {"status": "pending, check again"}}
    spec = [loop.tool_spec("check_status", "Check whether a service has recovered. Keep checking until it reports recovered.",
                           {"service_id": "The service id."})]
    converse("Has the payments service recovered? Keep checking until it has.", stubborn, spec, max_steps=3)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--one", action="store_true")
    ap.add_argument("--chain", action="store_true")
    ap.add_argument("--break", dest="breakit", action="store_true")
    ap.add_argument("--ask")
    ap.add_argument("--native", action="store_true", help="use the model's built-in tool calling (slow: it reasons before every turn)")
    args = ap.parse_args()
    global NATIVE
    NATIVE = args.native
    try:
        if args.one:
            one()
        elif args.chain:
            chain()
        elif args.breakit:
            breakit()
        elif args.ask:
            converse(args.ask)
        else:
            ap.print_help()
    except (RuntimeError, LookupError) as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
