#!/usr/bin/env bash
# scripts/build_engine.sh
# Alias wrapper for interval_engine/build.sh. Kept so that the
# historical "scripts/build_engine.sh" command documented in the
# GATCHA README still works under the new project.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$HERE/../interval_engine/build.sh" "$@"
