/task-review TASK-REV-C3E7 --mode=architectural

Review complete. Task moved to tasks/completed/TASK-REV-C3E7/.

Summary
TASK-REV-C3E7 — [I]mplemented

Report: .claude/reviews/TASK-REV-C3E7-review-report.md
Score: 75/100 (pre-merge gate inventory thin; 6 blockers for /system-arch now addressed)
What was done
Phase 1a — D90D verification: 7/8 findings resolved by prior FEAT-FVDA v2.2 commit. F4 (coverage figure) auto-resolved by 17 low-risk citation edits across 5 docs.

Phases 2–4 — Lessons gap analysis: 14 parity gaps surfaced from specialist-agent LES1 (6 BLOCKERS, 5 MEDIUM, 3 LOW) with full dispositions across 6 parity surfaces, 9 evidence pointers, and 22 checklist items.

9 surgical edits applied to primary docs (all anchor v2.2 preserved, purely additive):

forge-build-plan.md: 6 operations covering G1/G3/G4/G6/G7/G8/G10/G11/G12/G13/G14 — new provisioning prereq wording, ADR commit-annotation convention, [providers] extras rule, .env.example + deferred Dockerfile rows, new "LES1 Parity Gates" subsection (CMDW/PORT/ARFS/canonical-freeze), orphan-container + CLI-redaction risks
forge-pipeline-orchestrator-refresh.md: 3 operations covering G2/G5/G9 — reply-subject convention paragraph, provider-at-factory rule, fire-and-forget tool annotations + new forge_cancel manifest entry
fleet-master-index.md: no gap edits required (structurally aligned)
Files changed
6 modified, 2 deleted (D90D F5 stale tasks), 2 created (review report + completed task folder). Zero new docs/ files created.

Forge ideas docs are now ready for /system-arch consumption with specialist-agent LES1 parity gates baked in as pre-merge requirements.



/task-work /Users/richardwoollcott/Projects/appmilla_github/forge/tasks/backlog/project-scaffold/TASK-FORGE-SCAFFOLD-hand-scaffold-from-orchestrator-template.md


Task work complete. Final report:

✅ TASK-FORGE-SCAFFOLD — Complete (pending push approval)
Workflow: Minimal-intensity (mechanical file rendering, no design decisions per task file).

Files rendered
Source template	Destination	Notes
pyproject.toml.template	pyproject.toml	name→forge, description→Forge's, author added, [build-system] + [tool.setuptools.packages.find] added for editable-install
AGENTS.md.template	AGENTS.md	verbatim (R2A1 section at line 14)
agent.py.template	src/forge/agent.py	verbatim, env-var factory resolution intact
langgraph.json.template	langgraph.json	{{ProjectName}} → forge
orchestrator-config.yaml.template	orchestrator-config.yaml	verbatim (bonus 5th template)
(new)	src/forge/__init__.py	minimal package marker for src-layout
Acceptance criteria
AC	Status
pyproject.toml [providers] extras (langchain-openai, langchain-google-genai; langchain-anthropic in base)	✅
AGENTS.md R2A1 section	✅ line 14
src/forge/agent.py syntactically valid Python	✅ ast.parse OK
langgraph.json → ./src/forge/agent.py:agent	✅
No {{Placeholder}} strings remain	✅ grep clean
pip install -e ".[providers]" succeeds	✅ forge-0.1.0 installed, editable
.guardkit/context-manifest.yaml unchanged	✅ mtime still Apr 13 18:07
Anchor commit	✅ 5cf0da0
command_history.md entry	✅ follow-up commit e5ef119
Anchor commit pushed	⚠️ Awaiting your approval
State transitions
Task: backlog/project-scaffold/ → in_review/project-scaffold/
Branch main is ahead of origin/main by 3 commits (5cf0da0, e5ef119, and pre-existing fea6d87).
⚠️ Action needed: push anchor commit
The acceptance criterion requires the anchor pushed to the Forge repo. Per safety rules I did not push without explicit authorization. Want me to run git push origin main now? That will push both commits plus the pre-existing fea6d87.

graphiti.yaml
yes
Bash Push anchor commit to origin/main
IN
git push origin main 2>&1

OUT
To https://github.com/guardkit/forge.git
   39e5033..e5ef119  main -> main
Pushed. Anchor commit 5cf0da0 is now on origin/main (push range 39e5033..e5ef119 — carried the pre-existing fea6d87 along with my two scaffold commits).

TASK-FORGE-SCAFFOLD is complete. All 10 acceptance criteria met. Forge repo is now unblocked for /system-arch Step 1 of forge-build-plan.md (pending the NATS/specialist-agent prerequisites noted in the task).



system-arch \
  --context forge/docs/research/forge-pipeline-architecture.md \
  --context forge/docs/research/forge-build-plan-alignment-review.md \
  --context forge/docs/research/ideas/forge-pipeline-orchestrator-refresh.md \
  --context forge/docs/research/pipeline-orchestrator-conversation-starter.md \
  --context forge/docs/research/pipeline-orchestrator-motivation.md \
  --context forge/docs/research/ideas/fleet-master-index.md \
  --context specialist-agent/docs/research/ideas/architect-agent-vision.md \
  --context nats-core/docs/design/specs/nats-core-system-spec.md \
  --context nats-core/docs/design/contracts/agent-manifest-contract.md

All seeding complete. Final status:

30/30 ADRs ingested
685 total episodes in Graphiti (was 585 → +100 episodes added)
2 warnings for ADR-012 + ADR-022 ("Missing required section: Status") — non-blocking, episodes still ingested; the parser expects ## Status as a section heading rather than the - **Status:** Accepted inline-bullet format I used. Follow-up: I can re-format those two files to use the heading-style Status section if you want the warnings cleared. Not urgent.
/system-arch Session Complete
Artefacts on disk (docs/architecture/)
ARCHITECTURE.md — index + summary, module map, decision index
domain-model.md — entities, relationships, ownership rules
system-context.md — C4 Level 1 Mermaid
container.md — C4 Level 2 Mermaid
assumptions.yaml — 26 assumptions across 6 categories
decisions/ — 30 ADRs (ADR-ARCH-001 through ADR-ARCH-030)
Graphiti seeded (project_id=forge)
Group	Episodes added
architecture_decisions	30 (one per ADR)
project_architecture (via full_doc)	~70 chunks across 4 architecture docs
Total added	100
Downstream commands (/system-design, /system-plan, /feature-spec) will retrieve this context at startup via the same Graphiti connection.

Headline architectural position (Forge, one sentence)
"A DeepAgents-native reasoning orchestrator whose behaviour is entirely emergent from (a) live fleet capabilities discovered via AgentManifests, (b) retrieved priors from Rich's calibration corpus in Graphiti, and (c) constitutional safety rules in forge.yaml — with zero pre-coded pipeline stages, gate thresholds, or role-specific dispatch."

This is what 9 revisions of Category-level pushback produced — and the result is materially different from a conventional state-machine orchestrator. The agent harness earns its keep.

Suggested next steps
Review — open ARCHITECTURE.md and spot-check the module map + ADR index against the session's conclusions. The docs are in your working tree now.
Next command — /system-design "Forge" (Phase 2 of the upstream pipeline) to produce detailed tool contracts, NATS payload schemas beyond what nats-core already has, and the forge.yaml configuration schema.
Optional polish — if the ADR-012/ADR-022 Status-section warnings bother you, reformat those two ADRs to use heading style (## Status) and re-seed with guardkit graphiti add-context … --force. Cosmetic only.
Follow-on work (not for this session) — ADR-ARCH-025 mentioned a @forge_tool base decorator to enforce the "tools never raise" policy; that becomes a design point in /system-design.


/task-create please create a reivew task to implement these findings:
# TASK-REV-ARCH-POLISH — /system-arch artefact polish before /system-design

**Origin:** External review of forge/docs/architecture/ completed 2026-04-19.
**Scope:** Paperwork + two verifications. No structural changes to ADRs.
**Estimated effort:** 30-45 minutes

## In scope

1. **ARCHITECTURE.md §13 Decision Index** — add ADR-031 row, bump header
   count from 30 to 31. (Already tracked as TASK-DOC-B2A4 — fold in or
   merge.)

2. **ADR-012 and ADR-022 Status section format** — reformat from inline
   bullet `- **Status:** Accepted` to heading style `## Status\n\nAccepted`
   to match the parser expectation noted in command-history.md. Re-run
   `guardkit graphiti add-context --force` for these two after editing.

3. **ARCHITECTURE.md §3 module count** — recount the module list; reconcile
   "15 modules" header with the prose (current count appears to be 16+
   depending on how guardkit_* is grouped). Either fix the number or
   restructure the groupings so the count is accurate.

4. **ADR-012 (No MCP interface) content review** — given ADR-031 added
   async subagent supervisor tools (`list_async_tasks` etc.), confirm
   ADR-012's reasoning for rejecting MCP still holds and is not subtly
   undermined by the async-subagent observability surface. One read;
   either append a one-line note confirming, or flag for discussion.

5. **Spike: DeepAgents 0.5.3 primitives (ASSUM-008 + ASSUM-009)** —
   before /system-design, run a 1-2 hour verification:
   - Confirm DeepAgents permissions system actually refuses writes
     outside the allow_write allowlist (not just documented behaviour).
   - Confirm LangGraph `interrupt()` survives external resume with typed
     Pydantic payload round-trip (write a minimal two-file repro).
   - Capture findings in docs/research/ideas/deepagents-053-verification.md
   - If either fails, ADR-021 and ADR-023 need a revision before /system-design.

## Out of scope

- Any reopening of ADR-016, ADR-019, ADR-023 thesis. These are settled.
- Restructuring the module map or C4 diagrams.
- Compressing ADR-031 from 135 → 60-80 lines (deferred per TASK-REV-C7D1).
- Full ADR-by-ADR read of the 18 ADRs not covered in external review
  (003, 004, 009, 013, 014, 017, 018, 024, 027-030). Optional follow-up
  if confidence wanted before /system-plan.

## Acceptance criteria

- [ ] ARCHITECTURE.md §13 lists 31 ADRs
- [ ] ADR-012 and ADR-022 reformatted; Graphiti re-ingestion clean
- [ ] ARCHITECTURE.md §3 module count matches the prose list
- [ ] ADR-012 reviewed post-ADR-031; one-line note added or flag raised
- [ ] deepagents-053-verification.md committed; findings summarised
- [ ] No new ADRs created by this task (if verification fails, separate
      revision task spawned)

## Not doing / decisions captured

- Residual session drift: none found requiring ADR-level revision.
- Course-correction arc: documented in ARCHITECTURE.md + ADR Context
  sections; no further archaeology needed.

did you create the task?
Yes — task created at tasks/backlog/TASK-REV-A7D3/TASK-REV-A7D3-system-arch-artefact-polish.md.

/task-review TASK-REV-A7D3

