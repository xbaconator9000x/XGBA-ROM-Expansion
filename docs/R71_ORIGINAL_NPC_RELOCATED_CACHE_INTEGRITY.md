# R71 — original NPC dialogue survives EWRAM relocation without corruption

**Verified private input:** the owner-private R64 three-world provider has 377 resources, and SHA-256 verification succeeded on every resource entry. The three original R48 NPC packets have source-original CRC32 values `3ee29fb3` (Emerald), `dc79ff6b` (Rocket) and `fa898797` (Heart & Soul). Only noncopyrightable CRC constants are added to public source; original dialogue, ROM pixels, private manifests and saves stay private.

The original R48 script interpreter needs a **real EWRAM text pointer** instead of the NPC's source-ROM text address. R71 checks full-original 256-byte packet CRC on initial host fetch, then verifies that the relocated pointer still targets the exact in-packet text and recalculates CRC by virtually restoring only the original four pointer bytes. The live cached packet is never rewritten during preflight. Both the physical A-button script path and Fly-menu source-script preflight fail closed if the cached content or pointer has been corrupted. This also closes the previous `Ready[source] => TRUE` trust gap; an original packet's validity does not silently expire from scrutiny after its first use.

Guest cost: no new persistent EWRAM objects, no new per-world 256-byte packet copy and no extra host reads for cached scripts. C regression uses authored packet bytes and deliberately corrupts dialogue and pointer fields; the original Emerald ARM/mGBA/Flash workflow is rerun on the new native code.

**Status boundary:** this validates exactly three source NPC witnesses, not general foreign script execution or a completed three-ROM Fly. Full original Heart & Soul tileset/OBJ ingestion, native source warps, save/restart and live gameplay LCD acceptance remain pending.
