#!/usr/bin/env python3
"""Verify the bounded pinned mGBA savedata review packet; never an approval."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SOURCE_BLOBS = {
    "src/gba/savedata.c": "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
    "include/mgba/internal/gba/savedata.h": "6227be25e8c9d2c1cc14c06ded34389b96138577",
    "include/mgba-util/vfs.h": "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
    "include/mgba/internal/gba/memory.h": "0aad912613e726560d06bbdbf6061986e69e5842",
    "src/gba/memory.c": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
    "src/gba/serialize.c": "a307a51e751f412c64a7378323c56758304ebe85",
    "src/gba/gba.c": "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
    "src/gba/core.c": "6bfc518bb8899205c07d1d0fc091a287cb42f874",
    "src/gba/overrides.c": "566968162b29c90167199ef43f3d7a99248798e8",
    "src/gba/dma.c": "da2a800ba48cb32d6e10e42c3b3527ef406bad22",
    "src/gba/sharkport.c": "f6b908f3aee7e69625253f5b96da93afc9bd333e",
    "src/util/vfs.c": "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
    "src/util/vfs/vfs-fd.c": "2535bd0fb76740745ae038d5523ead28658f1035",
    "src/util/vfs/vfs-mem.c": "048194e2dd2d0b3b395a852d2092c694663c88a2",
    "src/util/vfs/vfs-file.c": "4a63e53f842b31b24d6188e6525ddcf121a0c7da",
    "src/util/memory.c": "89646d3bcb5a23e6c75ee5ea8ee8dfd7b940027b",
}
PROTECTED_STATE_SHA256 = {
    "docs/PHASE1_STATUS.md": "248b931af27d7fa38c18d636b8e7a0f09e6b6bb698117ab55e7fbd0d0e491e49",
    "docs/PHASE1_INDEPENDENT_SEMANTIC_REVIEW_QUEUE.md": "91e29885742be869d5eb382d2bff3190afc0e62ddf2777a9a6e1038d05bb8efb",
    "semantic-snapshots/independent-reviews/queue.json": "37bd0e2b0de315d6f8f1bc34d3f6c3951d4246e81892882afc7f4ab179ae5c7a",
    "semantic-snapshots/current/phase1_mapping_gate.json": "7df6ceb6641ccb24cdc114f0ed6af10bc0ecbf3b42db484b26be41907e96d953",
}
DEFINITIONS = (
    "_ashesToAshes", "GBASavedataInit", "GBASavedataReset", "GBASavedataDeinit",
    "GBASavedataMask", "GBASavedataUnmask", "GBASavedataClone", "GBASavedataSize",
    "GBASavedataLoad", "GBASavedataForceType", "GBASavedataInitFlash",
    "GBASavedataInitEEPROM", "GBASavedataInitSRAM", "GBASavedataInitSRAM512",
    "GBASavedataReadFlash", "GBASavedataWriteFlash", "_ensureEeprom",
    "GBASavedataWriteEEPROM", "GBASavedataReadEEPROM", "GBASavedataClean",
    "GBASavedataRTCWrite", "_unBCD", "GBASavedataRTCRead", "GBASavedataSerialize",
    "GBASavedataDeserialize", "_flashSwitchBank", "_flashErase", "_flashEraseSector",
)
SAVEDATA_ANCHORS = {
    162: "out->write(out, buffer, read);",
    210: "read = savedata->vf->write(savedata->vf, buffer, read);",
    285: "if (end < flashSize) {",
    286: "savedata->vf->truncate(savedata->vf, flashSize);",
    288: "savedata->data = savedata->vf->map(savedata->vf, flashSize, savedata->mapMode);",
    292: "if (end < GBA_SIZE_FLASH512) {",
    293: "memset(&savedata->data[end], 0xFF, flashSize - end);",
    316: "if (end < eepromSize) {",
    317: "savedata->vf->truncate(savedata->vf, eepromSize);",
    319: "savedata->data = savedata->vf->map(savedata->vf, eepromSize, savedata->mapMode);",
    321: "if (end < GBA_SIZE_EEPROM512) {",
    322: "memset(&savedata->data[end], 0xFF, GBA_SIZE_EEPROM512 - end);",
    494: "return;",
    500: "memset(&savedata->data[GBA_SIZE_EEPROM512], 0xFF, GBA_SIZE_EEPROM - GBA_SIZE_EEPROM512);",
    653: "size = savedata->vf->read(savedata->vf, &buffer, sizeof(buffer));",
    654: "if (size < sizeof(buffer)) {",
    720: "flags = GBASerializedSavedataFlagsTestFillFlashBank(flags, savedata->currentBank == &savedata->data[0x10000]);",
    769: "memset(&savedata->data[GBA_SIZE_FLASH512], 0xFF, GBA_SIZE_FLASH512);",
}
NATIVE_SAVEDATA_CHECKS = (
    "native_savedata_flash_direct_growth_zero_fills_new_bank",
    "native_savedata_flash_anonymous_promotion_leaves_new_bank_zero",
    "native_savedata_flash_bank_promotion_erases_new_bank",
    "native_savedata_eeprom_direct_growth_zero_fills_upper_range",
    "native_savedata_eeprom_promotion_erases_upper_range",
    "native_savedata_eeprom_anonymous_promotion_leaves_unwritten_bytes_zero",
    "native_savedata_eeprom_8k_empty_erases_only_first_512_bytes",
    "native_savedata_eeprom_512_empty_file_erases_entire_save",
    "native_savedata_clone_reports_success_after_readonly_output_error",
)


class ReviewEvidenceRejected(ValueError):
    pass


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(checkout: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(checkout), *args])


def git_blob_sha(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def check_savedata_source(data: bytes) -> None:
    if git_blob_sha(data) != SOURCE_BLOBS["src/gba/savedata.c"]:
        raise ReviewEvidenceRejected("savedata.c Git blob mismatch")
    text = data.decode("utf-8")
    lines = text.splitlines()
    if len(lines) != 800:
        raise ReviewEvidenceRejected("savedata.c whole-file line count mismatch")
    definitions = tuple(re.findall(
        r"^(?:static\s+)?(?:void|bool|size_t|uint8_t|uint16_t)\s+(\w+)\s*"
        r"\([^;\n]*\)\s*\{", text, re.M
    ))
    if definitions != DEFINITIONS:
        raise ReviewEvidenceRejected("savedata.c complete function inventory mismatch")
    for number, expected in SAVEDATA_ANCHORS.items():
        if number > len(lines) or expected not in lines[number - 1]:
            raise ReviewEvidenceRejected(f"savedata.c evidence anchor mismatch at line {number}")


def verify_checkout(checkout: Path) -> dict[str, dict[str, str]]:
    if git(checkout, "rev-parse", "HEAD").decode().strip() != PIN:
        raise ReviewEvidenceRejected("mGBA checkout is not the exact pinned commit")
    identities = {}
    for path, expected_blob in SOURCE_BLOBS.items():
        actual_tree_blob = git(checkout, "rev-parse", f"HEAD:{path}").decode().strip()
        if actual_tree_blob != expected_blob:
            raise ReviewEvidenceRejected(f"mGBA tree identity mismatch: {path}")
        data = git(checkout, "cat-file", "blob", expected_blob)
        if git_blob_sha(data) != expected_blob:
            raise ReviewEvidenceRejected(f"mGBA object identity mismatch: {path}")
        identities[path] = {
            "git_blob_sha1": expected_blob,
            "sha256": sha256(data),
        }
    check_savedata_source(git(checkout, "cat-file", "blob", SOURCE_BLOBS["src/gba/savedata.c"]))
    return identities


def source_negative_controls(data: bytes) -> int:
    cases = (
        (b"if (end < GBA_SIZE_FLASH512)", b"if (end <= GBA_SIZE_FLASH512)"),
        (b"if (end < GBA_SIZE_EEPROM512)", b"if (end <= GBA_SIZE_EEPROM512)"),
        (
            b"memset(&savedata->data[GBA_SIZE_EEPROM512], 0xFF, GBA_SIZE_EEPROM - GBA_SIZE_EEPROM512);",
            b"memset(&savedata->data[GBA_SIZE_EEPROM512], 0, GBA_SIZE_EEPROM - GBA_SIZE_EEPROM512);",
        ),
    )
    rejected = 0
    for old, new in cases:
        if data.count(old) != 1:
            raise ReviewEvidenceRejected("negative-control mutation anchor is not unique")
        try:
            check_savedata_source(data.replace(old, new, 1))
        except ReviewEvidenceRejected:
            rejected += 1
        else:
            raise ReviewEvidenceRejected("savedata source mutation escaped fail-closed checks")
    return rejected


def verify_record(
    record: dict,
    sources: dict[str, dict[str, str]],
    verifier_sha256: str,
) -> None:
    if record.get("schema") != "xgba.copilot.mgba_savedata_review.v1":
        raise ReviewEvidenceRejected("review record schema mismatch")
    identity = record.get("review_identity", {})
    if not identity.get("reviewer") or not identity.get("prior_interpretation") or not identity.get("prior_evidence"):
        raise ReviewEvidenceRejected("reviewer and prior evidence identities are required")
    if identity.get("independent_maintainer_approval") is not False:
        raise ReviewEvidenceRejected("reviewer identity cannot claim maintainer approval")
    if record.get("source_revision") != PIN or record.get("source_blobs") != sources:
        raise ReviewEvidenceRejected("review record source identities mismatch")
    if record.get("review_verifier_sha256") != verifier_sha256:
        raise ReviewEvidenceRejected("review verifier SHA-256 mismatch")
    if record.get("protected_state_sha256") != PROTECTED_STATE_SHA256:
        raise ReviewEvidenceRejected("protected Phase 1 state hashes mismatch")
    if record.get("phase1_gate") != "FAIL_INCOMPLETE":
        raise ReviewEvidenceRejected("review packet cannot change the Phase 1 gate")
    accounting = record.get("approval_accounting", {})
    if accounting != {
        "approved_before": 0,
        "approved_after": 0,
        "inventory_total": 14834,
        "phase1_completion_claimed": False,
    }:
        raise ReviewEvidenceRejected("review packet changes or misstates approval accounting")
    dispositions = record.get("file_dispositions")
    if not isinstance(dispositions, list) or not dispositions:
        raise ReviewEvidenceRejected("missing per-file dispositions")
    for item in dispositions:
        path = item.get("path")
        if path not in sources or item.get("git_blob_sha1") != sources[path]["git_blob_sha1"]:
            raise ReviewEvidenceRejected(f"unbound per-file disposition: {path}")
        if item.get("verdict") not in {"NEEDS_EVIDENCE", "REJECTED", "PROPOSED_REVIEWED"}:
            raise ReviewEvidenceRejected(f"invalid per-file verdict: {path}")
        if item.get("independent_approval") is not False:
            raise ReviewEvidenceRejected(f"unsupported approval claim: {path}")


def verify_protected_state(root: Path) -> None:
    for path, expected in PROTECTED_STATE_SHA256.items():
        if sha256((root / path).read_bytes()) != expected:
            raise ReviewEvidenceRejected(f"protected Phase 1 state changed: {path}")
    queue = json.loads((root / "semantic-snapshots/independent-reviews/queue.json").read_text())
    gate = json.loads((root / "semantic-snapshots/current/phase1_mapping_gate.json").read_text())
    if queue.get("phase1_gate") != "FAIL_INCOMPLETE" or queue.get("total_approved") != 0:
        raise ReviewEvidenceRejected("shared independent-review queue no longer has zero approvals")
    if gate.get("decision") != "FAIL_INCOMPLETE" or gate.get("approved_semantic_dispositions") != 0:
        raise ReviewEvidenceRejected("authoritative Phase 1 gate changed")


def verify_native_evidence(
    record: dict,
    native_log: Path,
    test_source: Path,
    configure_log: Path,
    build_log: Path,
    revision_evidence: Path,
) -> dict:
    log = native_log.read_bytes()
    source = test_source.read_bytes()
    configure = configure_log.read_bytes()
    build = build_log.read_bytes()
    revision = revision_evidence.read_bytes()
    native = record.get("native_run", {})
    if (
        native.get("run_kind") != "PINNED_NATIVE_MGBA_STATIC_LIBRARY_WITH_POSIX_VFILEFD_AND_SYNTHETIC_ROM"
        or native.get("assertions_passed") != 43
        or native.get("savedata_assertions_passed") != len(NATIVE_SAVEDATA_CHECKS)
        or native.get("native_semantic_approval") is not False
        or native.get("phase1_mapping_complete") is not False
    ):
        raise ReviewEvidenceRejected("native run context or non-approval metadata mismatch")
    if native.get("source_revision") != PIN:
        raise ReviewEvidenceRejected("native run used a different mGBA revision")
    if native.get("test_source_sha256") != sha256(source):
        raise ReviewEvidenceRejected("native test source SHA-256 mismatch")
    if native.get("runtime_log_sha256") != sha256(log):
        raise ReviewEvidenceRejected("native runtime log SHA-256 mismatch")
    if native.get("configure_log_sha256") != sha256(configure):
        raise ReviewEvidenceRejected("native configure log SHA-256 mismatch")
    if native.get("build_log_sha256") != sha256(build):
        raise ReviewEvidenceRejected("native build log SHA-256 mismatch")
    if native.get("revision_evidence_sha256") != sha256(revision) or revision != (PIN + "\n").encode():
        raise ReviewEvidenceRejected("native runner revision evidence mismatch")
    text = log.decode("utf-8")
    if "SUMMARY hard_failures=0 native_gap_observations=4 " not in text:
        raise ReviewEvidenceRejected("native boundary run did not terminate with zero failures")
    if re.search(r"^FAIL ", text, re.M):
        raise ReviewEvidenceRejected("native boundary run contains a failed assertion")
    missing = [label for label in NATIVE_SAVEDATA_CHECKS if f"PASS {label}" not in text]
    if missing:
        raise ReviewEvidenceRejected("native savedata assertions missing: " + ", ".join(missing))
    if len(re.findall(r"^PASS ", text, re.M)) != 43:
        raise ReviewEvidenceRejected("native run assertion count is not 34 baseline + 9 savedata")
    return {
        "decision": "PASS_PINNED_NATIVE_MGBA_SAVEDATA_CHARACTERIZATION_ONLY",
        "source_revision": PIN,
        "assertions_verified": 43,
        "savedata_assertions_verified": len(NATIVE_SAVEDATA_CHECKS),
        "runtime_log_sha256": sha256(log),
        "test_source_sha256": sha256(source),
        "native_semantic_approval": False,
        "phase1_mapping_complete": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, default=Path("upstream/mgba"))
    parser.add_argument(
        "--record", type=Path,
        default=Path("semantic-snapshots/independent-reviews/copilot-mgba-savedata/review.json"),
    )
    parser.add_argument("--native-log", type=Path, default=Path("audit-output/mgba-boundary-runtime.log"))
    parser.add_argument("--test-source", type=Path, default=Path("tests/mgba_bank_boundary.c"))
    evidence_dir = Path("semantic-snapshots/independent-reviews/copilot-mgba-savedata")
    parser.add_argument("--configure-log", type=Path, default=evidence_dir / "native-configure.log")
    parser.add_argument("--build-log", type=Path, default=evidence_dir / "native-build.log")
    parser.add_argument("--revision-evidence", type=Path, default=evidence_dir / "native-source-revision.txt")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    try:
        verify_protected_state(Path.cwd())
        sources = verify_checkout(args.checkout)
        savedata = git(args.checkout, "cat-file", "blob", SOURCE_BLOBS["src/gba/savedata.c"])
        controls = source_negative_controls(savedata)
        if args.self_test:
            print(f"PASS pinned whole-file source evidence; {len(sources)} blob identities; {controls} mutation controls rejected")
            return 0
        record = json.loads(args.record.read_text(encoding="utf-8"))
        verify_record(record, sources, sha256(Path(__file__).read_bytes()))
        native = verify_native_evidence(
            record, args.native_log, args.test_source,
            args.configure_log, args.build_log, args.revision_evidence,
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"FAIL_CLOSED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({
        "decision": "PASS_PINNED_SOURCE_AND_NATIVE_EVIDENCE_ONLY",
        "source_revision": PIN,
        "source_files_verified": len(sources),
        "source_mutation_controls_rejected": controls,
        "native_evidence": native,
        "independent_semantic_approvals_added": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
