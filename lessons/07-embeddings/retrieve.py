"""Experiments for session 7. Run from the project folder, with the service desk up (make desk)
and Ollama running with the embedding model (ollama pull nomic-embed-text):

    python lessons/07-embeddings/retrieve.py --neighbours INC0010405
    python lessons/07-embeddings/retrieve.py --neighbours hardest
    python lessons/07-embeddings/retrieve.py --ask "people say their card keeps getting rejected"
    python lessons/07-embeddings/retrieve.py --measure
    python lessons/07-embeddings/retrieve.py --variants

The first run embeds the 400 resolved incidents and the 100 held-back ones
(a few seconds) and keeps the vectors in data/embeddings/. Everything after
that uses YOUR top_k, hit_at_k and vote from search.py.
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import agentkit  # noqa: E402

search = agentkit.load("07-embeddings", "search")
scoring = agentkit.load("06-baseline", "scoring")

# This embedding model was trained with a short label in front of every text,
# saying whether it is something to be found or something to search with.
DOC, QUERY = "search_document: ", "search_query: "
VARIANTS = {
    "summary": lambda i: i["short_description"],
    "summary+description": lambda i: f"{i['short_description']}\n{i['description']}",
    "with-resolution": lambda i: f"{i['short_description']}\n{i['description']}\n{i.get('resolution') or ''}",
}
DEFAULT = "summary+description"


def load(variant: str = DEFAULT) -> dict:
    """History and held-back incidents with their vectors, embedding them on first use."""
    past, held = agentkit.history(), agentkit.eval_incidents()
    cache = Path("data/embeddings") / f"{agentkit.EMBED_MODEL.replace(':', '-')}-{variant}.npz"
    if cache.exists():
        saved = np.load(cache)
        if list(saved["past_numbers"]) == [p["number"] for p in past]:
            return {"past": past, "held": held, "past_vectors": saved["past"], "held_vectors": saved["held"]}
    print(f"Embedding {len(past)} resolved and {len(held)} held-back incidents ({variant}) with {agentkit.EMBED_MODEL}...")
    past_vectors = np.array(agentkit.embed([DOC + VARIANTS[variant](p) for p in past]))
    held_vectors = np.array(agentkit.embed([QUERY + VARIANTS[DEFAULT](h) for h in held]))
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.savez(cache, past=past_vectors, held=held_vectors, past_numbers=np.array([p["number"] for p in past]))
    print(f"  each text became {past_vectors.shape[1]} numbers; saved to {cache}\n")
    return {"past": past, "held": held, "past_vectors": past_vectors, "held_vectors": held_vectors}


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def keyword_ranking(data: dict) -> list[list[str]]:
    """The floor for retrieval: rank by the share of words two texts have in common."""
    docs = [words(VARIANTS[DEFAULT](p)) for p in data["past"]]
    out = []
    for h in data["held"]:
        q = words(VARIANTS[DEFAULT](h))
        overlap = [len(q & d) / len(q | d) for d in docs]
        out.append([data["past"][i]["number"] for i in np.argsort(overlap)[::-1][:5]])
    return out


def vector_ranking(data: dict, k: int = 5) -> list[list[tuple[int, float]]]:
    return [search.top_k(v, data["past_vectors"], k) for v in data["held_vectors"]]


def pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def neighbours(which: str) -> None:
    data = load()
    ranked = vector_ranking(data)
    if which == "hardest":
        n = min(range(len(ranked)), key=lambda i: ranked[i][0][1])
    else:
        n = next((i for i, h in enumerate(data["held"]) if h["number"] == which), None)
        if n is None:
            sys.exit(f"{which} is not one of the held-back incidents. Try INC0010405, or 'hardest'.")
    h = data["held"][n]
    print(f"{h['number']}  {h['short_description']}\n    {h['description'][:160]}\n")
    print("Its five nearest resolved incidents:")
    for i, score in ranked[n]:
        p = data["past"][i]
        print(f"  {score:.3f}  {p['number']}  P{p['priority']} {p['service']:<15} {p['short_description'][:58]}")
    near = [data["past"][i] for i, _ in ranked[n]]
    print(f"\nA vote among these five says: P{search.vote(near)['priority']} {search.vote(near)['service']}.")
    print("The truth is in data/eval_labels.json. Look only after you have written your prediction.")


def ask(text: str) -> None:
    """Your own words against the history, by shared words and by embedding, side by side."""
    data = load()
    q = words(text)
    docs = [words(VARIANTS[DEFAULT](p)) for p in data["past"]]
    overlap = [len(q & d) / len(q | d) for d in docs]
    by_words = [(int(i), overlap[i]) for i in np.argsort(overlap)[::-1][:5]]
    by_vector = search.top_k(np.array(agentkit.embed([QUERY + text])[0]), data["past_vectors"], 5)
    print(f"Looking for: {text}\n")
    for name, ranked in (("By shared words", by_words), ("By embedding", by_vector)):
        print(f"{name}:")
        for i, score in ranked:
            p = data["past"][i]
            print(f"  {score:.3f}  {p['number']}  P{p['priority']} {p['service']:<15} {p['short_description'][:58]}")
        print()


def measure() -> None:
    data, labels = load(), agentkit.eval_labels()
    relevant = [set(labels[h["number"]]["related"]) for h in data["held"]]
    by_words = keyword_ranking(data)
    ranked = vector_ranking(data)
    by_vector = [[data["past"][i]["number"] for i, _ in r] for r in ranked]
    print("Is an incident with the same underlying cause among those retrieved?")
    print(f"  {'':<22}{'at rank 1':>10}{'in top 5':>10}")
    for name, got in (("shared words (floor)", by_words), ("embeddings", by_vector)):
        print(f"  {name:<22}{pct(search.hit_at_k(got, relevant, 1)):>10}{pct(search.hit_at_k(got, relevant, 5)):>10}")
    predictions = {h["number"]: search.vote([data["past"][i] for i, _ in r]) for h, r in zip(data["held"], ranked)}
    s = scoring.score(predictions, labels)
    print("\nTriage by letting the five nearest incidents vote, with no language model:")
    print(f"  priority exact {pct(s['priority_exact'])}   within one {pct(s['priority_within_one'])}   service {pct(s['service'])}")
    agentkit.save_result("Nearest incidents vote (no model)", {**s, "hit_at_5": search.hit_at_k(by_vector, relevant, 5), "seconds": 0})
    print("Saved to the results board: http://localhost:8000/results")


def variants() -> None:
    labels = agentkit.eval_labels()
    print("What you embed for each resolved incident changes what is found:")
    print(f"  {'':<22}{'at rank 1':>10}{'in top 5':>10}")
    for name in VARIANTS:
        data = load(name)
        relevant = [set(labels[h["number"]]["related"]) for h in data["held"]]
        got = [[data["past"][i]["number"] for i, _ in r] for r in vector_ranking(data)]
        print(f"  {name:<22}{pct(search.hit_at_k(got, relevant, 1)):>10}{pct(search.hit_at_k(got, relevant, 5)):>10}")
    data = load()
    relevant = [set(labels[h["number"]]["related"]) for h in data["held"]]
    ranked = vector_ranking(data)
    order = sorted(range(len(ranked)), key=lambda i: ranked[i][0][1])
    print("\nDoes the best score tell you whether to trust the result? Held-back incidents in three groups, by their top score:")
    third = len(order) // 3
    for name, group in (("lowest third", order[:third]), ("middle third", order[third:2 * third]), ("highest third", order[2 * third:])):
        got = [[data["past"][i]["number"] for i, _ in ranked[n]] for n in group]
        low, high = ranked[group[0]][0][1], ranked[group[-1]][0][1]
        print(f"  {name:<14} top score {low:.2f} to {high:.2f}   related incident in top 5: {pct(search.hit_at_k(got, [relevant[n] for n in group], 5))}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--neighbours", metavar="INCIDENT")
    ap.add_argument("--ask", metavar="TEXT")
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--variants", action="store_true")
    args = ap.parse_args()
    try:
        if args.neighbours:
            neighbours(args.neighbours)
        elif args.ask:
            ask(args.ask)
        elif args.measure:
            measure()
        elif args.variants:
            variants()
        else:
            ap.print_help()
    except (RuntimeError, LookupError) as err:
        sys.exit(str(err))


if __name__ == "__main__":
    main()
