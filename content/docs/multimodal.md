---
title: Multimodal
description: Store what is in an image as searchable memories.
---

With a vision-capable LLM, ContextKit can read images in the messages you add. Each image is described by the LLM, and the description goes through fact extraction like any other message, so you can later search for what the picture showed.

<!-- diagram: multimodal -->

## Turn on vision

```python
from outhad_contextkit import Memory

memory = Memory.from_config({
    "llm": {
        "provider": "openai",
        "config": {"model": "gpt-4o", "enable_vision": True, "vision_details": "auto"},
    },
    "vector_store": {"provider": "qdrant", "config": {"path": "./memory", "on_disk": True}},
})
```

`vision_details` is passed to the model as the image detail level: `low`, `high`, or `auto`.

## Add an image

Put the image in a message as an `image_url` content part. The URL can be a public link or a `data:` URL with base64 data:

```python
memory.add(
    [
        {"role": "user", "content": "This is the new packaging for the spring line."},
        {"role": "user", "content": {"type": "image_url", "image_url": {"url": "https://example.com/packaging.jpg"}}},
    ],
    user_id="design-team",
)

hits = memory.search("what colour is the spring packaging?", user_id="design-team")
```

A message whose `content` is a list of parts is described as a whole, so you can send text and several images in one message.

What gets stored is text: the facts the LLM drew from its description of the image. The image itself is not kept, so store its URL in `metadata` if you need to show it again.

## Image and audio embeddings

The `multimodal` extra installs the libraries for CLIP (images) and CLAP (audio) embeddings, which place images and audio in the same space as text. You can use them directly from `outhad_contextkit.memory.temporal`; they are not connected to search yet, so the `multimodal_results` of [fused search](/docs/graph-memory/#fused-search) stays empty. They are large downloads, so install them only if you need them:

```bash
pip install "{{ library.dist }}[multimodal]"
```
