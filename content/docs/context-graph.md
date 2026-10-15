---
title: Context graph
description: Link memories to each other, and search through the links.
requires: outhad_contextkit.memory.context_graph
---

With the context graph on, every memory becomes a node, and ContextKit links nodes as you add them: replies in the same conversation, the order things were said, memories from the same document, and memories on the same topic. Search then starts from the closest matches, walks those links, and re-ranks what it finds, so the context around the best match comes back with it.

The context graph is separate from [graph memory](/docs/graph-memory/): graph memory links *entities* in a graph database; the context graph links *memories* to each other, in process by default.

## Turn it on

```bash
pip install networkx
```

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "context_graph": {"enabled": True, "persist_path": "./memory/context_graph.pkl"},
})

memory.add("I love pizza", user_id="u1", run_id="r1")
memory.add("Italian food is my favourite", user_id="u1", run_id="r1")

hits = memory.search("what should I eat?", user_id="u1")
for hit in hits["results"]:
    print(round(hit["score"], 3), hit["memory"], hit.get("context_graph"))
print(hits.get("subgraph", []))
```

`networkx` is not installed by any extra. If it is missing, or the graph fails to start for another reason, ContextKit logs the error and searches without the graph.

Already have memories? Build the graph from them in one call. It is safe to run again; existing nodes and edges are skipped:

```python
memory.backfill_context_graph(user_id="u1")   # {"nodes": 42, "edges": 117}
```

`backfill_context_graph` reads up to 100,000 memories, in batches of `batch_size` (500), for the given `user_id`, `agent_id`, or `run_id`, or for everyone when you pass none.

## How memories are linked

| Edge | Created when | Weight |
|---|---|---|
| `REPLY_TO` | The previous memory in the same run (or agent) for the same user was added within `reply_to_window_seconds` (30 minutes) | 1.0 |
| `TEMPORAL_NEXT` | Each memory follows the previous one in the same run (or agent) for the same user | 0.6 |
| `DOCUMENT_LINK` | Two memories share a `doc_id`, `document_id`, `source_id`, `source_url`, or `url` in metadata, or a URL in their text | 0.8 |
| `TOPIC_SIMILAR` | Embeddings are at least `topic_min_similarity` (0.75) alike; up to `topic_top_k` (5) per memory | The cosine similarity |
| `UPDATED_FROM` | A new version of a memory is written by [versioning](/docs/decay-and-versioning/) | 1.0 |
| `SUPPORTS`, `CONTRADICTS`, `REFINES`, `ELABORATES` | The LLM labels a pair of similar memories, when LLM edges are on | The LLM's confidence |

Turn individual edge types off under `context_graph.edges`, for example `"edges": {"enable_topic_similar": False}`.

### LLM edges

LLM edges ask the configured LLM how pairs of topic-similar memories relate. They cost tokens, so they are off by default and capped by a daily budget per user:

```python
memory = Memory.from_config({
    "context_graph": {
        "enabled": True,
        "edges": {"llm": {"enabled": True, "max_pairs_per_insert": 3, "daily_token_budget": 100_000}},
    },
})
```

Only pairs at least `min_topic_similarity` (0.80) alike are sent, and labels below `min_confidence` (0.60) are discarded.

## How search ranks

When the context graph is on, `search` uses it by default. Pass `use_context_graph=False` to skip it for one call, or set `retrieval.enabled` to `False` to make that the default.

1. **Seed.** The vector store's top `seed_top_k` (10) matches become seeds.
2. **Expand.** From the seeds, follow edges up to `expansion_depth` (2) hops, ignoring edges lighter than `edge_weight_floor` (0.1), up to `max_candidates` (50) nodes. `algorithm` is `bfs` (the default) or `ppr`, personalised PageRank from the seeds. PageRank needs `scipy`; without it, search falls back to the seeds.
3. **Re-rank.** Every candidate gets a score:

```text
score = (alpha_dense · dense + beta_bm25 · lexical + gamma_graph · graph) × relevance
```

`dense` is the vector similarity, `lexical` the share of query words the memory contains, and `graph` how strongly the candidate is connected to the seeds. `relevance` is the node's decaying relevance (below). The default weights are 0.55, 0.15, and 0.30, all under `context_graph.retrieval`. [Personalized retrieval](/docs/personalized-retrieval/) adds three more terms.

Each result's `score` is this final score, and it gains a `context_graph` key with the parts: `dense`, `lexical`, `graph`, `frequency`, `personal`, `success`, and `was_seed`. When any edges connect the results, the response has a `subgraph` list of `{"src", "dst", "type", "weight"}`; read it with `hits.get("subgraph", [])`, since it is left out when empty.

!!! warning "Graph expansion is not scoped by user"
    `TOPIC_SIMILAR` edges are built across all memories in the store, and expansion does not re-check `user_id`, `agent_id`, or `run_id`. A search for one user can therefore return a graph neighbour that belongs to another user. If one store serves many users, keep the graph off or check each result's `user_id` before using it.

## Decay

Edges and nodes fade unless they are used, so old, unused context stops crowding search results.

| Setting (`context_graph.decay`) | Default | Meaning |
|---|---|---|
| `half_life_days` | 30 | Edge weights and node relevance halve over this many days without use. |
| `min_edge_weight` | 0.05 | Edges lighter than this are pruned. |
| `min_node_relevance` | 0.02 | Nodes below this are archived and skipped in expansion. |
| `tick_on_read` | `True` | Apply decay during search, at most once an hour. |

`CONTRADICTS` edges never decay. Run a round yourself with `memory.tick_decay()`, which returns `{"decayed", "pruned", "archived"}`, or steer one memory:

```python
memory.mark_relevant(memory_id, delta=0.25)    # boost, and keep it from decaying below the new level
memory.mark_irrelevant(memory_id, delta=0.25)  # push it down
```

Pass `include_archived=True` to `search` to expand into archived nodes too.

## Saving the graph

The default `networkx` backend keeps the graph in memory. With `persist_path` set, the graph is loaded from that file when the `Memory` starts, but it is not saved automatically. Save it when you are done, or on a timer:

```python
memory.context_graph.snapshot()           # writes persist_path
print(memory.context_graph.stats())       # {"nodes": ..., "nodes_total": ..., "edges": ...}
```

For large graphs, or to share one graph between processes, use `"backend": "neo4j"`, which stores nodes and edges in the Neo4j database configured as your [graph store](/docs/graph-memory/).

`memory.reset_context_graph()` drops every node and edge, and leaves the vector store and history alone.

## Change log, replay, and streaming

With `log_changes` on (the default), every change to the graph is appended to `context_graph_changes.db`, in the folder of `persist_path`, or `~/.outhad_contextkit/` when it is not set.

```python
from datetime import datetime

memory.snapshot_context_graph("./graph-export.jsonl")             # export nodes and edges
past = memory.replay_context_graph(until=datetime(2026, 10, 1))   # the graph as it was then
print(past.stats())
```

Subscribe to changes as they happen. Each event has `event_type`, `target_id`, `timestamp`, `user_id`, and `payload`:

```python
def on_change(event):
    print(event.event_type, event.target_id)

token = memory.subscribe_context_graph_changes(on_change, event_types=["node_added", "edge_added"])
memory.unsubscribe_context_graph_changes(token)
```

Pass `from_event_id=0` to replay the whole log to a new subscriber first. Event types are `node_added`, `node_updated`, `node_archived`, `node_deleted`, `node_relevance_bumped`, `node_accessed`, `edge_added`, `edge_decayed`, `edge_pruned`, `memory_feedback_recorded`, and `reset`.

To forward changes to another system, pass a sink's `send` method as the callback:

```python
from outhad_contextkit.memory.context_graph.sinks.webhook import WebhookSink

sink = WebhookSink("https://example.com/hooks/memory", secret="whsec_...")
memory.subscribe_context_graph_changes(sink.send)
```

| Sink | Import from `outhad_contextkit.memory.context_graph.sinks` | Notes |
|---|---|---|
| `WebhookSink(url, secret=None)` | `.webhook` | POSTs JSON with an `X-CGL-Signature: sha256=…` HMAC; check it with `WebhookSink.verify_signature(...)`. Retries 3 times. |
| `SSESink()` | `.sse` | `async for chunk in sink.stream()` yields server-sent event lines for a streaming HTTP response. |
| `KafkaSink(bootstrap_servers, topic)` | `.kafka` | Needs `pip install "{{ library.dist }}[context-graph-kafka]"`. Messages are keyed by `target_id`. |

## Settings

All settings live under `context_graph` in the config. The full list, with defaults, is in the [configuration reference](/docs/reference/config/).
