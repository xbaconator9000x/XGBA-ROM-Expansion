# Phase 1 semantic disposition candidate 0007 — FireRed miscellaneous assembler constants

**State: PENDING_INDEPENDENT_REVIEW; NOT APPROVED.** Whole-file source-grounded analyst candidate. It is not an independent reviewer verdict, accepted disposition or proof of ROM expansion.

## Pinned source identity and coverage
- Upstream repository: `pret/pokefirered`; commit: `ce6406d8c2eaf46d543c8a2606de0c3cb1951982`.
- Entire [`constants/misc_constants.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/misc_constants.inc); exact Git blob SHA-1 `621ba2af89d25f44fee3c8507c50b34cd584ccc1`, verified from the pinned GitHub file response.
- 22 authored lines plus trailing newline. **All 17 assembler `.set` definitions** are covered: three scalar/sentinel definitions, twelve sprite-size/shape encodings and two image-animation flip flags. There are no executable instructions, labels, storage declarations, conditional branches, or byte emissions in this file.

## Entire-file semantic interpretation
1. Lines 1–4 set `TRUE=1`, `FALSE=0`, and `NULL=0` as assembler symbols. These are constants, not C pointer declarations, runtime addresses or independently allocated storage.
2. Lines 6–9 encode square sprite dimensions 8×8, 16×16, 32×32 and 64×64 by combining `OAM_SIZE_0..3 >> 28` with `OAM_SQUARE >> 14`. Given the exact upstream `constants/gba_constants.inc` definitions, the resulting values are **0, 4, 8, 12**.
3. Lines 11–14 encode horizontal rectangle sizes 16×8, 32×8, 32×16, 64×32 using `OAM_H_RECTANGLE >> 14` and the same size selectors. Resulting values are **1, 5, 9, 13**.
4. Lines 16–19 encode vertical rectangle sizes 8×16, 8×32, 16×32, 32×64 using `OAM_V_RECTANGLE >> 14`. Resulting values are **2, 6, 10, 14**.
5. Lines 21–22 set `OBJ_IMAGE_ANIM_H_FLIP = 1 << 6 = 0x40` and `OBJ_IMAGE_ANIM_V_FLIP = 1 << 7 = 0x80`. These are animation-flag masks in the source; this file does not establish every animation consumer's interpretation.

## Cross-file dependency and XGBA relevance
- Exact pinned producer [`constants/gba_constants.inc`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/constants/gba_constants.inc), Git blob `3ff857ee8dfb1f4e2dfaf8ac98373bac5dfdb25c`, lines 469–475: `OAM_SQUARE=0`, `OAM_H_RECTANGLE=0x4000`, `OAM_V_RECTANGLE=0x8000`, `OAM_SIZE_0=0`, `OAM_SIZE_1=0x40000000`, `OAM_SIZE_2=0x80000000`, `OAM_SIZE_3=0xc0000000`. Source arithmetic explains the packed four-bit shape/size values above.
- Pinned [`src/crt0.s`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/src/crt0.s), blob `a0d8a4b55237b38afc5b69d4e9aad0c2df232e14`, includes this constants file. Inclusion establishes availability of the symbols, not actual use of each definition by startup.
- Sprite shape/size encodings are finite graphics ABI constants; they **do not** specify ROM pointer width, external bank format or a larger cartridge address space. A future editor/asset pipeline must preserve these encodings when converting sprites, rather than treating the `SPRITE_SIZE_*` values as literal pixel counts.

## Independent reviewer checklist and unresolved proofs
- Re-read the exact pinned entire file and producer constants; independently confirm all 17 definitions and twelve arithmetic results, including precedence/shift behaviour under the actual assembler.
- Enumerate all pinned upstream source consumers of each symbol, not only the known `crt0.s` include; verify assembler symbol redefinitions and conditional build variants where applicable.
- For graphics assets, compare encoded shape/size and flip flags against compiled sprite/animation consumers and editor export/import representations. These checks are **not** claimed completed.
- Record a distinct independent reviewer, date, complete-file verdict and supporting evidence; use the actual gate ingestion format. No self-approval or manual gate-count editing.

**Verification level:** exact Git blob identities and source arithmetic, no compiled asset round-trip or independent review. **Gate contribution: zero. Phase 1: FAIL_INCOMPLETE; 0/14,834 approved.**
