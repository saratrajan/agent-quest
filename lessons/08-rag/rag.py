"""Experiments for session 8. Run from the project folder, with the service desk up (make desk) and Ollama running:

    python lessons/08-rag/rag.py --adopt
    python lessons/08-rag/rag.py --retrieval
    python lessons/08-rag/rag.py --run            (about 2 minutes; add --k 1 or --k 10 to vary the evidence)
    python lessons/08-rag/rag.py --run --anchor   (the same, with one more sentence of instruction)

Needs Chroma: make setup-lessons. Uses YOUR chunk, bm25_scores, rrf and
build_context from retrieval.py, your search from session 7 and your
scoring from session 6.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import agentkit  # noqa: E402

try:
    import chromadb  # noqa: E402,F401
    import store  # noqa: E402
except ModuleNotFoundError as err:
    if err.name != "chromadb":
        raise
    sys.exit("This session needs Chroma. Install it with: make setup-lessons")

retrieval = store.retrieval
search = agentkit.load("07-embeddings", "search")
scoring = agentkit.load("06-baseline", "scoring")


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def held_back() -> tuple[list[dict], list[list[float]], dict]:
    held = agentkit.eval_incidents()
    vectors = agentkit.embed([store.QUERY + store.text_of(h) for h in held])
    return held, vectors, agentkit.eval_labels()


def adopt() -> None:
    index = store.Index()
    held, vectors, _ = held_back()
    matrix = np.array(agentkit.embed([store.DOC + d["text"] for d in index.docs]))
    started = time.perf_counter()
    mine = [[index.docs[i]["number"] for i, _ in search.top_k(np.array(v), matrix, 5)] for v in vectors]
    my_time = time.perf_counter() - started
    started = time.perf_counter()
    theirs = [index.vector("", 5, vector=v) for v in vectors]
    their_time = time.perf_counter() - started
    same_top = sum(a[0] == b[0] for a, b in zip(mine, theirs))
    same_set = sum(set(a) == set(b) for a, b in zip(mine, theirs))
    shared = sum(len(set(a) & set(b)) for a, b in zip(mine, theirs))
    print(f"\n100 searches over {len(index.docs)} incidents, top 5 each:")
    print(f"  your exact search (session 7): {1000 * my_time / 100:.2f} ms per search")
    print(f"  Chroma (approximate index):    {1000 * their_time / 100:.2f} ms per search")
    print(f"  same first result: {same_top} of 100.  Same five results: {same_set} of 100.  Results in common: {shared} of 500.")
    print("  Chroma keeps its index in data/chroma/, so the next run starts without re-embedding.")


RERANK_SCHEMA = {"type": "object", "properties": {"order": {"type": "array", "items": {"type": "string"}}}, "required": ["order"]}


def rerank(incident: dict, candidates: list[dict], k: int = 5) -> list[str]:
    """Ask the language model to put retrieved candidates in order of relevance: a second, slower opinion."""
    listing = "\n".join(f"{c['number']}: {c['short_description']}. {c['description'][:160]}" for c in candidates)
    prompt = (f"New incident:\n{store.text_of(incident)}\n\nCandidate past incidents:\n{listing}\n\n"
              "Order the candidates from most to least likely to have the same underlying cause as the new incident. "
              'Answer as JSON: {"order": ["<incident number>", ...]} using every candidate number once.')
    try:
        order = json.loads(agentkit.ask(prompt, schema=RERANK_SCHEMA, temperature=0, num_predict=400)["text"])["order"]
    except (ValueError, KeyError, TypeError):
        order = []
    known = [c["number"] for c in candidates]
    order = [n for n in dict.fromkeys(order) if n in known]
    return (order + [n for n in known if n not in order])[:k]


def retrieval_table(with_rerank: bool) -> None:
    index = store.Index()
    held, vectors, labels = held_back()
    relevant = [set(labels[h["number"]]["related"]) for h in held]
    rows = {
        "vector (Chroma)": [index.vector("", 5, vector=v) for v in vectors],
        "keyword (your BM25)": [index.keyword(store.text_of(h), 5) for h in held],
        "hybrid (your RRF)": [index.hybrid(store.text_of(h), 5, vector=v) for h, v in zip(held, vectors)],
    }
    if with_rerank:
        print("Re-ranking the hybrid top 10 with the language model (100 calls, about two minutes)...")
        rows["hybrid, re-ranked by the model"] = [
            rerank(h, index.get(index.hybrid(store.text_of(h), 10, vector=v))) for h, v in zip(held, vectors)]
    print("\nOne text per incident (summary and description). Is a related incident retrieved?")
    print(f"  {'':<32}{'at rank 1':>10}{'in top 5':>10}")
    for name, got in rows.items():
        print(f"  {name:<32}{pct(search.hit_at_k(got, relevant, 1)):>10}{pct(search.hit_at_k(got, relevant, 5)):>10}")

    print("\nNow the full ticket thread (description, work notes, resolution), whole and in chunks:")
    threads = []
    for p in index.past:
        full = agentkit.desk(f"/api/now/table/incident/{p['number']}")["result"]
        notes = " ".join(n["text"] for n in full.get("work_notes", []))
        threads.append({"number": p["number"], "text": f"{store.text_of(p)}\n{notes}\n{p.get('resolution') or ''}"})
    lengths = [len(t["text"].split()) for t in threads]
    print(f"  a thread is {sum(lengths) // len(lengths)} words on average, {max(lengths)} at most")
    whole = store.Index("threads-whole", docs=[{"id": t["number"], **t} for t in threads])
    pieces = [{"id": f"{t['number']}#{n}", "number": t["number"], "text": piece}
              for t in threads for n, piece in enumerate(retrieval.chunk(t["text"], 60, 15))]
    chunked = store.Index("threads-chunked", docs=pieces)
    print(f"  {len(threads)} whole threads, or {len(pieces)} chunks of 60 words with 15 shared")
    print(f"  {'':<32}{'at rank 1':>10}{'in top 5':>10}")
    for name, idx in (("whole thread, one vector each", whole), ("chunks, best chunk per incident", chunked)):
        got = [idx.vector("", 5, vector=v) for v in vectors]
        print(f"  {name:<32}{pct(search.hit_at_k(got, relevant, 1)):>10}{pct(search.hit_at_k(got, relevant, 5)):>10}")


ANCHOR = ("Decide the priority this way: start from the priority that most of the similar past incidents ended at, "
          "and move away from it only if this ticket clearly describes a wider or narrower impact than they had.")


def run(k: int, limit: int | None, name: str | None, anchor: bool = False) -> None:
    index = store.Index()
    held, vectors, labels = held_back()
    if limit:
        held, vectors = held[:limit], vectors[:limit]
        labels = {h["number"]: labels[h["number"]] for h in held}
    services = [s["id"] for s in agentkit.desk("/api/services")["result"]]
    label = name or ("Model with retrieval (RAG)" if k == 5 else f"Model with retrieval, k = {k}") + (", anchored" if anchor else "")
    print(f"{label}: {len(held)} held-back incidents, {k} retrieved incidents in each prompt...")
    predictions, retrieved, prompt_tokens, started = {}, [], 0, time.perf_counter()
    for n, (h, v) in enumerate(zip(held, vectors), 1):
        numbers = index.hybrid(store.text_of(h), k, vector=v)
        retrieved.append(numbers)
        context = retrieval.build_context(index.get(numbers), 4000)
        prompt = ("Similar past incidents at this company, most similar first, with the priority and service they ended at:\n\n"
                  f"{context}\n\nUse them as evidence. Past incidents with the same cause are the best guide to priority and service.\n"
                  + (ANCHOR + "\n" if anchor else "") + "\n" + scoring.build_prompt(h, services))
        reply = agentkit.ask(prompt, temperature=0, num_predict=200, num_ctx=8192)
        prompt_tokens += reply["prompt_tokens"]
        predictions[h["number"]] = scoring.parse_triage(reply["text"])
        if n % 20 == 0:
            print(f"  {n} done")
    seconds = (time.perf_counter() - started) / len(held)
    s = scoring.score(predictions, labels)
    hit = search.hit_at_k(retrieved, [set(labels[h["number"]]["related"]) for h in held], 5)
    print(f"\n  priority exact {pct(s['priority_exact'])}   within one {pct(s['priority_within_one'])}   service {pct(s['service'])}   "
          f"usable answers {s['answered']}/{s['n']}")
    print(f"  {seconds:.1f}s per incident, {prompt_tokens // len(held)} prompt tokens on average")
    table = scoring.confusion(predictions, labels)
    print("\n  Rows are the true priority, columns what was predicted:")
    for i, row in enumerate(table):
        print(f"    really P{i + 1} " + "".join(f"{c:>6}" for c in row))
    if limit:
        print("\nA partial run is not saved. Drop --limit to put this on the results board.")
    else:
        agentkit.save_result(label, {**s, "hit_at_5": hit, "seconds": round(seconds, 1)})
        print("\nSaved to the results board: http://localhost:8000/results")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--adopt", action="store_true")
    ap.add_argument("--retrieval", action="store_true")
    ap.add_argument("--no-rerank", action="store_true", help="skip the slow re-ranking row")
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--anchor", action="store_true", help="tell the model to start from the neighbours' usual priority")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--name")
    args = ap.parse_args()
    try:
        if args.adopt:
            adopt()
        elif args.retrieval:
            retrieval_table(not args.no_rerank)
        elif args.run:
            run(args.k, args.limit, args.name, args.anchor)
        else:
            ap.print_help()
    except (RuntimeError, LookupError) as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
