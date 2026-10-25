# XGBA Phase 1 — v1.6 focused semantic dependencies

**Scope:** 4,685 source/config files inventoried, 14,834 files total. This document records **directly inspected, source-hash-pinned semantic paths**, not signed acceptance of all source files or a built emulator. Parser-generated graphs are a separate, tentative evidence layer.

## 1. CPU instruction fetch and ROM data access require distinct extension hooks

- [mGBA src/arm/arm.c:198-225](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/arm/arm.c#L198-L225), pinned blob `0b92d7f55f1fb853d4b1b9c9163ee086126066e2`: ARM and Thumb instruction steps advance `cpu->prefetch` using `LOAD_32` / `LOAD_16` with `cpu->memory.activeRegion` and `activeMask`, bypassing the generic `GBALoad*` ROM functions.
- [mGBA src/gba/memory.c:285-377](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L285-L377), pinned blob `aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc`: CPU `setActiveRegion` sets `activeRegion = memory->rom` and `activeMask = romMask` for ROM windows; if the PC falls beyond `romSize`, it can route execution to `_deadbeef`/crash path, except compatible special cases.
- [mGBA memory.c:586-625](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L586-L625) and [memory.c:701-716](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L701-L716): data-load paths use separate `romSize` checks and handle EEPROM/e-Reader/other mapped cases.

**Semantics:** changing ordinary reads does *not* change the CPU's prefetch memory base. A bank transition must coherently update instruction-region mapping, the active mask, prefetch reconstruction and data reads. **Design contract XS16-CPU-ROM-COHERENCE:** unmapped or inaccessible windows must fail closed; vanilla execution timing, ARM/Thumb widths, debugger reads and breakpoints must be preserved.

**Required but unexecuted tests:** CPU ARM/Thumb execution across a remap, data reads vs instruction fetch, invalid bank crash handling, ROM mirror regions, debugger/disassembler/cheats, snapshot/rewind across remap.

## 2. ROM2_EX is shared with EEPROM and platform cartridges

- [mGBA memory.c:611-624](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/memory.c#L611-L624): 16-bit loads at `GBA_REGION_ROM2_EX` dispatch to EEPROM or e-Reader before ordinary ROM when enabled.
- [mGBA src/gba/dma.c:259-330](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/dma.c#L259-L330), pinned blob `da2a800ba48cb32d6e10e42c3b3527ef406bad22`: DMA fetches via `cpu->memory.load32/load16`, but the 16-bit DMA path explicitly reads and writes EEPROM when source/destination is `ROM2_EX`; source- and destination-region boundary transitions affect cached timing.
- [mGBA src/gba/cart/matrix.c:16-79](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L16-L79), pinned blob `9ccbe883235b98bcf56cd609015e7b4003aa832c`: Matrix uses mapped bank state, validates size/offset constraints and physically loads ranges from `romVf` into `memory->rom`.
- [Matrix:100-128](https://github.com/mgba-emu/mgba/blob/fd9dc5c2cbf234365068855851107e762fc6211b/src/gba/cart/matrix.c#L100-L128): remapping state participates in savestate serialization/deserialization.

**Semantics:** a magic address or signature that conflicts with legacy EEPROM, e-Reader or Matrix commands risks data corruption. **Design contract XS16-PERIPHERAL-ARBITRATION:** XGBA extension activation must be explicit and opt-in; native device access remains authoritative for unextended images; compatible cartridges must not be reinterpreted. Matrix remapping and extension remapping cannot both mutate the same backing bytes without policy.

**Required tests:** EEPROM save and detect, DMA 16/32-bit, DMA region wrap, e-Reader read, Matrix register commands and state restoration, vanilla behavior at ROM2_EX.

## 3. FireRed script `word` operands have incompatible pointer *roles*

- [FireRed src/script.c:113-131](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c#L113-L131), [165-195](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/script.c#L165-L195), blob `d0433bdda062b138e53d1a1d3184b4566ad7d9dc`: interpreter advances an actual `scriptPtr` and decodes little-endian 32-bit operands.
- [FireRed src/scrcmd.c:92-123](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L92-L123), blob `97b695ee2f6fca80a3b78f52f6a444f696fe5814`: selected `ScriptReadWord` results become **native function pointers**, not script targets.
- [FireRed scrcmd.c:133-150](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L133-L150): other operands are script jump/call pointers.
- [FireRed scrcmd.c:286-333](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/scrcmd.c#L286-L333): other operands load/store bytes through cast pointers, including unguarded `*(u8*)ScriptReadWord`.

**Semantics:** a blanket `32-bit word = external resource handle` translation is not sound. **Design contract XS16-TYPED-SCRIPT-OPERANDS:** classify commands by operand ABI and only relocate explicitly negotiated data/script-resource references. Native function targets and writable RAM pointers require separate validation; vanilla bytecode and control flow remain byte-identical. Do not silently accept an external handle in `gotonative`, `callnative`, or raw memory-store commands.

**Required tests:** every opcode's argument kind, script PC/call-stack return across banks, 8/16/32-bit data access, native function callbacks, mismatched handle handling, save/load pending script context.

## 4. Map data has independent typed-event and mutable tile/collision lifecycles

- [Porymap src/project.cpp:290-346](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L290-L346), blob `d43b0949303433111d4478ad76117c2b3445dd13`: map loading invokes `loadMapData` and separate `loadLayout`; the layout loads tilesets, blockdata and border.
- [Porymap project.cpp:411-485](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/project.cpp#L411-L485): map JSON declares layout ID and separate object/warp/coord/background events; events deserialize into typed groups and heal locations are associated separately.
- [Porymap src/core/maplayout.cpp:104-149](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp#L104-L149), blob `44616ab6c9c3ea9b04eff011586b7ec29183588f`: mutable map blocks carry metatile ID, collision and elevation, and editing can trigger change callbacks.
- [Porymap maplayout.cpp:373-444](https://github.com/huderlem/porymap/blob/26b919d7ff4b54152de010abd5bf344af2ebe116/src/core/maplayout.cpp#L373-L444): tile rendering and collision rendering are distinct passes.
- [FireRed src/fieldmap.c:103-111](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/fieldmap.c#L103-L111), blob `41567772299000ba5855419e5c39ad9373a34c20`: runtime loads tile-grid data from `MapLayout.map` into a mutable virtual map.
- [FireRed fieldmap.c:401-417](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/fieldmap.c#L401-L417): separate map-grid operations update metatile entries and preserve/select elevation bits.

**Semantics:** a rasterized screenshot or flat tile array does *not* preserve event identities, warp links, object script targets or layer/collision semantics. **Design contract XS16-EDITOR-LOSSLESSNESS:** imported source-project formats must reconstruct separate layout, border, tileset, typed events, scripts, collision/elevation and map connections; for bare ROMs, report undecodable or heuristic semantics honestly. Export must round-trip IDs and unknown fields without flattening. A standalone ROM cannot be assumed to retain the original authoring JSON.

**Required tests:** JSON→editor→JSON no-op, event move and warp retarget, collision/elevation edit, layered tile palette continuity, imported compiled ROM uncertainty, two maps sharing a layout.

## 5. Savestates and game saves use different lifecycle and identity contracts

See [v1.5 contracts](CRITICAL_SOURCE_CONTRACTS_v15.md) for mGBA savestate CRC/serialization and FireRed randomized save-block relocation/encryption. **Design contract XS16-SAVE-SEPARATION:** an emulator XGBA save-state extension (host-side) must separately validate sidecar identity and remapping sequence, while in-game FireRed saves need stable resource IDs and must never persist transient host addresses. These are two distinct serialization formats.

## 6. Evidence and completion policy

- **Source confirmed:** the paths, branching decisions and read/write roles described above can be reproduced at the pinned revisions.
- **AST candidate:** cross-file call targets inferred from syntax trees only; subject to macro expansion, build flags, function-pointer aliases, templates and duplicate symbols.
- **Not yet verified:** compiler/linker ABI, generated map/resource table boundaries, full ROM binary layout, per-file side effects, external sidecar streaming throughput, all plugins/editor round-tripping, unexamined third-party/vendor code.
- **Signoff:** no file is marked `reviewed_not_relevant` just because it is an asset, vendor source or has zero lexical matches. A large automated call graph is *not* comprehensive semantic understanding by itself.

**Phase 1 acceptance:** FAIL_INCOMPLETE, pending source-backed dispositions and validated scope/exclusions for every tracked file. No implementation change here.
