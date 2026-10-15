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
| `history_db_path` | The SQLite file for change history | |
| `custom_fact_extraction_prompt` | Replaces the prompt that pulls facts out of messages | [below](#custom-prompts) |
| `custom_update_memory_prompt` | Replaces the prompt that decides ADD / UPDATE / DELETE / NONE | [below](#custom-prompts) |
| `chunking` | Splitting long documents stored with `infer=False` | [Chunking](/docs/chunking/) |
| `ppmf` | Settings for the privacy tools | [Privacy](/docs/privacy/) |
| `version` | Response shape: `"v1.1"` (default) or the deprecated `"v1.0"`, which returns bare lists | |

The next release adds four more, each off by default: `context_graph`, `mspr`, `tenant`, and `decay_v2`. Their guides are under **Advanced layers** in the sidebar.

Every field and default is listed in the [configuration reference](/docs/reference/config/), generated from the current release.

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
