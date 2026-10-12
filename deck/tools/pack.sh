#!/usr/bin/env bash
# Pack deck/src into a .pptx, validate against the template, and render PNGs.
# Usage: deck/tools/pack.sh [OUT_DIR]   (default: deck/out)
# Parallel agents MUST pass their own OUT_DIR (e.g. /tmp/swt-A) so renders don't collide.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-$ROOT/deck/out}"; mkdir -p "$OUT"
SKILL="${PPTX_SKILL:-/root/.claude/skills/synced/0abc3d93-ec27-44c0-8a62-a036d8a270cd_bcdbe58e-8b72-4088-a2fe-c40c19b45a25/pptx}"
DECK="$OUT/snowflake-world-tour.pptx"
rm -f "$DECK"
(cd "$ROOT/deck/src" && zip -qXr "$DECK" . -x '.DS_Store')
python3 "$SKILL/scripts/office/validate.py" "$DECK" --original "$ROOT/deck/template/SWT26_Customer_Speaker_Template.pptx"
if [[ "${NO_RENDER:-0}" != "1" ]]; then
  (cd "$OUT" && python3 "$SKILL/scripts/office/soffice.py" --headless --convert-to pdf "$DECK" >/dev/null 2>&1)
  rm -f "$OUT"/slide-*.png
  pdftoppm -png -r 60 "$OUT/snowflake-world-tour.pdf" "$OUT/slide"
  ls -1 "$OUT"/slide-*.png
fi
