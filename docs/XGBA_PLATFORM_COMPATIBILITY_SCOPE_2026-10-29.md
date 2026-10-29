# XGBA scope: general GBA expansion and compatibility with existing ROM hacks

**Date:** 29 October 2026  
**Status:** Accepted *design objective*; not an implementation, verified conversion, or Phase 1 semantic approval.

## Product objective and boundaries

XGBA is a **reusable, emulator-first GBA expansion platform**. FireRed is the first thoroughly researched integration, **not** the scope limit. Importing an existing, already modified ROM hack—including a FireRed-derived hack such as Team Rocket Edition, or an engine expansion with additional Pokémon—must be a first-class use case, rather than requiring the author to start again with vanilla FireRed.

The five currently pinned repositories (FireRed, mGBA, agbcc, Porymap, Poryscript) map a broad set of GBA hardware/emulator/build/editor contracts. They **do not** amount to semantic knowledge of every GBA game, downstream FireRed fork or binary patch. A modified ROM may have changed pointers, tables, save layouts, code relocation or custom loaders. Reusing the GBA-level memory mechanism is possible; automatically making a game use it requires separately proven engine integration.

## Architectural layers

1. **General GBA runtime layer:** Model CPU ROM aperture, cartridge bus, instruction fetching and prefetch, DMA and peripheral arbitration, save memory, and save-state restoration. Define an opt-in, versioned logical resource addressing protocol for large external backing stores, with accurate resource identity and bounds checking. Never pretend the GBA processor has acquired unlimited directly addressable memory. Preserve ordinary unmodified-ROM behavior.
2. **Game/engine adapter layer:** For each supported game or engine family, declare source and/or binary fingerprints, modification/variant recognition, pointer and relocation rules, resource formats and lifetimes, compiler/linker integration, save ABI, and tested hooks. FireRed decomp is first; distinct forks, binary ROM hacks, and other GBA titles require evidence-backed adapters or compatibility profiles.
3. **Read-only discovery layer:** Inspect supplied ROM bytes and identify exact known builds. Report game metadata, cryptographic identity, compatible profiles, missing information, and risks. Recognize “unknown” and “modified” as genuinely unknown until positive identification; do not identify Team Rocket Edition or CFRU merely from a title, four-letter game code, size or superficial similarity.
4. **Opt-in transformation layer (future Phase 2+):** Use a source-grounded recompile when available; otherwise use a strictly fingerprint-scoped binary conversion backed by relocation proofs and pre/postcondition checks. Record all changed offsets and original bytes in a signed or hash-bound transformation manifest. Do not automatically patch unknown or unreviewed ROMs.
5. **Runtime and tool interoperability:** The emulator, expansion pack, editor, compiler, linker and patcher share one versioned manifest, with deterministic failure when an expansion pack is missing or mismatched. Target desktop and Android compatibility as primary uses; physical cartridge support is optional future work.

## Explicit compatibility states

- **SUPPORTED_EXACT:** The input ROM SHA-256, byte length, engine profile, adapter version and required evidence all match an approved and tested conversion profile. *This is the only state eligible for automated binary transformation.*
- **KNOWN_FAMILY_UNVERIFIED_VARIANT:** The broad engine family may be known, but the precise ROM build or modification is not established. This is inspection-only, not a conversion approval.
- **UNKNOWN_ROM:** Engine or fork unknown. Inspection-only.
- **INVALID_OR_UNSAFE_INPUT:** Invalid container/header, resource limits, or inconsistent metadata. No transformation.

A GBA header, game code or presumed base version is *not* sufficient to promote a modified hack to SUPPORTED_EXACT. Conversely, a valid but unknown ROM is not automatically dangerous; it simply lacks an approved adapter.

## Acceptance tests and gates

- Import stock supported builds, known forks, modified standalone ROMs, unknown games and intentionally corrupted ROMs. All are recognized or accurately rejected without modifying source bytes.
- Exact build fingerprints and pinned manifests control acceptance. A one-byte mutation of an approved build must invalidate exact approval, even when the game title/code/size is unchanged.
- A known game family alone must never silently inherit a vanilla engine adapter. Missing evidence leaves the conversion blocked with a documented path for developing a new profile.
- Confirm actual compiled output, game boot, map loading, field scripts, battles, graphics/audio, long-running gameplay, save-write/read and cold reboot, save-state restore, and editor reimport; include negative tests for truncated resource packs, changed backing hashes, DMA/peripheral overlap and code prefetch coherence.
- Verify no original save data is silently overwritten or interpreted under a different save schema.
- Produce a complete conversion manifest: input hashes, profile provenance, required emulator features, relocated resources, changed references/bytes, tests, outputs and rollback metadata.
- Provide a compatibility report understandable to nontechnical ROM hackers and a precise diagnosis for developers.

## Existing Phase 1 relationship

The current Phase 1 still demands independent semantic dispositions and the full inventory, dependency, compiler/linker, emulator, save/asset, editor interoperability and regression gates. Machine-generated rechecking and this architecture note are **not** semantic approvals. Do not relax the gate to make an existing hack appear supported. Relevant source constraints: [external resource banking contract](PHASE1_P0_EXTERNAL_RESOURCE_BANKING_CONTRACT_2026-10-26.md), [architecture-aware review triage](PHASE1_ARCHITECTURE_AWARE_REVIEW_TRIAGE_2026-10-26.md), and [authoritative Phase 1 status](PHASE1_STATUS.md).

## Initial research milestone

Implement a **read-only, fail-closed exact-profile discovery tool** and synthetic tests for unknown, altered and malformed ROMs. It must not patch inputs, claim that any ROM hack is supported without a pinned approved profile, or move Phase 1's completion state. Follow with game-specific source/binary compatibility research, not unsupported universal conversion promises.
