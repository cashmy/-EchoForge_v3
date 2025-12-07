# Decision: EF-06 Entry Model Boundary Strategy (2025-12-07)

## Context
- Milestone: M01 — Capture & Ingress (tasks M01-T05/T06 covering EF-01 ↔ EF-06 integration).
- Prompt raised by reviewer: *"Your implementation methodology for the models seems overly complex. It appears that you have a dataclass per action/request. Explain the pros and cons when compared to a more traditional method of a model class with methods for the actions?"*
- Codex response (2025-12-07) outlined tradeoffs between (a) separate dataclasses for requests/records/fingerprint snapshots and (b) a single rich model class. The decision below records that response as the approved approach for EchoForge v3.

## Options Considered
1. **Spec-driven dataclasses per EF-06 boundary contract** (current implementation): `Entry`, `EntryCreateRequest`, `EntryFingerprintSnapshot`, etc., each immutable and mapped directly to spec payloads.
2. **Single "model" class with behavior** (ActiveRecord-style): one Entry object exposing `.create()`, `.save()`, `.fingerprint_status()`, etc., collapsing EF-01 DTOs into methods on a persistence-aware class.

## Decision
Continue using distinct dataclasses for each EF-06 boundary interaction (creation payload, stored record, fingerprint snapshot) instead of a single mutable model with behavior. Treat these dataclasses as the canonical DTOs for EF-01 ↔ EF-06 traffic until a future milestone explicitly revisits the abstraction.

## Rationale
- **Spec fidelity:** The EF06 spec differentiates between inbound payloads, stored records, and fingerprint lookups. Dataclasses keep these shapes explicit and prevent accidental coupling to future ORM details.
- **Testability & immutability:** EF-01 unit tests can assert against plain value objects without standing up persistence layers or stubbing rich model methods. This keeps watcher/idempotency tests simple and deterministic.
- **Boundary decoupling:** EF-01 remains agnostic to EF-06 implementation details. When EF-06 migrates to a real repository, mapping dataclasses to ORM models can happen inside the gateway without touching EF-01.
- **Risk containment:** A single behavior-heavy model would blur EF-01/EF-06 responsibilities, incentivizing direct state mutations and making later refactors harder if the ORM or storage strategy changes.

## Cons Acknowledged
- Additional boilerplate is required (multiple dataclasses, gateway helpers, conversions when persistence arrives).
- Contributors familiar with ActiveRecord-style APIs must learn the DTO-driven pattern.
- Behavior lives in gateway functions instead of hanging off a single "Entry" object, so the surface area feels wider.

## Follow-Ups
1. Keep the dataclass approach documented in EF-06 tactical specs/addenda so future contributors understand the rationale.
2. When the real database layer lands, add mapping helpers (dataclass ↔ ORM) rather than replacing the DTO boundary outright; revisit if that indirection becomes burdensome.
3. Reference this decision from relevant milestone/task notes (e.g., M01-T06) to signal that the complexity concern was reviewed and approved.

## Notes for Reviewers
- This decision captures the approved answer to the reviewer prompt and should be cited before re-opening the topic.
- Any proposal to move to a rich model class must demonstrate equal or better spec alignment and test ergonomics compared to the current DTO pattern.
