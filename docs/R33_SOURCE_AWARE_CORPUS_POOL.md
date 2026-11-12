# R33 — Source-aware multi-shard XGBA host resource pool

This phase connects the complete raw-source imports of R32 to a **selectively
addressable host pool** spanning every sidecar and every supplied world. It
does not claim cross-ROM execution.

The R32 importer could pack every tracked file into multiple XGBA v1
sidecars, but the earlier staging bridge only opened one sidecar at a time.
R33 adds **tools/xgba_corpus_pool.py** to validate the R32 whole-corpus
index, open every declared v1 sidecar, and resolve each original file across
the entire storage pool without preloading its payload bytes.

The pool validates all source snapshots and shard bounds, rejects orphaned
assets or duplicate/unsafe names, and checks original map group/number
identities against the SHA-256-verified source map_groups.json. Source
namespaces are explicit, so three games may all contain Group 0 / Map 9
without remapping any of them.

**Stage** verifies the complete resource SHA-256 before placing bytes in a
bounded host buffer. **Read_window** exposes at most 16 KiB by default and
only *after* verifying the full resource. Existing v1 sidecars lack
authenticated per-chunk hashes, so repeated small windows from enormous
resources currently rehash the whole source. This is correct but not yet
a high-throughput virtual-memory paging system. Damage to a newer pack or
index does not invalidate a previously verified staged buffer.

**Limits and separation of concerns:** this is a host-side lazy resolver
and source-provenance consistency layer. It does not yet replace the native
mGBA resource provider, import executable custom scripts, remap species
and move data, attach fly destinations, or implement shared party and
save state. The guest GBA still uses its existing limited RAM and no
additional physical memory has been added.

Acceptance has two parts: a synthetic three-world test proving all-shard
file retrieval, original map ID collisions, provenance checks, bounded
staging, empty files, atomic rollback and adversarial-index rejection;
and a full pinned original-Emerald source import checking resource
addressability and at least one original source item from each actual
sidecar. Public CI artifacts contain aggregate counts only, never game
data, ROMs or private save files.

- [Host source pool](../tools/xgba_corpus_pool.py)
- [Three-world source-pool tests](../tests/test_xgba_corpus_pool.py)
- [Full source and shard CI](../.github/workflows/xgba-r33-corpus-pool.yml)
- [R32 whole source-corpus importer](R32_WHOLE_CORPUS_IMPORT.md)

Native runtime integration and cross-game interaction are separate
follow-on milestones, not automatically proven by corpus lookups.
