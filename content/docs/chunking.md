---
title: Chunking
description: Store long documents as overlapping chunks, and stitch them back together at search time.
---

Facts extracted by the LLM are short. Documents, transcripts, and logs that you store with `infer=False` are not, and one long embedding is a poor match for a specific question. With chunking on, ContextKit splits long texts into overlapping chunks, stores each as its own memory, and can merge neighbouring chunks back together when you search.

<!-- diagram: chunking -->

## Turn it on

```bash
pip install tiktoken   # needed for the default "token" strategy
```

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "chunking": {
        "enabled": True,
        "strategy": "token",
        "chunk_size": 512,
        "chunk_overlap": 50,
        "min_document_size": 1500,
    },
})

memory.add(handbook_text, user_id="acme-support", infer=False, metadata={"source": "handbook.md"})
```

A text is chunked only when all of these hold:

- it is added with `infer=False`,
- it is at least `min_document_size` characters long, and
- it is longer than `chunk_size` characters.

Everything else is stored as a single memory, so short notes are never fragmented. The `add` result lists one entry per chunk, each with `chunk_index`, `total_chunks`, and a shared `document_id`.

## Strategies

| `strategy` | Splits by | Needs |
|---|---|---|
| `token` (default) | Tokens, counted with the `tokenizer_model` encoding (`gpt-4` by default) | `pip install tiktoken` |
| `character` | Characters, trying each of `separators` in turn (paragraphs, then lines, sentences, words) | Nothing |

The configuration also accepts `semantic` and `hierarchical`, but they are not implemented in {{ library.version }}: a `Memory` configured with either fails to start.

## Settings

| Setting | Default | Meaning |
|---|---|---|
| `chunk_size` | `512` | Target chunk length, in tokens or characters depending on the strategy (50 to 8000). |
| `chunk_overlap` | `50` | How much each chunk repeats from the one before. Must be less than `chunk_size`. |
| `min_document_size` | `0` | Texts shorter than this many characters are never chunked. |
| `min_chunk_size` | `50` | Smallest chunk kept. |
| `max_chunks_per_document` | `None` | Cap on chunks per text. |
| `separators` | `["\n\n", "\n", ". ", " ", ""]` | Split points for the `character` strategy, in order of preference. |
| `merge_chunks_on_retrieval` | `True` | Merge chunks of the same document in search results. |
| `chunk_context_window` | `1` | How many neighbouring chunks on each side to include when merging. |

## Searching chunked documents

With `merge_chunks_on_retrieval` on, matching chunks from the same document come back as one result:

```python
hits = memory.search("refund window for damaged items", user_id="acme-support")

for hit in hits["results"]:
    meta = hit["metadata"] or {}
    if meta.get("is_merged"):
        print(f"{hit['score']:.2f} {meta['chunk_count']} chunks of {hit['id']}")
    print(hit["memory"][:200])
```

A merged result's `id` is the `document_id`, not a memory id. Its `memory` is the chunks joined with blank lines, its `score` is the best chunk's score, and its `metadata` adds `is_merged`, `chunk_count`, and `chunk_indices`.

Override the defaults for a single search with `merge_chunks=False` or `chunk_context_window=2`.
