---
title: Providers
description: The LLMs, embedders, vector stores, and graph stores ContextKit works with, and how to configure each.
---

Each component is configured the same way: a `provider` name and a `config` dictionary.

```python
memory = Memory.from_config({
    "llm": {"provider": "...", "config": {...}},
    "embedder": {"provider": "...", "config": {...}},
    "vector_store": {"provider": "...", "config": {...}},
})
```

## LLMs

The LLM extracts facts from messages and decides how to update existing memories. It needs to follow instructions and return JSON reliably; small, fast models work well.

| `provider` | Key, from the config's `api_key` or the environment | Install |
|---|---|---|
| `openai` | `OPENAI_API_KEY` (or `OPENROUTER_API_KEY` to go through OpenRouter) | included |
| `openai_structured` | `OPENAI_API_KEY`; uses OpenAI structured outputs | included |
| `azure_openai`, `azure_openai_structured` | `azure_kwargs` or `LLM_AZURE_OPENAI_API_KEY`, `LLM_AZURE_DEPLOYMENT`, `LLM_AZURE_ENDPOINT`, `LLM_AZURE_API_VERSION` | included |
| `anthropic` | `ANTHROPIC_API_KEY` (see the note below) | `pip install anthropic` |
| `gemini` | `GOOGLE_API_KEY` | `[llms]` |
| `groq` | `GROQ_API_KEY` | `[llms]` |
| `together` | `TOGETHER_API_KEY` | `[llms]` |
| `deepseek` | `DEEPSEEK_API_KEY` | included |
| `xai` | `XAI_API_KEY` | included |
| `ollama` | none; `ollama_base_url` (default `http://localhost:11434`) | `[llms]` |
| `lmstudio` | none; `lmstudio_base_url` | included |
| `vllm` | `VLLM_API_KEY`; `vllm_base_url` or `VLLM_BASE_URL` | included |
| `litellm` | Whatever the LiteLLM model needs | `[llms]` |
| `aws_bedrock` | AWS credentials from the environment | `[extras]` |
| `sarvam` | `SARVAM_API_KEY` | included |
| `langchain` | Pass a LangChain chat model object as `model` | `pip install langchain` |

Common `config` keys: `model`, `temperature` (0.1), `max_tokens` (2000), `top_p` (0.1), and `api_key`. Always set `model`: some providers' built-in defaults are large or retired models.

```python
memory = Memory.from_config({
    "llm": {"provider": "groq", "config": {"model": "llama-3.3-70b-versatile", "temperature": 0.1}},
})
```

!!! warning "Anthropic models in {{ library.version }}"
    The `anthropic` provider in 0.1.2 and earlier sends both `temperature` and `top_p` with every request, and its default model has been retired. Current Claude models reject requests that set both, so the provider fails with any Claude model available today. A fix is on the main branch for the next release; until then, use another provider for fact extraction.

## Embedders

The embedder turns memories and queries into vectors. Its output size must match the vector store's `embedding_model_dims`; see [matching the embedding size](/docs/configuration/#match-the-embedding-size).

| `provider` | Default model | Size | Install |
|---|---|---|---|
| `openai` | `text-embedding-3-small` | 1536 | included |
| `azure_openai` | your deployment; keys in `azure_kwargs` or `EMBEDDING_AZURE_*` | | included |
| `ollama` | `nomic-embed-text` | set `embedding_dims` to the model's size (768 for `nomic-embed-text`) | `[llms]` |
| `huggingface` | `multi-qa-MiniLM-L6-cos-v1` (sentence-transformers) | read from the model | `[extras]` |
| `gemini` | `models/text-embedding-004` | 768 | `[llms]` |
| `vertexai` | `text-embedding-004` | | `[llms]` |
| `together` | | | `[llms]` |
| `lmstudio` | | | included |
| `aws_bedrock` | | | `[extras]` |
| `langchain` | Pass a LangChain embeddings object as `model` | | `pip install langchain` |

## Vector stores

| `provider` | Typical `config` | Install |
|---|---|---|
| `qdrant` (default) | `path` + `on_disk: True` locally, `host` + `port` for a server, or `url` + `api_key` for Qdrant Cloud | included |
| `pgvector` | `dbname`, `user`, `password`, `host`, `port` | `pip install psycopg2-binary` |
| `chroma` | `path`, or `host` + `port` | `[vector_stores]` |
| `pinecone` | `api_key`, `serverless_config` or `pod_config` | `[vector_stores]` |
| `weaviate` | `cluster_url`, `auth_client_secret` | `[vector_stores]` |
| `faiss` | `path` | `[vector_stores]` |
| `milvus` | `url`, `token` | `pip install pymilvus` |
| `mongodb` | `mongo_uri`, `db_name` | `[vector_stores]` |
| `redis` | `redis_url` | `pip install redis redisvl` |
| `elasticsearch` | `host`, `port`, or `cloud_id` + `api_key` | `[extras]` |
| `opensearch` | `host`, `port`, `http_auth` | `[extras]` |
| `supabase` | `connection_string` | `[vector_stores]` |
| `upstash_vector` | `url`, `token` | `[vector_stores]` |
| `azure_ai_search` | `service_name`, `api_key` | `[vector_stores]` |
| `vertex_ai_vector_search` | `project_id`, `endpoint_id`, `index_id`, `deployment_index_id` | `[llms]` |
| `langchain` | Pass a LangChain vector store as `client` | `pip install langchain` |

Every vector store also takes `collection_name` (default `outhad_contextkit`) and `embedding_model_dims` (default 1536). The [configuration reference](/docs/reference/config/#vector-store) and each provider's config class have the full list.

```python
memory = Memory.from_config({
    "vector_store": {
        "provider": "pgvector",
        "config": {"dbname": "app", "user": "app", "password": "...", "host": "localhost", "port": 5432},
    },
})
```

## Graph stores

| `provider` | `config` | Install |
|---|---|---|
| `neo4j` | `url`, `username`, `password`, optional `database` | `[graph]` |
| `memgraph` | `url`, `username`, `password` | `[extras]` |
| `neptune` | `endpoint="neptune-graph://<graph-id>"` | `[graph]` |

See [Graph memory](/docs/graph-memory/).

## Run everything locally

Ollama can serve both the LLM and the embedder, so memories never leave your machine:

```bash
pip install "{{ library.dist }}[llms]"
ollama pull llama3.1:8b
ollama pull nomic-embed-text
```

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "llm": {"provider": "ollama", "config": {"model": "llama3.1:8b", "temperature": 0}},
    "embedder": {"provider": "ollama", "config": {"model": "nomic-embed-text", "embedding_dims": 768}},
    "vector_store": {
        "provider": "qdrant",
        "config": {"path": "./memory", "on_disk": True, "embedding_model_dims": 768},
    },
})
```
