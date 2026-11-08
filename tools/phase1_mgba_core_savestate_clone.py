#!/usr/bin/env python3
"""Verify the pinned mCore savestate savedata-clone caller boundary."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
TREE = "5863e657d270d0fe3ccaa4299f48d5689d74fa1f"
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
RECEIPT = (
    "docs/phase1-review-readiness/"
    "mgba-core-savestate-clone-caller-20261108.json"
)

SOURCES = {
    "src/core/serialize.c": (
        "ff8a9a86747336bd792bf9c964c53f232a702a08",
        "45fb69d5da0c0c4c135efb2641c7d1c6140d575b1819f60a45985ebfa0081f3c",
        "e9ad34d5514e106adc1f56111abf530b72118d1780d8593ae490ee63772ab9b5",
        "COMPILED_EXTRACTED_MCORE_SAVESTATE_CLONE_CALLER_AND_EXTDATA_HELPERS",
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
        "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
        "SOURCE_TRACED_GBA_SAVEDATA_CLONE_CALLBACK_AND_REGISTRATION",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
        "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
        "SOURCE_TRACED_GBA_SAVEDATA_CLONE_RESULT",
    ),
    "include/mgba/core/core.h": (
        "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
        "e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9",
        "0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87",
        "COMPILED_PUBLIC_MCORE_CALLBACK_INTERFACE",
    ),
    "include/mgba/core/serialize.h": (
        "177a7871aa2761c0b478256ce16c7015a36b0fb8",
        "c1301365f7f24c8842e84b51324cc419e5ea01843f5366e9edbbf1cdf40f5c49",
        "4e61192f417f79c7210d2aae3132db1afbedff078fc1e6779b8944ec07bc38b7",
        "COMPILED_PUBLIC_SAVESTATE_EXTDATA_INTERFACE",
    ),
    "include/mgba/internal/gba/savedata.h": (
        "6227be25e8c9d2c1cc14c06ded34389b96138577",
        "30481cada83cc0e3a88b55298f3081cc660e18e55ca7f5a57356e6f2a75224dc",
        "eaee2c8bdb65c51e4f40daeb80af916f57ed430c48c88286562363f687ca6de9",
        "SOURCE_TRACED_GBA_SAVEDATA_API",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
        "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
        "COMPILED_VFILE_INTERFACE",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
        "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
        "COMPILED_ENDIAN_AND_COMMON_MACROS",
    ),
    "include/mgba/core/cheats.h": (
        "23a15c42976c998d292b382d08d51c0e3b797a65",
        "b25d46751653727f0a9814fef105b1efbd9498b7aa9d594f3547c6c2307ba3c7",
        "ddfa71cad7442c8052fe976d215288fa149cde7e7f5c6de8fe67249b62a97d00",
        "COMPILED_DORMANT_CHEAT_BRANCH_DECLARATIONS",
    ),
    "include/mgba/core/version.h": (
        "b261ab6d3a25de89c63420f48a0e3abe0a3113c1",
        "e4795aa1d78cfff79cb667d47576d9ed710aa823ffd5670c2f15a4baad51891a",
        "b6b2dfbf43be03aca5db7e4254ed594cfee09514432085119e6c2a4439f3a8f7",
        "COMPILED_DORMANT_METADATA_BRANCH_DECLARATIONS",
    ),
}

MCORE_SAVE_SIGNATURE = (
    "bool mCoreSaveStateNamed(struct mCore* core, struct VFile* vf, int flags)"
)
MCORE_SAVE_BODY_SHA256 = (
    "9e654c196c14fadd1e9f98c9c055fa0e7f9f07164a366a4a35c31719bb57648b"
)
EXTDATA_HEADER_SIGNATURE = "struct mStateExtdataHeader {"
EXTDATA_HEADER_SHA256 = (
    "3402135372a9421cae40fc1d86a79b9dab0dd32eee6e82a7252709540112a459"
)
EXTDATA_BODIES = {
    "mStateExtdataInit": (
        "void mStateExtdataInit(struct mStateExtdata* extdata)",
        "59161c62c270319177d850fae8a4b913d490ebe3a43215343444ea7cfef74a26",
    ),
    "mStateExtdataDeinit": (
        "void mStateExtdataDeinit(struct mStateExtdata* extdata)",
        "e909282685c02445a7e16ed9f63e2e630e4587626da1a20a121894b8db5185c4",
    ),
    "mStateExtdataPut": (
        "void mStateExtdataPut(struct mStateExtdata* extdata, "
        "enum mStateExtdataTag tag, struct mStateExtdataItem* item)",
        "7aab775b2bd3769b433149cca6f3de9ba583abfaf0d8f147c3021c12d10c7a9b",
    ),
    "mStateExtdataGet": (
        "bool mStateExtdataGet(const struct mStateExtdata* extdata, "
        "enum mStateExtdataTag tag, struct mStateExtdataItem* item)",
        "cd981ae228ceff9e64697a51ef193f3089cd0c573259a2bd6ce2fda0c5d99349",
    ),
    "mStateExtdataSerialize": (
        "bool mStateExtdataSerialize(struct mStateExtdata* extdata, "
        "struct VFile* vf)",
        "7ceae5bc2bdf9540c9a0ed0fb7d2ce24634522771b1ec5d8e966a1204f32eec8",
    ),
    "mStateExtdataDeserialize": (
        "bool mStateExtdataDeserialize(struct mStateExtdata* extdata, "
        "struct VFile* vf)",
        "81699573b8d6590f08955286bfe1c619549f085b6e77bbd61617d0bb7a05836a",
    ),
}
GBA_CLONE_SIGNATURE = (
    "static size_t _GBACoreSavedataClone(struct mCore* core, void** sram)"
)
GBA_CLONE_BODY_SHA256 = (
    "a61a31c42be82148a484832969105ebfae0d7ebc692c054d234e513b638728b7"
)
GBA_SAVEDATA_CLONE_SIGNATURE = (
    "bool GBASavedataClone(struct GBASavedata* savedata, struct VFile* out)"
)
GBA_SAVEDATA_CLONE_BODY_SHA256 = (
    "2b49c9f1e0cb3fe36bc6f77e01b35a84a8f015a920044d568908de93c8d7d6ea"
)
HARNESS_SHA256 = "aba2e8c825ed6d5f5696dbcfcf9f265d2e523020553598a965c4fe580318289c"
TERMINAL = "PHASE1_SAVESTATE_CLONE_DONE\n"
MPL_NOTICE = re.compile(rb"Mozilla Public\s+\*\s+License,\s+v\.\s+2\.0\.")
EXPECTED_LINES = (
    "PHASE1_CLONE_CASE normal caller_return=1 clone_result=8 "
    "clone_calls=1 state_bytes=8 savedata_present=1 payload_match=1",
    "PHASE1_CLONE_CASE zero_result_no_save caller_return=1 "
    "clone_result=0 clone_calls=1 state_bytes=8 savedata_present=0",
    "PHASE1_CLONE_CASE zero_result_failure caller_return=1 "
    "clone_result=0 clone_calls=1 state_bytes=8 savedata_present=0",
    "PHASE1_CLONE_CASE no_savedata_flag caller_return=1 "
    "clone_calls=0 state_bytes=8 savedata_present=0",
    "PHASE1_CLONE_CASE retry_after_zero caller_return=1 "
    "clone_result=8 clone_calls=1 state_bytes=8 savedata_present=1 "
    "payload_match=1",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def extract_function(source, signature):
    require(source.count(signature) == 1,
            "missing or ambiguous pinned function: " + signature)
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                return source[start:offset + 1]
    raise ValueError("unbalanced pinned function: " + signature)


def extract_declaration(source, signature):
    require(source.count(signature) == 1,
            "missing or ambiguous pinned declaration: " + signature)
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 0
    for offset in range(opening, len(source)):
        if source[offset] == "{":
            depth += 1
        elif source[offset] == "}":
            depth -= 1
            if depth == 0:
                end = source.index(";", offset) + 1
                return source[start:end]
    raise ValueError("unbalanced pinned declaration: " + signature)


def validate_body(source, signature, digest, anchors=()):
    body = extract_function(source, signature)
    require(hashlib.sha256(body.encode()).hexdigest() == digest,
            "pinned function body hash changed: " + signature)
    for anchor in anchors:
        require(body.count(anchor) == 1,
                "pinned function anchor missing or ambiguous: " + anchor)
    return body


def validate_declaration(source, signature, digest):
    declaration = extract_declaration(source, signature)
    require(hashlib.sha256(declaration.encode()).hexdigest() == digest,
            "pinned declaration hash changed: " + signature)
    return declaration


def expected_source_records():
    body_hashes = {
        "src/core/serialize.c": {
            "mCoreSaveStateNamed": MCORE_SAVE_BODY_SHA256,
            "mStateExtdataHeader": EXTDATA_HEADER_SHA256,
            "mStateExtdataInit": EXTDATA_BODIES["mStateExtdataInit"][1],
            "mStateExtdataDeinit": EXTDATA_BODIES["mStateExtdataDeinit"][1],
            "mStateExtdataPut": EXTDATA_BODIES["mStateExtdataPut"][1],
            "mStateExtdataGet": EXTDATA_BODIES["mStateExtdataGet"][1],
            "mStateExtdataSerialize": EXTDATA_BODIES["mStateExtdataSerialize"][1],
            "mStateExtdataDeserialize": (
                EXTDATA_BODIES["mStateExtdataDeserialize"][1]
            ),
        },
        "src/gba/core.c": {"_GBACoreSavedataClone": GBA_CLONE_BODY_SHA256},
        "src/gba/savedata.c": {
            "GBASavedataClone": GBA_SAVEDATA_CLONE_BODY_SHA256,
        },
    }
    return [
        {
            "path": path,
            "git_blob": values[0],
            "full_source_sha256": values[1],
            "canonical_dossier_row_sha256": values[2],
            "license": "MPL-2.0",
            "execution_scope": values[3],
            **({"function_body_sha256": body_hashes[path]}
               if path in body_hashes else {}),
        }
        for path, values in SOURCES.items()
    ]


def verify_sources(checkout):
    require(git(checkout, "rev-parse", "HEAD") == PIN,
            "wrong pinned mGBA revision")
    require(git(checkout, "rev-parse", "HEAD^{tree}") == TREE,
            "wrong pinned mGBA source tree")
    sources = {}
    for path, (blob, digest, _, _) in SOURCES.items():
        file_path = checkout / path
        raw = file_path.read_bytes()
        require(git(checkout, "rev-parse", "HEAD:" + path) == blob,
                "pinned tree blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        require(subprocess.check_output(
            ["git", "-C", str(checkout), "hash-object", str(file_path)],
            text=True,
        ).strip() == blob, "pinned source Git blob changed: " + path)
        require(MPL_NOTICE.search(raw) is not None,
                "missing MPL-2.0 source notice: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier_path = root / DOSSIER
    require(dossier_path.is_file(), "pinned machine dossier is missing")
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned machine-dossier Git blob changed")
    require(hashlib.sha256(dossier_path.read_bytes()).hexdigest() ==
            DOSSIER_SHA256, "pinned machine-dossier SHA-256 changed")

    expected_rows = {
        path: (values[2], values[0], values[1])
        for path, values in SOURCES.items()
    }
    found = {path: [] for path in SOURCES}
    with gzip.open(dossier_path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") == "mgba-emu/mgba" and
                    provenance.get("pinned_revision") == PIN and
                    path in found):
                canonical = json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
                ).encode()
                found[path].append((
                    hashlib.sha256(canonical).hexdigest(),
                    provenance.get("git_blob_sha"),
                    provenance.get("source_content_sha256"),
                ))
    require(found == {path: [value] for path, value in expected_rows.items()},
            "pinned dossier rows changed or are ambiguous")

    validate_body(
        sources["src/core/serialize.c"], MCORE_SAVE_SIGNATURE,
        MCORE_SAVE_BODY_SHA256,
        ("size = core->savedataClone(core, &sram);",
         "if (size) {", "mStateExtdataPut(&extdata, EXTDATA_SAVEDATA, &item);"),
    )
    validate_declaration(
        sources["src/core/serialize.c"], EXTDATA_HEADER_SIGNATURE,
        EXTDATA_HEADER_SHA256,
    )
    for name in ("mStateExtdataInit", "mStateExtdataDeinit",
                 "mStateExtdataPut", "mStateExtdataGet",
                 "mStateExtdataSerialize"):
        signature, digest = EXTDATA_BODIES[name]
        validate_body(sources["src/core/serialize.c"], signature, digest)
    deserialize_signature = EXTDATA_BODIES["mStateExtdataDeserialize"][0]
    deserialize_body = extract_function(
        sources["src/core/serialize.c"], deserialize_signature
    )
    deserialize_digest = hashlib.sha256(deserialize_body.encode()).hexdigest()
    require(deserialize_digest ==
            EXTDATA_BODIES["mStateExtdataDeserialize"][1],
            "pinned extdata deserializer body changed")
    validate_body(
        sources["src/gba/core.c"], GBA_CLONE_SIGNATURE,
        GBA_CLONE_BODY_SHA256,
        ("if (!size)", "if (!vf)", "if (!success)", "return size;"),
    )
    require("core->savedataClone = _GBACoreSavedataClone;" in
            sources["src/gba/core.c"],
            "pinned GBA core clone callback assignment changed")
    validate_body(
        sources["src/gba/savedata.c"], GBA_SAVEDATA_CLONE_SIGNATURE,
        GBA_SAVEDATA_CLONE_BODY_SHA256,
        ("return read >= 0;", "return true;"),
    )
    require("size_t (*savedataClone)(struct mCore*, void** sram);" in
            sources["include/mgba/core/core.h"],
            "pinned mCore clone callback declaration changed")
    require("EXTDATA_SAVEDATA = 2" in
            sources["include/mgba/core/serialize.h"],
            "pinned savestate savedata tag changed")
    return sources, deserialize_digest


def reject_source_mutations(sources, deserialize_digest):
    cases = (
        ("src/core/serialize.c", MCORE_SAVE_SIGNATURE, MCORE_SAVE_BODY_SHA256,
         "if (size) {", "if (true) {"),
        ("src/core/serialize.c", MCORE_SAVE_SIGNATURE, MCORE_SAVE_BODY_SHA256,
         "size = core->savedataClone(core, &sram);", "size = 0;"),
        ("src/gba/core.c", GBA_CLONE_SIGNATURE, GBA_CLONE_BODY_SHA256,
         "if (!success) {", "if (success) {"),
        ("src/gba/savedata.c", GBA_SAVEDATA_CLONE_SIGNATURE,
         GBA_SAVEDATA_CLONE_BODY_SHA256, "return read >= 0;", "return false;"),
        ("src/core/serialize.c",
         EXTDATA_BODIES["mStateExtdataSerialize"][0],
         EXTDATA_BODIES["mStateExtdataSerialize"][1],
         "if (vf->write(vf, header, size) != size) {",
         "if (false) {"),
    )
    rejected = 0
    for path, signature, digest, before, after in cases:
        body = extract_function(sources[path], signature)
        require(body.count(before) == 1,
                "source mutation anchor changed: " + before)
        mutated = body.replace(before, after, 1)
        try:
            validate_body(mutated, signature, digest)
        except ValueError:
            rejected += 1
    deserializer = extract_function(
        sources["src/core/serialize.c"],
        EXTDATA_BODIES["mStateExtdataDeserialize"][0],
    )
    changed = deserializer.replace("if (header.tag == EXTDATA_NONE)",
                                   "if (true)", 1)
    require(changed != deserializer and
            hashlib.sha256(changed.encode()).hexdigest() != deserialize_digest,
            "extdata-deserializer source mutation escaped")
    header = extract_declaration(
        sources["src/core/serialize.c"], EXTDATA_HEADER_SIGNATURE
    )
    mutated_header = header.replace("int32_t size;", "uint32_t size;", 1)
    require(mutated_header != header and
            hashlib.sha256(mutated_header.encode()).hexdigest() !=
            EXTDATA_HEADER_SHA256,
            "extdata-header source mutation escaped")
    return rejected + 2


def parse_output(output):
    require(output.endswith(TERMINAL) and output.count(TERMINAL) == 1,
            "savestate clone witness lacks a unique terminal marker")
    lines = tuple(output[:-len(TERMINAL)].splitlines())
    require(lines == EXPECTED_LINES,
            "savestate clone output differs from pinned caller contract")
    return {
        "normal_clone": {
            "caller_return": True,
            "clone_result": 8,
            "savedata_extdata_present": True,
            "payload_matches": True,
        },
        "fixture_zero_result_no_save": {
            "caller_return": True,
            "clone_result": 0,
            "savedata_extdata_present": False,
        },
        "fixture_zero_result_failure": {
            "caller_return": True,
            "clone_result": 0,
            "savedata_extdata_present": False,
        },
        "no_savedata_flag_control": {
            "caller_return": True,
            "clone_callback_calls": 0,
            "savedata_extdata_present": False,
        },
        "retry_after_zero_result": {
            "caller_return": True,
            "clone_result": 8,
            "savedata_extdata_present": True,
            "payload_matches": True,
        },
    }


def reject_output_mutations(output):
    changes = (
        output.replace("caller_return=1 clone_result=0",
                       "caller_return=0 clone_result=0", 1),
        output.replace("savedata_present=0", "savedata_present=1", 1),
        output.replace("clone_calls=0", "clone_calls=1", 1),
        output.replace("payload_match=1", "payload_match=0", 1),
        output.replace("clone_result=8", "clone_result=0", 1),
        output.replace(TERMINAL, "", 1),
    )
    for changed in changes:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("savestate clone output mutation escaped")
    return len(changes)


def verify_receipt(path):
    receipt = json.loads(path.read_text(encoding="utf-8"))
    require(receipt.get("schema") ==
            "phase1.mgba.core-savestate-clone-caller.v1" and
            receipt.get("repository") == "mgba-emu/mgba" and
            receipt.get("pinned_revision") == PIN and
            receipt.get("pinned_tree") == TREE,
            "savestate clone receipt pin/schema changed")
    require(receipt.get("status") == "NEEDS_EVIDENCE" and
            receipt.get("overall") == "FAIL_INCOMPLETE" and
            receipt.get("independent_approvals") == 0,
            "savestate clone receipt approval status changed")
    require(receipt.get("source_records") == expected_source_records(),
            "savestate clone source identities or scopes changed")
    require(receipt.get("machine_dossier") == {
        "path": DOSSIER,
        "git_blob": DOSSIER_BLOB,
        "compressed_sha256": DOSSIER_SHA256,
    }, "savestate clone dossier identity changed")
    require(receipt.get("call_graph") == [
        "The pinned GBA core registers _GBACoreSavedataClone as core->savedataClone.",
        "_GBACoreSavedataClone returns 0 when GBASavedataSize is zero.",
        "_GBACoreSavedataClone also returns 0 when VFile construction or GBASavedataClone fails.",
        "mCoreSaveStateNamed calls core->savedataClone only with SAVESTATE_SAVEDATA set.",
        "mCoreSaveStateNamed adds EXTDATA_SAVEDATA only when the returned size is nonzero.",
        "mCoreSaveStateNamed serializes and returns true even when clone result is zero and savedata extdata is omitted.",
    ], "savestate clone call graph changed")
    require(receipt.get("prior_witness_nonoverlap") == {
        "previous_receipt": (
            "docs/phase1-review-readiness/"
            "mgba-savedata-truncated-restore-20261107.json"
        ),
        "previous_caller": "_GBACoreSavedataRestore(writeback=true)",
        "current_caller": "mCoreSaveStateNamed -> core->savedataClone",
        "distinct_caller_body_sha256": MCORE_SAVE_BODY_SHA256,
        "distinct_from_prior_restore_body": True,
    }, "savestate clone nonoverlap inventory changed")
    require(receipt.get("evidence_class") ==
            "COMPILED_EXTRACTED_PINNED_MCORE_SAVESTATE_CALLER_AND_EXTDATA_"
            "HELPERS_WITH_HOST_VFILE_AND_CLONE_CALLBACK_FIXTURES" and
            receipt.get("observations") == parse_output(
                "\n".join(EXPECTED_LINES) + "\n" + TERMINAL
            ), "savestate clone evidence or observations changed")
    require(receipt.get("source_mutations_rejected") == 7 and
            receipt.get("output_mutations_rejected") == 6,
            "savestate clone mutation controls changed")
    for field in ("compiled_original_mcore_savestate_caller",
                  "compiled_original_extdata_helpers",
                  "source_traced_original_gba_clone_callback",
                  "source_traced_original_gba_savedata_clone",
                  "ten_pinned_source_records",
                  "host_vfile_fixture",
                  "clone_callback_is_test_fixture"):
        require(receipt.get(field) is True,
                "savestate clone receipt scope missing: " + field)
    for field in ("full_mgba_core_compiled",
                  "original_gba_clone_callback_executed",
                  "native_mgba_frontend_executed",
                  "natural_clone_failure_observed",
                  "savestate_frontend_roundtrip_tested",
                  "durable_persistence_tested",
                  "sav_interoperability_tested",
                  "stock_gameplay_tested",
                  "physical_flash_tested"):
        require(receipt.get(field) is False,
                "savestate clone receipt overstates evidence: " + field)
    return receipt


def run(command, timeout=90):
    return subprocess.run(command, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=timeout)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.resolve()
    root = Path(__file__).resolve().parents[1]
    receipt = verify_receipt(root / RECEIPT)
    sources, deserialize_digest = verify_sources(checkout)
    source_mutations_rejected = reject_source_mutations(
        sources, deserialize_digest
    )

    harness = args.harness.read_bytes()
    require(hashlib.sha256(harness).hexdigest() == HARNESS_SHA256,
            "savestate clone harness SHA-256 changed")
    expanded_harness = harness.decode("utf-8")
    marker = "PHASE1_INSERT_PINNED_SAVESTATE_CLONE_FUNCTIONS"
    require(expanded_harness.count(marker) == 1,
            "pinned savestate clone extraction marker changed")
    source = sources["src/core/serialize.c"]
    bodies = [
        validate_declaration(
            source, EXTDATA_HEADER_SIGNATURE, EXTDATA_HEADER_SHA256
        ),
        validate_body(source, MCORE_SAVE_SIGNATURE, MCORE_SAVE_BODY_SHA256),
        *[
            validate_body(source, signature, digest)
            for name, (signature, digest) in EXTDATA_BODIES.items()
            if name != "mStateExtdataDeserialize"
        ],
        extract_function(
            source, EXTDATA_BODIES["mStateExtdataDeserialize"][0]
        ),
    ]
    expanded_harness = expanded_harness.replace(
        marker, "\n\n".join(bodies), 1
    )

    with tempfile.TemporaryDirectory(
            prefix="xgba-mgba-savestate-clone-") as temp:
        temp = Path(temp)
        expanded_source = temp / "savestate-clone.c"
        binary = temp / "savestate-clone"
        expanded_source.write_text(expanded_harness, encoding="utf-8")
        command = [
            "gcc", "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-I", str(checkout / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(expanded_source), "-o", str(binary),
        ]
        compiled = run(command)
        require(compiled.returncode == 0,
                "pinned savestate clone caller compile failed:\n" +
                compiled.stdout)
        executed = run([str(binary)], timeout=20)
        require(executed.returncode == 0,
                "pinned savestate clone caller failed:\n" + executed.stdout)
        output_mutations_rejected = reject_output_mutations(executed.stdout)
        observations = parse_output(executed.stdout)
        require(observations == receipt["observations"] and
                source_mutations_rejected ==
                receipt["source_mutations_rejected"] and
                output_mutations_rejected ==
                receipt["output_mutations_rejected"],
                "savestate clone runtime differs from its receipt")
        print(
            "PHASE1_SAVESTATE_CLONE_WITNESS "
            f"pinned={PIN} sources={len(SOURCES)} "
            f"source_mutations_rejected={source_mutations_rejected} "
            f"output_mutations_rejected={output_mutations_rejected}"
        )
        print(executed.stdout, end="")


if __name__ == "__main__":
    main()
