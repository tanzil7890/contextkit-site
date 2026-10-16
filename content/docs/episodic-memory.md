---
title: Episodic memory (TCMGM)
nav: Episodic memory
description: Dated events and the cause → effect links between them, so your agent can answer when and why.
access: team
---

Facts tell your agent *what* is true. Episodic memory tells it *what happened, when, and what led to what*: a timeline of dated events with cause → effect links between them. Ask "why did checkout start timing out?" and you get back the deploy that came before it, not just the facts that look like the question.

In ContextKit this is TCMGM (temporal, causal, multimodal graph memory). It sits on top of [graph memory](/docs/graph-memory/) and needs the `neo4j` graph store.

## Turn it on

TCMGM is set up whenever a graph store is configured. The `tcmgm` block only changes how it behaves:

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "graph_store": {
        "provider": "neo4j",
        "config": {"url": "bolt://localhost:7687", "username": "neo4j", "password": "password"},
    },
    "tcmgm": {
        "build_timeline_on_add": True,    # also store events on every add()
        "causal_extraction_mode": "llm",  # or "cascade", or "rules"
    },
})
```

| `tcmgm` key | Default | What it does |
|---|---|---|
| `enabled` | `True` | Set up TCMGM when a graph store is configured. `False` keeps the entity graph and skips TCMGM. |
| `build_timeline_on_add` | `False` | Every `add()` (with `infer=True`) also stores its messages as events and causal links. Costs extra LLM calls. |
| `causal_extraction_mode` | `"llm"` | How cause → effect links are found. `"llm"` asks the LLM. `"rules"` makes no LLM call but is crude: one "because" links the event to every other event in the same batch. `"cascade"` tries the rules first and asks the LLM only when they find too little. |

## Store events

Without `build_timeline_on_add`, store a conversation as events yourself:

```python
from datetime import datetime

built = memory.build_timeline(
    [
        {"role": "user", "content": "We shipped the new caching layer"},
        {"role": "user", "content": "Checkout started timing out because of the cache"},
        {"role": "user", "content": "Rolling back the cache fixed the timeouts"},
    ],
    user_id="dev-team",
    session_start=datetime(2026, 10, 12, 9, 0),
)

built["events"]        # [{"id", "content", "timestamp", "confidence", "modality"}, ...]
built["causal_links"]  # [{"cause_id", "effect_id", "causal_type", "confidence", "evidence", "timestamp"}, ...]
```

<!-- diagram: tcmgm-write -->

`messages` can be a string or a list of messages with text content. Each event is stored as its own node in the graph, and its entities and relations are added to the entity graph too.

Things to know:

- **Times.** The first event is dated `session_start` (default: now) and each later one two minutes after the one before. Dates written in the text, like "yesterday", are not read.
- **Cost.** One LLM call pulls out the events, one finds the causal links (none in `"rules"` mode), and each event goes through the usual entity extraction.
- **Scope.** Events belong to one id: the first of `user_id`, `agent_id`, `run_id` you pass.

## Read the timeline

```python
events = memory.get_timeline(
    user_id="dev-team",
    time_window={"start": "2026-10-12T00:00:00"},  # optional; "start", "end", or both
    limit=50,
)

for event in events:
    print(event["timestamp"], event["content"])
```

Events come back oldest first, each with `event_id`, `content`, `timestamp`, `confidence`, `modality`, and `user_id`. `time_window` takes ISO 8601 strings or `datetime` objects.

## Ask why

Pass an event's `event_id` to `get_causal_chain` to follow its links:

```python
timeout = events[1]

causes = memory.get_causal_chain(timeout["event_id"], user_id="dev-team")  # why did this happen?
effects = memory.get_causal_chain(events[0]["event_id"], user_id="dev-team", direction="forward")  # what did it lead to?

for chain in causes:
    print(" → ".join(e["content"] for e in chain["events"]))
    print([link["causal_type"] for link in chain["causal_links"]])
```

<!-- diagram: tcmgm-chain -->

You get up to 10 chains, shortest first. Each is `{"events": [...], "causal_links": [...], "depth": n}`, with events in cause → effect order. Link types are `caused_by`, `leads_to`, `enables`, `prevents`, and `correlates_with`. `max_depth` (default 3) limits how far a chain goes.

## Search with events

`search(..., use_tcmgm=True)` adds the timeline to [fused search](/docs/graph-memory/#fused-search), which merges vector, entity-graph, and timeline matches into one ranking. Pass a `time_window` to include events:

```python
answer = memory.search(
    "why did checkout start timing out?",
    user_id="dev-team",
    use_tcmgm=True,
    time_window={"start": "2026-10-12T00:00:00"},
)
answer["timeline_results"]  # events in the window, ranked by relevance to the query
```

Fused search starts its `causal_chains` from the top vector matches. Those are memory ids, not event ids, so `causal_chains` is usually empty. To answer "why", use `get_causal_chain`.

## Graph stores and async

| | `neo4j` | `memgraph`, `neptune` |
|---|---|---|
| `search(use_tcmgm=True)` | Vector, entity graph, and timeline | Vector and entity graph only |
| `build_timeline`, `get_timeline`, `get_causal_chain` | Yes | Raise `RuntimeError` |

Every method on this page is on `AsyncMemory` too, as a coroutine (`await memory.build_timeline(...)`), and `AsyncMemory.search` takes `use_tcmgm`, `time_window`, and `include_causal`.

`build_timeline`, `get_timeline`, and `get_causal_chain` raise `RuntimeError` when there is no graph store or `tcmgm.enabled` is `False`. `search(use_tcmgm=True)` logs a warning once and runs a normal search instead.

## Images and audio

The "multimodal" in TCMGM is not connected yet. Fused search returns a `multimodal_results` key, but it is always empty. Images still work through [vision](/docs/multimodal/): a vision model describes them and the description is stored as text.
