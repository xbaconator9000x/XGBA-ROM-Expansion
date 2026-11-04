#!/usr/bin/env python3
"""Compile and execute pinned mGBA stdio VFile save paths on Linux."""
import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

PIN = "fd9dc5c2cbf234365068855851107e762fc6211b"
FILES = {
    "src/util/vfs/vfs-file.c": (
        "4a63e53f842b31b24d6188e6525ddcf121a0c7da",
        "77737a3fa897db96e31f1f5e56faa0c06afa0cc86c7697642b28026308ba0921",
    ),
    "src/util/vfs.c": (
        "3158c52659a83333cb23aeb0dd7ea4bba35908fc",
        "7b94fe172db57a97fef22047e79378bba3c8848b0808bca014d3a6554c1adc06",
    ),
    "src/gba/savedata.c": (
        "fdafa5b99a50ce0abcb9adb4dc25bae6497a65fb",
        "9887e36795ae51e39eecad09565d27d3feabe316d3e595b17f288e3205e13161",
    ),
    "src/gba/gba.c": (
        "c30bd943909dc00df0b5b9932e6d9ddb6e1c404e",
        "e84eaba17f6c96ac7b78431afaee79d7633dd50118f92e31e4432793f80c4c7b",
    ),
    "include/mgba-util/vfs.h": (
        "6c9bd299153af4c3c9cd5487f2425a2481331ee5",
        "4c829529f21c424196b4d1efe25ce11227312437cf1aa5028cae94a741bf6656",
    ),
    "include/mgba-util/memory.h": (
        "325f748f6fddc33a5539739ebc6eff6f3bb42bad",
        "509b56f31b2a279d954a16799501a1585cf7aa55f917a180432283b0205c198c",
    ),
    "include/mgba-util/common.h": (
        "923e93086adfa09c9a55fcc2f0f6fa4d560e5888",
        "ec13354a050e4a7432232214b9991dd74000980ab2b8949389af0871cc1b799f",
    ),
    "include/mgba-util/dllexports.h": (
        "a44480df6ec26821b8616650b2575ba794848eca",
        "96871f8861195f4ff9fedd861ff07ed5b0a10a0e7642d6a780a8221cafd163d4",
    ),
    "include/mgba/internal/defines.h": (
        "67b8ec8fd2f51ee2c0c6231443af752158397b03",
        "167896b30ed7f1cd3f9e5cbc99ee994a48a094b3e95989ab2f9e1ebf8cf4b46b",
    ),
}
DOSSIER = "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz"
DOSSIER_BLOB = "3b982876c7d810a827af8c80c7e5d9231fdaa327"
DOSSIER_SHA256 = "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609"
DOSSIER_ROWS = {
    "src/util/vfs/vfs-file.c": "263f5e29518c63b6c0cfb36819debd8c57dfc630a6490376255e2f1fd1fe3849",
    "src/util/vfs.c": "47d41523b021d9d124e30aae47163dd32773f50223bcde11b82d4b27508107a2",
    "src/gba/savedata.c": "99a6b3e97c52d67712e10204e08ced8819c7330e899b9f767aa280fc330c42e0",
    "src/gba/gba.c": "d1870b438fe6dd9bfa628a99d90189778e112588c14ae08f28fa379903595056",
    "include/mgba-util/vfs.h": "5d4c30179d703f5b013badf083d6c99c736186091873d65edcb3f0943c2763dd",
    "include/mgba-util/memory.h": "cf858e1e109d1346cab0d7b30bcd119c207cfb84e9b45a3e73321c1e3576315e",
    "include/mgba-util/common.h": "b0a970a0105d3d1b109325bda5fedc99cff7a182cb010f24f826944faa0616ec",
    "include/mgba-util/dllexports.h": "5a0c3158c1515885d4f326ea52cc891074b5e0cd54e40460eab89d55a1746070",
    "include/mgba/internal/defines.h": "05a6cd7248412bb03041f85841bf51db1f6a52e4b27bea5ac19c15ffa36a7bc2",
}
BODY_HASHES = {
    "vfs_open": "e41233c9f3694959554a63cb8ef2a2fdb456f245a11b26e79a533ff1e1c7a137",
    "vff_open": "f29e70f483a5ec25818a2107fc9519a8ce4b266289750970907060022d09ee5c",
    "vff_from_file": "422ad7388c3f935d66f453f2bd9812984f588026abc12d848a5a76c23767bffe",
    "vff_close": "2f2fbd58200cfe6f0fe411473192c253df86e50a09326f9caab4af1efcba5b9b",
    "vff_seek": "e225157f24d8b99ac6024bd204276b4e20d74e9973e8b07f074896819576d1e0",
    "vff_read": "f745b6405a74d4c4e107a4641e7b8aafe9cb700537a575f130d0ad17c6f47a5e",
    "vff_write": "cd62140cba8c43b11d0b049b943e1852b42c704366ecbb9b81d4fba1af9dd215",
    "vff_map": "74f93901553f023aa587c78daf6c1947efa3a0724733a5279f66ba5a3a4c46f7",
    "vff_unmap": "698e40b37554f78d53dd7b2b0bceea10f2397fe0c72c5e3e412b6234db7a9582",
    "vff_truncate": "ddc407cd412f7e431acba429d9ed9da9d26a7998b7e8e6df34a50944b8a394d0",
    "vff_size": "1644b0b5fc9d435abdd5e7528e81f6b4eccfd5430185e1d2d0101a1d6baff733",
    "vff_sync": "b215c978bac8c6538526073b0ae668bf278d0729f14a264c7293dc622e9f9135",
    "savedata_size": "9f3e0774073a8f44195f2b1b8c2d4c20977dedd1eb8c4d7ec4c1c42e467b02d1",
    "savedata_init": "e7acccd1db65be1be7e20e49b23167b4c237d6e6646bac75d16be857269be408",
    "savedata_deinit": "830e75777a5a94797eb4a5cc0d6294952340887bc5d5457ca4ea3d228a94f7d2",
    "savedata_mask": "713b702618c61c33848bf9d88c9c4799d4f133471369df394747275c3e739277",
    "savedata_load": "f272ab49e19f5be2284c9dc851f53b070606fd75b626db60a92b499c2d05c2b2",
    "savedata_unmask": "6517182aaa42db3fdc6fc4eb8582a5c9f5ff2e4364fedbf1abe4e7b7fc644709",
    "savedata_force_type": "7ffbdeaf9944c79c2fc2811070817427e071c9e49faa5f865b58d50e12b25cea",
    "savedata_init_sram": "d9b4d85db33cea2da5073208f512fe3c82d8f7450c1d074baeff37c79a29efbc",
    "gba_load_save": "cfbfe0068178dbc3c1ed8e8a034ed861cfc0deb777e32bcc48979ad710732b73",
    "gba_unload_rom": "1c7090ddfe712b836048af6492dedb4f8c4d2ec94ac0f30f3b8e92648071b7f6",
    "m_savedata_clean": "c34a3ce89da1f2e1823314ea38692d471a762746aa4d9d020c2faa50263d9fcb",
    "savedata_clean": "3fc3989ccac6c04fa32780fcffcb5cd49ff22ff306826e569c85d52647f701bb",
    "gba_frame_ended": "79da6a49b3bdb7101a950cef81837a5f18d2f1bda6294fa3ffe589ae25679942",
}
FIXTURE_SHA256 = "2458e0ed4e5cafc1e60dbac18e2bc5945b718377bd25b55213e63f55bf5c7a39"
EXPECTED_LINES = (
    "PHASE1_STDIO_CASE regular_lifecycle backend=stdio data_cleared=1 child_byte=92",
    "PHASE1_STDIO_CASE mapped_short_unmap requested=4096 written=3 data_cleared=1",
    "PHASE1_STDIO_CASE raw_short_load source_bytes=8 written=3 load_result=1",
    "PHASE1_STDIO_CASE unmask_short_read read_bytes=32 requested=4096 unmask_completed=1 child_byte=212",
    "PHASE1_STDIO_CASE injected_flush write_return=5 sync_result=0 injected=1 close_result=1 child_byte=70",
    "PHASE1_STDIO_CASE dev_full_clean write_errors=1 dirty=0 rtc_writes=0 close_result=1",
    "PHASE1_STDIO_CASE unload_close_error underlying_closed=1 wrapper_retained=1 savedata_cleared=1",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(command, *, timeout=60, cwd=None):
    return subprocess.run(
        command, cwd=cwd, text=True, stdout=subprocess.PIPE,
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


FUNCTION_SPECS = (
    ("include/mgba/internal/defines.h",
     "static inline bool mSavedataClean(int* dirty, uint32_t* dirtAge, uint32_t frameCount)",
     "m_savedata_clean"),
    ("src/util/vfs.c", "struct VFile* VFileOpen(const char* path, int flags)",
     "vfs_open"),
    ("src/util/vfs/vfs-file.c",
     "struct VFile* VFileFOpen(const char* path, const char* mode)", "vff_open"),
    ("src/util/vfs/vfs-file.c",
     "struct VFile* VFileFromFILE(FILE* file)", "vff_from_file"),
    ("src/util/vfs/vfs-file.c", "bool _vffClose(struct VFile* vf)", "vff_close"),
    ("src/util/vfs/vfs-file.c",
     "off_t _vffSeek(struct VFile* vf, off_t offset, int whence)", "vff_seek"),
    ("src/util/vfs/vfs-file.c",
     "ssize_t _vffRead(struct VFile* vf, void* buffer, size_t size)", "vff_read"),
    ("src/util/vfs/vfs-file.c",
     "ssize_t _vffWrite(struct VFile* vf, const void* buffer, size_t size)",
     "vff_write"),
    ("src/util/vfs/vfs-file.c",
     "static void* _vffMap(struct VFile* vf, size_t size, int flags)", "vff_map"),
    ("src/util/vfs/vfs-file.c",
     "static void _vffUnmap(struct VFile* vf, void* memory, size_t size)",
     "vff_unmap"),
    ("src/util/vfs/vfs-file.c",
     "static void _vffTruncate(struct VFile* vf, size_t size)", "vff_truncate"),
    ("src/util/vfs/vfs-file.c", "static ssize_t _vffSize(struct VFile* vf)",
     "vff_size"),
    ("src/util/vfs/vfs-file.c",
     "static bool _vffSync(struct VFile* vf, void* buffer, size_t size)",
     "vff_sync"),
    ("src/gba/savedata.c",
     "size_t GBASavedataSize(const struct GBASavedata* savedata)",
     "savedata_size"),
    ("src/gba/savedata.c",
     "void GBASavedataInit(struct GBASavedata* savedata, struct VFile* vf)",
     "savedata_init"),
    ("src/gba/savedata.c", "void GBASavedataDeinit(struct GBASavedata* savedata)",
     "savedata_deinit"),
    ("src/gba/savedata.c",
     "void GBASavedataMask(struct GBASavedata* savedata, struct VFile* vf, bool writeback)",
     "savedata_mask"),
    ("src/gba/savedata.c",
     "bool GBASavedataLoad(struct GBASavedata* savedata, struct VFile* in)",
     "savedata_load"),
    ("src/gba/savedata.c",
     "void GBASavedataUnmask(struct GBASavedata* savedata)",
     "savedata_unmask"),
    ("src/gba/savedata.c",
     "void GBASavedataForceType(struct GBASavedata* savedata, enum GBASavedataType type)",
     "savedata_force_type"),
    ("src/gba/savedata.c",
     "void GBASavedataInitSRAM(struct GBASavedata* savedata)",
     "savedata_init_sram"),
    ("src/gba/savedata.c",
     "void GBASavedataClean(struct GBASavedata* savedata, uint32_t frameCount)",
     "savedata_clean"),
    ("src/gba/gba.c", "bool GBALoadSave(struct GBA* gba, struct VFile* sav)",
     "gba_load_save"),
    ("src/gba/gba.c", "void GBAUnloadROM(struct GBA* gba)", "gba_unload_rom"),
    ("src/gba/gba.c", "void GBAFrameEnded(struct GBA* gba)", "gba_frame_ended"),
)


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
            "machine dossier does not cover the stdio save closure")

    bodies = {}
    for path, signature, key in FUNCTION_SPECS:
        bodies[key] = extract_function(
            sources[path], signature, BODY_HASHES[key])
    require(
        sources["src/util/vfs.c"].index("#ifdef ENABLE_VFS_FILE") <
        sources["src/util/vfs.c"].index("#elif defined(PSP2)") and
        sources["src/util/vfs.c"].index("return VFileFOpen(path, chflags);") <
        sources["src/util/vfs.c"].index("#elif defined(ENABLE_VFS_FD)"),
        "stdio VFile dispatcher precedence changed")
    require("return fflush(vff->file) == 0;" in bodies["vff_sync"] and
            "fwrite(memory, size, 1, vff->file);" in bodies["vff_unmap"] and
            "return fwrite(buffer, 1, size, vff->file);" in bodies["vff_write"],
            "stdio write/sync/unmap return paths changed")
    require("return in->read(in, savedata->data, size) == size;" in
            bodies["savedata_load"] and
            "GBASavedataLoad(savedata, vf);" in bodies["savedata_unmask"] and
            "if (!GBASavedataLoad" not in bodies["savedata_unmask"],
            "savedata load/unmask result propagation changed")
    require("gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);" in
            bodies["gba_unload_rom"] and
            "if (!gba->memory.savedata.realVf->close" not in
            bodies["gba_unload_rom"],
            "GBA unload close-result handling changed")
    require("savedata->vf->sync(savedata->vf, savedata->data, size)" in
            bodies["savedata_clean"] and
            "GBASavedataClean(&gba->memory.savedata" in
            bodies["gba_frame_ended"] and
            "callbacks->savedataUpdated && wasDirty && "
            "!gba->memory.savedata.dirty" in bodies["gba_frame_ended"],
            "savedata sync/callback boundary changed")
    return sources, bodies


def reject_source_mutations(sources):
    cases = (
        ("src/util/vfs.c", "return VFileFOpen(path, chflags);",
         "return VFileOpenFD(path, flags);"),
        ("src/util/vfs/vfs-file.c",
         "return fwrite(buffer, 1, size, vff->file);", "return size;"),
        ("src/util/vfs/vfs-file.c",
         "return fflush(vff->file) == 0;", "return true;"),
        ("src/util/vfs/vfs-file.c",
         "fwrite(memory, size, 1, vff->file);",
         "if (fwrite(memory, size, 1, vff->file) != 1) return;"),
        ("src/gba/savedata.c",
         "read = savedata->vf->write(savedata->vf, buffer, read);",
         "if (savedata->vf->write(savedata->vf, buffer, read) != read) return false;"),
        ("src/gba/savedata.c", "GBASavedataLoad(savedata, vf);",
         "if (!GBASavedataLoad(savedata, vf)) return;"),
        ("src/gba/gba.c",
         "gba->memory.savedata.realVf->close(gba->memory.savedata.realVf);",
         "if (!gba->memory.savedata.realVf->close(gba->memory.savedata.realVf)) return;"),
        ("src/gba/savedata.c",
         "if (savedata->data && savedata->vf->sync(savedata->vf, savedata->data, size))",
         "if (savedata->data)"),
        ("src/gba/gba.c",
         "callbacks->savedataUpdated && wasDirty && !gba->memory.savedata.dirty",
         "callbacks->savedataUpdated && wasDirty"),
    )
    rejected = 0
    for path, original, replacement in cases:
        require(sources[path].count(original) == 1,
                "source mutation anchor missing or ambiguous: " + original)
        changed = sources[path].replace(original, replacement, 1).encode()
        if hashlib.sha256(changed).hexdigest() != FILES[path][1]:
            rejected += 1
    require(rejected == len(cases), "a pinned source mutation escaped")
    return rejected


def parse_output(output):
    require(output.endswith("PHASE1_STDIO_DONE\n") and
            output.count("PHASE1_STDIO_DONE\n") == 1,
            "native stdio output lacks a unique terminal marker")
    require(output.splitlines() == [*EXPECTED_LINES, "PHASE1_STDIO_DONE"],
            "native stdio observations differ from the pinned expected matrix")
    return {
        "cases": [line.split()[1] for line in EXPECTED_LINES],
        "stdio_dispatcher_selected": True,
        "raw_short_write_reported_as_load_success": True,
        "mapped_unmap_has_no_error_return": True,
        "unmask_load_failure_result_ignored": True,
        "flush_error_reported_by_sync": True,
        "dirty_cleared_before_failed_sync": True,
        "rtc_write_skipped_after_sync_failure": True,
        "frame_end_callback_boundary_source_audited_not_executed": True,
        "unload_ignores_close_failure": True,
    }


def reject_evidence_mutations(output):
    cases = (
        output.replace("written=3 load_result=1", "written=3 load_result=0", 1),
        output.replace("written=3 data_cleared=1",
                       "written=4096 data_cleared=1", 1),
        output.replace("read_bytes=32", "read_bytes=4096", 1),
        output.replace("sync_result=0 injected=1",
                       "sync_result=1 injected=1", 1),
        output.replace("dev_full_clean write_errors=1",
                       "dev_full_clean write_errors=0", 1),
        output.replace("dirty=0 rtc_writes=0", "dirty=1 rtc_writes=0", 1),
        output.replace("wrapper_retained=1", "wrapper_retained=0", 1),
        output.replace("child_byte=212", "child_byte=0", 1),
        output.replace("PHASE1_STDIO_DONE\n", "", 1),
        output.replace("PHASE1_STDIO_DONE\n",
                       "PHASE1_STDIO_CASE extra=1\nPHASE1_STDIO_DONE\n", 1),
    )
    rejected = 0
    for changed in cases:
        try:
            parse_output(changed)
        except ValueError:
            rejected += 1
    require(rejected == len(cases), "a stdio evidence mutation escaped")
    return rejected


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
    require(FIXTURE_SHA256 != "FIXTURE_HASH_PENDING" and
            fixture_digest == FIXTURE_SHA256,
            "native stdio fixture SHA-256 changed")
    markers = {
        "PHASE1_INSERT_PINNED_M_SAVEDATA_CLEAN":
            bodies["m_savedata_clean"],
        "PHASE1_INSERT_PINNED_VFILE_OPEN": bodies["vfs_open"],
        "PHASE1_INSERT_PINNED_SAVEDATA_SIZE": bodies["savedata_size"],
        "PHASE1_INSERT_PINNED_SAVEDATA_INITIALIZER_BODY":
            bodies["savedata_init"],
        "PHASE1_INSERT_PINNED_SAVEDATA_DEINIT": bodies["savedata_deinit"],
        "PHASE1_INSERT_PINNED_SAVEDATA_MASK": bodies["savedata_mask"],
        "PHASE1_INSERT_PINNED_SAVEDATA_LOAD": bodies["savedata_load"],
        "PHASE1_INSERT_PINNED_SAVEDATA_UNMASK": bodies["savedata_unmask"],
        "PHASE1_INSERT_PINNED_SAVEDATA_FORCE_TYPE":
            bodies["savedata_force_type"],
        "PHASE1_INSERT_PINNED_SRAM_INITIALIZER_BODY":
            bodies["savedata_init_sram"],
        "PHASE1_INSERT_PINNED_SAVEDATA_CLEAN": bodies["savedata_clean"],
        "PHASE1_INSERT_PINNED_GBA_LOAD_SAVE": bodies["gba_load_save"],
        "PHASE1_INSERT_PINNED_GBA_UNLOAD_ROM": bodies["gba_unload_rom"],
    }
    expanded = fixture
    for marker, body in markers.items():
        require(expanded.count(marker) == 1,
                "native stdio extraction marker changed: " + marker)
        expanded = expanded.replace(marker, body)

    compiler = "gcc"
    command = [
        compiler, "-std=c11", "-D_POSIX_C_SOURCE=200809L", "-DENABLE_VFS",
        "-DENABLE_VFS_FILE", "-I", str(source_root / "include"),
        "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
        str(source_root / "src/util/vfs/vfs-file.c"),
    ]
    with tempfile.TemporaryDirectory(prefix="xgba-mgba-vfs-stdio-") as directory:
        directory = Path(directory)
        source_path = directory / "vfs-stdio-native.c"
        binary = directory / "vfs-stdio-native"
        source_path.write_text(expanded, encoding="utf-8")
        command.extend([
            str(source_path), "-Wl,--wrap=fflush", "-Wl,--wrap=fwrite",
            "-o", str(binary),
        ])
        compiled = run(command, timeout=90)
        require(compiled.returncode == 0,
                "pinned native stdio compile failed:\n" + compiled.stdout)
        executed = run([str(binary)], timeout=30)
        require(executed.returncode == 0,
                "pinned native stdio harness failed:\n" + executed.stdout)
        output = executed.stdout
        observations = parse_output(output)
        evidence_mutations_rejected = reject_evidence_mutations(output)
        artifact_digest = hashlib.sha256(binary.read_bytes()).hexdigest()

    evidence = {
        "class": "PINNED_MGBA_LINUX_STDIO_VFILE_SAVE_TEARDOWN_NATIVE",
        "mgba_commit": PIN,
        "source_tree_identity_verified": tree_identity_verified,
        "source_git_blobs": {path: value[0] for path, value in FILES.items()},
        "source_sha256": {path: value[1] for path, value in FILES.items()},
        "machine_dossier_blob": DOSSIER_BLOB,
        "machine_dossier_sha256": DOSSIER_SHA256,
        "machine_dossier_row_sha256": DOSSIER_ROWS,
        "function_sha256": BODY_HASHES,
        "fixture_sha256": fixture_digest,
        "original_stdio_vfs_translation_unit_compiled": True,
        "original_vfile_open_dispatcher_executed": True,
        "original_gba_load_save_and_savedata_lifecycle_executed": True,
        "original_gba_unload_rom_executed": True,
        "original_savedata_clean_executed": True,
        "gba_frame_ended_callback_path_source_audited_not_executed": True,
        "controlled_fopencookie_faults": ["short-write", "read", "close"],
        "controlled_fflush_failure_injected": True,
        "native_linux_dev_full_failure_executed": True,
        "compiler_version": subprocess.check_output(
            [compiler, "--version"], text=True
        ).splitlines()[0],
        "compile_command": command,
        "artifact_sha256": artifact_digest,
        "source_mutations_rejected": source_mutations_rejected,
        "evidence_mutations_rejected": evidence_mutations_rejected,
        "observations": observations,
        "raw_output": output.splitlines(),
        "fsync_or_power_loss_durability_tested": False,
        "real_mgba_frontend_or_gameplay_tested": False,
        "sav_interoperability_tested": False,
        "physical_flash_tested": False,
        "independent_approvals": 0,
        "gate": "FAIL_INCOMPLETE",
    }
    print("PHASE1_STDIO_VFILE_EVIDENCE " +
          json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
