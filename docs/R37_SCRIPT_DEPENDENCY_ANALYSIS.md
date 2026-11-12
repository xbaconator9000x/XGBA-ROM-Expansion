# R37 — Static Team Rocket event-script dependency graph

**VERIFIED / MERGED · 12 November 2026.** [PR #102](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/102) · [Merged source `2aca729`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/2aca7293c9b71944a85bba280234d13d9d0b119d). **4/4 exact-head workflows successful:** 20 new synthetic graph cases, R34–R36 parser/resource regression suite, immutable `pret/pokeemerald` original command table and critical macro widths, original FireRed Flash cold restart, original Emerald four-battle eviction, and repository privacy audit. [R37 exact-head tests](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43210338080) · [Full native non-regression](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43210337958). The user-owned Team Rocket ROM was only inspected in private; original ROM bytes and extracted code/assets were not published.


## Purpose and verified boundary

The R36 page store captured every byte from the user-owned Team Rocket Edition
3.06 ROM, but the earlier census identified *pointers*, not parsed scripts.
R37 is the first conservative **source-aware static command parser** for
those R36 roots. It loads the SHA-256-verified R36 sidecars, reconstructs the
original binary *only in a host/build-time analysis process*, then analyses
known Emerald-family script command layouts. No native GBA script is executed.

- The command profile is checked against the exact pinned upstream Emerald
  source: `pret/pokeemerald` commit `731ad5bfd6e6f265508d0efcca0ba42f9dcf5881`.
- Control flow follows identified goto/call and conditional pointer edges with
  strict instruction/branch budgets and no inferred fallthrough after goto.
- Unknown opcodes, ambiguous variable-length trainer battle records,
  malformed pointers, truncated commands and native-callback dependencies are
  *explicitly reported*, never silently reinterpreted as valid game logic.
- Namespaced source map IDs and original ROM addresses are preserved.
- Extracts provisional references to flags, event variables, item IDs,
  trainer IDs and engine-specific special functions; no cross-game ID
  translation is assumed. Event flags and variables are not modified.
- A complete 16-KiB page-sidecar SHA-256 verification, original ROM SHA
  validation, bounded graph traversal and readonly analysis all fail closed.
- Original source ROMs, extracted scripts and asset bytes are never committed,
  and public CI uses synthetic ROMs only.

## Private actual-ROM results (not public reproducible binaries)

The analysis of the user-supplied unofficial English Team Rocket Edition 3.06
ROM, SHA-256 `5a02069e9e1166290eb84ea98835158c54a91987ff81d26c210832b238a077ca`,
reported 11,962 map/event script-entry references at 9,189 unique ROM offsets.
The bounded traversal recognized **84,367** candidate script commands.
Of those root analyses, **6,160** reached a syntactically terminated state;
**3,029** were bounded or uncertain. Candidate unique referenced IDs were
656 flags, 571 variables, 49 items, 20 trainers and 115 special functions.
These are **provisional structural interpretations**, not executed events,
playable quest flows, or verified custom-engine semantics.

The profile deliberately does **not** infer variable-length `trainerbattle`
operands, special-function runtime compatibility, Pokémon mechanics, custom
battle effects or scripts beyond unknown command boundaries. The real ROM's
R36 census additionally identified two unresolved script-pointer references.
These remain documented and are not replaced with guessed data.

## Commands

Run on the private R36 page export **without needing the original .gba again**:

    python3 tools/xgba_r37_script_graph.py \
        --page-index /private/rocket/xgba-binary-rom-pages.json \
        --private-out /private/rocket-r37-script-dependencies.json \
        --counts-only /private/rocket-r37-summary.json

Optionally pass the original `.gba` as the positional first argument to
independently verify its identity against the R36 page store. Reports are
private by default. The counts-only report is not the ROM or script bytecode.

## Next interoperability milestones

A real common game runtime will need a translated script representation,
source-scoped save/event namespaces, a verified function/opcode compatibility
crosswalk, trainer battle parameter adapters, species/move/ability crosswalks,
and original save persistence. R37 provides an honest dependency inventory
for prioritising those adapters; it does not implement them. The next
milestone should begin with a bounded, read-only script intermediate
representation covering common original Emerald opcodes, then testing runtime
replay only in an isolated synthetic game context before importing a real
script into a gameplay environment.

Acceptance: `tests/test_xgba_r37_script_graph.py` plus upstream profile
verification in `tests/check_xgba_r37_upstream_profile.py`. Both contain
only original test code/fixtures; no proprietary ROM bytes.
