# mGBA mCore savestate clone caller boundary — Phase 1

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**. This packet is a bounded caller witness, not a semantic approval.

## Selected caller and pinned source

At mGBA revision `fd9dc5c2cbf234365068855851107e762fc6211b` (tree `5863e657d270d0fe3ccaa4299f48d5689d74fa1f`), `src/core/serialize.c` `mCoreSaveStateNamed` calls `core->savedataClone` when `SAVESTATE_SAVEDATA` is set. It adds `EXTDATA_SAVEDATA` only for a nonzero returned size, then serializes extdata and returns true on the non-PNG path. The exact caller body SHA-256 is `9e654c196c14fadd1e9f98c9c055fa0e7f9f07164a366a4a35c31719bb57648b`; the whole-file SHA-256 is `45fb69d5da0c0c4c135efb2641c7d1c6140d575b1819f60a45985ebfa0081f3c`, Git blob `ff8a9a86747336bd792bf9c964c53f232a702a08`, and canonical dossier-row SHA-256 `e9ad34d5514e106adc1f56111abf530b72118d1780d8593ae490ee63772ab9b5`.

The GBA registration in `src/gba/core.c` points `core->savedataClone` at `_GBACoreSavedataClone`. That callback returns zero both when `GBASavedataSize` is zero and when VFile construction or `GBASavedataClone` fails. `GBASavedataClone` can itself return false. Those bodies, interface declarations, and ten relevant source identities are pinned in the JSON receipt; the GBA callback path is source-traced, not compiled or executed here. All ten selected files carry MPL-2.0 notices.

This is distinct from the existing direct `_GBACoreSavedataRestore(writeback=true)` witness: it exercises the mCore savestate writer’s consumption of the separate `savedataClone` result, not restore, POSIX descriptor ownership, VFile sync/teardown, or save-file reopen.

## Executable witness

`tools/phase1_mgba_core_savestate_clone.py` validates the pinned mGBA commit/tree, source Git blobs, full-byte SHA-256 hashes, dossier archive and row hashes, MPL notices, and exact function-body hashes. It extracts the unchanged `mCoreSaveStateNamed` and extdata helper bodies into `tests/phase1_mgba_core_savestate_clone.c`, compiles them, and checks:

1. A nonzero clone result appears in serialized savedata extdata with the original payload.
2. A no-save zero result and a fixture-injected clone-failure zero result produce the same caller success and omitted extdata.
3. With the savedata flag off, the callback is not called and savedata extdata is absent.
4. A later successful clone retry includes savedata extdata again.

The runner rejects seven source mutations and six contradictory or incomplete output mutations. Its fixture uses an in-memory VFile and a controlled `mCore.savedataClone` callback. This is compiled extracted-source/host-fixture evidence, not execution of the full mGBA core.

## Objections and limits

- The zero return is not uniquely an error: pinned GBA code also returns zero when no save data exists. The caller cannot distinguish those outcomes from the size alone; the test does not claim that every zero return is a failure.
- The fixture injects zero at the callback boundary. It does not reproduce a natural allocation or VFile failure and does not execute the pinned GBA callback.
- The serialized bytes are read back only by the pinned extdata helper in the bounded fixture. This is not a frontend savestate round trip, emulator restart, or cross-version compatibility test.
- The mock VFile does not establish POSIX/stdio/console backend behavior, filesystem persistence, or durability.
- No `.sav` interoperability, stock gameplay, physical Flash, independent approval, or gate completion is claimed. The receipt retains `NEEDS_EVIDENCE`, `FAIL_INCOMPLETE`, and zero approvals.

The PR #35 source handoffs independently identified the need to trace actual mCore savedataClone consumers and noted that the serializer/round-trip path was not exercised. This witness closes only the bounded `mCoreSaveStateNamed` clone-result-consumption question; `mCoreLoadStateNamed`, Qt report export, RTC behavior, and remaining backend/runtime obligations stay open.
