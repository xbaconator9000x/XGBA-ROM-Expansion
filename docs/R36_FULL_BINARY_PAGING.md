# R36 — Lossless binary-ROM pages and audited script entrypoints

**Engineering scope.** R34 extracted only fixed-length map structures from an
Emerald-family ROM and R35 made those available next to source-built game
resources. R36 additionally addresses **every single byte** of the original
binary ROM, including data whose formats we do not yet understand.

The user-owned original is read-only. Every source byte is exported to
immutable, SHA-256-verified 16 KiB pages through the already deployed XGBA
sidecar v1 format, with 128 pages per shard by default. The index retains
the original ROM SHA-256, original group/map table identity, source-map count
and exact byte offset for each page; no map, species, event or move ID is
renumbered. On mount, the pool rechecks each shard's SHA and concatenated
**whole-ROM SHA-256**, and checks every page's contiguous offset and
complete manifest coverage before the corpus becomes visible.

A new `R36MixedWorldPool` layers the pages on R35's verified binary map
world **only when the exact original ROM identity and original map-group
layout match**. It supports source-aware 16 KiB bounded read windows crossing
two adjacent original pages, and uses the existing combined RAM staging
budget, so hundreds of megabytes of externally addressable source bytes
do not imply more guest physical RAM.

### Script reference census

R36 also audits entrypoint references from every structurally validated map
header and source-backed Emerald object/coordinate/background event:
- Unaligned 5-byte map-script table entries, respecting 1..7 script tags.
- Conditional type-2/type-4 map script tables, with original 8-byte records
  and 16-bit terminators.
- Object event pointer at +16, coordinate event pointer at +12, and script
  background event kinds 0..4 at +8.
- Hidden item kind 7 and secret base kind 8 are **not** misread as script
  pointers. Unresolved/invalid pointers remain explicit flagged records.

**Crucial limitation:** This records *entrypoint pointers*, not their
variable-length bytecode or any executable semantics. It does NOT run scripts,
translate modified battle engines, provide cross-ROM Fly travel, or implement
shared persistence. No claim of complete ROM-hack compatibility follows
from having all bytes available. The unrecognised binary assets are retained
for later parsing rather than being silently discarded.

### Private local reproduction

    python3 tools/xgba_r36_binary_pages.py your-own-rom.gba \
      --source-id rocket --export /private/xgba-rocket-pages \
      --counts-only /private/aggregate-counts.json

Only locally owned ROMs and user-provided assets should be used. The tool
never creates a patched ROM or modifies the input. Neither the original ROM
nor extracted content should be uploaded to public GitHub or CI.

### Evidence standard

Public exact-head CI uses synthetic non-copyrighted GBA binaries and a
pinned original Emerald decomp source tree: verified byte-for-byte paging,
script entrypoint recognition, original IDs, cross-source mounts, whole-source
asset access, tampering refusal and guest/host memory limits. The private
Team Rocket 3.06 image is checked locally using the same exporter and the
full original-byte readback; that ROM stays out of public CI.

This report claims **no verified success** until the CI passes.

[Paging and census](../tools/xgba_r36_binary_pages.py) ·
[Mixed-world mounting](../tools/xgba_r36_mixed_world.py) ·
[Public safety tests](../tests/test_xgba_r36_binary_pages.py) ·
[CI](../.github/workflows/xgba-r36-complete-rom-pages.yml)
