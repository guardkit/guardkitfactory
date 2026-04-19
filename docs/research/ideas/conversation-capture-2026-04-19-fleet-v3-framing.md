# Conversation Capture — 19 April 2026

> **Participants:** Rich Woollcott + Claude (Opus 4.7 via claude.ai)
> **Date:** 19 April 2026
> **Duration:** ~3 hours across multiple turns
> **Setting:** Project knowledge loaded — Forge `/system-arch` just completed, Study Tutor `/system-arch` just completed, Jarvis build planned for tomorrow
> **Outcome:** Fleet v3 framing, seven documents produced, architecture locked in at 1000-metre altitude before low-cost-of-rework window closed

This document captures the **full richness** of the conversation — explored, decided, deferred, rejected — so future-Rich (and future-Claude) can reconstruct the reasoning without re-doing it.

---

## 1. How the Conversation Started

Rich asked me to review the Jarvis repo docs in preparation for tomorrow's `/system-arch` run, check alignment with the Forge architecture that just shipped (30 ADRs, ARCHITECTURE.md, fleet-master-index v2), and set everything up for the build.

I used the Filesystem extension to read:
- Jarvis: README, vision, conversation-starter, GPA, NemoClaw, Reachy-integration
- Forge: full ARCHITECTURE.md, anchor v2.2, fleet-master-index v2, key ADRs (ARCH-015, 016, 019, 020)
- Graphiti: connection confirmed, but searches on Jarvis/Forge content returned empty (noted — may need reseeding investigation, out of scope for this session)

I identified six concrete mismatches between Jarvis's March 2026 vision and Forge's April 2026 reality:

1. Fleet count (6 specialists in vision vs. consolidated specialist-agent + Forge in reality)
2. Build trigger pattern (ADR-SP-014 Pattern A wasn't in Jarvis's conversation-starter)
3. Capability-driven dispatch (ADR-ARCH-015/016 needed in Jarvis too)
4. Singular topic convention (ADR-SP-016)
5. Driver 590 status (NemoClaw assessment needed update)
6. Build sequence (Jarvis repositioned relative to specialist-agent Phase 3 + Forge)

I proposed three tasks: update vision, update conversation-starter, create context-manifest.

---

## 2. The NemoClaw / DeepAgents Clarification

Rich asked for clarity: *"we have now moved away from nemoclaw? And will use LangChain DeepAgents SDK as per the other agents"*

I confirmed both using existing docs:
- D6 (March 2026): NemoClaw rejected — gateway infrastructure bugs, k3s issues on GB10, NIM silently falling over to cloud, alpha software
- D1 (fleet-wide): LangChain DeepAgents SDK committed, reinforced by Forge's ADR-ARCH-020 adopting the 0.5.3 built-ins
- NemoClaw revisit conditions: GitHub issues #341/#415/#878 resolved, NIM local inference actually working, community Docker image appearing

The Jarvis vision's NemoClaw positioning doesn't need to change — it stays rejected, potentially becoming a *sandbox backend* or *fleet participant* later if it matures.

---

## 3. The DeepAgents 0.5.3 Investigation

Rich flagged that he'd specified the latest DeepAgents SDK for Forge and Study Tutor and asked me to check what new features (async subagents, middleware) might affect the architecture.

I fetched:
- GitHub README (showed 0.4.2 as surface release tag — I initially mis-read this as "stale")
- PyPI stats (showed 0.5.1 live)
- DeepAgents docs overview (confirmed 0.5.x features, listed "Async subagents" as a new dedicated capability page)
- Async subagents dedicated page (full docs for `AsyncSubAgent`, `AsyncSubAgentMiddleware`, five supervisor tools, transport options)

Rich then pointed me to the actual 0.5.3 release notes page, which confirmed 0.5.3 released 15 April 2026. Forge's ADR-ARCH-020 pin of `>=0.5.3, <0.6` was correct; the earlier uncertainty was my misreading.

**Key discovery:** Async subagents are a preview feature in 0.5.x that offer:
- `start_async_task` / `check_async_task` / `update_async_task` / `cancel_async_task` / `list_async_tasks`
- Non-blocking parallelism (supervisor continues while subagent works)
- Mid-flight steering (interrupt-multitask pattern)
- Cancellation capability
- Stateful threads per subagent
- ASGI (co-deployed) or HTTP (remote) transport

**My initial framing of how this affected the three agents:**
- **Forge:** `autobuild_runner` should become async (long-running, supervisor benefits from not blocking); `build_plan_composer` stays sync (bounded, output gates next stage). This led to ADR-ARCH-031.
- **Study Tutor:** Conversational is sync-by-default, but async fits background paper-generation and Memory Store fits cross-session recall. Tactical additions, no `/system-arch` re-run needed.
- **Jarvis:** This was where it got interesting — I proposed async subagents enable the "persistent assistant" feel rather than request-response.

---

## 4. The Framing Inversion (The Big Moment)

I proposed: **"What if Jarvis is the GPA, and the GPA can dispatch?"**

Rather than "Jarvis is a thin router with a GPA as one of many specialists to dispatch to," invert it: **Jarvis IS a General Purpose DeepAgent. It has tools. Some tools are 'call a specialist via NATS.' Some are 'launch an async subagent for background research.' Some are 'publish a BuildQueuedPayload to wake Forge up.' Some are just 'answer from what you know.'**

The consequences I articulated:
- Routing becomes tool selection (DeepAgents is already good at this)
- Async subagents become first-class (model routing as a reasoning decision)
- Same pattern as Forge's ADR-ARCH-015 (capability-driven dispatch)
- The Iron Man aesthetic comes for free (persistent presence, proactive nudges, background research)
- Jarvis the repo stays small (~800 lines of Python, mostly tools + prompts + skills)

**Rich's response:** *"thanks love this framing and its where my internal thinking has been going 'I'm Tony Stark building a v1 mini-jarvis'"*

This was the 1000-metre decision that collapsed the hardest architectural tension.

---

## 5. Rich's Questions — Model Delegation and Selective Ambience

Rich responded with two architecturally-significant elaborations:

**Q1 — Model routing as multi-model delegation:**
> *"I am wondering if Jarvis thinks about the problem and delegates to subagents using different models e.g. for a problem requiring deep reasoning it might choose to use gemini 3.1 pro, for really long work gpt5.4 and for something else opus 4.7? other jobs it might delegate to the expanding fleet of registered specialist agents."*

This was Rich independently arriving at *model routing as a reasoning decision* — which is the crystallised insight that becomes the D43 decision and the talk's spine.

**Q2 — NemoClaw integration:**
> *"selectively ambient seems like a good middle ground and stops trying to re-invent openclaw/nemoclaw (although there might be an opportunity to consider jarvis delegating a task/mission to nemoclaw?)"*

Rich had the insight before I did that NemoClaw could be a *delegation target when mature* rather than a replacement. D46 captures this.

**My response to Q1 included:**
- Four launch async subagents (`deep_reasoner`, `adversarial_critic`, `long_research`, `quick_local`)
- Descriptions must include cost + latency signals (reasoning model has skin in routing decisions)
- Default to cheapest-that-fits, escalate on need
- Two mitigations for model-routing-can-go-wrong:
  1. Cost-aware descriptions
  2. Learned preference via prompts (not hard rules)

**My response to Q2:** NemoClaw integrates as (a) DeepAgents sandbox backend when it matures, (b) NATS-registered fleet participant with `trust_tier: sandboxed`. Zero rework needed — just hooks named now.

---

## 6. The Karpathy Loop Parallel (The Second Big Moment)

Rich's next turn introduced the Karpathy Loop transcript and Meta-Harness paper:

> *"my first instinct is to use the same learning/confirmation technique we used for the mode inference selection/confirmation and graphiti learning we use on the specialist agent and have specced for the forge."*

This was the moment I realised **Rich had already designed a Karpathy Loop without knowing the name for it.** Forge's ADR-ARCH-005/006 — Graphiti-fed learning loop with calibration priors, `CalibrationAdjustment` proposals, Rich-confirmed persistence — is structurally identical to Karpathy's auto-research pattern applied to gate decisions instead of code files.

I read the transcript + insights file + Meta-Harness paper summary and articulated the isomorphism:

| Karpathy / Meta-Harness | Forge calibration loop |
|---|---|
| One editable surface | `CalibrationAdjustment` entities |
| One metric | Rich's override rate |
| One time budget | One build |
| Meta-proposes, keep/revert | `forge.learning` proposes, Rich confirms |
| Full execution traces | `forge_pipeline_history` with reasoning chains |
| Emergent behaviours | Training-mode conservatism relaxing organically |

**What the Karpathy Loop material added that I applied to our architecture:**

1. **Meta-agent / task-agent split** — Goose's Auto-Agent found single-agent self-improvement underperforms the split. *Our decision:* defer. `*.learning` stays as modules, revisit after 6 months of real runs. (D45)

2. **Propose-then-apply in the harness itself** — Meta-Harness rewrites system prompts autonomously. *Our decision:* defer indefinitely. Personal-Jarvis scale makes drift risk higher than speed benefit. (D45)

3. **Full-filesystem context for the meta-agent** — Meta-Harness's 10M tokens/iter vs 26K for prior methods is the decisive quality differentiator. *Our decision:* adopt immediately via trace-richness schema (ADR-FLEET-001). This is cheap-now, expensive-to-retrofit. (D42)

**Rich's response:** *"I think Concrete scope discipline for v1: is about right"* and *"Big as in coherence: it uses the flywheel effect natively and each new addition as capabilities building on what's already there to leverage compounding effects."*

This crystallised the **coherence-via-flywheel** framing that becomes fleet v3's §7.

---

## 7. The Coherence Framing

The final piece Rich added: *"If we build with this in mind it becomes achievable without scope creep because the system grows organically over time."*

This is the architectural promise. Three things compound:

1. **Per-surface compounding** — every Forge build makes future builds better; every Jarvis session makes future sessions better; every Tutor session makes future sessions better.

2. **Infrastructure compounding** — improvements to Graphiti help all surfaces; better traces help all learning; better adapters help all UX.

3. **Pattern compounding** — adding a new surface means adding a new Graphiti group + a new learning module. Zero changes to existing surfaces.

**"Coherence via flywheel" became the keystone label.**

---

## 8. What Got Decided (D40-D46)

Added to fleet-master-index's D1-D39 decision log:

| # | Decision |
|---|---|
| **D40** | Three DeepAgents surfaces (Jarvis, Forge, Study Tutor), one substrate. Jarvis IS the GPA with dispatch as tools. |
| **D41** | Flywheel-via-calibration-loop fleet-wide. Every surface has `*.learning` module + `*_history` Graphiti group. |
| **D42** | Trace-richness by default. Full reasoning chains, subagent traces, cost/latency, human response text in every `*_history` write. |
| **D43** | Model routing is a reasoning decision, not a config decision. Async subagents expose models; supervisor picks. |
| **D44** | Selectively ambient — Pattern A (reactive) + B (triggered watchers) for v1. Pattern C (volitional) as opt-in skill only. |
| **D45** | Meta-agent split and harness auto-rewriting explicitly deferred. Research directions, not v1 scope. |
| **D46** | NemoClaw integration hooks named but not built. Plugs in as sandbox backend + `trust_tier: sandboxed` fleet participant when mature. |

---

## 9. What Got Deferred (Important — Don't Forget)

**Explicitly deferred with clear revisit conditions:**

1. **Meta-agent / task-agent split** (D45)
   - Revisit: After 6 months of real runs, if `*.learning` module quality is insufficient.
   - Signal: Rich stops confirming proposals, or proposals are pattern-matching rather than root-causing.
   - Pattern: Goose's Auto-Agent split meta from task for reason.

2. **Harness auto-rewriting** (D45)
   - Revisit: After (a) multiple agents in daily production use, (b) trace infrastructure mature, (c) eval metrics for "good behaviour" well-defined.
   - Signal: Not before v2. Possibly not ever at personal-Jarvis scale.
   - Pattern: Meta-Harness applies this at scale; failure modes too costly at our scale.

3. **Pattern C (volitional) ambient behaviour** (D44)
   - Revisit: When one of the Pattern C candidate skills (starting with "morning briefing") proves it earns its place.
   - Signal: Rich actively uses the skill; doesn't try to turn it off; returns value.
   - Pattern: Skill-as-toggle first, graduation to always-on watcher second.

4. **HTTP transport for async subagents** (ADR-ARCH-031, ADR-J-P7)
   - Revisit: When a subagent needs independent compute (different GPU profile, different team, different scaling).
   - Signal: Resource contention on GB10 or operational separation needs.
   - Pattern: ASGI first, HTTP when justified.

5. **NemoClaw integration** (D46)
   - Revisit: When GitHub issues #341/#415/#878 resolved; NIM local inference confirmed working on DGX Spark; driver 590 stable.
   - Signal: Community Docker image for NemoClaw from proven maintainers (eugr or similar).
   - Pattern: Rejected-but-revisitable; hooks named in architecture.

6. **Context7-style external tool docs lookup**
   - (Not discussed but adjacent.) DeepAgents has `langchain-mcp-adapters` for MCP; we have Context7 server available. Consider integration in Jarvis's tool set but not v1 scope.

---

## 10. What Got Considered and Rejected

- **Supervisor-per-adapter Jarvis:** rejected in favour of single supervisor thread-per-session. Reasoning: cross-adapter handoffs easier, Memory Store handles durable recall without thread duplication.

- **Rule-based signal-matching classifier + LLM fallback** (the original D11 direction in Jarvis v1 vision): rejected in favour of pure reasoning-over-capabilities. Reasoning: Forge's ADR-ARCH-015/016 pattern applies; classification is tool selection.

- **GPA as separate repo / separate process** (the original D12 direction): rejected by D40. Jarvis IS the GPA; no separation.

- **Always-on Pattern C from day one:** rejected as too risky for personal-assistant scale. Opt-in skill first.

- **Abandoning the static-config lean in favour of more YAML knobs:** never seriously considered — fleet v3 reinforces ADR-ARCH-019's reasoning-not-config principle across all three surfaces.

- **Building a `jarvis-mcp` adapter repo** (analogous to the now-superseded `architect-agent-mcp`): not needed — DeepAgents' native MCP support via `langchain-mcp-adapters` handles this without a separate repo.

---

## 11. The Physical Documents Produced

Seven documents written during this session:

1. **`forge/docs/research/ideas/fleet-architecture-v3-coherence-via-flywheel.md`** — keystone fleet vision (13 sections, D40-D46, the one-sentence thesis, three-surfaces-one-substrate picture, flywheel framing with Karpathy parallel)

2. **`forge/docs/research/ideas/ADR-FLEET-001-trace-richness.md`** — fleet-wide trace schema commitment (Meta-Harness-derived, 7 required field groups, retention policy, implementation sequencing)

3. **`forge/docs/architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md`** — Forge ADR amending ARCH-020 to use `AsyncSubAgent` for `autobuild_runner`

4. **`jarvis/docs/research/ideas/jarvis-vision.md`** (v2.0) — full rewrite: GPA-with-dispatch framing, four launch subagents, thread-per-session model, selectively ambient patterns, learning flywheel

5. **`jarvis/docs/research/ideas/jarvis-architecture-conversation-starter.md`** (v2.0) — rewritten for tomorrow's `/system-arch`: C4 diagrams, ADR-J-P1..P10 preferred directions, JA1-JA9 open questions, constraints

6. **`jarvis/.guardkit/context-manifest.yaml`** — cross-repo dependency map for Forge-driven builds (nats-core, forge, specialist-agent, nats-infrastructure, guardkit)

7. **`~/Projects/YouTube Channel/ddd-southwest-2026-software-factory-talk-outline.md`** — 45-minute talk outline with five-act narrative, slide cues, war stories, key quotes, preparation checklist

8. **This document** (`conversation-capture-2026-04-19-fleet-v3-framing.md`) — the richness-preservation doc

---

## 12. What's Still To Do (Next Actions from Fleet v3 §13)

- ◻ **Fleet-master-index v2 update** — add D40-D46 to the decision log, reference fleet v3 doc as companion
- ◻ **Forge ARCHITECTURE.md** — add reference to ADR-ARCH-031 in Decision Index §13
- ◻ **Study Tutor future-work note** — add a note to its docs referencing async subagents for background paper-gen and Memory Store for cross-session recall (no `/system-arch` re-run)
- ◻ **Tomorrow (20 April 2026):** Run `/system-arch` on Jarvis using the rewritten conversation-starter

Optional / later:
- ◻ **Forge doc-update for ADR-FLEET-001** — add reference to the trace-richness ADR in relevant Forge ADRs
- ◻ **`specialist-agent` context-manifest update** — ensure it references fleet v3 doc as `framing` category
- ◻ **Context7 integration research** — not v1, but worth noting for Jarvis's tool set
- ◻ **Graphiti reseeding** — Forge `/system-arch` content may not have written to standard groups; investigate before Jarvis `/system-arch` depends on retrieval

---

## 13. The External Material That Shaped This

Web-fetched during the session:

| Source | Used for |
|---|---|
| github.com/langchain-ai/deepagents | Verifying SDK status |
| pypi.org/project/deepagents (via search) | Checking released versions |
| docs.langchain.com/oss/python/deepagents/overview | Confirming 0.5.x feature set, listing Async subagents capability |
| docs.langchain.com/oss/python/deepagents/async-subagents | Full async subagents spec — five tools, transport options, state channel |
| github.com/langchain-ai/deepagents/releases/tag/deepagents%3D%3D0.5.3 | Confirming 0.5.3 released 15 April 2026 |
| yoonholee.com/meta-harness | Meta-Harness paper summary — 10M vs 26K tokens, counterfactual diagnosis, full-filesystem proposer |

Read from user's filesystem:

| Source | Used for |
|---|---|
| `~/Projects/YouTube Channel/transcripts/The Karpathy Loop...md` | Karpathy Triplet, meta-agent/task-agent split, model empathy, traces-everything, safety concerns |
| `~/Projects/YouTube Channel/insights/The Karpathy Loop...md` | Structured insights — 15 numbered items, action checklist |

All project documents read across Forge, Jarvis, and the shared knowledge via `project_knowledge_search`.

---

## 14. The Tony Stark Aesthetic (Why This Conversation Mattered)

Rich's *"I'm Tony Stark building a v1 mini-Jarvis"* comment wasn't flippant. It was signalling a specific aesthetic goal that changes what counts as success:

- **Persistent presence** — always available, doesn't need to be summoned
- **Knows what you're working on** — context-aware without being asked
- **Brings the right brain to the right problem** — model routing made architectural
- **Backs you up** — watchers, nudges, ambient support when it earns its place
- **Stays out of the way** — reactive default, volitional only when proven

This is not "chatbot with extra features." It's an **ambient intelligence** built on the exact same substrate as the batch-delivery Forge and the conversational Study Tutor, but leaning on different SDK features to feel different.

**The architectural insight:** you don't build different agents for different aesthetics. You build one substrate, three surfaces, and let each surface lean on the SDK features that produce its character.

Jarvis feels like Jarvis because it uses `AsyncSubAgent` for model routing, Memory Store for cross-session recall, Skills for composable shortcuts, and selectively-ambient Pattern B watchers. Forge feels like a batch processor because it uses sync `task()` for bounded gates and `interrupt()` for approval pauses. Study Tutor feels conversational because it's primarily sync with background async for non-blocking work.

**Same SDK. Same pattern. Different leaning. Same coherence.**

That's the Tony Stark aesthetic made buildable. And it's why this conversation mattered — without the 1000-metre framing, Jarvis would have been designed as "a thin router" and never felt like the thing Rich actually wanted.

---

## 15. Notes for Tomorrow's `/system-arch` Session

- Load `jarvis-architecture-conversation-starter.md` v2 as primary context
- Load `jarvis-vision.md` v2 as supporting context
- Load `fleet-architecture-v3-coherence-via-flywheel.md` as framing
- Load `ADR-FLEET-001-trace-richness.md` as trace-schema constraint
- Load Forge `ADR-ARCH-031-async-subagents-for-long-running-work.md` as parallel-pattern reference
- Load DeepAgents 0.5.3 docs — specifically async-subagents page — for SDK capability reference

Watch for these patterns during the session:
- Model might try to re-open D11 (intent classification) or D12 (GPA location) — both resolved by D40. Don't re-debate.
- Model might propose meta-agent split — that's D45 deferred. Hold the line.
- Model might propose static gate/threshold config — that's ADR-ARCH-019 inherited from Forge. Hold the line.
- Model might propose polling pattern for Jarvis status — redirect to async subagent + `list_async_tasks`.

Good questions to let the session genuinely work on:
- JA1 (schema fields for `jarvis_routing_history`)
- JA2 (ambient watcher resource limits)
- JA3 (cross-adapter handoff semantics)
- JA6 (`quick_local` fallback under GB10 pressure)

---

## 16. The Parting Thought

Rich asked for "1000 metres" altitude. What this conversation actually did was **get the architectural spine of the entire ecosystem settled before the cost of rework spiked.**

Forge's `/system-arch` is done. Study Tutor's `/system-arch` is done. Jarvis's is tomorrow. Without the fleet v3 framing, Jarvis would have been designed in isolation with a stale vision doc as its primary input, and the first real cross-surface decision (Jarvis↔Forge integration on a live build) would have surfaced the tension expensively.

Instead, the tension got surfaced and resolved in one conversation, on a Sunday, before anyone had written code. Seven documents exist that didn't exist this morning. Tomorrow's `/system-arch` run has clean inputs. The DDD Southwest talk has its spine. The Karpathy Loop becomes external validation rather than a future refactor. NemoClaw is in its right place. Async subagents are in their right place. The flywheel is named.

This is what "1000 metres" pays for.

---

*"One reasoning model that knows which reasoning model to use."*

*Conversation capture · 19 April 2026 · preserved so future-Rich knows why*
