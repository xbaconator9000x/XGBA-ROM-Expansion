#!/usr/bin/env python3
"""Compile and execute pinned mGBA VFile teardown error paths on Linux."""
import argparse
import gzip
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FILES = {
    "src/util/vfs/vfs-fd.c": (
        "2535bd0fb76740745ae038d5523ead28658f1035",
        "0073a68b6688f1baa26acaf609af52e9f29308605e449e7c3182c9f4d768da44",
    ),
    "src/util/vfs/vfs-mem.c": (
        "048194e2dd2d0b3b395a852d2092c694663c88a2",
        "6b5951a0cd634d398a69ce57766298bd32d5e6410ee0aa4e8b8894c6aaa5829b",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "src/gba/core.c": (
        "6bfc518bb8899205c07d1d0fc091a287cb42f874",
        "47a213e3f4de2299c8859822459a82ef1ae7784b0341ba49d9dd1433b8339596",
    ),
    "src/core/scripting.c": (
        "7ccb51e897685ce24b37dabc76beb27427331b4f",
        "8bb8d2ca9a744b51a96d5258b7a1cec49b724f92ae843a1504b22d4ae9d138b1",
    ),
    "src/script/stdlib.c": (
        "f84b62515315c119ec4ff5b9fb6df4de4517c738",
        "52c9fc2d9490f3f158f20c8eddfed07440ec22e4f174043f96e3704599c87b99",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
    ),
    "include/mgba-util/vector.h": (
        "c837379e2102ca6535db2b292233bd4983c3532c",
        "ae8d9ed36475bda93ab3d2ff581163cedd289b2275c5254b76ba9e4285696375",
    ),
    "include/mgba-util/memory.h": (
        "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
    ),
    "include/mgba-util/math.h": (
        "f7b3269c9d51967765379b951ba6f43d24c61865",
        "04f5ee1686f4b30744d4e62caef4cf16f2f4b80682b88a87e7e18cf117fd421e",
    ),
    "include/mgba/core/core.h": (
        "64ddf851ef00ab09416a9c1c9b5a88798fcd6fc8",
        "e77d0b72af5b76d9b66292968359122a15ab5c4c624d684af7ad339fa700e7a9",
    ),
    "include/mgba/gba/core.h": (
        "5cb0e468c100730a65199e9daeda78c2a885227d",
        "9e9eb686f85856a6c9b659f0c99d4eb5f5c831120970d616f8554a448f558c8d",
    ),
    "include/mgba/internal/gba/gba.h": (
        "65e994dc63a304cc9fb207536f09bb2c8a6cf3e5",
        "b50fc8ae1467f9ac1c6be3ba8452e22027571ff5c886695edb9be529d7962d4e",
    ),
    "include/mgba/internal/gba/savedata.h": (
        "6227be25e8c9d2c1cc14c06ded34389b96138577",
        "30481cada83cc0e3a88b55298f3081cc660e18e55ca7f5a57356e6f2a75224dc",
    ),
}
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROWS = {
    "src/util/vfs/vfs-fd.c": "bb351807533d3de29f1f87c2c3a644a70c67430f556e83e219b1e25292589942",
    "src/util/vfs/vfs-mem.c": "3c95e0a322b5aff0655ec59a1c1f5d34a740a21676da0bf5cce444d2434248ce",
    "src/gba/savedata.c": "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
    "src/gba/gba.c": "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
    "src/gba/core.c": "3431f140bdc22e29d591eacae07aadc5b4b0ae20b4c9036ef3d7e89dc9528784",
    "src/core/scripting.c": "9975d4c10ec523f164e9e0292ae795ccb8522343d7b926c233bee159de08abc8",
    "src/script/stdlib.c": "db8b3609ef7ae747d57b1b3a163dd9af6fbbf9c22d661b2a5261e274cbae6ad1",
    "include/mgba-util/vfs.h": "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
    "include/mgba-util/common.h": "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
    "include/mgba-util/dllexports.h": "5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070",
    "include/mgba-util/vector.h": "6a1179a47870dc93b443eff57599611d1b8d43d87560de25863a9e5805d83eb7",
    "include/mgba-util/memory.h": "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
    "include/mgba-util/math.h": "87d819c03b064e4665a27b5563f4a7261cfcdad051913229884d4f72cfd813f9",
    "include/mgba/core/core.h": "0fb39db4601aad348aa35a4adbb7a4a41b05a26128957595547a95bc72208a87",
    "include/mgba/gba/core.h": "08637ccef3dea51935b64aeea0a34d40008862ebc3eed75f7385df0394ebbd22",
    "include/mgba/internal/gba/gba.h": "d6e61894ce31db089d3fd04e64e0938d1e689fb6c7498a8056fced405bf2bba0",
    "include/mgba/internal/gba/savedata.h": "eaee2c8bdb65c51e4f40daeb80af916f57ed430c48c88286562363f687ca6de9",
}
BODY_HASHES = {
    "vfd_close": "047a214a51b79ddf2e6b01c50bdbb2fc201fb601c9e7d2fb67c917138a258af5",
    "vfd_unmap_posix": "6fa24bf9ba88d150e66baf99e3dc62fee2f8facfb439c616cd4709f307be61af",
    "vfm_unmap": "a9abf736086c31862111fbb4f2050f68be14f09b19908ffb9bf81f892b0f08b8",
    "vfm_sync": "aa681292c67cd4a34400bb3b247d30bfb2f66ed1f46a93c91436a0153c426a28",
    "ashes": "4c0e6539fb5c7aad4d915bee1cea35ba2a13b8d89d4bf5551f698a32ac683582",
    "size": "9f3e0774073a8f44195f2b1b8c2d4c20977dedd1eb8c4d7ec4c1c42e467b02d1",
    "init": "e7acccd1db65be1be7e20e49b23167b4c237d6e6646bac75d16be857269be408",
    "deinit": "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2",
    "mask": "713b702618c61c33848bf9d88c9c4799d4f133471369df394747275c3e739277",
    "load": "f272ab49e19f5be2284c9dc851f53b070606fd75b626db60a92b499c2d05c2b2",
    "unmask": "6517182aaa42db3fdc6fc4eb8582a5c9f5ff2e4364fedbf1abe4e7b7fc644709",
    "force_type": "7ffbdeaf9944c79c2fc2811070817427e071c9e49faa5f865b58d50e12b25cea",
    "unload_rom": "1c7090ddfe712b836048af6492dedb4f8c4d2ec94ac0f30f3b8e92648071b7f6",
    "gba_destroy": "45831c7737fc196fa77546805aa6f0cca2fd34565bd3d7a77d65d58e1a858535",
    "gba_core_deinit": "f118627b62bee1476c5351def9c9d5378e31091277913b6a71615ffcb789a04f",
    "savedata_restore": "8f3654b0b9164674275a28137a89decf55047436aa8df09225ccfcb326a6ea0b",
}
FIXTURE_SHA256 = "0b60bdb3178cfa60ef5f696b1a3a866b5adb490c41aa432fb16f00377d3b9bc8"
EXPECTED_LINES = (
    "PHASE1_TEARDOWN_CASE success sync_calls=1 sync_errors=0 unmap_calls=1 unmap_errors=0 close_calls=1 close_errors=0 state_cleared=1 orphan_map_read=0 retry_close=0 fresh_process_byte=161 trace=SUC",
    "PHASE1_TEARDOWN_CASE sync_failure sync_calls=1 sync_errors=1 unmap_calls=1 unmap_errors=0 close_calls=1 close_errors=0 state_cleared=1 orphan_map_read=0 retry_close=0 fresh_process_byte=162 trace=SUC",
    "PHASE1_TEARDOWN_CASE unmap_failure sync_calls=1 sync_errors=0 unmap_calls=1 unmap_errors=1 close_calls=1 close_errors=0 state_cleared=1 orphan_map_read=163 retry_close=0 fresh_process_byte=163 trace=SUC",
    "PHASE1_TEARDOWN_CASE close_failure sync_calls=1 sync_errors=0 unmap_calls=1 unmap_errors=0 close_calls=1 close_errors=1 state_cleared=1 orphan_map_read=0 retry_close=1 fresh_process_byte=164 trace=SUC",
    "PHASE1_TEARDOWN_CASE masked_writeback_short_read sync_calls=2 sync_errors=1 unmap_calls=2 unmap_errors=1 close_calls=2 close_errors=1 state_cleared=1 orphan_map_read=90 retry_close=1 fresh_process_byte=229 short_read=32 requested=4096 trace=SUCSUC",
    "PHASE1_TEARDOWN_CASE memory borrowed_unmap_live=1 borrowed_sync=1 borrowed_close=1 borrowed_byte=204 chunk_unmap_live=1 chunk_sync=1 chunk_close=1",
    "PHASE1_TEARDOWN_CASE restore_full_write caller_return=1 write_calls=2 first_write=2048 requested=2048 file_size=2048 content_match=1",
    "PHASE1_TEARDOWN_CASE restore_short_write caller_return=1 write_calls=1 first_write=1 requested=2048 file_size=1 prefix_match=1 retry=0",
    "PHASE1_TEARDOWN_CASE restore_negative_write caller_return=0 write_calls=1 first_write=-1 requested=2048 file_size=0 content_match=1",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, *, timeout=60, cwd=None, input_text=None):
    return subprocess.run(
        command, cwd=cwd, input=input_text, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=timeout
    )


def git(checkout, *command):
    return subprocess.check_output(
        ["git", "-C", str(checkout), *command], text=True
    ).strip()


def function_bodies(source, signature):
    bodies = []
    start = 0
    while True:
        position = source.find(signature, start)
        if position < 0:
            break
        start = position + len(signature)
        opening = source.find("{", position)
        semicolon = source.find(";", position)
        if opening < 0 or (semicolon >= 0 and semicolon < opening):
            continue
        depth = 0
        for offset in range(opening, len(source)):
            if source[offset] == "{":
                depth += 1
            elif source[offset] == "}":
                depth -= 1
                if depth == 0:
                    bodies.append(source[position:offset + 1])
                    break
    return bodies


def extract_function(source, signature, digest):
    matches = [
        body for body in function_bodies(source, signature)
        if hashlib.sha256(body.encode()).hexdigest() == digest
    ]
    require(len(matches) == 1,
            "missing, ambiguous, or changed pinned function: " + signature)
    return matches[0]


def verify_sources(source_root, checkout_identity):
    if checkout_identity:
        require(git(source_root, "rev-parse", "HEAD") == PIN,
                "wrong pinned mGBA revision")
    sources = {}
    for path, (blob, digest) in FILES.items():
        if checkout_identity:
            require(git(source_root, "rev-parse", "HEAD:" + path) == blob,
                    "pinned source tree blob changed: " + path)
        raw = (source_root / path).read_bytes()
        actual_blob = subprocess.check_output(
            ["git", "hash-object", "--stdin"], input=raw
        ).decode().strip()
        require(actual_blob == blob, "pinned source blob changed: " + path)
        require(hashlib.sha256(raw).hexdigest() == digest,
                "pinned source SHA-256 changed: " + path)
        sources[path] = raw.decode("utf-8")

    root = Path(__file__).resolve().parents[1]
    dossier = root / DOSSIER
    require(git(root, "hash-object", DOSSIER) == DOSSIER_BLOB,
            "pinned machine dossier blob changed")
    raw_dossier = dossier.read_bytes()
    require(hashlib.sha256(raw_dossier).hexdigest() == DOSSIER_SHA256,
            "pinned machine dossier SHA-256 changed")
    rows = {}
    with gzip.open(dossier, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            provenance = row.get("provenance", {})
            path = provenance.get("path")
            if (provenance.get("repository") != "mgba-emu/mgba" or
                    provenance.get("pinned_revision") != PIN or
                    path not in DOSSIER_ROWS):
                continue
            canonical = json.dumps(
                row, sort_keys=True, separators=(",", ":"), ensure_ascii=True
            ).encode()
            require(hashlib.sha256(canonical).hexdigest() ==
                    DOSSIER_ROWS[path],
                    "canonical dossier row changed: " + path)
            require(provenance.get("git_blob_sha") == FILES[path][0] and
                    provenance.get("source_content_sha256") == FILES[path][1],
                    "dossier source pin changed: " + path)
            require(path not in rows, "duplicate dossier row: " + path)
            rows[path] = True
    require(set(rows) == set(DOSSIER_ROWS),
            "machine dossier does not cover the teardown dependency closure")

    function_specs = (
        ("src/util/vfs/vfs-fd.c",
         "static void _vfdUnmap(struct VFile* vf, void* memory, size_t size)",
         BODY_HASHES["vfd_unmap_posix"]),
        ("src/util/vfs/vfs-fd.c", "bool _vfdClose(struct VFile* vf)",
         BODY_HASHES["vfd_close"]),
        ("src/util/vfs/vfs-mem.c",
         "void _vfmUnmap(struct VFile* vf, void* memory, size_t size)",
         BODY_HASHES["vfm_unmap"]),
        ("src/util/vfs/vfs-mem.c",
         "bool _vfmSync(struct VFile* vf, void* buffer, size_t size)",
         BODY_HASHES["vfm_sync"]),
        ("src/gba/savedata.c",
         "static void _ashesToAshes(struct mTiming* timing, void* user, uint32_t cyclesLate)",
         BODY_HASHES["ashes"]),
        ("src/gba/savedata.c",
         "size_t GBASavedataSize(const struct GBASavedata* savedata)",
         BODY_HASHES["size"]),
        ("src/gba/savedata.c",
         "void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf)",
         BODY_HASHES["init"]),
        ("src/gba/savedata.c",
         "void GBASavedataDeinit(struct GBASavedata* savedata)",
         BODY_HASHES["deinit"]),
        ("src/gba/savedata.c",
         "void GBASavedataMask(struct GBASavedata* savedata, struct VFile* vf, bool writeback)",
         BODY_HASHES["mask"]),
        ("src/gba/savedata.c",
         "bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in)",
         BODY_HASHES["load"]),
        ("src/gba/savedata.c",
         "void GBASavedataUnmask(struct GBASavedata* savedata)",
         BODY_HASHES["unmask"]),
        ("src/gba/savedata.c",
         "void GBASavedataForceType(struct GBASavedata* savedata, enum GBASavedataType type)",
         BODY_HASHES["force_type"]),
        ("src/gba/gba.c", "void GBAUnloadROM(struct GBA* gba)",
         BODY_HASHES["unload_rom"]),
        ("src/gba/gba.c", "void GBADestroy(struct GBA* gba)",
         BODY_HASHES["gba_destroy"]),
        ("src/gba/core.c", "static void _GBACoreDeinit(struct mCore* core)",
         BODY_HASHES["gba_core_deinit"]),
        ("src/gba/core.c",
         "static bool _GBACoreSavedataRestore(struct mCore* core, const void* sram, size_t size, bool writeback)",
         BODY_HASHES["savedata_restore"]),
    )
    bodies = {}
    for index, (path, signature, digest) in enumerate(function_specs):
        body = extract_function(sources[path], signature, digest)
        bodies[str(index)] = body
    require("void (*unmap)(struct VFile* vf, void* memory, size_t size);" in
            sources["include/mgba-util/vfs.h"] and
            "bool (*close)(struct VFile* vf);" in
            sources["include/mgba-util/vfs.h"],
            "VFile close/unmap return contracts changed")
    require("void (*deinit)(struct mCore*);" in
            sources["include/mgba/core/core.h"],
            "mCore deinit return contract changed")
    require("GBAUnloadROM(gba);" in
            bodies["13"] and "GBADestroy(core->board);" in bodies["14"] and
            "GBADestroy" in bodies["14"],
            "GBA/core teardown call chain changed")
    require("GBASavedataLoad(savedata, vf);" in bodies["10"] and
            "vf->close(vf);" in bodies["10"] and
            "gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);" in
            bodies["12"],
            "savedata teardown error-return sinks changed")
    require("savedataUpdated" not in bodies["12"],
            "unexpected scripting callback in GBAUnloadROM")
    require("success = GBASavedataLoad(&gba->memory.savedata, vf);" in
            bodies["15"] and "if (writeback)" in bodies["15"],
            "savedata restore caller no longer reaches the pinned writeback path")
    return sources, bodies


def reject_source_mutations(sources):
    cases = (
        ("src/util/vfs/vfs-fd.c", "msync(memory, size, MS_SYNC);",
         "msync(memory, size, MS_ASYNC);"),
        ("src/util/vfs/vfs-fd.c", "munmap(memory, size);",
         "return;"),
        ("src/util/vfs/vfs-fd.c", "if (close(vfd->fd) < 0) {",
         "if (close(vfd->fd) <= 0) {"),
        ("src/gba/savedata.c",
         "savedata->vf->unmap(savedata->vf, savedata->data, size)",
         "savedata->vf->close(savedata->vf)"),
        ("src/gba/savedata.c", "GBASavedataLoad(savedata, vf);",
         "return;"),
        ("src/gba/core.c", "success = GBASavedataLoad(&gba->memory.savedata, vf);",
         "success = true;"),
        ("src/gba/gba.c", "gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);",
         "return;"),
    )
    rejected = 0
    for path, original, replacement in cases:
        source = sources[path]
        require(source.count(original) >= 1,
                "source mutation anchor missing: " + original)
        changed = source.replace(original, replacement, 1).encode()
        if hashlib.sha256(changed).hexdigest() != FILES[path][1]:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith("PHASE1_TEARDOWN_DONE\n") and
            output.count("PHASE1_TEARDOWN_DONE\n") == 1,
            "native teardown output lacks a unique terminal marker")
    lines = output.splitlines()
    require(lines == [*EXPECTED_LINES, "PHASE1_TEARDOWN_DONE"],
            "native teardown observations differ from the pinned expected matrix")
    return {
        "cases": [line.split()[1] for line in EXPECTED_LINES],
        "async_sync_failure_preserved": True,
        "unmap_error_return_channel": False,
        "close_failure_return_ignored_by_gba_unload": True,
        "masked_short_read_result_ignored": True,
        "fresh_process_page_cache_reads": 5,
        "savedata_updated_reference_in_unload": False,
        "restore_short_write_reported_success": True,
        "restore_negative_write_reported_failure": True,
        "restore_short_write_retried": False,
    }


def reject_evidence_mutations(output):
    cases = (
        output.replace("sync_errors=1", "sync_errors=0", 1),
        output.replace("unmap_errors=1", "unmap_errors=0", 1),
        output.replace("close_errors=1", "close_errors=0", 1),
        output.replace("orphan_map_read=163", "orphan_map_read=0", 1),
        output.replace("retry_close=1", "retry_close=0", 1),
        output.replace("fresh_process_byte=229", "fresh_process_byte=0", 1),
        output.replace("short_read=32 requested=4096", "short_read=4096 requested=4096", 1),
        output.replace("trace=SUCSUC", "trace=SUC", 1),
        output.replace("borrowed_unmap_live=1", "borrowed_unmap_live=0", 1),
        output.replace("state_cleared=1", "state_cleared=0", 1),
        output.replace("PHASE1_TEARDOWN_DONE\n", "", 1),
        output.replace("restore_short_write caller_return=1", "restore_short_write caller_return=0", 1),
        output.replace("write_calls=1 first_write=1", "write_calls=2 first_write=1", 1),
        output.replace("restore_negative_write caller_return=0", "restore_negative_write caller_return=1", 1),
        output.replace("restore_full_write caller_return=1 write_calls=2 first_write=2048 requested=2048 file_size=2048 content_match=1",
                       "restore_full_write caller_return=1 write_calls=2 first_write=2048 requested=2048 file_size=2048 content_match=0",
                       1),
    )
    for changed in cases:
        try:
            parse_output(changed)
        except ValueError:
            continue
        raise ValueError("native teardown evidence mutation escaped")
    return len(cases)


def main():
    parser = argparse.ArgumentParser()
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--checkout", type=Path)
    source_group.add_argument("--source-dir", type=Path)
    parser.add_argument("--harness", type=Path, required=True)
    args = parser.parse_args()
    source_root = (args.checkout or args.source_dir).resolve()
    tree_identity_verified = bool(args.checkout)
    sources, bodies = verify_sources(source_root, tree_identity_verified)
    source_mutations_rejected = reject_source_mutations(sources)

    fixture = args.harness.read_text(encoding="utf-8")
    fixture_digest = hashlib.sha256(fixture.encode()).hexdigest()
    require(fixture_digest == FIXTURE_SHA256,
            "native teardown fixture SHA-256 changed")
    markers = {
        "PHASE1_INSERT_PINNED_ASHES": bodies["4"],
        "PHASE1_INSERT_PINNED_SAVEDATA_SIZE": bodies["5"],
        "PHASE1_INSERT_PINNED_SAVEDATA_INIT": bodies["6"],
        "PHASE1_INSERT_PINNED_SAVEDATA_DEINIT": bodies["7"],
        "PHASE1_INSERT_PINNED_SAVEDATA_MASK": bodies["8"],
        "PHASE1_INSERT_PINNED_SAVEDATA_LOAD": bodies["9"],
        "PHASE1_INSERT_PINNED_SAVEDATA_UNMASK": bodies["10"],
        "PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM": bodies["12"],
        "PHASE1_INSERT_PINNED_GBA_CORE_SAVEDATA_RESTORE": bodies["15"],
    }
    expanded = fixture
    for marker, body in markers.items():
        require(expanded.count(marker) == 1,
                "native teardown fixture extraction marker changed: " + marker)
        expanded = expanded.replace(marker, body)

    compiler = "gcc"
    macro_probe = run(
        [compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-dM", "-E",
         "-x", "c", "-"],
        input_text="#include <unistd.h>\n#include <sys/mman.h>\n",
    )
    mapped_files_match = re.search(
        r"^#define _POSIX_MAPPED_FILES (\d+L?)$", macro_probe.stdout, re.M
    )
    require(macro_probe.returncode == 0 and mapped_files_match,
            "native compiler lacks POSIX mapped-file backend")

    with tempfile.TemporaryDirectory(prefix="xgba-mgba-vfs-teardown-") as directory:
        directory = Path(directory)
        source_path = directory / "vfs-teardown-native.c"
        binary = directory / "vfs-teardown-native"
        source_path.write_text(expanded, encoding="utf-8")
        command = [
            compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L",
            "-DENABLE_VFS_FD", "-I", str(source_root / "include"),
            "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
            str(source_root / "src/util/vfs/vfs-fd.c"),
            str(source_root / "src/util/vfs/vfs-mem.c"),
            str(source_path), "-Wl,--wrap=msync", "-Wl,--wrap=munmap",
            "-Wl,--wrap=close", "-Wl,--wrap=read", "-Wl,--wrap=write",
            "-o", str(binary),
        ]
        compiled = run(command, timeout=90)
        require(compiled.returncode == 0,
                "pinned native teardown harness compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=30)
        require(executed.returncode == 0,
                "pinned native teardown harness failed:\n" + executed.stdout)
        output = executed.stdout
        observations = parse_output(output)
        evidence_mutations_rejected = reject_evidence_mutations(output)
        artifact_digest = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "class": "PINNED_MGBA_LINUX_VFILE_TEARDOWN_ERROR_PROPAGATION_NATIVE",
        "execution_scope": "COMPILED_EXTRACTED_PINNED_FUNCTIONS_AND_REAL_PINNED_POSIX_VFILE_TRANSLATION_UNITS_WITH_HOST_WRITE_FAULT_INJECTION",
        "mgba_commit": PIN,
        "source_tree_identity_verified": tree_identity_verified,
        "source_git_blobs": {path: value[0] for path, value in FILES.items()},
        "source_sha256": {path: value[1] for path, value in FILES.items()},
        "machine_dossier_blob": DOSSIER_BLOB,
        "machine_dossier_sha256": DOSSIER_SHA256,
        "machine_dossier_row_sha256": DOSSIER_ROWS,
        "function_sha256": BODY_HASHES,
        "fixture_sha256": fixture_digest,
        "original_vfs_fd_translation_unit_compiled": True,
        "original_vfs_memory_translation_unit_compiled": True,
        "original_savedata_init_deinit_mask_load_unmask_executed": True,
        "original_gba_unload_rom_executed": True,
        "original_gba_core_savedata_restore_executed": True,
        "original_gba_core_savedata_restore_full_write_and_fault_cases": True,
        "full_mgba_core_translation_unit_compiled": False,
        "full_headless_process_observed": False,
        "frontend_runtime_observed": False,
        "gba_core_deinit_and_destroy_source_audited_not_compiled": True,
        "compiler_version": subprocess.check_output(
            [compiler, "--version"], text=True
        ).splitlines()[0],
        "posix_mapped_files_macro": mapped_files_match.group(1),
        "backend": "POSIX fd VFile",
        "compile_command": command,
        "artifact_sha256": artifact_digest,
        "source_mutations_rejected": source_mutations_rejected,
        "evidence_mutations_rejected": evidence_mutations_rejected,
        "observations": observations,
        "raw_output": output.splitlines(),
        "physical_flash_tested": False,
        "power_loss_durability_tested": False,
        "process_restart_after_power_loss_tested": False,
        "sav_interoperability_tested": False,
        "stock_gameplay_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_VFS_TEARDOWN_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
