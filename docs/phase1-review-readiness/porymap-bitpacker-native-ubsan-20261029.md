# Phase 1 — pinned original Porymap BitPacker native Qt UBSan boundary (2026-10-29)

Status: **EXPERIMENTAL until exact-head CI finishes; FAIL_INCOMPLETE**. This is test-only native host Qt6 C++, not FireRed agbcc/ARM, mGBA gameplay, editor GUI or physical hardware. No original source is modified.

Immutable upstream: `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; `src/core/bitpacker.cpp` Git blob `34f86b4e3910021613a1d090746ae53a1c6782a2`; `include/core/bitpacker.h` Git blob `4e3767e48449a974bfe1d9c63c5bf63dd2826fe9`.

## Source and expected boundary

Original `BitPacker::setMask` loops over set bits and stores `1 << i` (line 18); it then calculates `m_maxValue` using `(1 << m_setBits.length()) - 1` (line 21), except at 32 bits. Under C++17, shifting into bit 31 itself is not necessarily diagnosed by UBSan; **do not infer a high-bit defect merely from that expression**. With 31 set bits (`0x7fffffff`), the subsequent signed subtraction from `INT_MIN` is an actual sanitizer candidate. The separate `0x80000000` and `0xffffffff` controls distinguish this case.

Test-only harness compiles the **unchanged original .cpp and .h** with native Qt6 and GCC UBSan, then runs separate subprocesses for masks `0x0f`, `0x80000000`, `0xffffffff`, `0x7fffffff`. The last must fail at original line 21 with `signed integer overflow`; three controls must succeed. Six scoped source and twelve evidence negative controls must reject forgery. The runner preserves actual stderr and JSON evidence.

## Reviewer obligations and limitations

Independently inspect the complete pinned sources, source line 21, Qt QList semantics, callers/actual mask constraints and build configuration; reproduce under GCC/Clang where feasible. Check whether production masks can have 31 set bits before assessing practical reachability. No editor file-write or ROM gameplay claim is supported. Upstream license/notice reconciliation remains pending. This partial dossier is **not whole-file coverage**, has no distinct reviewer or machine dossier validation, and contributes **zero** independent semantic approvals. Authoritative Phase 1 gate stays `FAIL_INCOMPLETE`.
