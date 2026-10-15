---
title: Graph memory
description: Add a graph database and memories gain entities, relations, timelines, and cause → effect links.
---

With a graph store configured, ContextKit keeps two views of what it learns. The vector store holds the facts, as before. The graph holds the **entities** in them (people, products, services, places) and the **relations** between them, stamped with when they were recorded. On top of the graph, ContextKit can build a **timeline** of events and the **causal links** between them, and search all of it at once. This part of ContextKit is called TCMGM: temporal, causal, multimodal graph memory.

## Set it up

```bash
pip install "{{ library.dist }}[graph]"
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:5
```

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "graph_store": {
        "provider": "neo4j",
        "config": {"url": "bolt://localhost:7687", "username": "neo4j", "password": "password"},
    },
})
```

| Provider | `config` | Install |
|---|---|---|
| `neo4j` | `url`, `username`, `password`, optional `database` | `[graph]` |
| `memgraph` | `url`, `username`, `password` | `[extras]` |
| `neptune` | `endpoint="neptune-graph://<graph-id>"` (Neptune Analytics; `neptune-db://` is not supported) | `[graph]` |

`graph_store` also takes an optional `llm` (a separate model for entity extraction) and `custom_prompt` (extra guidance on which entities and relations to keep).

## Entities and relations

Nothing changes in how you call `add` and `search`. Both now return a `relations` key next to `results`:

```python
result = memory.add("I deployed the payments API to production on Monday", user_id="dev-team")
print(result["relations"])
# {"added_entities": [...], "deleted_entities": [...]}

hits = memory.search("what did we deploy?", user_id="dev-team")
for rel in hits["relations"]:
    print(rel["source"], rel["relationship"], rel["destination"])
# dev-team  deployed  payments_api
```

Relations the LLM decides are outdated are removed from the graph when new information contradicts them, in the same way facts are updated in the vector store. `get_all` returns relations too, with the keys `source`, `relationship`, and `target`.

## Timelines and causes

To turn a conversation into dated events and the links between them, give a transcript to the timeline builder. It uses the same LLM and graph as your `Memory`:

```python
from datetime import datetime
from outhad_contextkit.memory.timeline import TimelineBuilder

timeline = TimelineBuilder(memory.llm, memory.graph)

result = timeline.build_from_transcript(
    transcript="""
User: We shipped the new caching layer on Monday.
User: Since Tuesday, checkout has been timing out.
User: Rolling back the cache fixed the timeouts.
""",
    user_id="dev-team",
    session_start=datetime(2026, 10, 12, 9, 0),
)
print(result["events"])        # dated events extracted from the transcript
print(result["causal_links"])  # e.g. caching layer shipped → checkout timeouts
```

The events and causal links are stored in the graph, so later searches can use them. `timeline.get_timeline(user_id, time_window=None, limit=50)` returns a user's events in order.

## Fused search

`use_tcmgm=True` searches the vector store, the entity graph, and the timeline together, follows causal chains from the best matches, and merges everything into one ranking:

```python
answer = memory.search(
    "why did checkout start timing out?",
    user_id="dev-team",
    use_tcmgm=True,
    time_window={"start": "2026-10-12T00:00:00", "end": "2026-10-19T00:00:00"},
    include_causal=True,
    limit=10,
)

for item in answer["fused_ranking"]:
    print(item["source"], round(item["final_score"], 3), item["content"])
```

Fused search returns a different shape from a normal search. There is no `results` key; instead:

| Key | What it holds |
|---|---|
| `fused_ranking` | The merged top results, ranked with reciprocal rank fusion. Each item has `content`, `id`, `source` (`vector`, `graph`, or `timeline`), `score`, `final_score`, `fusion_sources`, and `metadata`. |
| `vector_results` | The vector store matches. |
| `graph_results` | Matching entities and relations. |
| `timeline_results` | Events inside `time_window`. |
| `causal_chains` | For each seed event, the chains of causes before it and effects after it. |
| `multimodal_results` | Cross-modal matches, when [multimodal](/docs/multimodal/) embedders are set up. |

Things to know:

- `time_window` takes ISO 8601 strings for `start`, `end`, or both.
- Fused search uses the first of `user_id`, `agent_id`, `run_id` you pass, and ignores `filters` and `threshold`.
- Without a graph store, `use_tcmgm=True` is ignored and you get a normal search.
- It is available on `Memory`, not `AsyncMemory`.
