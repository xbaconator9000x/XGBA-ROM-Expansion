#!/usr/bin/env bash
# Standalone, reproducible pinned native mGBA test (NOT an XGBA implementation).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PIN="fd9dc5c2cbf234365068855851107e762fc6211b"
MGBA="$ROOT/upstream/mgba"
mkdir -p "$ROOT/upstream" "$ROOT/audit-output"
if [ ! -d "$MGBA/.git" ]; then
  git clone --filter=blob:none https://github.com/mgba-emu/mgba.git "$MGBA"
fi
git -C "$MGBA" fetch origin "$PIN"
git -C "$MGBA" checkout --detach "$PIN"
test "$(git -C "$MGBA" rev-parse HEAD)" = "$PIN"
test "$(git -C "$MGBA" hash-object src/gba/memory.c)" = "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc"
test "$(git -C "$MGBA" hash-object src/gba/cart/matrix.c)" = "9ccbe883235b98bcf56cd609015e7b4003aa832c"
test "$(git -C "$MGBA" hash-object src/arm/arm.c)" = "0b92d7f55f1fb853d4b1b9c9163ee086126066e2"
echo "$PIN" > "$ROOT/audit-output/mgba_native_test_revision.txt"
set -o pipefail
cmake -S "$ROOT/tests" -B "$ROOT/build-mgba-boundary" -DCMAKE_BUILD_TYPE=Debug \
  2>&1 | tee "$ROOT/audit-output/mgba-boundary-configure.log"
cmake --build "$ROOT/build-mgba-boundary" --target xgba_mgba_bank_boundary --parallel 2 \
  2>&1 | tee "$ROOT/audit-output/mgba-boundary-build.log"
# Distinguish a harness crash from a failed assertion. Keep precise original exit status.
ulimit -c 0 || true
set +e
"$ROOT/build-mgba-boundary/xgba_mgba_bank_boundary" \
  2>&1 | tee "$ROOT/audit-output/mgba-boundary-runtime.log"
status="${PIPESTATUS[0]}"
set -e
if [ "$status" -ne 0 ]; then
  echo "Boundary probe exited with status $status" | tee -a "$ROOT/audit-output/mgba-boundary-runtime.log"
  if command -v gdb >/dev/null 2>&1; then
    gdb --batch --quiet -ex run -ex "thread apply all bt 12" \
      --args "$ROOT/build-mgba-boundary/xgba_mgba_bank_boundary" \
      > "$ROOT/audit-output/mgba-boundary-backtrace.log" 2>&1 || true
  fi
  exit "$status"
fi
sha256sum "$ROOT/audit-output/mgba-boundary-"*.log > "$ROOT/audit-output/mgba-boundary-log-sha256.txt"
echo "Phase 1 remains incomplete. A passing native probe does not certify safe XGBA banking."
