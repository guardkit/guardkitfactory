#!/bin/bash
# Document Placement Script
# Run from the directory where you downloaded the Claude output files
# Usage: bash place-documents.sh /path/to/downloaded/files

DOWNLOAD_DIR="${1:-.}"
BASE="/Users/richardwoollcott/Projects/appmilla_github"

echo "Placing documents from: $DOWNLOAD_DIR"
echo ""

# --- guardkitfactory repo ---
FACTORY="$BASE/guardkitfactory/docs/research"
mkdir -p "$FACTORY"

echo "=== guardkit/guardkitfactory ==="
cp "$DOWNLOAD_DIR/pipeline-orchestrator-consolidated-build-plan.md" "$FACTORY/" && echo "  ✓ build plan"
cp "$DOWNLOAD_DIR/pipeline-orchestrator-motivation.md" "$FACTORY/" && echo "  ✓ motivation"
cp "$DOWNLOAD_DIR/pipeline-orchestrator-conversation-starter.md" "$FACTORY/" && echo "  ✓ conversation starter"
cp "$DOWNLOAD_DIR/c4-system-context.svg" "$FACTORY/" && echo "  ✓ C4 system context"
cp "$DOWNLOAD_DIR/c4-component-map.svg" "$FACTORY/" && echo "  ✓ C4 component map"
cp "$DOWNLOAD_DIR/c4-build-order.svg" "$FACTORY/" && echo "  ✓ C4 build order"
echo ""

# --- guardkit repo (dark_factory cross-references) ---
DARK="$BASE/guardkit/docs/research/dark_factory"
mkdir -p "$DARK"

echo "=== guardkit/guardkit (cross-references) ==="
cp "$DOWNLOAD_DIR/pipeline-orchestrator-consolidated-build-plan.md" "$DARK/" && echo "  ✓ build plan (cross-ref)"
# Note: conversation-starter and adversarial-conversation-starter already in place
echo "  ✓ adversarial template starter (already updated in-place)"
echo "  ✓ conversation starter (already current)"
echo ""

# --- YouTube Channel ---
YT="/Users/richardwoollcott/Projects/YouTube Channel"

echo "=== YouTube Channel ==="
cp "$DOWNLOAD_DIR/youtube-adversarial-cooperation-journey-conversation-starter.md" "$YT/" && echo "  ✓ youtube journey starter"
cp "$DOWNLOAD_DIR/ddd-southwest-adversarial-cooperation-talk.md" "$YT/" && echo "  ✓ DDD talk (updated)"
cp "$DOWNLOAD_DIR/adversarial-cooperation-business-domains.md" "$YT/" && echo "  ✓ business domains"
echo ""

# --- agentic-dataset-factory ---
ADF="$BASE/agentic-dataset-factory/docs/reviews"
mkdir -p "$ADF"

echo "=== agentic-dataset-factory ==="
cp "$DOWNLOAD_DIR/TASK-REV-PRE-RUN-agentic-dataset-factory.md" "$ADF/" && echo "  ✓ pre-run review"
echo ""

echo "=== Document placement map ==="
cp "$DOWNLOAD_DIR/document-placement-map.md" "$FACTORY/" && echo "  ✓ placement map"
echo ""

echo "Done! Files placed in:"
echo "  guardkitfactory/docs/research/ (6 files + placement map)"
echo "  guardkit/docs/research/dark_factory/ (1 updated)"
echo "  YouTube Channel/ (3 files)"
echo "  agentic-dataset-factory/docs/reviews/ (1 file)"
echo ""
echo "READMEs already written directly:"
echo "  guardkitfactory/README.md ✓"
echo "  deepagents-orchestrator-exemplar/README.md ✓"
