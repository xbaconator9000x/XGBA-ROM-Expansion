# Independent Phase 1 mGBA savedata review

**Review identity:** GitHub Copilot Coding Agent (`@copilot`), this task's source-review pass. Prior analyst interpretation is identified as `xbaconator9000x` in open PRs [#12](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/12) and [#13](https://github.com/xbaconator9000x/XGBA-ROM-Expansion/pull/13). This review does not claim maintainer validation or independent approval.

**Scope and gate:** Complete pinned `src/gba/savedata.c` (800 lines, 28 function definitions) plus the VFile API/backends and direct savedata callers needed to adjudicate the existing assumptions. Upstream is unchanged at `fd9dc5c2cbf234365068855851107e762fc6211b`. This packet is task-specific and unregistered; every listed file remains `NEEDS_EVIDENCE`. Protected baseline hashes are verified against review snapshot commit `d9a46bbdf50cf67a6b52322a68f56caace2aef7e`; current gate/queue invariants are checked independently, and the PR workflow confirms this PR does not edit the shared files. Thus unrelated future queue updates do not invalidate this historical snapshot. Phase 1 remains **`FAIL_INCOMPLETE`**, with **0/14,834** approvals before and after this review.

## Independent findings

1. **Direct Flash growth.** `savedata.c:275–294` truncates/maps to the requested 128 KiB but only explicitly fills 0xFF when the original size is below 64 KiB. On the pinned Linux `VFileFD` backend, an existing 64-KiB file grows with 0x00 in the new bank; the native test read both the mapping and the file through a separate descriptor. This resolves PR #13's backend caveat for this backend, not every platform.
2. **Direct EEPROM initialization/growth.** `savedata.c:299–325` fills at most the first 512 bytes. Native FD tests found 0x00 in the upper range when directly initializing 8-KiB EEPROM from both an empty file and an existing 512-byte file. The 512-byte empty-file control fills all 512 bytes with 0xFF.
3. **Promotion is conditional on a VFile.** `_flashSwitchBank` (`759–777`) and `_ensureEeprom` (`485–505`) fill upper storage on their file-backed growth paths, but their no-VFile branches skip that fill. The pinned native test observed 0xFF after file-backed promotion, but zeroed upper storage after anonymous promotion. For EEPROM, the first anonymous promoted byte becomes `0x80` after the test's single-bit write; untouched bytes remain zero. Thus “promotion fills the upper range” is not a general invariant.
4. **Signed I/O error handling.** `vfs.h:43–50` defines signed `ssize_t` reads/writes. `GBASavedataClone` (`savedata.c:157–164`) passes a read count to `write` without checking the write result and bases success on the input read. The real read-only memory VFile returns `-1` for write; the native test confirms clone still returns success. `GBASavedataLoad` (`203–223`) has a related signed count conversion/overwrite. Negative input-read conversion is source-confirmed but was not fault-injected.
5. **Unclosed error paths and persistence.** `VFileFD.size` can return `-1`, mapping can return `NULL`, and truncate has no reported result (`vfs-fd.c:135–148,232–244`). The savedata initializers do not check these before using `end` in pointer arithmetic or using `data`. `RTCRead` stores signed read output in `size_t` before the short-read comparison (`savedata.c:649–666`). `Clean`/RTC trailer writeback (`586–638`) is source-traced, not proved durable across power failure or mapping/write failures.

Relevant reachability was independently traced through `GBALoadSave` and lifecycle/ownership (`gba.c:84–87,140–176,496–504`), save-type auto-detection (`memory.c:1062–1092`), EEPROM DMA (`dma.c:294–314`), overrides/RTC initialization (`overrides.c:334–348`), serialization (`serialize.c:89,234`), clone/restore (`core.c:1469–1506`), and SharkPort import/export (`sharkport.c:20–55,245–249`). The VFS source shows Linux routing to FD (`vfs.c:99–100`), POSIX file growth/mapping (`vfs-fd.c:134–154,232–269`), zero-initialized memory expansion and read-only writes (`vfs-mem.c:90–136,266–281,298–313`), and stdio zero extension (`vfs-file.c:118–136`). Blob identities and detailed per-file limitations are in `review.json`.

## Native evidence (not a mock, not semantic approval)

The existing `tests/run_pinned_mgba_boundary.sh` was reused and its existing synthetic-ROM harness was extended; no alternate emulator was created. It compiled the unmodified pinned mGBA static library and exercised real POSIX `VFileFD` saves, mGBA anonymous allocation, and the pinned read-only memory VFile. The nine savedata assertions are included in the 43 passing assertions; all four pre-existing Matrix hazard observations remain visible. The committed `native-*.log` files and hashes below are local agent run evidence. The new pull-request workflow runs the same harness and both evidence verifiers against the PR checkout, then uploads a separate artifact named `copilot-mgba-savedata-review-<run-id>-<attempt>` with the workflow run identity and exact hashes. A local run is not an independently observed workflow run. A passing run characterizes only these paths and does not establish cross-platform save compatibility, durable persistence, XGBA behavior, or Phase 1 completion.

| Evidence | SHA-256 |
|---|---|
| mGBA commit | `fd9dc5c2cbf234365068855851107e762fc6211b` |
| Changed native test source `tests/mgba_bank_boundary.c` | `233206a92473469d5ebcd74cdcdedaf6e49395cb67b0cbe19cb2d3a0e2fead18` |
| `native-run.log` (43 PASS; 4 existing observations; 0 failures) | `334addf291ce91cd7f2419b7dc8b4780b63825959ce28c8f13af3aa5c7e23000` |
| Configure log | `e67a13c738bdbfd8e8b39875e3625a852f81f9ec4da04d7fb83924d7cfab5612` |
| Build log | `4f40f5d3e6bd02dfd9ab189490915f1ba0685e19c06da84c00b86e90159725ea` |
| Existing runner `tests/run_pinned_mgba_boundary.sh` | `85746b2690a89c19a78ee754e8d1a224e3907790ddfc94cdec53b141ec64b0e8` |
| Existing `tests/CMakeLists.txt` | `7035354e527c93b37300b7dc4960d38457b78872cd940a52e8668938203346a5` |
| Bounded verifier `tools/copilot_mgba_savedata_review.py` | `4b2a85024d1cf9cd327eeeaab4e381b7498cc193ad3a60ace9c589706bcd300c` |
| Pinned test runner revision receipt | `6283a270bf7e86ff1a6a4b01a69041c350a2f35f451239400bfaaddf3296c78a` |
| Existing native regression evidence gate `tools/verify_native_mgba_regressions.py` | updated in this PR; workflow records its exact checkout SHA |

Original packets are kept in their proper evidence class: PR #13's mock-VFile CI run #40480788248 at `9bf2b6f31c7e0ebf00e1ebaf6aee6f0930c90444` is not counted as native execution; the prior 34-check native Matrix run #40205086061 at `d2c31ac826209752a249f9694e50d5ed5cc3ef97` is not a savedata semantic review.

## Reproduction and bounded verifier

From the repository root with the pinned checkout at `upstream/mgba`:

```sh
bash tests/run_pinned_mgba_boundary.sh
python3 tools/copilot_mgba_savedata_review.py --checkout upstream/mgba --self-test
python3 tools/copilot_mgba_savedata_review.py \
  --checkout upstream/mgba \
  --record semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json \
  --native-log semantic-snapshots/independent-reviews/copilot-mgba-savedata/native-run.log \
  --test-source tests/mgba_bank_boundary.c
python3 tools/verify_native_mgba_regressions.py --self-test
```

The bounded verifier checks the exact upstream commit and 16 Git blobs, all 800 savedata lines/function definitions and pinned risk anchors, the historical protected-file hashes at the review snapshot, current fail-closed gate invariants, all nine native savedata checks, and three mutated-source negative controls. The existing native regression gate preserves all 34 original named assertions and four hazard observations, requires exactly these nine additions, and runs its synthetic and negative controls. Both `PASS` results are evidence-integrity only; neither can approve files or advance the gate.

For PR validation, `.github/workflows/copilot-mgba-savedata-review.yml` is triggered by only the review packet, harness, verifier, and protected-gate paths. It builds/runs the pinned native harness, runs both verifiers on the generated PR-run logs, checks that the PR does not modify shared state, and archives CI-specific evidence and checksums. The locally recorded run above remains distinct from those workflow artifacts.

## Remaining evidence obligations

- Inject negative reads, short/failed writes, negative `size`, failed `truncate`, `NULL map`, and failed `sync`/remap; run error cases under sanitizers.
- Exercise `GBASavedataLoad` copying and RTCRead with negative and short reads.
- Run Windows, stdio VFile, 3DS and PSP2 backends; this run tested Linux POSIX VFileFD only.
- Validate RTC trailer contents, Flash bank pointer restoration, crash/power-loss durability, and user save/tool/editor interoperability.
- Have maintainers review the source dispositions. This record proposes no approval, gate edit, Phase 2 work, or upstream source change.
