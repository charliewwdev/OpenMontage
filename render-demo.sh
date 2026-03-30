#!/usr/bin/env bash
# render-demo.sh — Render zero-key demo videos using only Remotion components
# No API keys, no external services, no GPU required.
#
# Usage:
#   ./render-demo.sh                    # Render all demos
#   ./render-demo.sh world-in-numbers   # Render one specific demo
#   ./render-demo.sh --list             # List available demos
#
# Prerequisites: Node.js 18+, npm install in remotion-composer/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSER_DIR="$SCRIPT_DIR/remotion-composer"
PROPS_DIR="$COMPOSER_DIR/public/demo-props"
OUTPUT_DIR="$SCRIPT_DIR/projects/demos/renders"

# Available demos
declare -A DEMOS=(
  ["world-in-numbers"]="The World in Numbers — 45s data visualization showcase"
  ["code-to-screen"]="From Code to Screen — 50s developer education explainer"
  ["focusflow-pitch"]="FocusFlow Pitch — 40s startup pitch deck video"
)

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

list_demos() {
  echo ""
  echo -e "${CYAN}Available zero-key demos:${NC}"
  echo ""
  for name in "${!DEMOS[@]}"; do
    echo -e "  ${GREEN}$name${NC}  ${DEMOS[$name]}"
  done
  echo ""
  echo "Usage: ./render-demo.sh [demo-name]"
  echo "       ./render-demo.sh          (renders all)"
  echo ""
}

render_demo() {
  local name="$1"
  local props_file="$PROPS_DIR/$name.json"
  local output_file="$OUTPUT_DIR/$name.mp4"

  if [ ! -f "$props_file" ]; then
    echo "Error: Props file not found: $props_file"
    exit 1
  fi

  mkdir -p "$OUTPUT_DIR"

  echo ""
  echo -e "${CYAN}Rendering:${NC} ${DEMOS[$name]:-$name}"
  echo -e "${CYAN}Props:${NC}     $props_file"
  echo -e "${CYAN}Output:${NC}    $output_file"
  echo ""

  cd "$COMPOSER_DIR"
  npx remotion render src/index.tsx Explainer "$output_file" \
    --props "$props_file" \
    --codec h264

  if [ -f "$output_file" ]; then
    local size=$(du -h "$output_file" | cut -f1)
    echo ""
    echo -e "${GREEN}Done!${NC} $output_file ($size)"
  else
    echo "Render may have failed — check output above."
  fi
}

# Main
if [ "${1:-}" = "--list" ] || [ "${1:-}" = "-l" ]; then
  list_demos
  exit 0
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "render-demo.sh — Render zero-key demo videos"
  echo ""
  echo "These demos use ONLY Remotion components (animated charts, text cards,"
  echo "stat reveals, comparisons) — no API keys, no images, no external services."
  echo ""
  list_demos
  exit 0
fi

# Check prerequisites
if ! command -v node &> /dev/null; then
  echo "Error: Node.js is required. Install from https://nodejs.org/"
  exit 1
fi

if [ ! -d "$COMPOSER_DIR/node_modules" ]; then
  echo -e "${YELLOW}Installing Remotion dependencies...${NC}"
  cd "$COMPOSER_DIR" && npm install
fi

if [ -n "${1:-}" ]; then
  # Render specific demo
  if [ -z "${DEMOS[$1]+x}" ]; then
    echo "Unknown demo: $1"
    list_demos
    exit 1
  fi
  render_demo "$1"
else
  # Render all demos
  echo -e "${CYAN}Rendering all zero-key demos...${NC}"
  for name in world-in-numbers code-to-screen focusflow-pitch; do
    render_demo "$name"
  done
  echo ""
  echo -e "${GREEN}All demos rendered!${NC} Check $OUTPUT_DIR/"
fi
