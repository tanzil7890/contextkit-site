---
title: Quickstart
description: Give a chat loop long-term memory in a few minutes.
---

This walks through a small assistant that remembers what each user tells it, across sessions.

## 1. Install and set a key

```bash
{{ library.install }} openai
export OPENAI_API_KEY="sk-..."
```

ContextKit uses OpenAI by default: `gpt-4o-mini` to extract facts and `text-embedding-3-small` to embed them. To use Anthropic, Gemini, Ollama, or another provider instead, see [Providers](/docs/providers/).

## 2. Create a memory

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {
        "provider": "qdrant",
        "config": {"path": "./memory", "on_disk": True},
    },
})
```

This keeps memories in a local Qdrant database under `./memory`. No server is needed.

!!! warning "Set a path with `on_disk: True`"
    With no configuration, Qdrant runs from `/tmp/qdrant` with `on_disk` off, and that directory is cleared every time a `Memory` starts. The config above keeps memories across restarts. Create memories with `Memory.from_config(...)` rather than `Memory()`, so each instance gets its own config.

## 3. Add what the user says

Pass a string, or a list of chat messages:

```python
memory.add(
    [
        {"role": "user", "content": "I'm vegetarian, and I'm allergic to peanuts."},
        {"role": "assistant", "content": "Got it, I'll keep that in mind."},
    ],
    user_id="alice",
)
```

The LLM reads the exchange and stores the facts it finds, such as "Is vegetarian" and "Allergic to peanuts". The return value lists what changed:

```python
{"results": [
    {"id": "…", "memory": "Is vegetarian", "event": "ADD"},
    {"id": "…", "memory": "Allergic to peanuts", "event": "ADD"},
]}
```

Later, when Alice says "I've started eating fish again", the LLM updates the existing memory instead of adding a contradictory one, and the result has `"event": "UPDATE"` with the old text in `previous_memory`.

## 4. Search before you answer

```python
hits = memory.search("What should I cook tonight?", user_id="alice", limit=3)

for hit in hits["results"]:
    print(f'{hit["score"]:.2f}  {hit["memory"]}')
```

Each result has the memory text, its `id`, a similarity `score`, its `metadata`, and `created_at` / `updated_at` timestamps.

## 5. Put it together

```python
from openai import OpenAI
from outhad_contextkit import Memory

llm = OpenAI()
memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
})


def reply(message: str, user_id: str) -> str:
    hits = memory.search(message, user_id=user_id, limit=5)
    known = "\n".join(f"- {hit['memory']}" for hit in hits["results"])

    answer = llm.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": f"You are a helpful assistant. What you know about the user:\n{known}"},
            {"role": "user", "content": message},
        ],
    ).choices[0].message.content

    memory.add(
        [{"role": "user", "content": message}, {"role": "assistant", "content": answer}],
        user_id=user_id,
    )
    return answer


print(reply("I'm vegetarian and allergic to peanuts.", "alice"))
print(reply("What should I make for dinner?", "alice"))
```

Each turn sends the model a few relevant facts instead of the whole conversation, and stores whatever the turn taught it.

## What is stored where

| Data | Where |
|---|---|
| Memories and embeddings | The vector store: `./memory` with the config above |
| Change history | `~/.outhad_contextkit/history.db` (SQLite) |
| An anonymous install id | `~/.outhad_contextkit/config.json` |

Set `OUTHAD_CONTEXTKIT_DIR` to move the `~/.outhad_contextkit` directory, or `history_db_path` in the config to move only the history. Details are on the [Installation](/docs/installation/) page.

## Next steps

- [Memory operations](/docs/memory-operations/): update, delete, history, and the full `add` / `search` options.
- [Scoping and filters](/docs/scoping/): agents, runs, and metadata filters.
- [Providers](/docs/providers/): other LLMs, embedders, and vector stores.
