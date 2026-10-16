---
title: Installation
description: Requirements, optional extras, environment variables, and where ContextKit keeps its files.
---

## Requirements

- Python 3.9 or newer.
- An API key for an LLM and an embedder. With the defaults that is one OpenAI key in `OPENAI_API_KEY`. [Ollama](/docs/providers/#run-everything-locally) runs both locally with no key.
- Optionally, a graph database (Neo4j, Memgraph, or AWS Neptune) for [graph memory](/docs/graph-memory/).

## Install

```bash
{{ library.install }}
```

The base install includes the Qdrant client, the OpenAI SDK, and the encryption libraries used by the privacy tools. Everything else is an extra:

| Extra | Adds | For |
|---|---|---|
| `graph` | `neo4j`, `langchain-neo4j`, `langchain-aws`, `rank-bm25` | [Graph memory](/docs/graph-memory/) on Neo4j or Neptune |
| `vector_stores` | Chroma, Weaviate, Pinecone, FAISS, Upstash, Azure AI Search, MongoDB, pgvector (`vecs`), Baidu | [Vector stores](/docs/providers/#vector-stores) other than Qdrant |
| `llms` | Groq, Together, LiteLLM, Ollama, Vertex AI, Gemini | [LLM providers](/docs/providers/#llms) other than OpenAI |
| `extras` | `boto3`, Elasticsearch, OpenSearch, `sentence-transformers`, `langchain-memgraph` | Bedrock, Elasticsearch, OpenSearch, Hugging Face, Memgraph |
| `multimodal` | `torch`, `transformers`, `laion-clap` | Image and audio embeddings for [multimodal](/docs/multimodal/) graph memory |
| `postgres` | `psycopg2-binary` | A Postgres `history_db_path`, and the [state store](/docs/configuration/#state-store) (0.1.4) |

Install one or more with brackets:

```bash
pip install "{{ library.dist }}[graph,llms]"
```

A few features need packages that are not part of any extra:

```bash
pip install tiktoken        # token chunking
pip install networkx scipy  # the context graph; scipy for PageRank retrieval
```

## Environment variables

| Variable | Used for |
|---|---|
| `OPENAI_API_KEY` | The default LLM and embedder. |
| `OPENAI_BASE_URL` | Send OpenAI calls to a compatible endpoint. |
| `OPENROUTER_API_KEY` | When set, the `openai` LLM provider calls OpenRouter instead of OpenAI. |
| `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY`, `TOGETHER_API_KEY`, `DEEPSEEK_API_KEY`, `XAI_API_KEY` | The matching LLM providers, when no `api_key` is set in the config. |
| `OUTHAD_CONTEXTKIT_DIR` | Where ContextKit keeps its files. Defaults to `~/.outhad_contextkit`. |
| `OUTHAD_CONTEXTKIT_TELEMETRY` | Set to `False` to turn off anonymous usage telemetry. |

## Where files live

ContextKit creates `~/.outhad_contextkit` (or `$OUTHAD_CONTEXTKIT_DIR`) on import. It holds:

| File | What it is |
|---|---|
| `history.db` | SQLite change history for every memory. Move it with `history_db_path`. |
| `config.json` | A random install id used for telemetry. |
| `migrations_qdrant/` | A small local Qdrant collection that holds the install id. |

Your memories live in whatever vector store you configure. The default is a local Qdrant database at `/tmp/qdrant` that is cleared every time it starts, so set a `path` and `on_disk: True` as in the [Quickstart](/docs/quickstart/#2-create-a-memory), or point at a Qdrant server.

## Telemetry

ContextKit sends anonymous usage events to PostHog: which operation ran (`add`, `search`, …), the Python version and OS, the package version, the class names of the configured providers, hashed scoping ids, and the memory id for `get`, `update`, `delete`, and `history` calls. The content of messages and memories is not sent.

Turn it off with:

```bash
export OUTHAD_CONTEXTKIT_TELEMETRY=False
```

Any value other than `true`, `1`, or `yes` turns it off.

## Run a graph database

[Graph memory](/docs/graph-memory/) needs Neo4j, Memgraph, or Neptune. For local development, Neo4j in Docker is enough:

```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password neo4j:5
```

## Upgrade

```bash
pip install --upgrade {{ library.dist }}
```

What changed in each release is in the [changelog](/changelog/).
