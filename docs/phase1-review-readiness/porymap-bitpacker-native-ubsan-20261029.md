# Phase 1 — pinned original Porymap BitPacker native Qt UBSan boundary (2026-10-29)

Status: **EXPERIMENTAL until exact-head CI finishes; FAIL_INCOMPLETE**. This is test-only native host Qt6 C++, not FireRed agbcc/ARM, mGBA gameplay, editor GUI or physical hardware. No original source is modified.

Immutable upstream: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; `src/core/bitpacker.cpp` Git blob `34f86b4e3910021613a1d090746ae53a1c6782a2`; `include/core/bitpacker.h` Git blob `4e3767e48449a974bfe1d9c63c5bf63dd2826fe9`.

## Source and expected boundary

Original `BitPacker::setMask` loops over set bits and stores `1 << i` (line 18); it then calculates `m_maxValue` using `(1 << m_setBits.length()) - 1` (line 21), except at 32 bits. Under C++17, shifting into bit 31 itself is not necessarily diagnosed by UBSan; **do not infer a high-bit defect merely from that expression**. With 31 set bits (`0x7fffffff`), the subsequent signed subtraction from `INT_MIN` is an actual sanitizer candidate. The separate `0x80000000` and `0xffffffff` controls distinguish this case.

Test-only harness compiles the **unchanged original .cpp and .h** with native Qt6 and GCC UBSan, then runs separate subprocesses for masks `0x0f`, `0x80000000`, `0xffffffff`, `0x7fffffff`. The last must fail at original line 21 with `signed integer overflow`; three controls must succeed. Six scoped source and twelve evidence negative controls must reject forgery. The runner preserves actual stderr and JSON evidence.

## Reviewer obligations and limitations

Independently inspect the complete pinned sources, source line 21, Qt QList semantics, callers/actual mask constraints and build configuration; reproduce under GCC/Clang where feasible. Check whether production masks can have 31 set bits before assessing practical reachability. No editor file-write or ROM gameplay claim is supported. Upstream license/notice reconciliation remains pending. This partial dossier is **not whole-file coverage**, has no distinct reviewer or machine dossier validation, and contributes **zero** independent semantic approvals. Authoritative Phase 1 gate stays `FAIL_INCOMPLETE`.

## First native CI and source-to-config closure

First exact-head [push #40845800164](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40845800164) and [PR #40845807904](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/40845807904) were **RED** because the test-only forged-evidence check altered the failing case's stdout without the validator requiring it to be empty. The actual positive native runs and original line-21 UBSan stderr had already passed the preceding `validate_evidence` call. This revision closes the test-only validation gap; prior red evidence is retained.

Additional pinned original source closure (all source-only, no runtime reachability inference):
- `src/core/metatile.cpp` blob `00fff2ba`, `packer.setMask(behaviorMask)` inside attribute layout;
- `src/config.cpp` blob `9264f99b`, metatile behavior mask loaded via `getConfigUint32` without a 16-bit Block limit;
- `include/config.h` blob `539c5f3d`, metatile attribute masks are `uint32_t` while Block masks are `uint16_t`;
- `src/core/block.cpp` blob `fc4fe774`, Block masks are separately limited to 16-bit;
- `src/ui/projectsettingseditor.cpp` blob `0df96149`, project settings can set the behavior mask from the UI, subject to attribute-size UI maximum.

The source checker pins all five complete Git blob identities and representative anchors, with five new dependency-source negative controls. A 31-set-bit metatile attribute mask is therefore a **source-reachable configuration candidate**, but no actual project settings or MainWindow execution of this malformed mask has been observed. No production crash claim is made.
