# Phase 1 P0 — Porymap reciprocal connection offsets have an INT_MIN boundary

**27 October 2026 · EXACT-PINNED SOURCE REVIEW · NOT APPROVED.** Porymap `huderlem/porymap@26b919d7ff4b54152de010abd5bf344af2ebe116`; FireRed `pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982`. This is a **representability and caller-precondition** finding, not a demonstrated editor crash or a native ROM bug. Phase 1 **FAIL_INCOMPLETE**, independent approvals **0/14,834**.

## Source provenance

| Repo | Exact file | Git blob SHA-1 | Anchors |
| --- | --- | --- | --- |
| Porymap | `src/core/parseutil.cpp` | `a1c3e69daed3f04d7ed64e1a34bd95db56137ae2` | 767–778 JSON integer conversion |
| Porymap | `src/project.cpp` | `d43b0949303433111d4478ad76117c2b3445dd13` | 488–500 connection JSON import |
| Porymap | `include/core/mapconnection.h` | `40713d3a26157fce7a36465858e8273c78dc12f6` | 35–36 offset getter/setter; 62 signed member |
| Porymap | `src/core/mapconnection.cpp` | `d2d3f0460c6a52669ca8f6856bfe7ec3103cd9e4` | 19–26 reciprocal match; 44–47 create mirror; 155–169 edit mirror |
| Porymap | `src/core/editcommands.cpp` | `684d98c7ea8b2c600a5fb8888831b95723e741f3` | 703–725 mirrored add and redo |
| Porymap | `src/config.cpp` | `9264f99bb18e0a725ef023f514c00df529d1d28d` | 324–336 default mirror preference |
| FireRed | `tools/mapjson/mapjson.cpp` | `8d8ec4e4e6e1c011b06f00819abe40bad10d19d5` | 188–209 per-map connection text emission |
| FireRed | `asm/macros/map.inc` | `83ef472c926ce767c9133ab9bd6922280b38bb2d` | 146–153 native 4-byte offset |
| FireRed | `include/global.fieldmap.h` | `e2828ec0cb1439718e830fbef4366770b3b77b1c` | 177–188 native unsigned 32-bit field |

## OFF-001 — the JSON input and reciprocal operation have different domains

Porymap loads each connection's `offset` via `ParseUtil::jsonToInt` into a C++ `int` (project.cpp:488–498). The JSON-number path delegates to `QJsonValue::toInt()` (parseutil.cpp:767–778); a representable signed integer value is therefore not restricted to a symmetric range. The connection model stores an `int m_offset` (mapconnection.h:35–36,62).

The reciprocal relation is defined by **negation**: `MapConnection::areMirrored` tests `a->m_offset == -b->m_offset` (mapconnection.cpp:19–26), `createMirror` constructs a new connection with `-m_offset` (44–47), and mirrored `setOffset` calls `connection->setOffset(-offset, false)` (155–169). On conventional 32-bit two's-complement `int`, **-2147483648 is representable but +2147483648 is not**. Applying unary minus to `INT_MIN` therefore has undefined signed-overflow behaviour in standard C++. The same boundary exists for the minimum representable `int` on any two's-complement width.

This is an **input-conditioned source hazard**. It does not establish that an ordinary authored FireRed map contains such an offset, that the Qt editor can enter it through the normal drag UI, or that a real editor run crashed. The relevant call paths are conditional on finding a matching mirror or creating one (including `MapConnectionAdd` with mirroring enabled). Other valid signed offsets have representable negations.

## OFF-002 — native storage is not an authorization to mirror every value

The pinned FireRed assembler writes the connection offset with `.4byte` (map.inc:146–153); the native C structure exposes `u32 offset` (global.fieldmap.h:177–188). This permits a 32-bit **bit pattern** but does not provide a second signed `int` value that is the mathematical negative of `INT_MIN`. A project/ROM merger must distinguish a valid native 32-bit offset field from an editor-level reciprocal relationship that cannot be represented in the same signed type.

**Acceptance obligation:** preserve the original authored value and native bit pattern, validate the representable signed domain before reciprocal negation, and fail closed or mark the mirror association nonrepresentable rather than silently wrapping or changing source IDs. Test `INT_MIN`, `INT_MIN+1`, `-1`, `0`, `1`, and `INT_MAX` through Porymap JSON import, mirror toggle on/off, add/edit/undo, Save Current/All, and FireRed assembler output. Include both debug-checked and sanitized Qt builds and verify caller-level range constraints. No such editor/runtime/compiled boundary test is claimed here.

## Review disposition

The source chain identifies **three unguarded reciprocal negations** with a conditional representability boundary. The next gate is an actual Qt and compiled assembler fixture, including a review of source-origin validation and UI range clamping. The complete upstream files above have **not** been independently reviewed or approved; this dossier does not increase the analyst whole-file candidate count. **Phase 1 remains FAIL_INCOMPLETE.**
