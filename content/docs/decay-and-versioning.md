---
title: Decay and versioning
description: Score memories by freshness and use, archive the stale ones, and move them to cold storage.
requires: outhad_contextkit.memory.lifecycle
---

Long-lived memory stores fill up with facts nobody needs any more. The lifecycle layer gives every memory a decay score from how recently and how often it was used and whether it helped, archives the ones that fall below a threshold, and can move them to cheap storage and bring them back on demand.

## Turn it on

The decay score is computed from the [context graph](/docs/context-graph/), so turn both on:

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "context_graph": {"enabled": True},
    "decay_v2": {
        "enabled": True,
        "archive_threshold": 0.05,
        "track_references": True,
        "schedule": {"enabled": True, "interval_seconds": 1800},
    },
})
```

## The decay score

`memory.decay_score(memory_id)` returns a number from 0 (stale) to 1 (fresh), or `None` when the layer is off or the memory is not in the graph. It blends three parts:

| Part | Weight | How it is measured |
|---|---|---|
| recency | `weight_recency` (0.6) | Halves every `context_graph.decay.half_life_days` (30) since the memory was last used or updated |
| frequency | `weight_frequency` (0.3) | The memory's access count against the most-used memory's, on a log scale |
| feedback | `weight_feedback` (0.1) | Helpful minus unhelpful [feedback](/docs/personalized-retrieval/#feedback); 0.5 when there is none |

The three weights must add up to 1.0 or less.

## Archive stale memories

```python
preview = memory.archive_low(threshold=0.05, dry_run=True)
print(preview["candidates"])       # ids that would be archived

memory.archive_low(threshold=0.05) # {"archived": 12, "candidates": [...], "threshold": 0.05}
```

Archived memories stay in the store but are skipped when search expands through the graph, unless you pass `include_archived=True`. Without `threshold`, `archive_threshold` from the config is used.

## Run it on a schedule

With `schedule.enabled`, a background thread starts with the `Memory` and, every `interval_seconds` (one hour by default, with up to `jitter_seconds` of random spread), applies graph decay, archives memories below the threshold, and prunes old version records. Control it yourself with:

```python
memory.start_decay_scheduler()   # needs decay_v2.enabled
memory.stop_decay_scheduler()
memory.close()                   # stops the scheduler; call it on shutdown
```

`memory.backfill_decay_v2()` runs one archive pass over existing data and returns `{"archived", "candidates"}`.

## Count real use

Being returned by a search is not the same as being used. When your agent actually relies on a memory in its answer, record it, so frequency reflects real use:

```python
memory.record_reference(memory_id, strength=1.0)   # returns the new access count
```

This needs `track_references: True` and the context graph.

## Cold storage

Move a memory out of the vector store into cheap storage, and bring it back when it is needed:

```python
memory.demote_to_cold(memory_id)            # True when moved
payload = memory.promote_from_cold(memory_id)  # re-embedded and restored with the same id
```

| `cold_storage.backend` | Where | Settings |
|---|---|---|
| `disabled` (default) | Nowhere; the calls do nothing | |
| `local` | JSON files on disk | `local_root`, defaulting to `~/.outhad_contextkit/cold_storage` |
| `s3` | One object per memory | `s3_bucket`, `s3_prefix`; needs `boto3` and AWS credentials from the environment |

Demoting removes the memory from the vector store, so it no longer appears in any search until it is promoted.

## Versions

`diff_versions` compares the stored text of two memories:

```python
print(memory.diff_versions(old_id, new_id))               # unified diff
print(memory.diff_versions(old_id, new_id, mode="json"))  # {"removed": ..., "added": ...}
```

The layer also has a version-chain API, `versions`, `latest_version`, and `rollback`, for `versioning.mode: "immutable"`, where an update writes a new memory and marks the old one superseded. As of 0.1.3, `update` still edits memories in place and only `rollback` writes a new version, so treat the chain API as a preview.

## Telemetry

The layer sends `outhad_contextkit.lifecycle.tick`, `.archive`, `.rollback`, and `.reference` events with counts and timings, never memory content.
