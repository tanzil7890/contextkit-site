---
title: Cloud SDK
description: A thin HTTP client for the hosted ContextKit service, with no model or database dependencies.
cloud_notice: true
---

`{{ sdk.dist }}` talks to a ContextKit server over HTTPS. It depends only on `httpx`: models, vector stores, and the graph all run on the server. The current release is **{{ sdk.version }}**.

```bash
{{ sdk.install }}
```

```python
from outhad_contextkit_sdk import MemoryClient

client = MemoryClient(api_key="ock_live_...")   # or set OUTHAD_CONTEXTKIT_API_KEY

client.add(messages=[{"role": "user", "content": "I love sushi."}], user_id="alice")
hits = client.search(query="What food do I like?", user_id="alice")
for hit in hits["results"]:
    print(hit["memory"])
```

## Connecting

```python
client = MemoryClient(
    api_key="ock_live_...",              # or OUTHAD_CONTEXTKIT_API_KEY
    host="https://memory.example.com",   # or OUTHAD_CONTEXTKIT_HOST
    timeout=30.0,
)
```

- **API key.** `api_key`, or `OUTHAD_CONTEXTKIT_API_KEY`. Keys look like `ock_live_…` or `ock_test_…`, and are sent as `Authorization: Token <key>`. Test keys keep their data apart from live keys.
- **Host.** `host`, then `OUTHAD_CONTEXTKIT_HOST`, then the built-in default (`DEFAULT_HOST` in the [SDK reference](/docs/reference/sdk/#constants)).
- **Development fallback.** When you rely on the built-in default host and it cannot be reached, the client retries once against `http://localhost:8000` and stays there. Pass `host=` or `allow_dev_fallback=False` to turn that off.
- **Identity.** The constructor calls the server once to check the key, and fills in `client.org_id`, `client.project_id`, and `client.user_email`.

Use it as a context manager, or call `client.close()`, to release the connection pool.

## Memories

The methods mirror the [library's](/docs/memory-operations/):

```python
client.add(messages, user_id="alice", metadata={"source": "chat"}, infer=True)
client.search("dietary restrictions", user_id="alice", limit=10, threshold=0.3)
client.get_all(user_id="alice", page=1, page_size=50)
client.get(memory_id)
client.update(memory_id, text="Allergic to peanuts and tree nuts")
client.history(memory_id)
client.delete(memory_id)
client.delete_all(user_id="alice")
```

`search` also takes the server-side retrieval flags: `use_context_graph`, `use_tcmgm`, `time_window={"start": ..., "end": ...}`, `include_causal`, `keyword_search`, and `categories`. `output_format="v1.0"` returns a bare list instead of `{"results": [...]}`, and `includes=` / `excludes=` trim each result to the keys you want.

`get_all_filtered` takes a structured filter with `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$nin`, `$contains`, and `AND` / `OR` / `NOT`:

```python
client.get_all_filtered({"AND": [{"category": {"$eq": "billing"}}, {"priority": {"$gte": 2}}]}, user_id="alice")
```

## Pick the model per request

`add`, `search`, and `summary` accept `llm=` (and `add` and `search` accept `embedder=`) to override the project's models for one call:

```python
client.search("What food do I like?", user_id="alice", llm={"provider": "openai", "model": "gpt-4o-mini"})
```

Each override is `{"provider": ..., "model": ..., "api_key": ...}`; `api_key` is optional when the server has a key for that provider.

## More operations

| Area | Methods |
|---|---|
| Feedback | `feedback(memory_id, helpful=True, query=...)`, `reset_feedback()` |
| Writes | `add_idempotent(key, messages, ...)`, `batch_update([...])`, `batch_delete([...])` (up to 1000), `pin(id)`, `unpin(id)` |
| Reading | `summary(user_id=...)`, `export(user_id=..., include_history=False)`, `users()`, `delete_users(user_id=...)` |
| Versions | `versions(id)`, `latest_version(id)`, `diff_versions(old, new)`, `rollback(id, to_version=...)` |
| Lifecycle | `decay_score(id)`, `tick_decay()`, `archive_low(threshold=..., dry_run=True)`, `demote_to_cold(id)`, `promote_from_cold(id)`, `record_reference(id)` |
| Maintenance | `backfill("context_graph" \| "mspr" \| "decay_v2")`, `reset_cgl()`, `reset()` |
| Observability | `usage()`, `requests(...)`, `top_users()`, `graph_snapshot(user_id=...)`, `audit_log(...)` |
| Account | `list_api_keys()`, projects, members, and webhooks |

Creating, rotating, and revoking keys, and changing projects, members, and webhooks, need a dashboard session; with an API key the server answers 403. A pinned memory cannot be updated or deleted until it is unpinned (409).

Every method, with its arguments, is in the [Cloud SDK API reference](/docs/reference/sdk/).

## Errors

| Exception | Raised when |
|---|---|
| `AuthenticationError` | No key is configured, or the server answers 401 |
| `APIError` | Any other non-2xx answer; has `.status` and `.body` |
| `ValueError` | A call is missing a required argument, such as `update` without `text` |

Connection errors from `httpx` are raised as they are.

## Async

`AsyncMemoryClient` has the same memory, search, feedback, lifecycle, and observability methods as coroutines, and works with `async with`. Unlike `MemoryClient`, it does not contact the server when it is created; call `await client.validate()` to check the key. It has no API-key management methods.

```python
import asyncio
from outhad_contextkit_sdk import AsyncMemoryClient


async def main():
    async with AsyncMemoryClient(api_key="ock_live_...") as client:
        await client.add(messages=[{"role": "user", "content": "I prefer aisle seats"}], user_id="alice")
        print(await client.search(query="seat preference", user_id="alice"))


asyncio.run(main())
```
