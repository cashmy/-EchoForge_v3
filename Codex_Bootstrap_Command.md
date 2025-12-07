Initialize the EchoForge v3 Development Environment.

Load and follow the instructions in `Activation_Packet_v1.1.md` as the operating contract for this workspace.

Specifically:

1. Load and adopt the behavioral rules in:
   - `protocols/EP/Codex_LLM_Engagement_Protocol_v1.0.md`
   - This defines how you handle ambiguity, drift, decision escalation, allowed modifications, and documentation generation.

2. Load the following core protocols:
   - `protocols/MxVA/MxVA_MachineSpec_v1.0.md`
   - `protocols/MTS/Milestone_Task_Subsystem_v1.1.md`
   - `protocols/ArtfGen/ArtfGen_v02.md`
   - `protocols/ETS/EnaC_TestingSubsystem_v1.0.md`

3. Load the strategic documents under `project-scope/strategic/`:
   - Architecture overview
   - Scope and boundaries
   - Component summaries and component lists
   - Integration boundary statements
   - Pain points and high-level mission

4. Load the tactical specifications under `project-scope/tactical/`:
   - All EF-series specifications (EF01, EF05, EF06, EF07)
   - All INF-series specifications (INF01–INF04)
   - Any addendum or API contract files

5. Load all active milestone documents under `pm/milestones/`.

After loading all materials:

- Do not infer missing behavior when information is incomplete.
- Ask the human coordinator for clarification when ambiguity is present.
- Do not modify artifacts except for updating Status Blocks in milestone files.
- Follow ArtfGen rules when generating new artifacts.
- Honor all governance behaviors defined in the Engagement Protocol.

When ready, respond with:
"EchoForge v3 Development Environment Initialized — Ready."
