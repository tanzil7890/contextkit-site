---
title: Memory operations
nav: Memory operations
description: Add, search, read, update, and delete memories, and see how each one changed.
---

Every example on this page uses a `memory` built as in the [Quickstart](/docs/quickstart/#2-create-a-memory). All methods are on `Memory`; `AsyncMemory` has the same methods as coroutines.

## add

```python
result = memory.add(messages, user_id="alice", metadata={"source": "chat"})
```

`messages` can be a string, a single `{"role": ..., "content": ...}` dict, or a list of them. At least one of `user_id`, `agent_id`, or `run_id` is required.

| Argument | Default | What it does |
|---|---|---|
| `user_id`, `agent_id`, `run_id` | `None` | Who the memories belong to. See [Scoping](/docs/scoping/). |
| `metadata` | `None` | Extra fields stored with each memory and usable as [filters](/docs/scoping/#filter-by-metadata). |
| `infer` | `True` | Extract facts with the LLM. `False` stores each message's content as-is. |
| `memory_type` | `None` | `"procedural_memory"` (with an `agent_id`) stores a summary of the agent's steps instead of facts. |
| `prompt` | `None` | The system prompt for procedural memory. |

<!-- diagram: add-decision -->

With `infer=True`, the result lists each change the LLM decided on:

```python
{"results": [
    {"id": "4f1c…", "memory": "Allergic to peanuts", "event": "ADD"},
    {"id": "a3f1…", "memory": "Eats fish, no other meat", "event": "UPDATE",
     "previous_memory": "Is vegetarian"},
]}
```

`event` is `ADD`, `UPDATE`, or `DELETE`. Facts the LLM judged already known (`NONE`) are not listed. With a graph store configured, the result also has `relations`, with the entities that were added and removed.

With `infer=False`, nothing goes to the LLM: each non-system message becomes one memory. Use it for documents, logs, or text you have already distilled. Long texts can be [chunked](/docs/chunking/).

## search

```python
hits = memory.search("dietary restrictions", user_id="alice", limit=5, threshold=0.3)
```

| Argument | Default | What it does |
|---|---|---|
| `query` | required | What to look for. It is embedded with the configured embedder. |
| `user_id`, `agent_id`, `run_id` | `None` | At least one is required. Only that scope's memories are searched. |
| `limit` | `100` | The most results to return. |
| `filters` | `None` | Metadata equality filters, such as `{"source": "chat"}`. |
| `threshold` | `None` | Drop results scoring below this. |
| `use_tcmgm`, `time_window`, `include_causal` | off | Fused graph and timeline search. See [Graph memory](/docs/graph-memory/). |
| `merge_chunks`, `chunk_context_window` | from config | Rejoin chunks of one document. See [Chunking](/docs/chunking/). |

Each result looks like this:

```python
{
    "id": "4f1c…",
    "memory": "Allergic to peanuts",
    "score": 0.82,
    "hash": "…",
    "metadata": {"source": "chat"},
    "created_at": "2026-10-01T09:14:03.511-07:00",
    "updated_at": None,
    "user_id": "alice",
}
```

`metadata` holds the metadata you passed to `add`. The scoping ids, and `actor_id` and `role` when present, are promoted to top-level keys. With a graph store configured, `search` also returns `relations`: `[{"source": ..., "relationship": ..., "destination": ...}]`.

## get and get_all

```python
one = memory.get("4f1c…")                         # a single memory, or None
everything = memory.get_all(user_id="alice", limit=200)
for item in everything["results"]:
    print(item["memory"])
```

`get_all` takes the same scoping ids and `filters` as `search`, plus `limit` (default 100), and returns `{"results": [...]}` without scores.

## update

```python
memory.update("4f1c…", "Allergic to peanuts and tree nuts")
```

Replaces the memory's text, re-embeds it, and records an `UPDATE` in its history. Returns `{"message": "Memory updated successfully!"}`.

## delete and delete_all

```python
memory.delete("4f1c…")
memory.delete_all(user_id="alice")
```

`delete_all` needs at least one scoping id. With Qdrant it removes up to 100 memories per call, so loop until `get_all` comes back empty when a scope holds more.

## history

```python
for row in memory.history("a3f1…"):
    print(row["event"], row["old_memory"], "→", row["new_memory"], row["created_at"])
```

Every `add`, `update`, and `delete` writes a row, oldest first. Each row has `id`, `memory_id`, `old_memory`, `new_memory`, `event` (`ADD`, `UPDATE`, or `DELETE`), `created_at`, `updated_at`, `is_deleted`, `actor_id`, and `role`.

## reset

```python
memory.reset()
```

Deletes every memory in the vector store collection and clears the history database. There is no undo.

## Procedural memory

For agents that should remember how they did something rather than facts about a user, pass the agent's run as messages with `memory_type="procedural_memory"` and an `agent_id`:

```python
memory.add(agent_steps, agent_id="travel-booker", memory_type="procedural_memory")
```

The LLM writes a summary of the steps and their outcomes, stored as one memory with `metadata["memory_type"] = "procedural_memory"`. Without an `agent_id`, the call is a normal `add`.

## Async

`AsyncMemory` mirrors `Memory`. Note that `from_config` is a coroutine too:

```python
import asyncio
from outhad_contextkit import AsyncMemory


async def main():
    memory = await AsyncMemory.from_config({
        "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    })
    await memory.add("I prefer window seats", user_id="alice")
    hits = await memory.search("seat preference", user_id="alice")
    print(hits["results"])


asyncio.run(main())
```

`AsyncMemory.search` takes the graph-memory arguments (`use_tcmgm`, `time_window`, `include_causal`) from 0.1.4; in earlier releases, use `Memory` for those.

## Full signatures

The [API reference](/docs/reference/library/) lists every argument of every method in {{ library.version }}, with its docstring.
