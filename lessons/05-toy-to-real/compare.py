"""Experiments for session 5. Run from the project folder:

    python lessons/05-toy-to-real/compare.py --sweep
    python lessons/05-toy-to-real/compare.py --limits
    python lessons/05-toy-to-real/compare.py --triage 5

--sweep needs the model you trained in session 4 (data/checkpoints/base.pt)
and Ollama. --limits needs Ollama. --triage needs Ollama and the service desk
(`make desk`).
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from ollama_client import generate  # noqa: E402
from sampling import sample_next  # noqa: E402

DESK = "http://localhost:8080"
SERVICES = ["search", "flight-booking", "hotel-booking", "cruises", "payments", "identity", "notifications",
            "pricing", "supplier-sync", "web-frontend", "mobile-gateway", "loyalty"]


def load_tiny_gpt():
    path = Path("data/checkpoints/base.pt")
    if not path.exists():
        sys.exit("data/checkpoints/base.pt is missing. Run session 4's training first: python lessons/04-tiny-gpt/train.py")
    sys.path.insert(0, str(HERE.parent / "04-tiny-gpt"))
    from gpt import GPT
    from parts import Config

    saved = torch.load(path, map_location="cpu")
    model = GPT(Config(**saved["config"]))
    model.load_state_dict(saved["state"])
    return model.eval(), saved["chars"]


@torch.no_grad()
def write(model, chars, prompt: str, n: int, g, **controls) -> str:
    """Generate n characters from your GPT using YOUR sample_next."""
    to_id = {c: i for i, c in enumerate(chars)}
    idx = torch.tensor([[to_id[c] for c in prompt]])
    for _ in range(n):
        logits, _ = model(idx[:, -model.cfg.block_size:])
        idx = torch.cat([idx, torch.tensor([[sample_next(logits[0, -1], generator=g, **controls)]])], dim=1)
    return "".join(chars[i] for i in idx[0].tolist())[len(prompt):]


def sweep() -> None:
    model, chars = load_tiny_gpt()
    g = torch.Generator().manual_seed(7)
    prompt = "Payments error rate"
    print(f"Your GPT (827,981 parameters), continuing {prompt!r}:")
    for label, controls in [("temperature 0  ", dict(temperature=0)), ("temperature 0.7", dict(temperature=0.7)),
                            ("temperature 1.5", dict(temperature=1.5)), ("1.5 with top-p 0.9", dict(temperature=1.5, top_p=0.9))]:
        print(f"  {label}: {write(model, chars, prompt, 110, g, **controls)!r}")
    ask = "In one sentence, tell a customer that card payments are temporarily failing."
    print(f"\nqwen3:4b (4 billion parameters), asked: {ask}")
    for t in (0, 0, 0.7, 1.5):
        r = generate(ask, temperature=t, num_predict=2500)
        print(f"  temperature {t}: {r['text']!r}   [{r['output_tokens']} tokens generated, {r['seconds']}s]")


def limits() -> None:
    ask = "Explain in two sentences what a runbook is."
    slow = generate(ask, temperature=0, num_predict=2500)
    fast = generate(ask, temperature=0, num_predict=2500, think=False, json_output=True)
    print("Speed, same question asked two ways:")
    print(f"  thinking first:  {slow['output_tokens']:>5} tokens generated in {slow['seconds']:>5}s at {slow['tokens_per_second']} tokens a second; "
          f"the visible answer is {len(slow['text'].split())} words")
    print(f"  direct answer:   {fast['output_tokens']:>5} tokens generated in {fast['seconds']:>5}s at {fast['tokens_per_second']} tokens a second")
    if fast["tokens_per_second"]:
        print(f"  A 250-token triage note at this speed takes about {250 / fast['tokens_per_second']:.0f} seconds, before any thinking.")

    filler = "\n".join(f"Log line {i}: health check passed for service node {i % 7}." for i in range(400))
    prompt = (f"The incident code word is HERON-42. Remember it.\n{filler}\n"
              'What is the incident code word? Answer as JSON: {"code_word": "<the code word>"}')
    print("\nContext window: a fact at the start, then 400 log lines, then a question about the fact.")
    for ctx in (1024, 16384):
        r = generate(prompt, temperature=0, num_ctx=ctx, num_predict=200, think=False, json_output=True)
        print(f"  window of {ctx:>5} tokens: the model read {r['prompt_tokens']:>5} prompt tokens and answered {r['text'][:70]!r}")


def triage(n: int) -> None:
    try:
        with urllib.request.urlopen(f"{DESK}/api/now/table/incident?limit={n}&offset=40", timeout=10) as resp:
            incidents = json.loads(resp.read())["result"]
    except (urllib.error.URLError, OSError):
        sys.exit(f"Could not reach the service desk at {DESK}. Start it with: make desk")
    print(f"Asking qwen3:4b to triage {len(incidents)} resolved incidents from the description alone.\n")
    hits_p = hits_s = 0
    for inc in incidents:
        prompt = ("You are triaging an incident for a travel booking company.\n"
                  f"Summary: {inc['short_description']}\nDescription: {inc['description']}\n\n"
                  f"Choose a priority from 1 (critical) to 4 (low) and the affected service from this list: {', '.join(SERVICES)}.\n"
                  'Answer as JSON: {"priority": <number>, "service": "<name>"}')
        r = generate(prompt, json_output=True, think=False, temperature=0, num_predict=200)
        try:
            guess = json.loads(r["text"])
            p, s = guess.get("priority"), guess.get("service")
        except ValueError:
            p, s = None, f"(not valid JSON: {r['text'][:40]!r})"
        hits_p += p == inc["priority"]
        hits_s += s == inc["service"]
        print(f"{inc['number']}  {inc['short_description'][:52]:<52}")
        print(f"    model: P{p} {s}    actual: P{inc['priority']} {inc['service']}    "
              f"{'priority ok' if p == inc['priority'] else 'priority WRONG'}, {'service ok' if s == inc['service'] else 'service WRONG'}")
    print(f"\nPriority right {hits_p} of {len(incidents)}, service right {hits_s} of {len(incidents)}. "
          "The model saw no past incidents, no runbooks and no service catalog.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--limits", action="store_true")
    ap.add_argument("--triage", type=int, metavar="N")
    args = ap.parse_args()
    try:
        if args.sweep:
            sweep()
        elif args.limits:
            limits()
        elif args.triage:
            triage(args.triage)
        else:
            ap.print_help()
    except RuntimeError as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
