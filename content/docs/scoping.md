---
title: Scoping and filters
nav: Scoping and filters
description: Keep memories per user, agent, or run, and narrow searches by metadata.
---

Every memory belongs to at least one scope, and every search runs inside one. That is what keeps one user's memories out of another user's answers.

## The three ids

| Id | Use it for |
|---|---|
| `user_id` | Facts about a person: preferences, history, constraints. |
| `agent_id` | What one agent has learned, shared across the users it serves. |
| `run_id` | A single session, task, or workflow run. |

`add`, `search`, `get_all`, and `delete_all` all take the same three keyword arguments. `add` and `search` need at least one; you can pass more than one to narrow further.

```python
memory.add("Prefers morning meetings", user_id="alice")
memory.add("Booked the Lisbon trip for alice", agent_id="travel-agent", run_id="trip-118")

memory.search("meeting times", user_id="alice")          # alice's memories
memory.search("bookings", agent_id="travel-agent")        # everything that agent stored
memory.search("bookings", agent_id="travel-agent", run_id="trip-118")  # one run only
```

When you pass several ids, a memory must match all of them.

## Agents that share memory

Several agents can read and write the same scope. A research agent stores findings that a coding agent picks up later:

```python
memory.add(
    "The login endpoint builds SQL by string concatenation",
    agent_id="security-review",
    run_id="audit-2026-10",
)

findings = memory.search("SQL injection risks", agent_id="security-review", run_id="audit-2026-10")
```

## Filter by metadata

Anything you pass as `metadata` to `add` is stored with the memory and can be filtered on:

```python
memory.add("Refund issued for order 1042", user_id="alice",
           metadata={"category": "billing", "channel": "email"})

memory.search("refunds", user_id="alice", filters={"category": "billing"})
memory.get_all(user_id="alice", filters={"channel": "email"})
```

Filters are exact matches, combined with AND. In `search`, filter values must be strings, numbers, or booleans; dictionaries and lists are ignored.

With Qdrant, `get_all` also accepts a range, with both bounds given:

```python
memory.get_all(user_id="alice", filters={"priority": {"gte": 2, "lte": 5}})
```

## Who said it

With `infer=False`, the `name` field of a message is stored as the memory's `actor_id`, and its `role` as `role`. Both come back as top-level keys in results, and `actor_id` can be used as a filter:

```python
memory.add(
    [{"role": "user", "name": "bob", "content": "Ship the hotfix on Friday"}],
    run_id="standup-0915",
    infer=False,
)
memory.search("hotfix", run_id="standup-0915", filters={"actor_id": "bob"})
```

## Multi-tenant apps

For software that serves many organisations, put the tenant in the scope (for example `user_id=f"{tenant}:{user}"`) or in metadata and filter on it. The [tenant layer](/docs/tenants/) adds a registry with sub-tenants and roles on top of this.
