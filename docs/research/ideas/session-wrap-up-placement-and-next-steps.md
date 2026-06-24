# Session Wrap-Up — Placement & Next-Steps Plan

## 20 June 2026 (refreshed) · factory scaling · presentation layer · output-side loop · **LPA demo grounded**

> **Refresh note.** Updated after the LPA platform grounding and the forge-docs cleanup, both of which post-date the original. Key changes: the LPA demo plan + screen brief now exist; the Lovable cutover is understood as a *build* (four screens + auth bridge), not a repoint; Moneyhub is in (Mock-Bank-via-Moneyhub); the forge research conflicts are reconciled.

---

## Where we stand (one paragraph)

The strategy is settled and the LPA demo is grounded. The LPA platform already implements the **entire** ideal demo flow end-to-end — extraction (Docling + LLM), real Moneyhub (private-key JWT OAuth), dedicated attorney access (PII-matched claim + delegated reads), and the rules engine that flags transactions against LPA instructions (per-flag LLM reasoning, confidence threshold) — behind a clean, content-negotiated JSON API. The backend is not the risk; the frontend cutover and the auth bridge are.

---

## Documents → repo homes

| Document | Repo / home | Role | Status |
|----------|-------------|------|--------|
| `lpa-hsbc-demo-plan.md` | **lpa-platform-poc** `docs/poc/` (with `lovable-integration-sketch.md`) | The parallel-track plan to 9 July | **Done this session** |
| `lovable-demo-screens-brief.md` | **lpa-project-docs** (FinProxy-facing) / hand to James | Four screens + exact API data contracts | **Done this session** |
| `factory-scaling-and-output-bottleneck-findings.md` | **guardkitfactory** `docs/research/ideas/` (cross-cutting) | Strategic anchor; D1–D15 | Placed |
| `forge-output-loop-conversation-starter.md` | **forge** `docs/handoffs/` (runbook-driven version) | `/system-arch` → `/system-design` | Placed; stale pre-runbook copy deleted |
| `factory-dashboard-conversation-starter.md` | **factory-dashboard** `docs/` | `/system-arch` → `/system-design` | Placed |
| `fleet-gateway-slack-jarvis-door-conversation-starter.md` | **fleet-gateway** `docs/` | `/feature-spec` → AutoBuild | Placed |
| `session-wrap-up-placement-and-next-steps.md` (this) | **guardkitfactory** `docs/research/ideas/` | The "what's next" index | This refresh |

**Forge research cleanup (this session):** the stale duplicate output-loop doc was deleted, and three reconciliation banners were applied — to `conversation-starter-forge-ideation.md`, `conversation-capture-2026-06-14-forge-meta-harness.md`, and `proposer-eval-build-plan.md` — covering Telegram→Slack, Forge's widened remit, the UBS-001 / `run_autobuild` overlap, the "AutoBuild done" disambiguation, the improve-loop resequencing, and the two-substrate distinction.

---

## Priority: LPA HSBC demo (9 July) — everything else behind it

The HSBC meeting on 9 July is a hard external deadline with a real client. It reorders the work — but **not** the way the obvious reading suggests (the strategic call below).

### The strategic call: do NOT put the unproven executor on a hard deadline

The trap: "LPA is now top priority, so point the output-side runbook executor at the LPA deploy first." That would debut a **brand-new, unproven automation** against **real blast radius** on a **hard client deadline** — the worst combination of all three risk axes at once.

The discipline holds the other way: **hit 9 July with the proven attended method** — Claude Desktop ideation → Claude Code driving the work, Rich approving the irreversible steps manually (exactly how the factory got built in ~8 weeks). The runbook executor matures **later**, on the low-stakes fleet-memory exemplar. The bonus that makes this non-wasteful: doing the LPA cutover attended *generates the real step vocabulary* the executor will later codify — **capture the steps as you go.** fleet-memory is the clean-room exemplar; the LPA cutover is the real-world harvest source. (This is "harvest, don't author" — applied across both tracks.)

### What the demo actually is

Demoed on the **Fincare Companion (Lovable) app**, with the platform as the verified backend and **silent break-glass** (the stakeholder-perception call: non-technical HSBC viewers read a polished surface as "more progress" than the plain-but-real HTMX UI — even though the HTMX UI does all the real work).

**Corrected cost model — it's a build, not a repoint.** The Lovable app has onboarding / dashboard / mock-accounts / attorney-CRM but **not** the four demo screens (extracted-rules review, Moneyhub connect, transactions-with-flags, attorney delegated view) — those must be built in React. The clean API makes the *data wiring* cheap; the four screens and the auth bridge (Supabase Auth → Keycloak OIDC PKCE) are the work.

**Two parallel tracks — start both now:**
- **FinProxy / James** — build the four screens in Lovable from `lovable-demo-screens-brief.md`, against the exact API data shapes (so Rich's swap is drop-in). Guardrails in the brief: Moneyhub-connect = button only (Rich owns the OAuth redirect); freeze-then-don't-reprompt per screen.
- **Rich** — (a) stand the platform up in dev on **Mock-Bank-via-Moneyhub** and verify the full flow end-to-end (Keycloak + extraction already work → add the Moneyhub, rules, and attorney legs); (b) build the **auth bridge** now — the long pole, independent of James's screens, so it must run in parallel or it won't fit the window.

**Sequence:** tracks run now → **freeze** the Lovable feature set ~28 June → **integrate** to 5 July (mock data → live API, wire Moneyhub OAuth, auth at Keycloak) → **rehearse** to 9 July. HTMX UI = silent break-glass.

**De-risking:** Mock-Bank-via-Moneyhub (real Moneyhub integration, stable sandbox data — real where it counts, controllable for a demo); pre-seed extraction (raster OPG PDFs are GPU-bound ~8 min/doc — not demo-safe); seed one transaction that visibly trips a **binding instruction** (the £500 gift-cap → £1,200 gift → `instruction`-severity flag is the money shot); target **5 July** for rehearsal buffer, not the 9th.

> **Moneyhub note (refined from the original "Mock-Bank, not Moneyhub"):** you now have Moneyhub portal access, and `mock-bank-uk` is a Moneyhub *sandbox provider* — so connecting through it is a real Moneyhub integration against stable test-bank data. That is the right demo path: genuinely "real Moneyhub" without live-bank-data variability. (A real live bank account would be real-er but introduces variability into a client demo — avoid for the 9th.)

---

## Then, sequenced behind the demo

1. **fleet-memory** — the next major piece once the demo is underway (low-stakes, runnable in parallel / spare cycles). Dual role: the memory substrate (Postgres + pgvector, replaced Graphiti) **and** the first clean-room exemplar for the output-side runbook loop. Sequence: deploy it via the output loop → validate retrieval (ADR-FLEET-002) → let the learning loops lean on it. Walk away with fleet-memory deployed + the executor + the first two step types (`deploy_compose`, `run_smoke_tests`), no gates (local, reversible — proves the executor where a mistake costs nothing).
2. **Output-side runbook executor (forge)** — matures on fleet-memory, then carries LPA deploy #2/#3 and FinProxy self-serve. Harvest the typed step library from the LPA + fleet-memory deploys; don't author it speculatively. Executor stays thin; Claude Code generates runbooks.
3. **Presentation layer** — **dashboard** first (factory-dashboard: the NATS read-model + FinProxy delivery ledger / commercial instrument), then the **Slack/Jarvis door** (fleet-gateway: a thin adapter onto the Jarvis intent router). **Nail the `await_approval` gate-step contract first** when the output-loop `/system-arch` runs — four things lean on it.
4. **Proposer-eval + improve / meta-harness loop** — resequenced behind all of the above. ~2 days of latency-insensitive batch work on the Sparks; run opportunistically, no longer the gating next step.
5. **QA-verifier / Coach fine-tunes** — parked (D15); the bottleneck moved off the build.

---

## One open decision (not blocking the demo)

The **output-side fix-agent substrate**: does frontier Claude Code in the verify-debug step violate DF-001's no-cloud-on-critical-path rule, or does the approval gate keep it attended-by-exception? The demo doesn't force the call (proven attended method); it shapes the runbook executor when you reach it.

---

## Immediate next actions (this week)

1. **Hand `lovable-demo-screens-brief.md` to James** for the FinProxy workshop. *(unblocks the FinProxy track)*
2. **Start the auth bridge** (Supabase Auth → Keycloak OIDC) — parallel, now. *(the long pole)*
3. **Stand the platform up in dev** on Mock-Bank-via-Moneyhub; verify Moneyhub + rules + attorney end-to-end.
4. *(minor, when convenient)* Patch findings-doc **D7** to record the Jarvis-fronted door decision (Slack adapts onto Jarvis, not the PO agent directly), if not already done.

---

## The thread tying it together

One **approval mechanism** runs through everything: the `await_approval` gate step is the same `awaiting-approval`-plus-notification surface behind the deploy gate, PR-merge, the Slack approve-to-build, and the dashboard's single write — one mechanism, one seat at the front for James and one at the back for Rich, on **Slack** (the channel decision that superseded Telegram). When the output-loop `/system-arch` runs, that contract is the first thing to settle — four things lean on it.

---

*Refreshed: 20 June 2026 | session wrap-up — placement + next-steps. Supersedes the original (the LPA grounding and forge cleanup post-date it).*
*Companion to factory-scaling-and-output-bottleneck-findings.md, lpa-hsbc-demo-plan.md, lovable-demo-screens-brief.md, and the three conversation-starters.*
