#!/usr/bin/env python3
"""Execute pinned SaveConverter EEPROM detection/conversion methods with Qt6."""
import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
SOURCE = "src/platform/qt/SaveConverter.cpp"
SOURCE_BLOB = "4c32280c9c5288e806ffd237119186e2a633c4a7"
SOURCE_SHA256 = "3a6498a4fa69064d9b3723b49398cfe9d8e827ada3d8be26215db3a5ead2184f"
MEMORY_HEADER = "include/mgba/internal/gba/memory.h"
MEMORY_HEADER_BLOB = "0aad912613e726560d06bbdbf6061986e69e5842"
MEMORY_HEADER_SHA256 = "fca671fc3bc5ab06641f6259ebf092688e1ba1ddd8eb80e4fba9a43cda44fb41"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROW_SHA256 = "dc4112a41e57a7496c02986e900cb3d089cc081ae36ee02f4df479d0fc890357"
HARNESS_SHA256 = "90ef78f72ba584bb60e2edbd9e4e51ff0f68b279192fb8b9da7c00003b2f4e9b"
FUNCTIONS = {
    "detect_from_size": (
        "void SaveConverter::detectFromSize(std::shared_ptr<VFileDevice> vf) {",
        6431,
        8166,
        "30ca11a50224c7e7222fe169a85a84a5749331506d7230b6b940b5656de25693",
    ),
    "as_raw": (
        "SaveConverter::AnnotatedSave SaveConverter::AnnotatedSave::asRaw() const {",
        13986,
        14352,
        "b84a0b61acf676453134f702ac5b5491ddb9c6c4637a442055ddd11963463c0f",
    ),
    "equality": (
        "bool SaveConverter::AnnotatedSave::operator==(const AnnotatedSave& other) const {",
        17318,
        17820,
        "7b4e9373110673020d9934aa7bf53e74b2447ab7c3a57e851318c7cdd8ce5299",
    ),
    "possible_conversions": (
        "QList<SaveConverter::AnnotatedSave> SaveConverter::AnnotatedSave::possibleConversions() const {",
        17822,
        19498,
        "6974552e6a38b6bcffa6bd92bab05f7dca87dfb0b99a8d78fb7652b5e99a7d01",
    ),
    "convert_to": (
        "QByteArray SaveConverter::AnnotatedSave::convertTo(const SaveConverter::AnnotatedSave& target) const {",
        19500,
        22225,
        "7ad4cfd2ca18ff21e265bc7cbe86df3c2b60a852fac9436f68a7540b9c40c3dc",
    ),
}
MARKERS = {
    "detect_from_size": "PHASE1_INSERT_PINNED_DETECT_FROM_SIZE",
    "as_raw": "PHASE1_INSERT_PINNED_AS_RAW",
    "equality": "PHASE1_INSERT_PINNED_ANNOTATED_EQUALITY",
    "possible_conversions": "PHASE1_INSERT_PINNED_POSSIBLE_CONVERSIONS",
    "convert_to": "PHASE1_INSERT_PINNED_CONVERT_TO",
}
CASE_RE = re.compile(
    r"^PHASE1_EEPROM_CASE (eeprom512_plus16|eeprom8k_plus16) "
    r"size=(\d+) payload=(\d+) source_tail=([0-9a-f]{32}) "
    r"converted_tail_hex=([0-9a-f]{32}) converted_tail_preserved=([01]) "
    r"roundtrip_tail_preserved=([01]) payload_roundtrip=PASS$",
    re.M,
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def extract_function(source, signature):
    require(source.count(signature) == 1, "missing or ambiguous function: " + signature)
    start = source.index(signature)
    depth = 0
    for offset in range(source.index("{", start), len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return start, offset + 1, source[start:offset + 1]
    raise ValueError("unbalanced function: " + signature)


def source_functions(source):
    extracted = {}
    for name, (signature, expected_start, expected_end, expected_sha) in FUNCTIONS.items():
        start, end, body = extract_function(source, signature)
        require((start, end) == (expected_start, expected_end),
                name + " pinned byte offsets changed")
        require(hashlib.sha256(body.encode()).hexdigest() == expected_sha,
                name + " pinned function SHA-256 changed")
        extracted[name] = body

    checks = {
        "detect_from_size": (
            ("case GBA_SIZE_EEPROM + 16:", 1),
            ("case GBA_SIZE_EEPROM512 + 16:", 1),
        ),
        "possible_conversions": (
            ("endianSwapped.endianness = Endian::BIG;", 1),
            ("if ((size & 0xFF) == 0x10)", 1),
            ("noRtc.size &= ~0xFF;", 2),
        ),
        "convert_to": (
            ("converted.resize(target.size);", 1),
            ("for (int i = 0; i < (size & ~0xFF); i += 8)", 1),
            ("LOAD_64LE(word, i, in);", 1),
            ("STORE_64BE(word, i, out);", 1),
        ),
    }
    for name, anchors in checks.items():
        for anchor, count in anchors:
            require(extracted[name].count(anchor) == count,
                    name + " source anchor changed: " + anchor)
    return extracted


def mutation_controls(source):
    mutations = (
        ("for (int i = 0; i < (size & ~0xFF); i += 8)",
         "for (int i = 0; i < size; i += 8)"),
        ("case GBA_SIZE_EEPROM + 16:",
         "case GBA_SIZE_EEPROM + 15:"),
        ("STORE_64BE(word, i, out);", "STORE_64LE(word, i, out);"),
    )
    rejected = 0
    for old, new in mutations:
        require(source.count(old) == 1, "source mutation anchor not unique: " + old)
        mutated = source.replace(old, new, 1)
        try:
            source_functions(mutated)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + old)
    require(rejected == len(mutations), "source mutation controls incomplete")
    return rejected


def verify_dossier(root):
    path = root / "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
    if not path.exists():
        return {"available": False}
    raw = path.read_bytes()
    require(git(root, "hash-object", str(path.relative_to(root))) == DOSSIER_BLOB,
            "machine-dossier Git blob changed")
    require(hashlib.sha256(raw).hexdigest() == DOSSIER_SHA256,
            "machine-dossier compressed digest changed")
    import gzip

    with gzip.open(path, "rt", encoding="utf-8") as stream:
        row = None
        for index, line in enumerate(stream, 1):
            item = json.loads(line)
            provenance = item.get("provenance", {})
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("path") == SOURCE):
                row = (index, item)
                break
    require(row is not None and row[0] == 11744, "target dossier row changed")
    canonical = json.dumps(row[1], sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True).encode()
    require(hashlib.sha256(canonical).hexdigest() == DOSSIER_ROW_SHA256,
            "canonical per-file dossier digest changed")
    return {
        "available": True,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
        "row": row[0],
        "canonical_row_sha256": DOSSIER_ROW_SHA256,
    }


def parse_cases(output):
    require(output.count("PHASE1_EEPROM_DONE\n") == 1,
            "native Qt6 EEPROM harness did not finish")
    require(output.count("PHASE1_EEPROM_CASE ") == 2,
            "unexpected or malformed EEPROM case lines")
    cases = {}
    for match in CASE_RE.finditer(output):
        label = match.group(1)
        require(label not in cases, "duplicate EEPROM case: " + label)
        size, payload = int(match.group(2)), int(match.group(3))
        require((size, payload) in ((528, 512), (8208, 8192)),
                "unexpected EEPROM dimensions")
        cases[label] = {
            "size": size,
            "payload_size": payload,
            "source_tail_hex": match.group(4),
            "converted_tail_hex": match.group(5),
            "converted_tail_preserved": match.group(6) == "1",
            "roundtrip_tail_preserved": match.group(7) == "1",
            "payload_roundtrip": "PASS",
        }
    require(set(cases) == {"eeprom512_plus16", "eeprom8k_plus16"},
            "one or more native Qt6 EEPROM cases missing")
    require(cases["eeprom512_plus16"]["source_tail_hex"] ==
            "a0a1a2a3a4a5a6a7a8a9aaabacadaeaf",
            "512-byte EEPROM source sentinel changed")
    require(cases["eeprom8k_plus16"]["source_tail_hex"] ==
            "c0c1c2c3c4c5c6c7c8c9cacbcccdcecf",
            "8-KiB EEPROM source sentinel changed")
    for case in cases.values():
        require(case["converted_tail_preserved"] ==
                (case["source_tail_hex"] == case["converted_tail_hex"]),
                "converted-tail flag contradicts the emitted bytes")
        require(case["converted_tail_preserved"] is False,
                "endian conversion unexpectedly preserved the sentinel RTC tail")
        require(case["roundtrip_tail_preserved"] is False,
                "round-trip unexpectedly restored the sentinel RTC tail")
    return cases


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    require(git(args.checkout, "rev-parse", "HEAD") == PIN,
            "wrong pinned mGBA revision")
    require(git(args.checkout, "rev-parse", "HEAD:" + SOURCE) == SOURCE_BLOB,
            "pinned source tree blob changed")
    require(git(args.checkout, "hash-object", SOURCE) == SOURCE_BLOB,
            "pinned source worktree blob changed")
    source_bytes = (args.checkout / SOURCE).read_bytes()
    require(hashlib.sha256(source_bytes).hexdigest() == SOURCE_SHA256,
            "pinned source SHA-256 changed")
    header = args.checkout / MEMORY_HEADER
    require(git(args.checkout, "rev-parse", "HEAD:" + MEMORY_HEADER) ==
            MEMORY_HEADER_BLOB, "EEPROM constants tree blob changed")
    require(git(args.checkout, "hash-object", MEMORY_HEADER) == MEMORY_HEADER_BLOB,
            "EEPROM constants worktree blob changed")
    require(hashlib.sha256(header.read_bytes()).hexdigest() == MEMORY_HEADER_SHA256,
            "EEPROM constants SHA-256 changed")

    source = source_bytes.decode("utf-8")
    functions = source_functions(source)
    rejected = mutation_controls(source)
    harness = args.harness.read_text(encoding="utf-8")
    require(hashlib.sha256(harness.encode()).hexdigest() == HARNESS_SHA256,
            "EEPROM native test fixture SHA-256 changed")
    expanded = harness
    for name, marker in MARKERS.items():
        require(expanded.count(marker) == 1, "harness marker drift: " + marker)
        expanded = expanded.replace(marker, functions[name])
    dossier = verify_dossier(args.root.resolve())

    flags = subprocess.check_output(
        ["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True
    ).split()
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-eeprom-tail-") as directory:
        directory = Path(directory)
        source_path = directory / "eeprom_tail.cpp"
        binary_path = directory / "eeprom_tail"
        source_path.write_text(expanded, encoding="utf-8")
        compile_result = subprocess.run(
            ["g++", "-std=c++17", "-fPIC", "-O0", "-g", "-Wall",
             "-I", str(args.checkout / "include"), str(source_path),
             "-o", str(binary_path), *flags],
            text=True,
            capture_output=True,
            timeout=60,
        )
        require(compile_result.returncode == 0,
                "native Qt6 source-body compile failed: " +
                compile_result.stderr[-6000:])
        run = subprocess.run(
            [str(binary_path)], text=True, capture_output=True, timeout=20
        )
        require(run.returncode == 0,
                "native Qt6 EEPROM harness failed: " +
                run.stdout + run.stderr)
        output = run.stdout + run.stderr

    cases = parse_cases(output)
    evidence = {
        "class": "PINNED_MGBA_SAVECONVERTER_NATIVE_QT6_EEPROM_RTC_TAIL",
        "mgba_commit": PIN,
        "source_blob": SOURCE_BLOB,
        "source_sha256": SOURCE_SHA256,
        "memory_header_blob": MEMORY_HEADER_BLOB,
        "memory_header_sha256": MEMORY_HEADER_SHA256,
        "function_sha256": {
            name: hashlib.sha256(body.encode()).hexdigest()
            for name, body in functions.items()
        },
        "fixture_sha256": hashlib.sha256(harness.encode()).hexdigest(),
        "qt6_version": subprocess.check_output(
            ["pkg-config", "--modversion", "Qt6Core"], text=True
        ).strip(),
        "compiler": subprocess.check_output(
            ["g++", "--version"], text=True
        ).splitlines()[0],
        "compile_flags": ["-std=c++17", "-fPIC", "-O0", "-g", "-Wall",
                          "-I", "pinned/include", "pkg-config Qt6Core"],
        "source_mutations_rejected": rejected,
        "cases": cases,
        "dossier": dossier,
        "compiled_original_pinned_methods": [
            "detectFromSize",
            "AnnotatedSave::asRaw",
            "AnnotatedSave::operator==",
            "AnnotatedSave::possibleConversions",
            "AnnotatedSave::convertTo",
        ],
        "full_qt_application": False,
        "sav_interoperability": False,
        "stock_gameplay": False,
        "physical_flash": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
