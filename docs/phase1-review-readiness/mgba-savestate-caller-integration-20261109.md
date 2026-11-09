# Pinned mGBA savestate caller integration

Status: **NEEDS_EVIDENCE / FAIL_INCOMPLETE**. Independent approvals: **0**.

This follow-up closes a different evidence gap from the prior restore-consumer
receipt: the original `retro_unserialize` caller in pinned
`src/platform/libretro/libretro.c` is now compiled and exercised around the
already-pinned core/GBA restore closure. The Qt and SDL production callers are
traced with full-file identities, but are not executed.

The source trace finds that libretro's `retro_serialize_size` and
`retro_serialize` call `mCoreSaveStateNamed` with
`SAVESTATE_SAVEDATA | SAVESTATE_RTC`. The pinned core serializer puts a
`SAVESTATE_SAVEDATA` clone into `EXTDATA_SAVEDATA` only when `savedataClone`
returns a nonzero size. `retro_unserialize` constructs a const-memory VFile,
calls `mCoreLoadStateNamed` with `SAVESTATE_RTC`, closes that input VFile and
returns the core loader's result. The restore flag omits
`SAVESTATE_SAVEDATA`, so the GBA callback takes its deferred savedata mask path
for a present extdata item.

The compiled host witness runs the unchanged extracted `retro_unserialize`
body with the exact pinned restore functions and complete pinned VFile memory
translation unit. It checks valid core bytes with absent extdata, short
extdata headers and payloads, a short fixed-size core state, and a valid retry
after a malformed extdata attempt. The caller closes each input VFile; the
short core state returns false through the caller, while malformed extdata
does not prevent a true core-state load. The valid case transfers the temporary
savedata VFile to the mask and later applies/closes it on unmask.

Qt's default save flags include savedata extdata. Its named and QIODevice load
paths close their input VFiles and emit `stateLoaded` only on a true loader
result; those Qt paths and backup recovery are source-traced only. SDL's
`_loadState` ignores the loader result, and `mSDLRun` closes the VFile after the
core-thread callback; the SDL frontend is likewise not run. The existing PR #13
restore-consumer receipt already records the headless caller and core restore
closure. PR #35's savedata and VFile wrapper-allocation receipts cover distinct
backend/source obligations and do not execute these load callers.

The three new per-file records bind Git blob IDs, full-byte SHA-256 values,
canonical pinned-dossier row hashes, MPL-2.0 notices, limited review scopes,
dependencies and objections. The compressed dossier SHA-256 was independently
verified. Three source-body and six output mutation controls fail closed.
Transitive licensing, native GUI/libretro behavior, natural user-produced
malformed states, durable savestate/`.sav` persistence, stock gameplay and
physical Flash remain unproven. This evidence is not semantic approval.
