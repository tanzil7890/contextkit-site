---
title: Tenants
description: A registry of tenants, sub-tenants, and roles for software that serves many organisations.
requires: outhad_contextkit.memory.tenant
---

The tenant layer gives a multi-tenant app a registry to work from: tenants (your customers), sub-tenants under them (departments, projects, or users), and role bindings that say who can do what. It is stored in SQLite next to your other ContextKit files, so it needs no new infrastructure.

<!-- diagram: tenants -->

## Turn it on

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
    "tenant": {"enabled": True},
})
```

With the layer on, `memory.tenant` is the admin API. With it off, `memory.tenant` is `None` and nothing else changes.

## Manage tenants

```python
admin = memory.tenant

acme = admin.create_tenant(id="acme", name="Acme Corp", metadata={"plan": "enterprise"})
admin.list_tenants()                        # all tenants, oldest first
admin.get_tenant("acme")                    # a Tenant, or None
admin.update_tenant("acme", status="suspended")

finance = admin.create_sub_tenant(tenant_id="acme", name="finance", kind="department")
print(finance.id)                           # "acme::department::finance"
admin.list_sub_tenants("acme")
admin.delete_sub_tenant(finance.id)
```

- A `Tenant` has `id`, `name`, `status` (`active`, `suspended`, or `deleted`), `created_at`, and `metadata`. `update_tenant` replaces `metadata` rather than merging it.
- A sub-tenant's id is derived from the tenant, kind, and name, so creating the same one twice returns the existing one. `kind` is `department`, `user`, `project`, or `custom` (the default).
- The id `__default__` is reserved for memories that have no tenant.

## Roles

```python
admin.assign_role(tenant_id="acme", principal="alice@acme.com", role="admin")
admin.assign_role(tenant_id="acme", sub_tenant_id=finance.id, principal="bob@acme.com", role="member")

admin.has_role(principal="bob@acme.com", tenant_id="acme", sub_tenant_id=finance.id)   # True
admin.has_role(principal="alice@acme.com", tenant_id="acme", role="admin")             # True
admin.list_roles_for("alice@acme.com")
admin.revoke_role(tenant_id="acme", principal="alice@acme.com", role="admin")
```

Roles are free-form strings. A tenant-level binding also counts for every sub-tenant under it. `principal_kind` is `user` by default; `agent`, `run`, and `service` are also accepted. Assigning the same role twice is a no-op.

## Tenant data

Mark each memory with its tenant in `metadata`, and filter on it when you read:

```python
memory.add(
    "Q4 forecast: $4.2M",
    user_id="alice",
    metadata={"tenant_id": "acme", "sub_tenant_id": finance.id},
)

memory.search("revenue forecast", user_id="alice", filters={"tenant_id": "acme"})
memory.get_all(user_id="alice", filters={"tenant_id": "acme", "sub_tenant_id": finance.id})
```

To enforce tenant boundaries in search, install the `TenantIsolationPolicy` from [personalized retrieval](/docs/personalized-retrieval/#roles).

`memory.history(memory_id, tenant_id="acme")` narrows a memory's history to a tenant; rows written before the tenant layer was on are included.

### Isolation modes

`tenant.isolation.mode` is `filter` (the default): all tenants share one vector-store collection and are separated by the `tenant_id` metadata filter, as above. The `collection` mode (one collection per tenant) and `physical` mode (one database per tenant) are accepted by the config, but `add` and `search` do not route to per-tenant collections yet, so treat `filter` as the mode in use. The `deny_cross_tenant_writes` and `require_tenant_id_on_add` settings are reserved and not enforced yet.

## Deleting a tenant

```python
memory.tenant.delete_tenant("acme")              # soft: status "deleted", graph nodes archived
memory.tenant.delete_tenant("acme", hard=True)   # remove the tenant's records
```

Both return counts of what changed. A hard delete removes the tenant's history rows, [context graph](/docs/context-graph/) nodes and edges, sub-tenants, and role bindings, and the registry entry. In `filter` mode it does not remove the tenant's memories from the vector store: delete those with `memory.delete_all(user_id=...)` for each of the tenant's users, or by id.

## Export, import, migrate

```python
memory.export_tenant("acme", "./exports/acme")   # tenant.json, sub_tenants.json, role_bindings.json, history.jsonl, ...
memory.import_tenant("./exports/acme")
memory.migrate_tenant("acme-trial", "acme")      # rewrite tenant ids from one tenant to another
```

Exports cover the registry, the history rows, and, when the context graph is on, its nodes and edges. Vector-store memories are not exported. `migrate_tenant` needs both tenants to exist and leaves the source tenant in place.

## Existing data

Memories and history written before you turned the tenant layer on have no tenant. `memory.backfill_tenant()` stamps those history rows and graph nodes with the default tenant id (or the `default_tenant_id` you pass), and is safe to run again.
