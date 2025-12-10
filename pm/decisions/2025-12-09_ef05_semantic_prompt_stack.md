# Decision: EF-05 Semantic Prompt & Model Stack (2025-12-09)

## Context
- Milestone: M02 — Processing Pipeline
- Trigger: `backend/app/jobs/semantic_worker.py` now routes summaries/classifications through INF-04 with structured prompts and retry logic; governance needs a record of those choices.
- Signals: Contract work in `project_scope/tactical/EF05_GptEntrySemanticService_Spec_v1.0.md` plus ETS guidance assumes the finalized prompt text, mode resolution, and confidence handling documented here.

## Decision
1. **Operation profiles** — Map `summarize_v1` → `echo_summary_v1` and `classify_v1` → `echo_classify_v1` (both via INF-04). Default operation stays `summarize_v1`; operators can override via job payload when running classification-only reruns.
2. **Mode selection** — Accept `auto|preview|deep` from payloads; `auto` resolves to `deep` when normalized text ≤ `summary.max_deep_chars` (default 6 k) and `preview` otherwise. Preview slices use `summary.max_preview_chars` (default 400) to keep prompt tokens bounded.
3. **Prompt content** — System prompts are purpose-built: summarization demands a 2–5 sentence summary + ≤120 char display title, while classification stresses concise `type_label`/`domain_label`. User-provided hints (base + `classification_hint`) append to the prompt when present.
4. **Retry/backoff + error taxonomy** — Wrap INF-04 `SemanticGatewayError` codes with exponential backoff (250 ms base, doubling each attempt) up to `summary.max_retry_attempts` (default 2). Retryable errors: `llm_timeout`, `llm_rate_limited`, `provider_unavailable`; others are terminal and mark EF-06 `pipeline_status='semantics_failed'` with capture metadata of the error code.
5. **Persistence & telemetry** — Successful runs update EF-06 summary/title/tags/classification fields, log `semantic_completed` capture events with timing, mode, attempts, and confidence map, and patch `capture_metadata.semantics`. Missing response fields fall back to prompt snippets or existing EF-06 values to keep UI content stable.

## Rationale
- Operation/profile mapping mirrors the EF-05 contract, ensuring ETS, API clients, and INF-04 stay in sync without additional branching.
- Automatic mode selection provides deterministic token budgets while still delivering deep summaries for shorter entries.
- Explicit system prompts and hint composition avoid prompt drift and give operators a clear override mechanism for tricky classification runs.
- Retry/backoff policy protects against transient gateway hiccups without hiding terminal prompt/schema issues, satisfying MG06 governance expectations.
- Rich telemetry (capture events + metadata) lets operators trace every semantic attempt and ties into the broader structured logging effort from M02-T11.

## Follow-Ups
1. Document the prompt text and override knobs in `tests/README.md`’s semantic rehearsal section for operator awareness.
2. When new semantic operations (e.g., tag-only) are introduced, append an addendum capturing their prompts and persistence rules.
3. Reference this memo when updating the M02-T14 status block to `done`.
