#!/usr/bin/env python3
"""Verify bounded typed-video and ARM NV evidence without changing review status."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import phase1_mgba_arm_decode_emit_review_verify as arm_review
import phase1_mgba_gba_memory_alias_audit as memory_audit

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
GATE_BLOB = "dab5789433dc55cf325a917a220d060088bf1d29"
REPORT_SCHEMA = "xgba.phase1.mgba_video_nv_followup.v1"

FOCUS_SOURCES = {
    "include/mgba/internal/gba/video.h": {
        "blob": "289689446a6cf2334f8f478e35b376c9e87aa736",
        "sha256": "5121b0486b889ff134deafbfeac42afa9dc0e1e134affb106c6b6bcf78824500",
        "dossier": "0723c5fade118b9999f0203af025b2761e867341653af8cbbc3cf0fae5811c32",
        "anchors": [(105, "uint16_t raw[512];"), (225, "uint16_t palette[512];")],
    },
    "src/gba/memory.c": {
        "blob": "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "sha256": "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
        "dossier": "4b18ab8b7b5f947457093503c6c085e0ba6677f321255d140720cb2965b07f54",
        "anchors": [
            (404, "LOAD_32(value, address & (GBA_SIZE_PALETTE_RAM - 4), gba->video.palette);"),
            (423, "#define LOAD_OAM LOAD_32(value, address & (GBA_SIZE_OAM - 4), gba->video.oam.raw);"),
            (566, "LOAD_16(value, address & (GBA_SIZE_PALETTE_RAM - 2), gba->video.palette);"),
            (575, "LOAD_16(value, address & 0x00017FFE, gba->video.vram);"),
            (584, "LOAD_16(value, address & (GBA_SIZE_OAM - 2), gba->video.oam.raw);"),
            (785, "STORE_32(value, address & 0x00017FFC, gba->video.vram);"),
            (806, "STORE_32(value, address & (GBA_SIZE_OAM - 4), gba->video.oam.raw);"),
        ],
    },
    "src/gba/video.c": {
        "blob": "28f072ec0b880d272f4f9564cc5ca8f5af389caf",
        "sha256": "77f6bd32b19a5e78f06b0826cf3b5135abfcc3be24e08bd278829cdc564eda4d",
        "dossier": "20c76a3c969ef4b98f090290b1183872d6c87cb4f68521375e5f5369d16479c0",
        "anchors": [(61, "video->vram = anonymousMemoryMap(GBA_SIZE_VRAM);")],
    },
    "src/arm/arm.c": {
        "blob": "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "sha256": "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
        "dossier": "37c2acf57fc04d0327426d88d01b3353f46868be77fa73f3fa633fcc0a267934",
        "anchors": [(198, "0x0000 // NV"), (210, "bool conditionMet = conditionLut[condition] & (1 << flags);")],
    },
    "src/arm/debugger/debugger.c": {
        "blob": "d5e443ddc3d1af686cfb276a7f89dd489bfa9bac",
        "sha256": "3532e7432d1a3d047e1e646b5660e6ca6b5f55f19f41a94d2255e3a1514b6838",
        "dossier": "0baba7b8e8fbf5e486a55f8852a8bcd02bc389014db90d8126a3bb7c7fc27410",
        "anchors": [(70, "if (!ARMTestCondition(cpu, info.condition)) {")],
    },
    "include/mgba/internal/arm/isa-inlines.h": {
        "blob": "ebda28e411f627c6cd1570aff6f29a3b79a60840",
        "sha256": "17d976d898d9e412f863ea5a1ff41bde3232c16c13e08f9b0f9350a911e269a9",
        "dossier": "22099dfd7b67ee163af3dd04afe6aed7b70f059d9df2ebb14f713aeec91f58db",
        "anchors": [(129, "static inline bool ARMTestCondition(struct ARMCore* cpu, unsigned condition) {")],
    },
    "include/mgba/internal/arm/arm.h": {
        "blob": "5ef2da96519ac3f429b65fd6d323be0775f3b3cf",
        "sha256": "47822ffc4592230f6045dd2d8677dec5d72f518bff0b42e15ff26b5c77330bef",
        "dossier": "aca7d604d669aced639ef33deb3a23ca309747d961c83972ec9baf8805ebd1b1",
        "anchors": [],
    },
    "include/mgba/internal/arm/decoder.h": {
        "blob": "f6e19769884054b42b5fb77988b156d48b1c6489",
        "sha256": "d67f8d528e3d7090878df4c9d44cb4b1cdf1f5af0a68ae89a631c35b4ae39729",
        "dossier": "69bf00c7af7ef592cc5d115ebd892095fc4b55150a6690e299fcafec047f9f3e",
        "anchors": [(81, "enum ARMCondition {")],
    },
    "src/arm/decoder.c": {
        "blob": "21ea0e872c32689b46f7ab746d871a7a1070c97c",
        "sha256": "0676c6934b3f3fbce0204b5aff8afb4cd85286db724f6ca04e0a626ad1180fd1",
        "dossier": "c2fdc6d4229837ff35c4786c446ecf25eef97fa1f11bc57f037c31f284581961",
        "anchors": [(390, "if (info->condition != ARM_CONDITION_AL && info->condition < ARM_CONDITION_NV) {")],
    },
    "src/arm/decoder-arm.c": {
        "blob": "074c04314a2a6d4c1c0133d38f128ab0e90d7b1d",
        "sha256": "8423b699b14681c8be12b3893865a10cb0bbb5281c88f9a0e7953338711a1083",
        "dossier": "c89dae86be2d3950707b164cc683909bf10ffead0cd3c9c9e1329f659c8eda35",
        "anchors": [],
    },
    "src/arm/decoder-thumb.c": {
        "blob": "e96ae839613f846fbb477a6ddefc284a745c8e0d",
        "sha256": "627e5919e13c5c909193839c0fbc8069f55fb1e173c03d4ed5956e4168c1f4e0",
        "dossier": "585228eef510e0acd6cf7df901a04d63bca7f71bcc82e320b28d463ff9b7016f",
        "anchors": [],
    },
    "src/arm/isa-arm.c": {
        "blob": "af697fa0866fd7511cc430d4a2261704918e15bf",
        "sha256": "22063ad7c73d39265a4b1be963a33eeff6400514ea70f4e9b4e923d39e8afb47",
        "dossier": "44a019048049057453379fe6de9ce7b9c76b9f6c9ed015c392a19f71b202a350",
        "anchors": [],
    },
    "src/arm/isa-thumb.c": {
        "blob": "30fcfde9d614dc631c7fd9945bbda3ba99d4f55c",
        "sha256": "84c95dbb3295423ad81c0ee67d8b84d873399723363c59a82772e515e3a5b9f4",
        "dossier": "c8ef9ff3b98d39160d5a0e458f77b7110f942be562098a90a651de949cd84e4a",
        "anchors": [],
    },
}
LICENSE_EVIDENCE = {
    "git_blob_sha1": "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
    "source_sha256": "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85",
    "license": "MPL-2.0",
    "distribution_clearance": False,
}

VIDEO_CONTROL = {
    "status": "HOST_CONTROLS_EXECUTED",
    "host_compilers": ["gcc", "clang"],
    "alias_modes": ["strict", "no-strict"],
    "allocator_modes": ["mmap", "calloc"],
    "alignment_variants": 8,
    "limitations": [
        "alignment sanitizer does not diagnose effective-type violations",
        "successful host word/halfword observations do not establish C effective-type legality",
        "host behavior is not GBA hardware behavior",
    ],
}
NV_CONTROL = {
    "status": "HOST_CONTROL_EXECUTED",
    "predicate_for_condition_f": True,
    "core_effect": "SKIPPED",
    "debugger_stack_trace_condition_check": "SOURCE_ONLY_ARMTestCondition",
    "disassembler_condition_f_suffix": "SOURCE_GUARD_EXCLUDES_NV",
    "debugger_paths_executed": False,
    "independent_armv4t_oracle": "NOT_RUN",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def _load_rows(snapshot: Path) -> dict[tuple[str, str], dict]:
    import gzip

    rows = {}
    with gzip.open(snapshot / "candidate_review_dossiers.jsonl.gz", "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            identity = (provenance.get("repository"), provenance.get("path"))
            if identity[0] == "mgba-emu/mgba":
                rows[identity] = row
    return rows


def _source_records(source_root: Path, snapshot: Path) -> dict[str, dict]:
    data = (snapshot / "candidate_review_dossiers.jsonl.gz").read_bytes()
    if _sha256(data) != ARCHIVE_SHA256:
        raise ValueError("Original compressed dossier archive SHA-256 mismatch")
    rows = _load_rows(snapshot)
    records = {}
    for path, expected in FOCUS_SOURCES.items():
        raw = (source_root / path).read_bytes()
        row = rows.get(("mgba-emu/mgba", path))
        if row is None:
            raise ValueError(f"Original dossier row missing: {path}")
        provenance = row.get("provenance", {})
        row_payload = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
        if (
            _git_blob(raw) != expected["blob"]
            or _sha256(raw) != expected["sha256"]
            or provenance.get("git_blob_sha") != expected["blob"]
            or provenance.get("source_content_sha256") != expected["sha256"]
            or _sha256(row_payload) != expected["dossier"]
        ):
            raise ValueError(f"Pinned source/dossier identity mismatch: {path}")
        lines = raw.decode("utf-8", "strict").splitlines()
        anchors = []
        for number, expected_line in expected["anchors"]:
            if number < 1 or number > len(lines) or expected_line not in lines[number - 1]:
                raise ValueError(f"Pinned source anchor mismatch: {path}:{number}")
            anchors.append({"line": number, "text": expected_line})
        records[path] = {
            "git_blob_sha1": expected["blob"],
            "source_sha256": expected["sha256"],
            "dossier_row_sha256": expected["dossier"],
            "dossier_archive_sha256": ARCHIVE_SHA256,
            "line_anchors": anchors,
        }
    return records


def compose_report(source_records: dict[str, dict], nv_control: dict | None = None) -> dict:
    return {
        "schema": REPORT_SCHEMA,
        "upstream": {"repository": "mgba-emu/mgba", "commit": PIN},
        "dossier_archive_sha256": ARCHIVE_SHA256,
        "source_records": source_records,
        "license_evidence": copy.deepcopy(LICENSE_EVIDENCE),
        "video_backing": {
            "disposition": "NEEDS_EVIDENCE",
            "source_scope": [
                "declared uint16_t palette and OAM backing is passed to 32-bit memory access macros and retains separate 16-bit paths",
                "VRAM is dynamically mapped and separately accessed through 16-bit and 32-bit paths",
            ],
            "alignment_control": copy.deepcopy(VIDEO_CONTROL),
            "effective_type": "NEEDS_EVIDENCE",
            "effective_type_limit": (
                "uint32_t lvalue access to declared uint16_t palette/OAM arrays remains unresolved; "
                "mmap alignment and host value probes do not prove C effective-type legality"
            ),
        },
        "arm_condition_f": {
            "disposition": "NEEDS_EVIDENCE",
            "host_control": copy.deepcopy(nv_control or NV_CONTROL),
            "source_observation": (
                "ARM condition-F host test reports ARMTestCondition true while the ARM core condition LUT "
                "skips dispatch; debugger stack-trace and disassembly paths require separate semantic review"
            ),
            "independent_armv4t_oracle": "NOT_RUN",
            "oracle_limit": "No ARMv4T hardware/emulator oracle result is included or claimed",
        },
        "independent_approvals_added": 0,
        "gate_contribution": 0,
        "gate": "FAIL_INCOMPLETE",
    }


def validate_report(report: dict) -> None:
    if report.get("schema") != REPORT_SCHEMA or report.get("upstream") != {
        "repository": "mgba-emu/mgba",
        "commit": PIN,
    }:
        raise ValueError("Unexpected report schema or upstream identity")
    if report.get("dossier_archive_sha256") != ARCHIVE_SHA256:
        raise ValueError("Dossier archive identity mismatch")
    if set(report.get("source_records", {})) != set(FOCUS_SOURCES):
        raise ValueError("Missing or unexpected pinned source records")
    if report.get("license_evidence") != LICENSE_EVIDENCE:
        raise ValueError("Unsupported license or distribution-clearance claim")
    for path, expected in FOCUS_SOURCES.items():
        record = report["source_records"][path]
        if (
            record.get("git_blob_sha1") != expected["blob"]
            or record.get("source_sha256") != expected["sha256"]
            or record.get("dossier_row_sha256") != expected["dossier"]
            or record.get("dossier_archive_sha256") != ARCHIVE_SHA256
            or record.get("line_anchors")
            != [{"line": number, "text": text} for number, text in expected["anchors"]]
        ):
            raise ValueError(f"source/dossier identity or anchor drift: {path}")
    if report.get("video_backing", {}).get("disposition") != "NEEDS_EVIDENCE":
        raise ValueError("Video-backing disposition must remain NEEDS_EVIDENCE")
    if report["video_backing"].get("effective_type") != "NEEDS_EVIDENCE":
        raise ValueError("Effective-type conclusion cannot be promoted")
    if report["video_backing"].get("alignment_control") != VIDEO_CONTROL:
        raise ValueError("Unsupported video alignment control claim")
    if report.get("arm_condition_f", {}).get("disposition") != "NEEDS_EVIDENCE":
        raise ValueError("ARM condition-F disposition must remain NEEDS_EVIDENCE")
    if report["arm_condition_f"].get("host_control") != NV_CONTROL:
        raise ValueError("Unsupported ARM condition-F host control claim")
    if report["arm_condition_f"].get("independent_armv4t_oracle") != "NOT_RUN":
        raise ValueError("Unsupported ARMv4T oracle claim")
    if report.get("independent_approvals_added") != 0 or report.get("gate_contribution") != 0:
        raise ValueError("This evidence package cannot add approvals or gate contribution")
    if report.get("gate") != "FAIL_INCOMPLETE":
        raise ValueError("This evidence package cannot change the gate")
    if report != compose_report(report["source_records"]):
        raise ValueError("Unsupported report fields or evidence claims")


def _run_nv_control(source_root: Path, generated_include: Path) -> None:
    compiler = shutil.which("gcc")
    if compiler is None:
        raise ValueError("gcc is required for the bounded ARM condition-F host control")
    compile_sources = [
        "src/arm/arm.c",
        "src/arm/isa-arm.c",
        "src/arm/isa-thumb.c",
        "src/arm/decoder-arm.c",
        "src/arm/decoder-thumb.c",
        "src/arm/decoder.c",
    ]
    with tempfile.TemporaryDirectory(prefix="xgba-arm-nv-") as directory:
        output = Path(directory) / "nv-probe"
        command = [
            compiler,
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            f"-I{generated_include}",
            f"-I{source_root / 'include'}",
            *(str(source_root / path) for path in compile_sources),
            str(ROOT / "tests/phase1_mgba_arm_nv_probe.c"),
            "-o",
            str(output),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
        result = subprocess.run([str(output)], check=True, capture_output=True, text=True)
        if result.stdout.strip() != "ARM_NV_HOST_CONTROL_PASS predicate=TRUE cpu_effect=SKIPPED oracle=NONE":
            raise ValueError("Condition-F host control produced an unexpected result")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--generated-include", type=Path, required=True)
    parser.add_argument("--snapshot-root", type=Path, default=ROOT / "semantic-snapshots/current")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    source_root = args.source_root.resolve()
    if subprocess.check_output(["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True).strip() != PIN:
        raise ValueError("Pinned mGBA source checkout revision mismatch")
    memory_audit.verify_gate((args.snapshot_root / "phase1_mapping_gate.json").read_bytes())
    if memory_audit._git_blob((args.snapshot_root / "phase1_mapping_gate.json").read_bytes()) != GATE_BLOB:
        raise ValueError("Authoritative mapping gate snapshot changed")
    memory_audit._verify_dossiers(args.snapshot_root, source_root)
    memory_audit._verify_sources(source_root)
    arm_review.verify_packet()
    arm_review.verify_sources(source_root)
    source_records = _source_records(source_root, args.snapshot_root)
    host_variants = memory_audit._run_host_probes(source_root, args.generated_include.resolve())
    if host_variants != VIDEO_CONTROL["alignment_variants"]:
        raise ValueError(f"Unexpected video alignment control count: {host_variants}")
    _run_nv_control(source_root, args.generated_include.resolve())

    report = compose_report(source_records)
    validate_report(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(
        "P0_VIDEO_NV_FOLLOWUP_PASS "
        f"sources={len(source_records)} video_host_variants={host_variants} "
        "arm_nv_host_control=PASS effective_type=NEEDS_EVIDENCE "
        "armv4t_oracle=NOT_RUN approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()
