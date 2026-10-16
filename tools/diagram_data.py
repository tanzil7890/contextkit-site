"""Build the data behind the context-graph diagrams from a real run of the library.

Every node, edge, weight and score in those diagrams comes from this script:
the released library builds the graph and ranks the results with its default
context-graph settings. Memories are added with infer=False, so no LLM is
called; similarities come from a small local embedding model so the run is
reproducible without an API key.

Run it in an environment with the release the site documents, networkx and
sentence-transformers, from outside a checkout of the library (-I keeps
Python from importing a local copy):

    pip install "outhad-contextkitai==0.1.3" networkx sentence-transformers
    python -I tools/diagram_data.py content/data/context-graph.json

Re-run it for each library release and commit the JSON.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections import deque
from importlib.metadata import version

WORK = tempfile.mkdtemp(prefix="ck-diagram-")
os.environ["OUTHAD_CONTEXTKIT_DIR"] = WORK          # keep the run's files out of ~/.outhad_contextkit
os.environ["OUTHAD_CONTEXTKIT_TELEMETRY"] = "False"
os.environ.setdefault("OPENAI_API_KEY", "not-used")  # infer=False: the LLM is never called

from outhad_contextkit import Memory  # noqa: E402
from outhad_contextkit.memory.context_graph.retriever import GraphFirstRetriever  # noqa: E402

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
USER = "maya"
QUERY = "Which pizza should I order?"
LIMIT = 3

# (key, text, ids, metadata), added in this order. Maya's first chat, two pages of a
# menu imported separately, and one memory that belongs to another user.
MEMORIES = [
    ("pizza", "I love pizza", {"user_id": "maya", "run_id": "chat-1"}, None),
    ("margherita", "Margherita is my favourite pizza", {"user_id": "maya", "run_id": "chat-1"}, None),
    ("dairy", "I'm avoiding dairy this month", {"user_id": "maya", "run_id": "chat-1"}, None),
    ("menu", "Menu: margherita, marinara, diavola", {"user_id": "maya", "run_id": "menu-page-1"},
     {"doc_id": "menu.pdf"}),
    ("marinara", "Marinara is made without cheese", {"user_id": "maya", "run_id": "menu-page-2"},
     {"doc_id": "menu.pdf"}),
    ("sam", "Pizza is my favourite food", {"user_id": "sam", "run_id": "chat-9"}, None),
]


def main(out_path: str) -> None:
    memory = Memory.from_config({
        "vector_store": {"provider": "qdrant", "config": {
            "path": os.path.join(WORK, "qdrant"), "on_disk": True,
            "collection_name": "diagram", "embedding_model_dims": 384}},
        "embedder": {"provider": "huggingface", "config": {"model": MODEL, "embedding_dims": 384}},
        "history_db_path": os.path.join(WORK, "history.db"),
        "context_graph": {"enabled": True},
    })
    cg = memory.context_graph
    rcfg = memory.config.context_graph.retrieval

    ids: dict[str, str] = {}
    for key, text, scope, meta in MEMORIES:
        result = memory.add(text, infer=False, metadata=meta, **scope)
        ids[key] = result["results"][0]["id"]
    key_of = {v: k for k, v in ids.items()}

    nodes = []
    for key, text, scope, meta in MEMORIES:
        node = cg.backend.get_node(ids[key])
        nodes.append({
            "key": key, "text": text, "user_id": scope["user_id"], "run_id": scope["run_id"],
            "doc_id": (meta or {}).get("doc_id"), "relevance": round(node.relevance, 4),
        })
    edges = sorted(
        ({"src": key_of[e.src], "dst": key_of[e.dst], "type": e.type.value, "weight": round(e.weight, 4)}
         for e in cg.backend.all_edges() if e.src in key_of and e.dst in key_of),
        key=lambda e: (e["src"], e["dst"], e["type"]),
    )

    # What search does, step by step, with the library's own functions.
    filters = {"user_id": USER}
    seeds = memory._search_vector_store(QUERY, filters, LIMIT)
    q_emb = memory.embedding_model.embed(QUERY, "search")
    everything = GraphFirstRetriever(cg, rcfg).retrieve(
        QUERY, seeds, limit=rcfg.max_candidates,
        payload_resolver=memory._cgl_resolve_payloads, query_embedding=q_emb,
    )["results"]
    plain = memory.search(QUERY, user_id=USER, limit=LIMIT, use_context_graph=False)["results"]
    graph = memory.search(QUERY, user_id=USER, limit=LIMIT)

    # Hops from the seeds, walking edges both ways above the floor, as the retriever does.
    hop = {key_of[s["id"]]: 0 for s in seeds}
    queue = deque(hop)
    while queue:
        cur = queue.popleft()
        if hop[cur] >= rcfg.expansion_depth:
            continue
        for e in edges:
            if e["weight"] < rcfg.edge_weight_floor:
                continue
            for a, b in ((e["src"], e["dst"]), (e["dst"], e["src"])):
                if a == cur and b not in hop:
                    hop[b] = hop[cur] + 1
                    queue.append(b)

    candidates = []
    for r in everything:
        parts = r["context_graph"]
        key = key_of[r["id"]]
        candidates.append({
            "key": key, "score": round(r["score"], 4), "dense": round(parts["dense"], 4),
            "lexical": round(parts["lexical"], 4), "graph": round(parts["graph"], 4),
            "relevance": next(n["relevance"] for n in nodes if n["key"] == key),
            "was_seed": bool(parts["was_seed"]), "hop": hop.get(key), "user_id": r.get("user_id"),
        })

    top = [key_of[r["id"]] for r in graph["results"]]
    if top != [c["key"] for c in candidates[:LIMIT]]:
        raise SystemExit(f"search returned {top}, the retriever ranked {[c['key'] for c in candidates]}")

    data = {
        "library": version("outhad-contextkitai"),
        "embedder": MODEL,
        "query": QUERY,
        "user_id": USER,
        "limit": LIMIT,
        "settings": {
            "seed_top_k": rcfg.seed_top_k, "expansion_depth": rcfg.expansion_depth,
            "max_candidates": rcfg.max_candidates, "edge_weight_floor": rcfg.edge_weight_floor,
            "alpha_dense": rcfg.alpha_dense, "beta_bm25": rcfg.beta_bm25, "gamma_graph": rcfg.gamma_graph,
            "topic_min_similarity": memory.config.context_graph.edges.topic_min_similarity,
        },
        "nodes": nodes,
        "edges": edges,
        "seeds": [{"key": key_of[s["id"]], "score": round(s["score"], 4)} for s in seeds],
        "candidates": candidates,
        "results": top,
        "plain_results": [{"key": key_of[r["id"]], "score": round(r["score"], 4)} for r in plain],
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print(json.dumps({k: data[k] for k in ("seeds", "results", "plain_results")}, indent=1))
    for e in edges:
        print(f"  {e['src']:>10} -{e['type']}-> {e['dst']:<10} {e['weight']}")
    for c in candidates:
        print(f"  {c['key']:>10} score={c['score']:.3f} dense={c['dense']:.3f} lex={c['lexical']:.3f} "
              f"graph={c['graph']:.3f} seed={c['was_seed']} hop={c['hop']} user={c['user_id']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "content/data/context-graph.json")
