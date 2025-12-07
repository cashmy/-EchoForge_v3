# Decision: Timing for Whisper/Transcript UI Surface (2025-12-07)

## Context
- Milestones: MI99 (Edge-Case backlog) and M05 (UI Framework & Layout).
- Recent work externalized EF-02 transcripts to filesystem paths configured via INF-01 and updated EF-06 to store `verbatim_path`/`verbatim_preview`.
- Operators need a quick way inside the EF-07 desktop UI to verify Whisper enablement, model/device selections, and the transcript output root/public URL.
- The UI shell/layout work is scheduled for M05; prior to that the desktop UI has minimal settings infrastructure.

## Options Considered
1. **Implement an immediate standalone settings dialog** in the current UI.
2. **Defer entirely** until after M05, risking that the requirement is forgotten once layout work completes.
3. **Plan the UI surface now but land it with the M05 settings shell**, ensuring it is tracked in both MI99 and M05 scopes.

## Decision
Adopt option **3**: document the requirement immediately and tie it to M05 execution.
- Added MI99-T06 to capture the operator need and maintain traceability from INF-01/EF-02 decisions.
- Added M05-T13 so the Whisper/transcript configuration panel ships alongside the broader settings/navigation work.

## Rationale
- Building ad-hoc UI before the M05 layout/state decisions would create throwaway code and inconsistent UX.
- Waiting until after M05 risks missing the feature entirely; explicit tasks keep it in scope.
- The settings shell introduced in M05 is the natural home for this read-only status view, and implementing it there ensures consistent styling and routing.

## Follow-Ups
1. During M05 planning, include the Whisper configuration panel in design mocks and acceptance criteria.
2. Ensure the panel reads from the same INF-01 settings loader used by EF-02 so values stay in sync.
3. Consider adding a quick path validation or “open folder” helper once the UI surface exists.
4. Update ETS guidance (MI99-T06 follow-up) to cover verifying the settings view on desktop builds.
