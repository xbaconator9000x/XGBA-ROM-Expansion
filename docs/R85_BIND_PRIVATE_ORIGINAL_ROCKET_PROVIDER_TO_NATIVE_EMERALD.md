# R85 — bind original private Rocket resource catalogue to actual Emerald mGBA sidecar

**Found a real integration gap.** The preexisting R79 private ZIP contains **435 correctly hashed original resource pages**, including all three original `emerald.r48.npc`, `rocket.r48.npc`, and `heart_soul.r48.npc` witnesses, but the R79 resource offsets start at **zero** and its `source_identity` belongs to the *original-source catalogue*, not the **source-built Emerald game ROM**. Supplying the raw private ZIP to `xgba_mgba_run.launch` would fail because its host registration requires each game resource offset above 32 MiB, the original R17 map/boot packs, and the complete exact game ROM SHA.

The new `tools/xgba_r85_bind_private_source_provider.py` verifies exact original R79 ZIP SHA `92980dd3dc1144e54288669988f60bf7d39a191980d428220675fb073c21e948`, original catalogue identity, original witness packet SHA, every private resource bound and hash, source resource uniqueness and nonoverlap. It authenticates the **actual built Emerald binary** against the R17 native game manifest, preserves original native resource offsets and bytes, then atomically rebases 435 source catalogue records to true host-sidecar offsets above 32MiB and registers them alongside the R17 original Emerald boot/tileset packs. Output manifest identifies the actual built GBA SHA so the patched mGBA XGBA device can physically fetch these bytes. No ROMs, proprietary source graphics, dialogue or private resource pages are shipped or committed publicly.

Usage in an **owner-private** native build directory:
```sh
python3 tools/xgba_r85_bind_private_source_provider.py \
  --built-emerald /private/pokeemerald_modern.gba \
  --native-manifest /private/r17-native/manifest.json \
  --original-private-r79 /private/XGBA_R79_PRIVATE_Rocket_All_Three_First_Hops.zip \
  --private-output-dir /private/r85-bound
```
The native R17 manifest must originate from the *same exact patched Emerald ROM* and contain the actual original Emerald external game boot/map assets. The script refuses an output directory that already exists. Public tests use only completely authored fake ROM/resource bytes; no private assets are in CI.

**Acceptance boundary:** R85 makes the private provider registerable by the real native mGBA launcher. It does not simulate a player warp, prove the ROM built and loaded private Rocket original graphics, solve live camera NPC scrolling, or implement source-qualified Flash persistence. Genuine private LCD/door proof, saves and Johto gameplay still need a real native test. PR stays draft.
