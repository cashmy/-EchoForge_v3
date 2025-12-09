# ETS Pipeline Fixture Kit

Deterministic fixtures live in this directory so ETS dry runs can be repeated without hunting for large media
assets. The fixture generator (`python scripts/setup_ets_fixtures.py`) populates the following files:

| Subdir | Filename | Purpose | Referenced Scenarios |
| --- | --- | --- | --- |
| `audio/` | `20250907115516.wav` | 1.5 s sine-wave clip used for scenario **A1** (audio happy path) | A1, R1, I1 |
| `audio/` | `20250908132309.wav` | Alternate tone used for **retry** validations | R1 |
| `documents/` | `doc_pipeline_reference.txt` | Text-heavy document for extraction + normalization assertions | D1 |
| `documents/` | `doc_ocr_simulation.txt` | Uppercase/OCR-style text exercising normalization rules | D1 |
| `payloads/` | `normalized_snapshot.json` | Canonical normalization output for semantic-only reruns | S1 |

## Placement Instructions

1. Ensure watch roots exist:
   ```powershell
   python scripts/setup_watch_roots.py
   ```
2. Generate and copy fixtures into the watch roots:
   ```powershell
   python scripts/setup_ets_fixtures.py --copy-to-watch-roots
   ```
   - Audio fixtures land in `watch_roots/audio/incoming/`.
   - Document fixtures land in `watch_roots/documents/incoming/`.
3. For semantic-only reruns (scenario **S1**), keep `payloads/normalized_snapshot.json` in place; tests or
   orchestration scripts import it when constructing EF-05 payloads.
4. Re-run the setup script whenever fixtures are modified. Existing files are overwritten deterministically so
   hashing/verification remains stable.

Keep these fixtures under source control so MG06 governance can audit the exact media/text inputs used during the
pipeline ETS rehearsals.
