---
title: ContextKit
nav: Overview
description: Long-term memory for AI agents, in one Python library.
---

ContextKit is a memory layer for AI agents. Your agent hands it conversations; ContextKit pulls out the facts worth keeping, stores them per user, and gives back only the few that matter for the next request. Instead of resending the whole history every turn, the prompt carries a handful of relevant memories.

- **Facts, not transcripts.** An LLM reads each conversation, extracts durable facts ("Allergic to peanuts"), and decides whether each one is new, an update to something it already knows, or something to forget. Pass `infer=False` to store text exactly as given.
- **Scoped by default.** Every memory belongs to a `user_id`, `agent_id`, or `run_id`, and every search is narrowed to one of them. See [Scoping and filters](/docs/scoping/).
- **Your models, your store.** 15 LLM providers, 10 embedders, and 16 vector stores, configured with one dictionary. Qdrant on local disk needs no servers. See [Providers](/docs/providers/).
- **When and why.** Add Neo4j, Memgraph, or Neptune and memories also become an entity graph with timestamps, plus timelines and cause → effect links you can query. See [Graph memory](/docs/graph-memory/).
- **A record of every change.** Each add, update, and delete writes a history row, so you can see how a fact changed over time.
- **Building blocks for sensitive data.** Find emails, phone numbers, API keys, and anything you write a rule for, redact them before storing, and encrypt values. See [Privacy](/docs/privacy/).
- **Opt-in layers.** A [context graph](/docs/context-graph/) that links memories to each other, [personalized ranking](/docs/personalized-retrieval/), [tenants](/docs/tenants/), and [decay and versioning](/docs/decay-and-versioning/). Each is off until you turn it on, and off means no change in behaviour.

## Install

```bash
{{ library.install }}
```

The current release is **{{ library.version }}**. ContextKit needs Python 3.9 or newer and, with the defaults, an OpenAI API key in `OPENAI_API_KEY`. Extras for graph stores, other vector stores, and local models are on the [Installation](/docs/installation/) page.

## A first memory

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
})

memory.add("I'm vegetarian and allergic to peanuts", user_id="alice")

hits = memory.search("What should I cook for Alice?", user_id="alice")
for hit in hits["results"]:
    print(round(hit["score"], 2), hit["memory"])
```

`add` sent the sentence to the LLM, which extracted two facts and stored each one with its embedding. `search` embedded the question and returned the closest memories for `alice`. The [Quickstart](/docs/quickstart/) builds this into a chat loop.

## How it works

When you **add**, ContextKit:

1. Extracts candidate facts from the messages with the LLM (skipped with `infer=False`).
2. Looks up the user's existing memories that are close to each fact.
3. Asks the LLM whether each fact is new (`ADD`), changes an existing memory (`UPDATE`), contradicts one (`DELETE`), or is already known (`NONE`).
4. Writes the result to the vector store and a history row to SQLite, and, with a graph store configured, adds the entities and relations to the graph.

When you **search**, ContextKit embeds the query, runs a similarity search in the vector store filtered to the given `user_id`, `agent_id`, or `run_id`, and returns the matches with their scores. With a graph store, related entities come back alongside in `relations`.

## Two packages

| Package | What it is | Install |
|---|---|---|
| `{{ library.dist }}` | The memory engine. Runs in your process with your LLM, embedder, and vector store. | `{{ library.install }}` |
| `{{ sdk.dist }}` | A thin HTTP client for the hosted ContextKit cloud. No model or database dependencies. | `{{ sdk.install }}` |

Most people want the library. The [cloud SDK](/docs/cloud/) is for the hosted ContextKit service.

## Where to next

- [Quickstart](/docs/quickstart/): a chat loop with memory in a few minutes.
- [Memory operations](/docs/memory-operations/): everything `add`, `search`, `update`, and `delete` can do.
- [Configuration](/docs/configuration/): models, stores, and prompts.
- [API reference](/docs/reference/library/): every public method in {{ library.version }}, generated from the release.
