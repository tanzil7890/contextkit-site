from outhad_contextkit import Memory

# Keep memories on disk in ./memory, so they survive a restart.
memory = Memory.from_config({
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
})

memory.add("I'm allergic to peanuts", user_id="alice")

hits = memory.search("What should I avoid eating?", user_id="alice", limit=3)
for hit in hits["results"]:
    print(hit["memory"])  # Allergic to peanuts
