"""Given: the vector database, adopted. Nothing here needs editing.

Session 7 was search by hand: every vector in one matrix, compared with
every query. This file hands that job to Chroma, a vector database that
runs inside this project (no server, no account; its files live in
data/chroma/). Read build() and vector(): adopting it is about ten lines.

    index = Index()                  embeds and stores the history on first use
    index.vector("refunds late", 5)  nearest by embedding, through Chroma
    index.keyword("refunds late", 5) best by YOUR bm25_scores
    index.hybrid("refunds late", 5)  the two merged by YOUR rrf
"""
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import agentkit  # noqa: E402

retrieval = agentkit.load("08-rag", "retrieval")

DOC, QUERY = "search_document: ", "search_query: "   # the labels this embedding model was trained with


def tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def text_of(incident: dict) -> str:
    return f"{incident['short_description']}\n{incident['description']}"


class Index:
    """The resolved incidents, searchable three ways."""

    def __init__(self, name: str = "incidents", path: str = "data/chroma", docs: list[dict] | None = None):
        import chromadb

        self.past = agentkit.history()
        self.by_number = {p["number"]: p for p in self.past}
        # docs lets a caller index something other than one text per incident, for example chunks.
        self.docs = docs or [{"id": p["number"], "number": p["number"], "text": text_of(p)} for p in self.past]
        self.words = [tokens(d["text"]) for d in self.docs]
        client = chromadb.PersistentClient(path=path)
        self.collection = client.get_or_create_collection(name, metadata={"hnsw:space": "cosine"})
        if self.collection.count() != len(self.docs):
            self.build(client, name)

    def build(self, client, name: str) -> None:
        print(f"Indexing {len(self.docs)} texts in Chroma ({name})...")
        client.delete_collection(name)
        self.collection = client.create_collection(name, metadata={"hnsw:space": "cosine"})
        vectors = agentkit.embed([DOC + d["text"] for d in self.docs])
        self.collection.add(ids=[d["id"] for d in self.docs], embeddings=vectors,
                            documents=[d["text"] for d in self.docs],
                            metadatas=[{"number": d["number"]} for d in self.docs])

    def _incidents(self, doc_ids: list[str], k: int) -> list[str]:
        """Document ids to incident numbers, best first, each incident once."""
        numbers = []
        for doc_id in doc_ids:
            number = doc_id.split("#")[0]
            if number not in numbers:
                numbers.append(number)
        return numbers[:k]

    def vector(self, text: str, k: int = 5, vector: list[float] | None = None) -> list[str]:
        vector = vector or agentkit.embed([QUERY + text])[0]
        found = self.collection.query(query_embeddings=[vector], n_results=min(4 * k, len(self.docs)))
        return self._incidents(found["ids"][0], k)

    def keyword(self, text: str, k: int = 5) -> list[str]:
        scores = retrieval.bm25_scores(tokens(text), self.words)
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:4 * k]
        return self._incidents([self.docs[i]["id"] for i in order if scores[i] > 0], k)

    def hybrid(self, text: str, k: int = 5, vector: list[float] | None = None) -> list[str]:
        merged = retrieval.rrf([self.vector(text, 20, vector), self.keyword(text, 20)])
        return merged[:k]

    def get(self, numbers: list[str]) -> list[dict]:
        return [self.by_number[n] for n in numbers]
