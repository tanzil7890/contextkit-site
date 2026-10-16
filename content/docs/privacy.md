---
title: Privacy
description: Detect sensitive data, redact it, and encrypt values before you store them.
---

ContextKit ships privacy building blocks under `outhad_contextkit.memory.privacy`, known as PPMF (privacy-preserving memory firewall): a classifier that finds sensitive spans in text, a redaction helper, and an encryption manager.

!!! note "Call them yourself"
    In {{ library.version }}, setting `ppmf.enabled` in the `Memory` config does not run these tools inside `add` or `search`. Use them directly on text before you pass it to `add`, as shown below.

<!-- diagram: privacy -->

## Find sensitive spans

```python
from outhad_contextkit.memory.privacy import MemorySanitizer, PPMFConfig

config = PPMFConfig(enabled=True)
sanitizer = MemorySanitizer(config)

result = sanitizer.classify("Email me at john@example.com or call 555-123-4567")
print(result.overall_privacy_level)   # PrivacyLevel.CONFIDENTIAL
for span in result.sensitive_spans:
    print(span.span_type, span.text, span.start, span.end)
```

`classify` returns `has_sensitive_content`, `overall_privacy_level` (`public`, `internal`, `confidential`, `sensitive`, or `restricted`), and `sensitive_spans`, each with its `text`, `start` and `end` offsets, `span_type`, `privacy_level`, and `confidence`. `classify_batch` takes a list of texts.

The built-in rules are regular expressions for:

| Type | Matches |
|---|---|
| `pii_email` | Email addresses |
| `pii_phone` | 10-digit phone numbers, such as `555-123-4567` |
| `secret_api_key` | OpenAI (`sk-` + 48 characters), Google (`AIza…`), and AWS (`AKIA…`) keys |

Anything else, such as national ids, card numbers, or health details, needs a rule of your own or the LLM classifier.

## Add your own rules

Rules you pass replace the built-in ones, so add them to the defaults to keep both:

```python
from outhad_contextkit.memory.privacy import (
    MemorySanitizer, PPMFConfig, PrivacyLevel, RedactionMode, SensitiveSpanType, SensitivityRule,
)
from outhad_contextkit.memory.privacy.config import get_default_sensitivity_rules

rules = get_default_sensitivity_rules() + [
    SensitivityRule(
        span_type=SensitiveSpanType.PII_SSN,
        privacy_level=PrivacyLevel.RESTRICTED,
        redaction_mode=RedactionMode.REPLACE,
        patterns=[r"\b\d{3}-\d{2}-\d{4}\b"],
    ),
    SensitivityRule(
        span_type=SensitiveSpanType.FINANCIAL_CREDIT_CARD,
        privacy_level=PrivacyLevel.RESTRICTED,
        redaction_mode=RedactionMode.MASK,
        patterns=[r"\b(?:\d[ -]?){13,16}\b"],
    ),
]
sanitizer = MemorySanitizer(PPMFConfig(enabled=True, sensitivity_rules=rules))
```

For text that regular expressions cannot judge, set `use_llm_classifier=True` and pass an LLM: `MemorySanitizer(config, llm=memory.llm)`. Spans scoring below `classification_threshold` (0.7 by default) are dropped.

## Redact

```python
from outhad_contextkit.memory.privacy import RedactionMode, redact_text

text = "Email me at john@example.com or call 555-123-4567"
spans = sanitizer.classify(text).sensitive_spans

redact_text(text, spans, RedactionMode.REPLACE)  # "Email me at [PII_EMAIL] or call [PII_PHONE]"
redact_text(text, spans, RedactionMode.MASK)     # "Email me at **************** or call ************"
redact_text(text, spans, RedactionMode.HASH)     # "Email me at [HASH:855f96e9] or call [HASH:d36e8308]"
redact_text(text, spans, RedactionMode.REMOVE)   # "Email me at  or call "
```

A typical pattern is to redact before storing:

```python
clean = redact_text(message, sanitizer.classify(message).sensitive_spans, RedactionMode.REPLACE)
memory.add(clean, user_id="alice")
```

`RedactionMode.ENCRYPT` leaves the text unchanged in `redact_text`; to encrypt values, use the encryption manager.

## Encrypt

```python
from outhad_contextkit.memory.privacy import EncryptionAlgorithm, EncryptionManager, PPMFConfig

encryption = EncryptionManager(config=PPMFConfig(
    enabled=True,
    encryption_algorithm=EncryptionAlgorithm.AES_256_GCM,
    encryption_key_path="/secure/contextkit.key",
))

ciphertext, meta = encryption.encrypt("john@example.com")
encryption.decrypt(ciphertext, meta)  # "john@example.com"
```

Supported algorithms are `FERNET` (the default) and `AES_256_GCM`. `NACL` is listed in the enum but fails to initialise in {{ library.version }}.

Keep the key somewhere stable with `encryption_key_path`. Without it, a new key is generated for each `EncryptionManager`, and anything encrypted with an earlier one can no longer be decrypted.
