# Pinned mGBA ARM decode/emit closure review — 2026-11-02

**NON-APPROVING source review handoff.** Scope: six P0 packet entries from the immutable original packet and mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b`. This review adds no receipt, whole-file semantic disposition, or independent approval. The authoritative gate remains `FAIL_INCOMPLETE`; external approvals remain 0/338 P0 and 0/14,834 total.

## Immutable evidence

The original packet is `docs/phase1-review-readiness/packet-0000-0099.json`, Git blob `a48c12900acc7e0211a8071119763e2b5de4b1a4`. The original compressed `candidate_review_dossiers.jsonl.gz` bytes have SHA-256 `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609` and Git blob `3b982876c7d810a827af8c80c7e5d9231fdaa327`. All six rows below were rehashed from that original 14,834-row archive and match their packet identities.

| Packet | Pinned file | Lines | Git blob SHA-1 | Source SHA-256 | Original dossier SHA-256 | Disposition |
|---:|---|---:|---|---|---|---|
| 10 | `include/mgba/internal/arm/arm.h` | 217 | `5ef2da96519ac3f429b65fd6d323be0775f3b3cf` | `47822ffc4592230f6045dd2d8677dec5d72f518bff0b42e15ff26b5c77330bef` | `aca7d604d669aced639ef33deb3a23ca309747d961c83972ec9baf8805ebd1b1` | `NEEDS_REVIEW` |
| 12 | `include/mgba/internal/arm/decoder.h` | 231 | `f6e19769884054b42b5fb77988b156d48b1c6489` | `d67f8d528e3d7090878df4c9d44cb4b1cdf1f5af0a68ae89a631c35b4ae39729` | `69bf00c7af7ef592cc5d115ebd892095fc4b55150a6690e299fcafec047f9f3e` | `NEEDS_EVIDENCE` |
| 27 | `include/mgba/internal/arm/emitter-arm.h` | 336 | `04c3715d2c2ba42fbd9644c0171111756723bbb8` | `ca5f3eb7d40bf8a6244002c160eed1cb36f6530d0567fa351107bb4660a5ccb2` | `53c0c115e727903bbab355b19ca6d7e4813f4b6c949c85bb38000df764277a57` | `NEEDS_EVIDENCE` |
| 68 | `src/arm/decoder-arm.c` | 466 | `074c04314a2a6d4c1c0133d38f128ab0e90d7b1d` | `8423b699b14681c8be12b3893865a10cb0bbb5281c88f9a0e7953338711a1083` | `c89dae86be2d3950707b164cc683909bf10ffead0cd3c9c9e1329f659c8eda35` | `NEEDS_REVIEW` |
| 69 | `src/arm/decoder-thumb.c` | 344 | `e96ae839613f846fbb477a6ddefc284a745c8e0d` | `627e5919e13c5c909193839c0fbc8069f55fb1e173c03d4ed5956e4168c1f4e0` | `585228eef510e0acd6cf7df901a04d63bca7f71bcc82e320b28d463ff9b7016f` | `NEEDS_REVIEW` |
| 70 | `src/arm/decoder.c` | 601 | `21ea0e872c32689b46f7ab746d871a7a1070c97c` | `0676c6934b3f3fbce0204b5aff8afb4cd85286db724f6ca04e0a626ad1180fd1` | `c2fdc6d4229837ff35c4786c446ecf25eef97fa1f11bc57f037c31f284581961` | `NEEDS_REVIEW` |

## Per-file findings and line anchors

* **#10 `arm.h` — `NEEDS_REVIEW`.** Lines 113–137 define the active-memory interface; line 127 makes `activeRegion` a `const uint32_t*`. The pinned `common.h:236–240` implements little-endian loads/stores through typed `uint32_t*`/`uint16_t*` dereferences. Pinned `src/gba/memory.c:320–335` assigns `uint16_t` palette/VRAM/OAM storage (including `video.h:105,225–227`) through `uint32_t*` casts; ARM prefetch uses the 32-bit helper (`isa-inlines.h:73–80`, `arm.c:201–217`). This is a concrete effective-type/strict-aliasing boundary for execution from those regions; alignment and cross-compiler behavior are not cleared. No miscompile or stock-ROM failure is claimed.
* **#12 `decoder.h` — `NEEDS_EVIDENCE`, not a standalone defect finding.** Lines 15–79 define operand and memory-format masks; lines 81–137 define conditions, access widths and branch flags; lines 196–222 define the output record and API. Exact pinned decoder sources compile and host fixtures consume representative fields. The record's C bitfield/ABI behavior has only been checked on the host compiler, and the declared resolver API's implementation has a reproduced undefined-behavior case (#70). These gaps prevent a receipt for the complete API/dependency contract.
* **#27 `emitter-arm.h` — `NEEDS_EVIDENCE`.** Lines 11–76 define table-expansion blocks; lines 78–334 enumerate the ARM dispatch classes, including BX/BKPT at 112–120 and B/BL at 299–300. The exact table producer compiles and its 4,096 entries are non-null in the host control. This is expansion/dispatch evidence, not an independent ARMv4T oracle for every slot or proof of the mapped handlers; handler dependencies retain unresolved source concerns below.
* **#68 `decoder-arm.c` — `NEEDS_REVIEW`.** The branch decoder at lines 355–365 shifts an unsigned opcode into `int32_t` and right-shifts a possibly negative signed value; conversion of out-of-range unsigned values to signed and right shift of negative values are implementation-defined in C11. GCC's pinned-source host control returns `-8` for `0xEAFFFFFE`, but that does not establish cross-toolchain behavior. `ARMDecodeARM` preserves condition `0xF` at line 462. The core execution path's `conditionLut[15]` is zero (`arm.c:182–199`) and skips it before dispatch (`207–215`), while debugger stack-trace code calls `ARMTestCondition` (`debugger.c:66–71`) whose default returns true (`isa-inlines.h:129–161`). The execution/debugger distinction is established; debugger interpretation of reserved NV instructions remains unverified.
* **#69 `decoder-thumb.c` — `NEEDS_REVIEW`.** Conditional branches convert the low byte to `int8_t` and left-shift it at lines 219–225; BL1 sign-extends via `int16_t` and left-shifts at lines 272–279. Compiling this exact pinned source with C11 UBSan and executing `ARMDecodeThumb(0xD080, ...)` reports `left shift of negative value -128`; `ARMDecodeThumb(0xF400, ...)` reports `left shift of negative value -32768`. The GBA idle-loop analyzer calls this decoder while scanning Thumb code (`src/gba/memory.c:173–181, 247–276`), so the paths are not merely disassembly fixtures. No particular authored-ROM trigger or emulator failure is claimed.
* **#70 `decoder.c` — `NEEDS_REVIEW`.** `ARMResolveMemoryAccess` takes a register offset at lines 573–577 and applies signed `offset <<= shiftSize` at lines 578–590. The actual debugger caller reaches it for indirect PC loads (`src/arm/debugger/debugger.c:121–124`). An exact-source host UBSan probe with `offset=-1`, `LSL #1` reports `left shift of negative value -1`; a second with subtract enabled and `offset=INT32_MIN` reports signed-negation overflow at line 600. These are debugger stack-trace paths, not evidence of failure in ordinary CPU execution.

## Connected objections and closure

The pre-existing packet #5 and #9 objections remain **unresolved**:

1. `macros.h:11–16` aliases accesses to `common.h` little-endian helpers; the typed-pointer implementations are at `common.h:234–240`. The actual GBA active-region casts and memory object types are shown above. A correctly typed aligned host fixture does not establish effective-type safety for the `uint16_t` video objects. No sanitizer result clears this C-language constraint.
2. `isa-inlines.h:29–31` uses signed left shifts in `ARM_SXT_8/16`. The original pinned consumers are `isa-arm.c:559–560` and `isa-thumb.c:287–288`; exact-source host UBSan reproduces negative-value left-shift diagnostics for `0xff` and `0xffff`. This is source-level UB, not a native emulator or stock-gameplay failure.

Other related details were bounded rather than treated as defects: `ARM_BORROW_FROM` returns `M >= N`, which is the ARM subtraction C/no-borrow flag used by the pinned `isa-arm.c` subtraction helpers; `ARM_WAIT_SMUL`'s current Thumb call passes a plain register lvalue and literal zero, and no `ARM_WAIT_UMUL` use was found in the pinned ARM/Thumb implementation. `ARMWritePC`/`ThumbWritePC` prefetch and active-region changes were traced to the GBA memory setup. These observations do not resolve the two objections.

All six target files carry an MPL-2.0 file notice; the pinned root `LICENSE` is MPL-2.0. The dependency closure is within pinned mGBA sources plus the C standard library. `src/arm/CMakeLists.txt:2–13` compiles the three decoder files and separates debugger sources; root `CMakeLists.txt:25–27` selects C11. File-notice mapping is not combined-work/distribution clearance. No dependency was added.

## Controls and limits

Run the deterministic verifier from the repository root after the pinned census checkout:

```sh
python3 tools/phase1_mgba_arm_decode_emit_review_verify.py --source-root upstream/mgba
```

It rehashes the packet and original compressed dossier archive, all six original dossier rows, the complete target files and relevant pinned dependency/build/license sources. It rejects 26 source-byte mutations plus six dossier-row mutations and one packet mutation. Its bounded GCC C11 host fixture compiles the actual decoder and execution-table producer sources; it verifies all 4,096 ARM and 1,024 Thumb table entries are populated, five representative decode cases, and two simple ADD execution cases. Six separate non-recovering UBSan controls are expected to fail on the reproduced signed shifts/negation (two Thumb branch cases, two resolver edges, and both sign-extension macros). Passing positive controls or expected sanitizer failures are not a full mGBA native link, cross-compiler test, emulator/gameplay run, save/restart, physical Flash test, or semantic approval.

No target meets the full receipt policy while these dependent objections and evidence gaps remain. No receipt or attestation is added; the original receipt register and authoritative gate are unchanged.
