# R32 — Whole-corpus importing and three-source stress

**VERIFIED / MERGED · 12 November 2026.** [PR #92](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/92) · [source merged `f4e8eb9`](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/commit/f4e8eb9da33de3db9b62a8a3aa1607cdf7b7e70d). Full original-Emerald source import: **11,557 tracked files, 31 sharded local sidecars**, SHA-256 verified readback of all non-empty resources using the actual XGBA production sidecar reader; zero-length sources represented in the index. Synthetic multi-source **13/13** passing tests with **12,000+ logical resources** across three independently named source worlds and overlapping original map IDs. All **4/4 exact-head workflows** passed, including real FireRed cold-save and original Emerald battle regressions. [Exact-head full-corpus CI #43184932530](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43184932530) · [Only aggregate-count evidence artifact #13927519305](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/actions/runs/43184932530/artifacts/13927519305).

**Purpose:** Import ALL relevant *source bytes* without a curated shortlist. Runtime translation and binary-ROM extraction remain distinct, unimplemented deliverables.

The new tool inventories every tracked file from each user-provided decomp
source directory, including maps, layouts, scripts, events, trainer data,
species, moves, abilities, items, sprites, graphics, music, text, engine code,
and unrecognised formats. Unknown source files are retained. It classifies
their likely role but never claims that raw assets or engine code can already
execute in the receiving game. The index includes SHA-256 for each file,
original source path, source namespace and immutable source snapshot identity.

It optionally copies **all source bytes** into multiple existing-format XGBA
v1 sidecars (default at most 384 entries per shard), preserving the actual
1 MB manifest limit. Source files are re-hashed during packing and rechecked
by the production sidecar reader; a mutated source fails rather than becoming
a partial world. Zero-byte files are represented precisely in metadata because
sidecar v1 does not allow empty resource entries.

Original group/map numbers are read from each source's existing map-group JSON
and never changed. Multi-source identity conflicts are counted and namespaced.
Original connection references are parsed; missing definitions are reported.
For Git repositories, only tracked inputs are inventoried, so local untracked
secrets and build products do not become imported assets.

**This is a whole-corpus storage/import foundation, NOT native interoperability.**
Persistent shared party, items, per-world event flags, cross-world Fly,
cross-engine script translation, binary-only ROM disassembly and real
cross-source double battles remain unimplemented and require further adapters.
Binary ROM hacks cannot automatically be decoded as a decomp source tree.
Unknown custom game mechanics must not be treated as compatible without proof.

Example for user-owned source trees:

    python3 tools/xgba_whole_corpus.py --source emerald=/path/emerald --source rocket=/path/rocket --source heartsoul=/path/heartsoul --pack --output /tmp/xgba-import

Without --pack, the output only inventories and categorises every file.

The R32 CI runs three synthetic independent source worlds with 12,000+
resources and genuine full-source inventory/ephemeral asset packing from the
pinned original Emerald decomp tree. It uploads ONLY aggregate counts, not
Nintendo assets, extracted ROMs, source paths or game binaries.

[Importer](../tools/xgba_whole_corpus.py) ·
[Synthetic source stress tests](../tests/test_xgba_whole_corpus.py) ·
[Original-source CI](../.github/workflows/xgba-r32-whole-corpus.yml).
