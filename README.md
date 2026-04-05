# GuardKit Factory — Autonomous Software Development Pipeline

The primary deliverable in the Ship's Computer agent fleet. An autonomous pipeline agent
that drives the full GuardKit slash command lifecycle — from architecture through to
verified, deployable code — using a two-model architecture where a reasoning model
orchestrates and validates while an implementation model executes.

## Status: Pre-Architecture (Ready to Build)

Conversation starters and consolidated build plan ready. Templates proven. Next step:
run `/system-arch` using the conversation starter.

**Domain:** guardkitfactory.ai

## What It Does

Replaces the human operator in the GuardKit pipeline. The human moves from operator to
approver at defined checkpoints.

Pipeline: `/system-arch` → `/system-design` → `/feature-spec` → `/feature-plan` → `autobuild` → `/task-review`

**Evidence this works:** 43 tasks across 6 features built with only 3 high-impact human
decisions. 93% of outputs accepted as defaults (TASK-REV-F5F5).

## Docs

### Architecture & Build Plan
- `docs/research/pipeline-orchestrator-conversation-starter.md` — For `/system-arch` session
- `docs/research/pipeline-orchestrator-consolidated-build-plan.md` — Full build plan
- `docs/research/pipeline-orchestrator-motivation.md` — Why we're building this
- `docs/research/c4-*.svg` — C4 architecture diagrams

### Fleet Context
- `docs/research/ideas/fleet-master-index.md` — Master index across all repos

## Part of the Jarvis Fleet

The heaviest agent in the fleet. Dispatched by the Jarvis intent router for software
engineering tasks. Uses `langchain-deepagents-weighted-evaluation` template as base,
with reasoning model layer, slash commands as tools, and NATS integration on top.

### Related Repos
- `guardkit/jarvis` — Intent router + General Purpose Agent
- `guardkit/youtube-planner` — Content planning pipeline
- `guardkit/ideation-agent` — Structured brainstorming
- `guardkit/guardkit` — CLI (slash commands, templates, AutoBuild)
- `guardkit/deepagents-player-coach-exemplar` — Proven adversarial pattern exemplar

## Build Command

```bash
# Start architecture:
# 1. Paste pipeline-orchestrator-conversation-starter.md into Claude Desktop
# 2. Run: /system-arch "GuardKit Factory Pipeline Orchestrator"
# 3. Then: /system-design, /system-plan, /feature-spec, /feature-plan, autobuild
```
