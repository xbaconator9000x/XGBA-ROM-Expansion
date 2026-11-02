#!/usr/bin/env python3
"""Verify pinned ARM decode/emit review evidence without creating approvals."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SNAPSHOT = ROOT / "semantic-snapshots/current"
PACKET = ROOT / "docs/phase1-review-readiness/packet-0000-0099.json"
PACKET_BLOB = "a48c12900acc7e0211a8071119763e2b5de4b1a4"
DOSSIER_ARCHIVE_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"

TARGETS = {
    10: {
        "path": "include/mgba/internal/arm/arm.h",
        "blob": "5ef2da96519ac3f429b65fd6d323be0775f3b3cf",
        "sha256": "47822ffc4592230f6045dd2d8677dec5d72f518bff0b42e15ff26b5c77330bef",
        "dossier": "aca7d604d669aced639ef33deb3a23ca309747d961c83972ec9baf8805ebd1b1",
        "anchors": [(127, "const uint32_t* activeRegion;")],
    },
    12: {
        "path": "include/mgba/internal/arm/decoder.h",
        "blob": "f6e19769884054b42b5fb77988b156d48b1c6489",
        "sha256": "d67f8d528e3d7090878df4c9d44cb4b1cdf1f5af0a68ae89a631c35b4ae39729",
        "dossier": "69bf00c7af7ef592cc5d115ebd892095fc4b55150a6690e299fcafec047f9f3e",
        "anchors": [
            (81, "enum ARMCondition {"),
            (196, "struct ARMInstructionInfo {"),
            (218, "void ARMDecodeARM(uint32_t opcode, struct ARMInstructionInfo* info);"),
        ],
    },
    27: {
        "path": "include/mgba/internal/arm/emitter-arm.h",
        "blob": "04c3715d2c2ba42fbd9644c0171111756723bbb8",
        "sha256": "ca5f3eb7d40bf8a6244002c160eed1cb36f6530d0567fa351107bb4660a5ccb2",
        "dossier": "53c0c115e727903bbab355b19ca6d7e4813f4b6c949c85bb38000df764277a57",
        "anchors": [
            (11, "#define DECLARE_INSTRUCTION_ARM(EMITTER, NAME) \\"),
            (78, "#define DECLARE_ARM_EMITTER_BLOCK(EMITTER) \\"),
            (299, "/* -AX---X- */ DECLARE_ARM_BRANCH_BLOCK(EMITTER, B), \\"),
        ],
    },
    68: {
        "path": "src/arm/decoder-arm.c",
        "blob": "074c04314a2a6d4c1c0133d38f128ab0e90d7b1d",
        "sha256": "8423b699b14681c8be12b3893865a10cb0bbb5281c88f9a0e7953338711a1083",
        "dossier": "c89dae86be2d3950707b164cc683909bf10ffead0cd3c9c9e1329f659c8eda35",
        "anchors": [
            (355, "DEFINE_DECODER_ARM(B, B,"),
            (453, "static const ARMDecoder _armDecoderTable[0x1000] = {"),
            (464, "ARMDecoder decoder = _armDecoderTable[((opcode >> 16) & 0xFF0) | ((opcode >> 4) & 0x00F)];"),
        ],
    },
    69: {
        "path": "src/arm/decoder-thumb.c",
        "blob": "e96ae839613f846fbb477a6ddefc284a745c8e0d",
        "sha256": "627e5919e13c5c909193839c0fbc8069f55fb1e173c03d4ed5956e4168c1f4e0",
        "dossier": "585228eef510e0acd6cf7df901a04d63bca7f71bcc82e320b28d463ff9b7016f",
        "anchors": [
            (219, "#define DEFINE_CONDITIONAL_BRANCH_THUMB(COND) \\"),
            (222, "info->op1.immediate = immediate << 1; \\"),
            (276, "info->op3.immediate = (((int32_t) immediate) << 7);"),
            (312, "ThumbDecoder decoder = _thumbDecoderTable[opcode >> 6];"),
        ],
    },
    70: {
        "path": "src/arm/decoder.c",
        "blob": "21ea0e872c32689b46f7ab746d871a7a1070c97c",
        "sha256": "0676c6934b3f3fbce0204b5aff8afb4cd85286db724f6ca04e0a626ad1180fd1",
        "dossier": "c2fdc6d4229837ff35c4786c446ecf25eef97fa1f11bc57f037c31f284581961",
        "anchors": [
            (560, "uint32_t ARMResolveMemoryAccess(struct ARMInstructionInfo* info, struct ARMRegisterFile* regs, uint32_t pc) {"),
            (582, "offset <<= shiftSize;"),
            (600, "return address + (info->memory.format & ARM_MEMORY_OFFSET_SUBTRACT ? -offset : offset);"),
        ],
    },
}

SUPPORT = {
    "include/mgba/internal/arm/macros.h": (
        "4832f054611044e63f1e2393fe4072f48004545a",
        "196d6bf1210d223dd58930908dcf5d538a7111fe93e0a0b36b45721cd93dbad9",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba/internal/arm/isa-inlines.h": (
        "ebda28e411f627c6cd1570aff6f29a3b79a60840",
        "17d976d898d9e412f863ea5a1ff41bde3232c16c13e08f9b0f9350a911e269a9",
    ),
    "include/mgba/internal/arm/decoder-inlines.h": (
        "11d41d520f1c9661eb56352f1a0b7a651fd99577",
        "216481c93aec0456cba015fcb224ac737d727534fc98243d61bfd91ccde7a84c",
    ),
    "include/mgba/internal/arm/isa-arm.h": (
        "fb347cd89f97482e0dbbf5fafed129f1679952df",
        "619d6208fdbee4f15a7120c3e6f8300cc24c4390373d83586b8c883d83b9f65f",
    ),
    "include/mgba/internal/arm/isa-thumb.h": (
        "69839d47a0f67d6b9c10eb635da388d0cf88cfb9",
        "a3c88e85789f261947ad3eb2c3831b51ddc193d750be24acc6eb5de069ffc7a0",
    ),
    "include/mgba/internal/arm/emitter-inlines.h": (
        "38bab70bddf08f6160461ab73a1649a2bdbd256f",
        "693c06f0336b5b47222529a4125d04f60ba855d3d559ea256611c7c2cf7bbaac",
    ),
    "include/mgba/internal/arm/emitter-thumb.h": (
        "7d27524b2e723696df642a72135bac024bbd8071",
        "b7a0167782c8fd63665345ed4520bd00a530e792be712e111bd9b056900b7353",
    ),
    "include/mgba/core/cpu.h": (
        "e538f4a5984f6426346fb3504871da335b160463",
        "7ecb55841bf4c1db741cf3369f4ec0003339cbfbc344d4f3fa468a227ea61538",
    ),
    "include/mgba/internal/debugger/symbols.h": (
        "12af3256459d32835955ee686eaa47006b6569a2",
        "a711c430b70bf8da14017faffae3f1ed14492a7821131f174fe1233c01eef74e",
    ),
    "include/mgba-util/string.h": (
        "bc29e28d71bbb4cbb51261a9ded26399c019fb2e",
        "80434f7f78cf6fa0bb60a7d3fcc4fe2ee09acf8ac14295a8c9e5c9a6a8715a9d",
    ),
    "src/arm/arm.c": (
        "0b92d7f55f1fb853d4b1b9c9163ee086126066e2",
        "c241587e974ac29aa09ed4992c9244c7ac65fad938e61d45836dc457f57129d2",
    ),
    "src/arm/isa-arm.c": (
        "af697fa0866fd7511cc430d4a2261704918e15bf",
        "22063ad7c73d39265a4b1be963a33eeff6400514ea70f4e9b4e923d39e8afb47",
    ),
    "src/arm/isa-thumb.c": (
        "30fcfde9d614dc631c7fd9945bbda3ba99d4f55c",
        "84c95dbb3295423ad81c0ee67d8b84d873399723363c59a82772e515e3a5b9f4",
    ),
    "src/arm/debugger/debugger.c": (
        "d5e443ddc3d1af686cfb276a7f89dd489bfa9bac",
        "3532e7432d1a3d047e1e646b5660e6ca6b5f55f19f41a94d2255e3a1514b6838",
    ),
    "src/gba/memory.c": (
        "aa01fdcc7d6ae5ecdf8753efc63b3a60a1e8d3dc",
        "501dbbca7d5d7cbaa86240de2d6a4e2e1186b50f74dde11bcf2f323c4af8c437",
    ),
    "include/mgba/internal/gba/video.h": (
        "289689446a6cf2334f8f478e35b376c9e87aa736",
        "5121b0486b889ff134deafbfeac42afa9dc0e1e134affb106c6b6bcf78824500",
    ),
    "src/arm/CMakeLists.txt": (
        "a86f0bea1f38aeb88222fb5b532b4ea9e256767f",
        "37d9b15aa461a72eba64465856d9377085d6dde56b8ba888e3a4e30f6859390e",
    ),
    "CMakeLists.txt": (
        "834e9fd9ceb94a972941fb7b12494270702601e8",
        "6dd68feaebc479a02606b14be889e7c966949aa6aa5a4c52f601861c5d369a31",
    ),
    "LICENSE": (
        "14e2f777f6c395e7e04ab4aa306bbcc4b0c1120e",
        "fab3dd6bdab226f1c08630b1dd917e11fcb4ec5e1e020e2c16f83a0a13863e85",
    ),
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require_source(source_root: Path, path: str, expected_blob: str, expected_sha: str) -> bytes:
    raw = (source_root / path).read_bytes()
    if git_blob(raw) != expected_blob or sha256(raw) != expected_sha:
        raise ValueError(f"Pinned source identity mismatch: {path}")
    return raw


def check_anchors(raw: bytes, path: str, anchors: list[tuple[int, str]]) -> None:
    lines = raw.decode("utf-8").splitlines()
    for line_number, expected in anchors:
        if line_number < 1 or line_number > len(lines) or lines[line_number - 1].strip() != expected:
            raise ValueError(f"Pinned source anchor mismatch: {path}:{line_number}")


def verify_packet() -> int:
    sys.path.insert(0, str(ROOT / "tools"))
    from phase1_bulk_triage import canonical, checked_dossiers, digest, read_queue

    packet_bytes = PACKET.read_bytes()
    if git_blob(packet_bytes) != PACKET_BLOB:
        raise ValueError("Original 100-file packet identity mismatch")
    archive = SNAPSHOT / "candidate_review_dossiers.jsonl.gz"
    if sha256(archive.read_bytes()) != DOSSIER_ARCHIVE_SHA256:
        raise ValueError("Original compressed dossier bytes mismatch")
    gate = json.loads((SNAPSHOT / "phase1_mapping_gate.json").read_bytes())
    if gate["decision"] != "FAIL_INCOMPLETE" or gate["approved_semantic_dispositions"] != 0:
        raise ValueError("Authoritative mapping gate changed; stop")
    packet = json.loads(packet_bytes)
    if (packet["phase1_gate"] != "FAIL_INCOMPLETE"
            or packet["independent_approvals_added"] != 0
            or packet["prepared_whole_file_dispositions_added"] != 0):
        raise ValueError("Packet contains a disposition or approval")
    queue = read_queue(SNAPSHOT)
    dossiers = checked_dossiers(SNAPSHOT, queue)
    packet_rows = {
        row["identity"]["path"]: row
        for row in packet["packets"]
        if row["identity"]["repository"] == "mgba-emu/mgba"
    }
    dossier_mutations = 0
    for index, target in TARGETS.items():
        path = target["path"]
        row = packet_rows.get(path)
        dossier = dossiers.get(("mgba-emu/mgba", path))
        if row is None or dossier is None:
            raise ValueError(f"Original packet/dossier row missing: {path}")
        if (row["identity"]["pinned_commit"] != PIN
                or row["identity"]["git_blob_sha1"] != target["blob"]
                or row["priority"] != "P0"
                or row["state"] != "MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION"
                or row["independently_approved"] is not False):
            raise ValueError(f"Packet identity or non-approval state mismatch: #{index}")
        if digest(canonical(dossier)) != target["dossier"] or row["dossier_sha256"] != target["dossier"]:
            raise ValueError(f"Original machine dossier row hash mismatch: #{index}")
        if dossier["provenance"]["source_content_sha256"] != target["sha256"]:
            raise ValueError(f"Dossier source SHA-256 mismatch: #{index}")
        changed = dict(dossier)
        changed["source_review_negative_mutation"] = True
        if digest(canonical(changed)) == target["dossier"]:
            raise AssertionError("Dossier mutation was not detected")
        dossier_mutations += 1
    if git_blob(packet_bytes + b"\nXGBA_PACKET_NEGATIVE_MUTATION") == PACKET_BLOB:
        raise AssertionError("Packet mutation was not detected")
    return dossier_mutations + 1


def verify_sources(source_root: Path) -> int:
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"], text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Pinned mGBA Git checkout HEAD is unavailable") from exc
    if commit != PIN:
        raise ValueError(f"Source checkout is not the pinned commit: {commit}")

    blobs = {}
    for index, target in TARGETS.items():
        raw = require_source(source_root, target["path"], target["blob"], target["sha256"])
        check_anchors(raw, target["path"], target["anchors"])
        notice = " ".join(raw.decode("utf-8").replace("*", " ").split())
        if "Mozilla Public License, v. 2.0." not in notice:
            raise ValueError(f"Expected file-level MPL-2.0 notice missing: #{index}")
        blobs[target["path"]] = raw
    for path, (blob, source_sha) in SUPPORT.items():
        raw = require_source(source_root, path, blob, source_sha)
        blobs[path] = raw

    negative_source_mutations = 0
    with tempfile.TemporaryDirectory(prefix="xgba-arm-mutated-") as temp:
        negative_root = Path(temp)
        for path, raw in blobs.items():
            mutated = raw + b"\nXGBA_PHASE1_NEGATIVE_MUTATION\n"
            target_path = negative_root / path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(mutated)
            try:
                require_source(negative_root, path, git_blob(raw), sha256(raw))
            except ValueError as exc:
                if "Pinned source identity mismatch" not in str(exc):
                    raise
            else:
                raise AssertionError(f"Mutated source passed the actual verifier: {path}")
            negative_source_mutations += 1
    license_text = blobs["LICENSE"]
    if b"Mozilla Public License" not in license_text:
        raise ValueError("Pinned root license does not contain the MPL text")
    return negative_source_mutations


def run_host_controls(source_root: Path) -> int:
    compiler = shutil.which("gcc")
    if compiler is None:
        raise RuntimeError("gcc is required for the pinned C11 controls")
    include = source_root / "include"
    compile_sources = [
        "src/arm/arm.c",
        "src/arm/isa-arm.c",
        "src/arm/isa-thumb.c",
        "src/arm/decoder-arm.c",
        "src/arm/decoder-thumb.c",
        "src/arm/decoder.c",
    ]
    harness = r"""
#include <stdio.h>
#include <mgba/internal/arm/arm.h>
#include <mgba/internal/arm/decoder.h>
#include <mgba/internal/arm/isa-arm.h>
#include <mgba/internal/arm/isa-thumb.h>
#include <mgba/internal/arm/isa-inlines.h>
static uint32_t fetch[16];
static void set_region(struct ARMCore *cpu, uint32_t address) {
    (void) cpu; (void) address;
}
int main(void) {
    for (unsigned i = 0; i < 0x1000; ++i) if (!_armTable[i]) return 10;
    for (unsigned i = 0; i < 0x400; ++i) if (!_thumbTable[i]) return 11;
    struct ARMInstructionInfo info;
    ARMDecodeARM(0xE2800001u, &info);
    if (info.mnemonic != ARM_MN_ADD || info.op1.reg != 0
            || info.op2.reg != 0 || info.op3.immediate != 1) return 12;
    ARMDecodeARM(0xEAFFFFFEu, &info);
    if (info.mnemonic != ARM_MN_B || info.branchType != ARM_BRANCH
            || info.op1.immediate != -8) return 13;
    ARMDecodeARM(0xFA000000u, &info);
    struct ARMCore conditionCpu = {0};
    if (info.condition != ARM_CONDITION_NV
            || !ARMTestCondition(&conditionCpu, info.condition)) return 14;
    ARMDecodeThumb(0x3001u, &info);
    if (info.mnemonic != ARM_MN_ADD || info.op1.reg != 0
            || info.op2.immediate != 1
            || !(info.operandFormat & ARM_OPERAND_IMMEDIATE_2)) return 15;
    ARMDecodeThumb(0xD07Fu, &info);
    if (info.mnemonic != ARM_MN_B || info.branchType != ARM_BRANCH
            || info.condition != ARM_CONDITION_EQ || info.op1.immediate != 254) return 16;
    struct ARMInstructionInfo first, second, combined;
    ARMDecodeThumb(0xF000u, &first);
    ARMDecodeThumb(0xF800u, &second);
    if (!ARMDecodeThumbCombine(&first, &second, &combined)
            || combined.op1.immediate != 0) return 17;
    struct ARMCore cpu = {0};
    cpu.memory.activeRegion = fetch;
    cpu.memory.activeMask = sizeof(fetch) - 1;
    cpu.memory.setActiveRegion = set_region;
    cpu.executionMode = MODE_ARM;
    cpu.nextEvent = 100;
    cpu.gprs[0] = 4;
    ARMRunFake(&cpu, 0xE2800001u);
    ARMRun(&cpu);
    if (cpu.gprs[0] != 5) return 18;
    cpu = (struct ARMCore){0};
    cpu.memory.activeRegion = fetch;
    cpu.memory.activeMask = sizeof(fetch) - 1;
    cpu.memory.setActiveRegion = set_region;
    cpu.executionMode = MODE_THUMB;
    cpu.nextEvent = 100;
    cpu.gprs[0] = 4;
    ARMRunFake(&cpu, 0x3001u);
    ARMRun(&cpu);
    if (cpu.gprs[0] != 5) return 19;
    puts("PINNED_HOST_TABLE_PASS arm_entries=4096 thumb_entries=1024 decode_fixtures=5 execution_fixtures=2");
    return 0;
}
"""
    probes = {
        "thumb-negative-conditional-branch": (
            "#include <mgba/internal/arm/decoder.h>\n"
            "int main(void) { struct ARMInstructionInfo i; ARMDecodeThumb(0xD080, &i); return 0; }\n",
            ["src/arm/decoder-thumb.c"],
            "left shift of negative value",
        ),
        "thumb-negative-bl1-prefix": (
            "#include <mgba/internal/arm/decoder.h>\n"
            "int main(void) { struct ARMInstructionInfo i; ARMDecodeThumb(0xF400, &i); return 0; }\n",
            ["src/arm/decoder-thumb.c"],
            "left shift of negative value",
        ),
        "debugger-negative-shifted-memory-offset": (
            "#include <mgba/internal/arm/decoder.h>\n"
            "int main(void) { struct ARMInstructionInfo i = {0}; struct ARMRegisterFile r = {0}; "
            "i.memory.format = ARM_MEMORY_REGISTER_BASE | ARM_MEMORY_REGISTER_OFFSET | ARM_MEMORY_SHIFTED_OFFSET; "
            "i.memory.offset.reg = 1; i.memory.offset.shifterOp = ARM_SHIFT_LSL; "
            "i.memory.offset.shifterImm = 1; r.gprs[1] = -1; "
            "return (int) ARMResolveMemoryAccess(&i, &r, 0); }\n",
            ["src/arm/decoder.c"],
            "left shift of negative value",
        ),
        "resolver-int-min-subtract": (
            "#include <mgba/internal/arm/decoder.h>\n"
            "int main(void) { struct ARMInstructionInfo i = {0}; struct ARMRegisterFile r = {0}; "
            "i.memory.format = ARM_MEMORY_REGISTER_BASE | ARM_MEMORY_REGISTER_OFFSET | ARM_MEMORY_OFFSET_SUBTRACT; "
            "i.memory.offset.reg = 1; r.gprs[1] = INT32_MIN; "
            "return (int) ARMResolveMemoryAccess(&i, &r, 0); }\n",
            ["src/arm/decoder.c"],
            "negation of -2147483648",
        ),
        "signed-byte-extension": (
            "#include <mgba/internal/arm/isa-inlines.h>\n"
            "int main(void) { return ARM_SXT_8(0xff); }\n",
            [],
            "left shift of negative value",
        ),
        "signed-halfword-extension": (
            "#include <mgba/internal/arm/isa-inlines.h>\n"
            "int main(void) { return ARM_SXT_16(0xffff); }\n",
            [],
            "left shift of negative value",
        ),
    }
    with tempfile.TemporaryDirectory(prefix="xgba-arm-review-") as tmp_name:
        tmp = Path(tmp_name)
        objects = []
        flags = [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", f"-I{include}"]
        for source in compile_sources:
            obj = tmp / (Path(source).stem + ".o")
            subprocess.run(flags + ["-c", str(source_root / source), "-o", str(obj)], check=True)
            objects.append(str(obj))
        harness_path = tmp / "positive.c"
        harness_path.write_text(harness)
        executable = tmp / "positive"
        subprocess.run(flags + [str(harness_path), *objects, "-o", str(executable)], check=True)
        completed = subprocess.run([str(executable)], check=True, text=True, capture_output=True)
        if "arm_entries=4096 thumb_entries=1024" not in completed.stdout:
            raise AssertionError("Pinned execution table controls did not report complete tables")

        sanitized = {}
        sanitizer_flags = [
            compiler, "-std=c11", "-O1", "-fsanitize=undefined",
            "-fno-sanitize-recover=undefined", f"-I{include}",
        ]
        for source in ("src/arm/decoder-thumb.c", "src/arm/decoder.c"):
            obj = tmp / (Path(source).stem + "-ubsan.o")
            subprocess.run(
                sanitizer_flags + ["-c", str(source_root / source), "-o", str(obj)],
                check=True,
            )
            sanitized[source] = str(obj)
        expected_failures = 0
        for name, (body, dependencies, expected_diagnostic) in probes.items():
            path = tmp / f"{name}.c"
            path.write_text(body)
            exe = tmp / name
            objects_for_probe = [sanitized[dep] for dep in dependencies]
            subprocess.run(sanitizer_flags + [str(path), *objects_for_probe, "-o", str(exe)], check=True)
            result = subprocess.run([str(exe)], text=True, capture_output=True)
            diagnostic = (result.stdout + result.stderr).lower()
            if result.returncode == 0 or expected_diagnostic not in diagnostic:
                raise AssertionError(f"Expected pinned-source UBSan counterexample did not reproduce: {name}")
            expected_failures += 1
    print(completed.stdout.strip())
    return expected_failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=ROOT / "upstream/mgba")
    args = parser.parse_args()
    if not args.source_root.is_dir():
        raise ValueError(f"Pinned mGBA source checkout not found: {args.source_root}")
    dossier_mutations = verify_packet()
    mutation_count = verify_sources(args.source_root)
    ubsan_count = run_host_controls(args.source_root)
    print(
        "P0_ARM_DECODE_EMIT_REVIEW_PASS "
        f"targets={len(TARGETS)} source_mutations={mutation_count} "
        f"dossier_packet_mutations={dossier_mutations} "
        f"ubsan_counterexamples={ubsan_count} approvals=0 gate=FAIL_INCOMPLETE"
    )
    print("SOURCE_ONLY: review handoff and controls are not native emulator/gameplay proof")


if __name__ == "__main__":
    main()
