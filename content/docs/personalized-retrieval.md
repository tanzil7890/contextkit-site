---
title: Personalized retrieval
nav: Personalized retrieval
description: Rank memories by what has helped before, how often they are used, and who is asking.
requires: outhad_contextkit.memory.personalized
---

Personalized retrieval (MSPR, multi-stage personalized retrieval) adds signals to the [context graph](/docs/context-graph/)'s ranking: feedback on which memories helped, how often each one is used, which memories answered the same question before, what kind of question is being asked, and what the caller is allowed to see. Each signal has its own switch and weight, and every weight starts at zero, so you can turn them on one at a time and measure each.

## Turn it on

MSPR works on top of the context graph, so both must be on:

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "context_graph": {
        "enabled": True,
        "retrieval": {"delta_personal": 0.3, "epsilon_frequency": 0.1, "zeta_success": 0.2},
    },
    "mspr": {
        "enabled": True,
        "feedback": {"enabled": True},
        "frequency": {"enabled": True},
        "success": {"enabled": True},
    },
})
```

The ranking becomes:

```text
score = (alpha_dense · dense + beta_bm25 · lexical + gamma_graph · graph
         + delta_personal · personal + epsilon_frequency · frequency + zeta_success · success) × relevance
```

All six weights live under `context_graph.retrieval`. With `mspr.enabled` on but every new weight at 0, ranking is exactly what the context graph alone gives.

| Signal | Switch | Weight | Comes from |
|---|---|---|---|
| personal | `mspr.feedback.enabled` | `delta_personal` | Helpful and unhelpful verdicts on the memory |
| frequency | `mspr.frequency.enabled` | `epsilon_frequency` | How often the memory has been returned, relative to the most used one |
| success | `mspr.success.enabled` | `zeta_success` | How often the memory helped for this same query before |
| intent | `mspr.intent.enabled` | adjusts α, β, γ, δ | The kind of question |
| role | `mspr.role.enabled` | filter or multiplier | A `RolePolicy` you install |

## Feedback

Tell ContextKit whether a retrieved memory helped:

```python
hits = memory.search("Q4 revenue forecast", user_id="u1")
top = hits["results"][0]

memory.record_feedback(top["id"], helpful=True, user_id="u1", query="Q4 revenue forecast")
# {"memory_id": "...", "delta_applied": 0.15, "new_relevance": ..., "event_id": ..., "helpful": True}
```

A helpful verdict raises the memory's relevance by `boost_delta` (0.15), up to `max_boost_per_memory` (0.60), and by default keeps it from decaying below the new level. An unhelpful one lowers it by `penalty_delta` (0.10). The verdict also feeds the `personal` term. Verdicts are stored in `feedback_events.db`.

`record_feedback` returns `None` when MSPR, feedback, or the context graph is off, or when the memory is not in the graph. `memory.reset_feedback(user_id="u1")` deletes one user's verdicts, or everyone's without `user_id`.

## Answers that worked

With `success` on, passing `query=` to `record_feedback` also records whether that memory helped for that exact query (lowercased, trimmed, and hashed). Later searches with the same query lift memories with a good record. A memory needs `min_sample_size` (3) verdicts for the query before it counts. These rows are stored in `query_success.db`.

`memory.backfill_mspr()` rebuilds the success table from existing feedback. Run it once: running it again adds the same rows a second time.

## Intent

With `intent` on, each query is classified as `FACTUAL`, `CONVERSATIONAL`, `DOCUMENTARY`, `EXPLORATORY`, or `UNKNOWN`, and the weights are adjusted for that search:

| Intent | Adjustment |
|---|---|
| `FACTUAL` | dense +0.10, lexical +0.10, graph −0.10 |
| `CONVERSATIONAL` | graph +0.15 |
| `DOCUMENTARY` | graph +0.10 |
| `EXPLORATORY`, `UNKNOWN` | none |

`strategy` is `regex` (the default; fast, no LLM call), `llm`, or `hybrid`. With the regex fast path on, the LLM is asked only when no pattern matches, and a slow or failed LLM call counts as `UNKNOWN`.

## Roles

A role policy decides which memories a caller may see. Install one on the `Memory`:

```python
from outhad_contextkit.memory.personalized.role import TenantIsolationPolicy

memory = Memory.from_config({
    "context_graph": {"enabled": True},
    "mspr": {"enabled": True, "role": {"enabled": True, "hard_filter": True}},
})
memory.set_role_policy(TenantIsolationPolicy())

memory.add("Board deck draft", user_id="cfo", metadata={"tenant_id": "acme"})
hits = memory.search("board deck", user_id="cfo", filters={"tenant_id": "acme"})
```

The caller's tenant and role are read from `filters["tenant_id"]` and `filters["role"]`. Those keys are also applied as ordinary metadata filters, so a `role` filter only matches memories stored with that same `role` value; that limits `RoleScopePolicy` in this build. The bundled policies:

| Policy | Allows a memory when |
|---|---|
| `TenantIsolationPolicy()` | Its `tenant_id` matches the caller's, or it has none |
| `RoleScopePolicy()` | Its `allowed_roles` include the caller's role, or it has none |
| `CompositePolicy([...])` | Every policy in the list allows it |
| `AllowAllPolicy()` | Always |

Write your own by subclassing `RolePolicy` and implementing `allow(self, *, memory_payload, role_ctx) -> bool`, and optionally `reweight(...) -> float`.

With `hard_filter: True`, denied memories are removed from the seeds before ranking. With `False`, each result's score is multiplied by the policy's `reweight`, and denied results score 0. Graph neighbours added during expansion are not filtered by the policy, so combine roles with the [scoping warning](/docs/context-graph/#how-search-ranks) in mind.

## Telemetry

Each MSPR search sends one `outhad_contextkit.mspr.search` event with which signals were on and how many results each affected. Like all telemetry it contains no memory content, and `OUTHAD_CONTEXTKIT_TELEMETRY=False` turns it off.
