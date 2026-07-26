#!/usr/bin/env bash
# scripts/verify_engine_copy.sh
# Asserts that interval_engine/ matches the GATCHA ancestor byte-for-byte
# modulo the documented Italian-to-English translations recorded in
# interval_engine/.translation_notes.md.
#
# Strategy:
#   1. Get the list of files that differ between the two trees.
#   2. The ONLY file allowed to differ in content is src/Main.cpp
#      (the translated CLI).
#   3. New files/directories in interval_engine/ are allowed only at the
#      root and only as documented.
#   4. Ancestor's target/ tree is ignored (pre-built Windows binaries).
#
# Exit code 0  -> engine is in sync
# Exit code 1  -> drift detected
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

ANCESTOR="${WATCHOUT_ANCESTOR_DIR:-/home/ghiffaryr/iseql/GATCHA/app with VLM/cpp-iseql}"
ENGINE="$ROOT/interval_engine"

if [[ ! -d "$ANCESTOR" ]]; then
  echo "ERROR: ancestor not found at: $ANCESTOR"
  echo "       Set WATCHOUT_ANCESTOR_DIR to the GATCHA cpp-iseql path."
  exit 1
fi

if [[ ! -d "$ENGINE" ]]; then
  echo "ERROR: $ENGINE does not exist"
  exit 1
fi

echo ">> Comparing $ENGINE"
echo "          to $ANCESTOR"
echo ""

DIFF_FILES="$(diff -rq "$ANCESTOR" "$ENGINE" 2>&1 || true)"

ALLOWED_CONTENT_DIFFS=("src/Main.cpp")
ALLOWED_ROOT_NEW=(
  ".translation_notes.md"
  "build.sh"
  "build"        # cmake build artefacts, intentionally not committed in source
)

# Filter out the ancestor's pre-built target/ tree.
RELEVANT_DIFFS="$(echo "$DIFF_FILES" | grep -v 'target' || true)"

EXIT_CODE=0

echo ">> New files/directories in interval_engine/ (allowed: ${ALLOWED_ROOT_NEW[*]}):"
NEW_ENTRIES="$(echo "$RELEVANT_DIFFS" | grep '^Only in ' | awk -F': ' '{print $2}' | sort -u || true)"
if [[ -n "$NEW_ENTRIES" ]]; then
  while IFS= read -r f; do
    [[ -z "$f" ]] && continue
    allowed="false"
    for a in "${ALLOWED_ROOT_NEW[@]}"; do
      if [[ "$f" == "$a" ]]; then allowed="true"; break; fi
    done
    if [[ "$allowed" == "true" ]]; then
      echo "    [ok]      $f"
    else
      echo "    [ERROR]   $f (not in the allow-list; remove it or add it to scripts/verify_engine_copy.sh)"
      EXIT_CODE=1
    fi
  done <<< "$NEW_ENTRIES"
fi
echo ""

echo ">> Files with content differences (allowed: ${ALLOWED_CONTENT_DIFFS[*]}):"
# Format: "Files <pathA> and <pathB> differ"
CONTENT_DIFFS="$(echo "$RELEVANT_DIFFS" | grep -v '^Only in ' || true)"
if [[ -z "$CONTENT_DIFFS" ]]; then
  echo "    (none)"
else
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    # Extract the path of the file under our engine.
    # e.g. "Files /A/.../src/Main.cpp and /B/.../src/Main.cpp differ"
    #       -> the path under engine is the one starting with $ENGINE.
    f="$(echo "$line" | grep -oE "${ENGINE//\//\\/}/[^ ]+" | head -1 || true)"
    [[ -z "$f" ]] && continue
    rel="${f#$ENGINE/}"
    allowed="false"
    for a in "${ALLOWED_CONTENT_DIFFS[@]}"; do
      if [[ "$rel" == "$a" ]]; then allowed="true"; break; fi
    done
    if [[ "$allowed" == "true" ]]; then
      echo "    [ok]      $rel"
    else
      echo "    [ERROR]   $rel (differs from ancestor but is not in the allow-list)"
      EXIT_CODE=1
    fi
  done <<< "$CONTENT_DIFFS"
fi
echo ""

if [[ $EXIT_CODE -eq 0 ]]; then
  echo "OK: interval_engine/ is in sync with GATCHA ancestor"
  echo "    (only the documented Italian-to-English translations differ;"
  echo "     see interval_engine/.translation_notes.md)"
fi
exit $EXIT_CODE
