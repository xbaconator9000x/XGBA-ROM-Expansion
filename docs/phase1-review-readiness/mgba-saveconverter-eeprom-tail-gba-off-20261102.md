# Phase 1 — EEPROM RTC-tail conversion and GBA-disabled Qt compile closure

**Disposition:** bounded source/host evidence only; not a semantic approval.
The source remains unchanged. This note does not alter the legacy evaluator,
gate, or approval counts. Gate status remains `FAIL_INCOMPLETE`; independent
approvals remain `0`.

## Pinned provenance

- mGBA commit: `fd9dc5c2cbf234365068855851107e762fc6211b`
- `src/platform/qt/SaveConverter.cpp` Git blob:
  `4c32280c9c5288e806ffd237119186e2a633c4a7`
- Source SHA-256:
  `3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f`
- `include/mgba/internal/gba/memory.h` Git blob:
  `0aad912613e726560d06bbdbf6061986e69e5842`
- Memory-header SHA-256:
  `fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41`
- Source file notice: MPL-2.0. No upstream source was changed or vendored.
  This bounded test does not determine combined-distribution licensing rights.
- Compressed machine dossier: Git blob
  `3b982876c7d810a827af8c80c7e5d9231fdaa327`, SHA-256
  `1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609`.
  The pinned file is row 11744; canonical per-file row SHA-256:
  `dc4112a41e57a7496c02986e900cb3d089cc081ae36ee02f4df479d0fc890357`.

The EEPROM harness extracts and compiles the original pinned function bodies,
after checking the source commit, Git blobs, SHA-256 values, byte offsets and
per-function hashes. The captured function hashes are:

| Original method | SHA-256 |
| --- | --- |
| `detectFromSize` | `30ca11a50224c7e7222fe169a85a84a5749331506d7230b6b940b5656de25693` |
| `AnnotatedSave::asRaw` | `b84a0b61acf676453134f702ac5b5491ddb9c6c4637a442055ddd11963463c0f` |
| `AnnotatedSave::operator==` | `7b4e9373110673020d9934aa7bf53e74b2447ab7c3a57e851318c7cdd8ce5299` |
| `AnnotatedSave::possibleConversions` | `6974552e6a38b6bcffa6bd92bab05f7dca87dfb0b99a8d78fb7652b5e99a7d01` |
| `AnnotatedSave::convertTo` | `7ad4cfd2ca18ff21e265bc7cbe86df3c2b60a852fac9436f68a7540b9c40c3dc` |

Harness fixture SHA-256:
`90ef78f72ba584bb60e2edbd9e4e51ff0f68b279192fb8b9da7c00003b2f4e9b`.

## Native Qt6 EEPROM test

Local command:

```sh
python3 -m py_compile tools/phase1_mgba_saveconverter_eeprom_tail.py
python3 tools/phase1_mgba_saveconverter_eeprom_tail.py \
  --checkout /tmp/xgba-mgba-core-lifetime \
  --harness tests/phase1_mgba_saveconverter_eeprom_tail.cpp \
  --root .
```

The harness compiled with GCC 13.3.0 and native Qt6 Core 6.4.2
(`-std=c++17 -fPIC -O0 -g -Wall`). It exercised both accepted payload-plus-16
sizes: 512-byte EEPROM plus 16 bytes and 8-KiB EEPROM plus 16 bytes. It also
checked both exact payload sizes and detector rejection at one byte below and
one byte above the accepted RTC-tail size. The payload passed the native
endian-conversion round trip in both cases. Three source mutations (conversion
loop bound, accepted size, and endian store) were rejected by pinned-source
validation.

Observed single-run output:

| Case | Source 16-byte suffix | Converted suffix | Preserved on convert? | Preserved on round trip? |
| --- | --- | --- | --- | --- |
| 512-byte EEPROM + 16 | `a0a1a2a3a4a5a6a7a8a9aaabacadaeaf` | `5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a5a` | no | no |
| 8-KiB EEPROM + 16 | `c0c1c2c3c4c5c6c7c8c9cacbcccdcecf` | `00000000000000000000000000000000` | no | no |

The suffix is accepted as part of the input size but the pinned endian
conversion loop processes only `size & ~0xFF` bytes. The two observed output
suffixes differ; the test does **not** treat either suffix value as a
zero-fill or preservation guarantee. In this execution the 512-byte
destination exposed a stale `0x5a` allocation pattern while the 8-KiB
destination contained zeroes. This is native Qt6 `QByteArray` behavior in a
controlled `VFileDevice` harness, not a real `QFile`, real mGBA application,
or real `.sav` observation.

## GBA-disabled Qt translation-unit compile

Local command:

```sh
python3 -m py_compile tools/phase1_mgba_saveconverter_gba_off.py
python3 tools/phase1_mgba_saveconverter_gba_off.py \
  --checkout /tmp/xgba-mgba-core-lifetime \
  --build-dir /tmp/xgba-mgba-gba-off-qt-check
```

The helper configures the pinned source with Qt enabled, `M_CORE_GBA=OFF`,
`M_CORE_GB=ON`, Qt6 Core/Widgets/Multimedia, and the optional scripting/debug
and unrelated library features disabled. It verifies CMake generated the Qt
target containing the original `SaveConverter.cpp` and that the actual
translation-unit flags omit `-DM_CORE_GBA`. After CMake Qt autogen and UI
header generation, it invokes the generated CMake object rule for
`qt/CMakeFiles/mgba-qt.dir/SaveConverter.cpp.o`.

The compile was attempted and **failed as expected** (compiler exit 2), with
GCC reporting unguarded GBA references in the original `detectFromHeaders()`
path, including:

```text
SaveConverter.cpp:277:30: error: ‘GBASavedataSharkPortGetPayload’ was not declared
SaveConverter.cpp:281:37: error: ‘GBA_SIZE_FLASH1M’ was not declared
SaveConverter.cpp:293:30: error: ‘GBASavedataGSVGetPayload’ was not declared
```

The complete observed compiler output also reports missing GBA savedata type
and size constants at lines 282–312. This confirms a compile-closure failure
for this pinned Qt translation unit under the tested `M_CORE_GBA=OFF`
configuration. The Qt frontend was not linked, and no upstream fix is included.

## Evidence boundary and review status

These are source-derived native host tests and an attempted native Qt
translation-unit compile. They do not establish full application behavior,
real file persistence, `.sav` restart/interoperability, stock gameplay,
physical Flash behavior, or combined distribution licensing. The compile
result is a reproducible failure observation, not an instruction to patch
upstream here. No independent review receipt is created and no approval or
gate count changes.

## Exact-head workflow status

The workflow was triggered for commit
`01eb42af254e10254760937b7e45f14491a72e3e` on the existing PR13 branch.
GitHub Actions run [#41424775602](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/41424775602)
reported `action_required` with **zero jobs**. This is a workflow permission
blocker, not an executed pass or failure; no Actions step evidence exists for
this commit. The native tests and compile attempt listed above were executed
locally only. No permission bypass or retry was attempted.
