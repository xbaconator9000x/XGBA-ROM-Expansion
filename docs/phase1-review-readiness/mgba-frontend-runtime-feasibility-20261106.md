# mGBA frontend runtime feasibility handoff

## Result

The headless executable was launched, but the run did not reach a save lifecycle.
The Qt frontend did not build; SDL was not attempted. Thus this bounded attempt
did not produce frontend save-failure runtime evidence. The machine-readable result is `NEEDS_EVIDENCE` and
`FAIL_INCOMPLETE`. The earlier compiled host logger witness remains a host
witness only; it is not promoted or relabeled here.

## Pinned caller and observer closure

The source identities in the JSON record are tied to mGBA
`fd9dc5c2cbf234365068855851107e762fc6211b`, tree
`5863e657d270d0fe3ccaa4299f48d5689d74fa1f`, and the repository's compressed
candidate-review dossier. The verifier checks each original Git blob, complete
file-byte SHA-256, canonical dossier-row SHA-256, MPL-2.0 header, and anchored
line. Six files were inspected for this runtime-feasibility question. Four
shared dependencies are included as identity-only references to earlier work,
not counted as new source reviews.

The headless source calls `unloadROM` and `deinit`, but does not call
`mCoreAutoloadSave` or `mCoreLoadSaveFile`; GBA initialization uses a null
savedata VFile. The pinned headless target compiled and was launched, but the synthetic BIOS/ROM
run repeatedly logged BIOS SWI `00` and timed out before reaching the intended
save/shutdown path. This is not a save-error, `.sav`, or shutdown witness.

The Qt caller source opens its configured save suffix and closes the VFile if
`loadSave` returns false. Its INFO logger route is conditional on the log
filter and configured stdout/file sinks. Neither behavior was observed in a
running frontend. The Qt build attempts did not produce an executable:
`BUILD_GL=OFF` failed compilation with `ShaderSelector` undeclared, while
`BUILD_GL=ON` reached link and failed on unresolved `ShaderSelector` Qt
meta-object/vtable symbols. No Qt runtime or injected failure was executed.
SDL was not attempted and supplies no evidence in this package.

The savedata dirty-to-clean callback remains distinct from persistence success.
Core teardown/unmap/close operations in the inspected path do not provide a
save-success acknowledgment to the frontend. The source observations do not
establish that a failed sync is surfaced to a user.

## Evidence classes and blockers

- **Pinned source:** exact identities and source anchors are checked by the
  verifier. Source conclusions are not runtime observations.
- **Compiled native executable:** the pinned headless binary built, but did not
  reach save lifecycle. The Qt frontend did not build.
- **Frontend save-failure runtime / injected failure:** not observed; remains
  `NEEDS_EVIDENCE`.
- **Cold-process `.sav` reopen:** not observed.
- **Persistence, power loss, stock gameplay, physical Flash:** not established.
- **Approval/gate:** no independent semantic approval or gate/approval-state
  change is claimed.

The pinned files carry MPL-2.0 notices. Preserve those notices and the
repository license when distributing combined artifacts. No upstream source
was modified.
