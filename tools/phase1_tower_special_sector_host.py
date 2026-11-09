#!/usr/bin/env python3
"""Execute unchanged pinned FireRed special-sector wrappers with host-only Flash stubs.

Evidence is original C function execution, NOT original-agbcc ARM or mGBA.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
BLOBS = {
    "src/save.c": "36b960f375c92711aa49b99bdfe9c6b3a99d6b1c",
    "include/save.h": "87fb9b615b434b58823d15688056695acda9feab",
}
SIGNATURES = (
    "u32 TryReadSpecialSaveSector(u8 sectorId, u8 *dst)",
    "u32 TryWriteSpecialSaveSector(u8 sector, u8 *src)",
)
EXPECTED = [
    "SPECIAL_WRITE_READ sector=30 payload_bytes=4092 counter_tail_preserved=4",
    "SPECIAL_SENTINEL_BAD rejected=1 destination_unchanged=4092",
    "SPECIAL_LAST_BYTE_MODIFIED accepted=1",
    "SPECIAL_INVALID_SECTOR read_rejected=1 write_rejected=1",
    "SPECIAL_WRITE_FAIL sector=31 returned_error=1",
    "SPECIAL_TORN_WRITE first_updated=1 second_old=1",
    "SPECIAL_DONE gate=FAIL_INCOMPLETE approvals=0",
]

def require(condition, reason):
    if not condition:
        raise ValueError(reason)

def extract(source, signature):
    require(source.count(signature) == 1, "missing/duplicate pinned function " + signature)
    start = source.index(signature)
    opening = source.find("{", start + len(signature))
    require(opening > start, "function body missing")
    depth = 0
    for i in range(opening, len(source)):
        depth += (source[i] == "{") - (source[i] == "}")
        if depth == 0:
            return source[start:i + 1]
    raise ValueError("unterminated function " + signature)

def source_contract(read, write, header):
    require("#define SECTOR_DATA_SIZE 3968" in header and
            "#define SECTOR_FOOTER_SIZE 128" in header and
            "#define SPECIAL_SECTOR_SENTINEL 0xB39D" in header and
            "#define SECTOR_ID_TRAINER_TOWER_1    30" in header and
            "#define SECTOR_ID_TRAINER_TOWER_2    31" in header,
            "physical sector layout or IDs changed")
    for name, body in (("read", read), ("write", write)):
        require("size = SECTOR_COUNTER_OFFSET - 1;" in body and
                "savData = &gSaveDataBuffer.data[4];" in body and
                "for (; i <= size; i++)" in body,
                name + " copy extent changed")
        require("SECTOR_ID_TRAINER_TOWER_1 &&" in body and
                "SECTOR_ID_TRAINER_TOWER_2)" in body,
                name + " sector allowlist changed")
    require("ReadFlash(sectorId, 0, (u8 *)&gSaveDataBuffer, SECTOR_SIZE);" in read,
            "pinned physical read changed")
    require("if (*(u32 *)(&gSaveDataBuffer.data[0]) != SPECIAL_SECTOR_SENTINEL)" in read,
            "pinned sentinel validation changed")
    require("dst[i] = savData[i];" in read, "read destination changed")
    require("*(u32 *)(savDataBuffer) = SPECIAL_SECTOR_SENTINEL;" in write,
            "writer sentinel assignment changed")
    require("savData[i] = src[i];" in write, "writer copy changed")
    require("ProgramFlashSectorAndVerify(sector, savDataBuffer) != 0" in write,
            "flash write failure check changed")
    return True

def source_negatives(read, write, header):
    changes = [
        (read.replace("i <= size", "i < size", 1), write, header),
        (read.replace("SECTOR_COUNTER_OFFSET - 1", "SECTOR_COUNTER_OFFSET - 2", 1), write, header),
        (read.replace("ReadFlash(sectorId", "ReadFlash(0", 1), write, header),
        (read.replace("SPECIAL_SECTOR_SENTINEL)", "0xFFFFFFFF)", 1), write, header),
        (read.replace("dst[i] = savData[i];", "dst[i] = 0;", 1), write, header),
        (read, write.replace("i <= size", "i < size", 1), header),
        (read, write.replace("savData[i] = src[i];", "savData[i] = 0;", 1), header),
        (read, write.replace("ProgramFlashSectorAndVerify(sector, savDataBuffer) != 0",
                             "ProgramFlashSectorAndVerify(sector, savDataBuffer) == 0", 1), header),
        (read, write, header.replace("#define SECTOR_DATA_SIZE 3968",
                                     "#define SECTOR_DATA_SIZE 3967", 1)),
    ]
    for i, (r, w, h) in enumerate(changes):
        require((r, w, h) != (read, write, header), "ineffective source mutation " + str(i))
        try:
            source_contract(r, w, h)
        except ValueError:
            continue
        raise ValueError("source mutation escaped: " + str(i))
    return len(changes)

def check_trace(lines):
    require(lines == EXPECTED, "native host transcript differs: " + repr(lines))
    return True

def evidence_negatives(lines):
    edits = [
        lines[:-1],
        [x.replace("payload_bytes=4092", "payload_bytes=4091") for x in lines],
        [x.replace("counter_tail_preserved=4", "counter_tail_preserved=0") for x in lines],
        [x.replace("destination_unchanged=4092", "destination_unchanged=0") for x in lines],
        [x.replace("accepted=1", "accepted=0") for x in lines],
        [x.replace("first_updated=1", "first_updated=0") for x in lines],
        [x.replace("gate=FAIL_INCOMPLETE", "gate=PASS") for x in lines],
        [x.replace("approvals=0", "approvals=1") for x in lines],
    ]
    for i, changed in enumerate(edits):
        require(changed != lines, "ineffective trace mutation " + str(i))
        try:
            check_trace(changed)
        except ValueError:
            continue
        raise ValueError("trace mutation escaped " + str(i))
    return len(edits)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--harness", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--log", type=Path, required=True)
    args = ap.parse_args()
    def git(*cmd):
        return subprocess.check_output(["git", "-C", str(args.source), *cmd],
                                       text=True).strip()
    require(git("rev-parse", "HEAD") == PIN, "FireRed commit mismatch")
    for path, blob in BLOBS.items():
        require(git("hash-object", path) == blob, "source blob mismatch: " + path)
    src = (args.source / "src/save.c").read_text()
    header = (args.source / "include/save.h").read_text()
    read, write = (extract(src, sig) for sig in SIGNATURES)
    source_contract(read, write, header)
    negative_count = source_negatives(read, write, header)
    harness = args.harness.read_text()
    marker = "PHASE1_PINNED_SPECIAL_SECTOR_FUNCTIONS"
    require(harness.count(marker) == 1, "harness injection marker changed")
    require("PHASE1_SPECIAL_DONE" not in harness, "harness completion marker spoof")
    with tempfile.TemporaryDirectory() as td:
        cfile = Path(td) / "special_sector.c"
        exe = Path(td) / "special_sector"
        cfile.write_text(harness.replace(marker, read + "\n\n" + write))
        built = subprocess.run(["cc", "-std=gnu11", "-O0", "-Wall", "-Wextra", "-Werror",
                                str(cfile), "-o", str(exe)], text=True, capture_output=True)
        require(built.returncode == 0, "pinned host C compile failed: " + built.stderr[-5000:])
        run = subprocess.run([str(exe)], text=True, capture_output=True)
        args.log.parent.mkdir(parents=True, exist_ok=True)
        args.log.write_text(run.stdout + run.stderr)
        require(run.returncode == 0, "pinned C execution failed: " + run.stderr[-4000:])
        lines = run.stdout.strip().splitlines()
    check_trace(lines)
    evidence = {
        "class": "PINNED_FIRERED_SPECIAL_SECTOR_ORIGINAL_C_HOST_EXECUTION",
        "source_pin": PIN,
        "source_blobs": BLOBS,
        "source_sha256": hashlib.sha256(src.encode()).hexdigest(),
        "original_read_and_write_function_bodies_unmodified": True,
        "host_fake_flash_backend_only": True,
        "original_agbcc_arm_executed": False,
        "mgba_or_physical_flash_executed": False,
        "stock_gameplay_reachability_proved": False,
        "source_mutations_rejected": negative_count,
        "transcript_mutations_rejected": evidence_negatives(lines),
        "trace": lines,
        "complete_file_approvals": 0,
        "independent_approvals": 0,
        "phase1_gate": "FAIL_INCOMPLETE",
        "next": ["actual original-agbcc ARM + mGBA sector 30/31 execution",
                 "native Flash fault/recovery and gameplay reachability",
                 "independent complete-file semantic review"],
    }
    require(evidence["source_mutations_rejected"] == 9 and
            evidence["transcript_mutations_rejected"] == 8 and
            evidence["phase1_gate"] == "FAIL_INCOMPLETE" and
            evidence["independent_approvals"] == 0, "evidence gate failed")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"result": "PASS_HOST_ONLY", "source_mutations_rejected": negative_count,
                      "transcript_mutations_rejected": 8,
                      "phase1_gate": "FAIL_INCOMPLETE"}))

if __name__ == "__main__":
    main()
