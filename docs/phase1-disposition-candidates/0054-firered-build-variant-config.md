# Analyst whole-file candidate 0054 — FireRed build-variant configuration and debug/UB gates

**ANALYST-PREPARED ONLY — no independent review or Phase 1 gate credit.** Exact pinned file: [`pret/pokefirered@ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/config.h`](https://github.com/pret/pokefirered/blob/ce6406d8c2eaf46d543c8a2606de0c3cb1951982/include/config.h), Git blob SHA-1 **`db131b2717ab739e62e41c5054a798f045c0631d`**. The **complete 76-line file** (77 split lines including terminal newline) was inspected; no executable implementation is claimed from this header.

## Whole-file semantic disposition

| Lines | Meaning and dependencies |
| --- | --- |
| 1–4 | Include guard and `#include "global.h"`. `global.h:4` itself includes `config.h`, making inclusion order and guard state relevant. |
| 6–15 | Original FireRed asserts/debug commentary; `REVISION >= 0xA` defines `NDEBUG`. |
| 17–41 | Debug/pretty-print feature macros are provided when `!defined(NDEBUG) || REVISION >= 0xA`. Three pretty-print formats and three emulator/debug log handlers are enumerated; default handlers are disabled/AGBPrint. These are preprocessor selections, not evidence of actual logging output. |
| 43–48 | `FIRERED` versus default LeafGreen `GAME_VERSION` selection. |
| 50–57 | Revision 0 versus other revision `CODE_ROOT` string and `ABSPATH` macro. The path is a diagnostic source string, not a host filesystem dependency. |
| 59–63 | `ENGLISH` selects imperial units; otherwise metric units. |
| 65–74 | `MODERN` forcibly defines `BUGFIX` and `UBFIX` unless already set; modern mode changes semantics and is not a byte-exact original-behaviour guarantee. |
| 76 | Include guard closes. |

## Cross-file dependencies and reviewer obligations

Pinned `Makefile` blob `8b454dbd18eb0069fa5851d788697190890a5b37` passes `-DREVISION=$(GAME_REVISION)` and `-DMODERN=$(MODERN)` to C preprocessing (78–93). `config.mk` blob `c07d31fc083fa341cca29c340e560ed107d5364a` defaults `MODERN=0` and changes the build name for `MODERN=1`. The `MODERN=1` configuration therefore selects `UBFIX` in [the saved-map-view scan](../PHASE1_P0_FIRERED_MAPVIEW_SAVE_ARRAY_BOUNDARY_2026-10-27.md), while the original-compatible configuration does not automatically enable it.

**Include-order question:** `global.h:4` includes `config.h`, but `config.h:4` includes `global.h`. With `global.h` included first, `config.h` defines `UBFIX` before `global.h` defines its `SAFE_DIV` macro. If a translation unit includes `config.h` directly first, `global.h` may define `SAFE_DIV` before `config.h` reaches the modern `UBFIX` block. Pinned `src/isagbprn.c:3` and `src/mini_printf.c:38` directly include `config.h`, but neither file contains a textual `SAFE_DIV` use; **no observed compiled or runtime discrepancy is claimed**. The effective preprocessed macro selection for all affected translation units remains a compiler-evidence obligation.

Review the whole-file conditional tree against original agbcc, revision10 and modern compiler preprocessors, its build-flag overrides, and downstream headers. The source-anchored map-view checker pins this file's identity and `MODERN`/`UBFIX` selection; it is not a reviewer approval or linked-ROM proof.

**Disposition: complete-file source preparation only; unresolved compiler include-order and build-variant effects; independent approval pending. Phase 1 FAIL_INCOMPLETE.**
