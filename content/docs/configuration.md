---
title: Configuration
description: Choose the LLM, embedder, vector store, and graph store, and tune how facts are extracted.
---

Pass a dictionary to `Memory.from_config`. Every key is optional; anything you leave out keeps its default.

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "llm": {"provider": "openai", "config": {"model": "gpt-4o-mini", "temperature": 0.1}},
    "embedder": {"provider": "openai", "config": {"model": "text-embedding-3-small"}},
    "vector_store": {
        "provider": "qdrant",
        "config": {"host": "localhost", "port": 6333, "collection_name": "support_agent"},
    },
    "history_db_path": "/var/lib/support-agent/memory-history.db",
})
```

The dictionary is checked with Pydantic when the `Memory` is created, so a wrong type fails at startup. Unknown keys are ignored rather than rejected, though: a misspelled `"vector_stor"` silently leaves the vector store on its default, so check the spelling against the [configuration reference](/docs/reference/config/).

## Defaults

| Key | Default |
|---|---|
| `llm` | OpenAI `gpt-4o-mini`, temperature 0.1, 2000 max tokens |
| `embedder` | OpenAI `text-embedding-3-small` (1536 dimensions) |
| `vector_store` | Qdrant at `/tmp/qdrant`, collection `outhad_contextkit`, cleared on every start |
| `graph_store` | None: graph memory is off until you configure one |
| `history_db_path` | `~/.outhad_contextkit/history.db` |
| `version` | `"v1.1"`: results come back as `{"results": [...]}` |

The Qdrant default is meant for trying things out. For anything you want to keep, give it a `path` with `on_disk: True`, or a server's `host` and `port` (or `url` and `api_key`).

## Top-level keys

| Key | What it sets | Guide |
|---|---|---|
| `llm` | The model that extracts facts and decides what to update. `{"provider": ..., "config": {...}}` | [LLMs](/docs/providers/#llms) |
| `embedder` | The model that embeds memories and queries | [Embedders](/docs/providers/#embedders) |
| `vector_store` | Where memories and embeddings live | [Vector stores](/docs/providers/#vector-stores) |
| `graph_store` | Neo4j, Memgraph, or Neptune for entities and relations | [Graph memory](/docs/graph-memory/) |
| `tcmgm` | Timelines and cause → effect links on top of the graph store; on whenever `graph_store` is set | [Episodic memory](/docs/episodic-memory/) |
| `history_db_path` | The SQLite file for change history | |
| `state_store` | A Postgres database for the opt-in layers' state, from 0.1.4 | [below](#state-store) |
| `custom_fact_extraction_prompt` | Replaces the prompt that pulls facts out of messages | [below](#custom-prompts) |
| `custom_update_memory_prompt` | Replaces the prompt that decides ADD / UPDATE / DELETE / NONE | [below](#custom-prompts) |
| `chunking` | Splitting long documents stored with `infer=False` | [Chunking](/docs/chunking/) |
| `ppmf` | Settings for the privacy tools | [Privacy](/docs/privacy/) |
| `version` | Response shape: `"v1.1"` (default) or the deprecated `"v1.0"`, which returns bare lists | |

Four more keys switch on the opt-in layers, each off by default: `context_graph`, `mspr`, `tenant`, and `decay_v2`. Their guides are under **Advanced layers** in the sidebar, and each says at the top if its layer is not in the current release yet.

From 0.1.3, `history_db_path` also accepts a Postgres URL (`postgresql://user:password@host/db`, with `psycopg2` installed), so several processes can share one history.

<!-- diagram: config-layers -->

Every field and default is listed in the [configuration reference](/docs/reference/config/), generated from the current release.

## State store

The opt-in layers keep their state on local disk by default: the context graph in memory or a file, feedback in SQLite files, cold storage in JSON files. From 0.1.4, `state_store` puts it in a Postgres database instead, so several processes or servers share it and a restart loses nothing.

```bash
pip install "{{ library.dist }}[postgres]"
```

```python
memory = Memory.from_config({
    "state_store": {
        "url": "postgresql://user:password@host/db",
        "namespace": "acme-prod",
    },
    "context_graph": {"enabled": True, "backend": "postgres"},
    "mspr": {"enabled": True, "feedback": {"enabled": True}},
    "decay_v2": {"enabled": True, "cold_storage": {"backend": "postgres"}},
})
```

| State | Kept in the state store when |
|---|---|
| [Context graph](/docs/context-graph/): nodes, edges, embeddings, change log | `context_graph.backend` is `"postgres"` |
| [Personalized retrieval](/docs/personalized-retrieval/): feedback and query-success rows | `state_store.url` is set and that store has no `sqlite_path` |
| [Cold storage](/docs/decay-and-versioning/#cold-storage) | `decay_v2.cold_storage.backend` is `"postgres"` |

- **Tables.** ContextKit creates its tables (named `ck_…`) on first use. If the database has the pgvector extension, graph similarity lookups run in SQL; otherwise embeddings are compared in Python.
- **Namespace.** `namespace` (default `"default"`) keeps the state of several memories apart in one database, for example one per project or environment.
- **Missing URL.** A `"postgres"` backend without `state_store.url` logs an error: the context graph stays off, and cold storage does nothing.
- **Everything else.** For several processes to share all of a memory, the vector store and history must be shared too: use a vector store server, and a Postgres URL for `history_db_path`.

## Match the embedding size

The vector store creates its collection with `embedding_model_dims` dimensions, 1536 by default. If you switch to an embedder with a different size, set the same number on both, and use a new collection name: an existing collection keeps the size it was created with.

```python
memory = Memory.from_config({
    "embedder": {
        "provider": "openai",
        "config": {"model": "text-embedding-3-large", "embedding_dims": 3072},
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "path": "./memory",
            "on_disk": True,
            "collection_name": "memories_3072",
            "embedding_model_dims": 3072,
        },
    },
})
```

## Custom prompts

Two prompts drive `add`. Override either to change what counts as a fact for your domain.

```python
memory = Memory.from_config({
    "custom_fact_extraction_prompt": """
Extract facts about the customer's products, orders, and support issues.
Ignore small talk. Return JSON: {"facts": ["...", "..."]}.

Input: Hi, my order 1042 arrived with a cracked screen.
Output: {"facts": ["Order 1042 arrived with a cracked screen"]}

Input: Thanks, have a nice day!
Output: {"facts": []}
""",
})
```

The fact extraction prompt must make the LLM return `{"facts": [...]}`. Few-shot examples like the ones above work well.

The update prompt is given the existing memories and the new facts, and must return `{"memory": [{"id": ..., "text": ..., "event": ..., "old_memory": ...}]}`, where `event` is `ADD`, `UPDATE`, `DELETE`, or `NONE`. Start from the default prompt and edit it rather than writing one from scratch.

## Use one config per Memory

Build every `Memory` with `Memory.from_config(...)`. Calling `Memory()` with no arguments shares one default config object across the whole process, and creating a second `Memory()` that way points it at the wrong collection.
