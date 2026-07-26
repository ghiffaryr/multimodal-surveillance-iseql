#!/usr/bin/env bash
# interval_engine/build.sh
# Builds the WATCHOUT ISEQL interval engine on Linux.
# Mirrors the original GATCHA `make` script's three target variants:
#   - release  (default): -O3, no debug counters
#   - counters          : -O3 with algorithm performance counters (COUNTERS=1)
#   - ebi               : -O3 using EBI instead of LEBI (EBI=1)
#
# Usage:
#   ./build.sh               # release
#   ./build.sh counters      # with counters
#   ./build.sh ebi           # with EBI
#   ./build.sh clean         # remove build artefacts
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

BUILD_TYPE="${1:-release}"

case "$BUILD_TYPE" in
  release)
    EXTRA_ARGS=""
    ;;
  counters)
    EXTRA_ARGS="-DCOUNTERS=ON"
    ;;
  ebi)
    EXTRA_ARGS="-DEBI=ON"
    ;;
  clean)
    echo "Cleaning build artefacts..."
    rm -rf build
    echo "Done."
    exit 0
    ;;
  *)
    echo "Usage: $0 [release|counters|ebi|clean]"
    exit 1
    ;;
esac

echo ">> interval_engine build: $BUILD_TYPE"
echo ">> extra cmake args: $EXTRA_ARGS"

mkdir -p build
cd build

cmake -DCMAKE_BUILD_TYPE=Release $EXTRA_ARGS ..
cmake --build . --config Release -- -j"$(nproc)"

echo ""
echo ">> Built executables:"
find . -type f -executable -name 'iseql*' | sort
echo ""

# Stage the release binary at the conventional location the backend looks for.
mkdir -p ../build/release
cp -f src/iseql ../build/release/iseql
echo ">> Staged release binary at build/release/iseql"
echo ""
echo "Done. To run a smoke test: ./build/release/iseql"
