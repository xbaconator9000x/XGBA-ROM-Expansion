#!/usr/bin/env python3
"""Verify the pinned Porymap Tileset persistence boundary and bounded native witness."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import zipfile
from pathlib import Path

PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
DOSSIER_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
DOSSIER_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"

FILES = {
    "src/core/tileset.cpp": {
        "blob": "0aa1f7d6726e3c8670f0758724284c792f7d9272",
        "sha256": "ec94552b325e26362046b5288a6c448d62ff4407c8bfa9cb5ed392407adc4b99",
        "row": "6fb6cc663f859d2783badd95b7606b497e2c7da2d322fcc1e4e04b367f9ba7e2",
        "role": "Focal full-file semantic scope: Tileset ownership, ID mapping, source generators, binary/image/palette load/save, dirty state, and query helpers.",
    },
    "include/core/tileset.h": {
        "blob": "dcf55ec182200985125ee308a1ac7c8df54ab066",
        "sha256": "d1c8b5b37bfa14ccc528d648d9250ce23b25a668dec013e9d159095fbfe8c613",
        "row": "31030025f279eab70c34efe0941876015dee23fd74439b25206b3959f9515009",
        "role": "Focal full-file declaration/ownership scope for Tileset, save/load entry points, owned metatiles, images, palettes, and dirty flag.",
    },
    "src/project.cpp": {
        "blob": "d43b0949303433111d4478ad76117c2b3445dd13",
        "sha256": "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
        "row": "b6b90abf56f02452537a9b096fa191ead9ee7360dd19d72c6f5486834bed02d7",
        "role": "Caller context only: Project::saveTilesets aggregates primary/secondary save results; Project::createTileset ignores save result.",
    },
    "include/project.h": {
        "blob": "50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354",
        "sha256": "7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51",
        "row": "0a5103fa34ee62748f39cbcbd0d50c3bb9ccabc824cf9813ca53bd5118cc69eb",
        "role": "Caller declaration context only; not a new whole-file semantic review.",
    },
    "src/ui/tileseteditor.cpp": {
        "blob": "723a2afdeb89c1752e9811a07715462c2279c645",
        "sha256": "a85e7827754d3f08cec5ebe90aa7a737958524ac379d563adfd269d1b7557ced",
        "row": "940f1b1723b84449dbc3f20648e057643c96d9be19a08e9fa210746193a35ee7",
        "role": "Caller context only: UI save status/dirty behavior and post-save layout/editor updates.",
    },
    "src/scriptapi/apimap.cpp": {
        "blob": "dcd4fc3300ca9dabb283ea2f803b396702d0715e",
        "sha256": "169dbd39e409d3fadfa09a224cd9842c78a4157802e9c7b4ba8ce3cee71e066c",
        "row": "792d485116bb9d872e8d54172a89eeb596ba6878a0160920e464ffe486bed9f0",
        "role": "Caller context only: script API mutators invoke saveMetatiles/saveMetatileAttributes and discard their return values.",
    },
    "porymap.pro": {
        "blob": "53d8055ecfe5d88afb6f183b82d4a3472727ad4f",
        "sha256": "cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996",
        "row": "93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2",
        "role": "Build context only: links the focal Tileset source and Qt Core/Gui application dependencies.",
    },
    "LICENSE.md": {
        "blob": "65c5ca88a67c30becee01c5a8816d964b03862f9",
        "sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
        "row": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
        "role": "Pinned root notice context; not a distribution-compliance conclusion.",
    },
}

SHORTLIST = (
    {
        "rank": 1,
        "id": "porymap-tileset-persistence",
        "status": "SELECTED_NEEDS_EVIDENCE",
        "focal_paths": ["include/core/tileset.h", "src/core/tileset.cpp"],
        "reason": "Distinct high-impact asset persistence path with independently pinned source identities, direct UI and script callers, and a bounded native Qt failure control.",
        "limits": "Candidate archive rows are automated triage, not original semantic receipts; full GUI/project behavior and multi-file recovery remain unverified.",
    },
    {
        "rank": 2,
        "id": "porymap-layout-blockdata-persistence",
        "status": "EXCLUDED_EXISTING_SEMANTIC_OVERLAP",
        "focal_paths": ["src/core/maplayout.cpp", "src/core/blockdata.cpp"],
        "evidence": "docs/PHASE1_P0_PORYMAP_PACKED_BLOCK_MASK_LIFETIME_2026-10-27.md",
        "reason": "Existing dossier already analyzes serialization, ignored QFile::write result, odd trailing bytes, and dimension reconciliation.",
    },
    {
        "rank": 3,
        "id": "firered-mapjson-authored-order",
        "status": "EXCLUDED_EXISTING_PACKAGE",
        "focal_paths": ["tools/mapjson"],
        "evidence": "tools/mapjson_semantic_proof.py and docs/phase1-disposition-candidates/0032-firered-mapjson-generator.md",
        "reason": "Existing generator/authored-order evidence; repeating it would not be a distinct semantic package.",
    },
    {
        "rank": 4,
        "id": "mgba-matrix-savestate",
        "status": "EXCLUDED_EXISTING_PACKAGE",
        "focal_paths": ["src/gba"],
        "evidence": "tools/phase1_mgba_matrix_prefetch_lifecycle.py and tools/phase1_firered_mgba_savestate_mapping.py",
        "reason": "Existing matrix/prefetch and save-state mapping evidence.",
    },
    {
        "rank": 5,
        "id": "poryscript-generated-include",
        "status": "EXCLUDED_EXISTING_PACKAGE",
        "focal_paths": ["scripts.pory", "scripts.inc"],
        "evidence": "docs/phase1-review-readiness/poryscript-compiler-source-closure-20261105.md",
        "reason": "Existing generated-include and consumer closure evidence.",
    },
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    header = b"blob " + str(len(data)).encode("ascii") + b"\0"
    return hashlib.sha1(header + data).hexdigest()


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def source_function(source: str, marker: str) -> str:
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for pos in range(opening, len(source)):
        if source[pos] == "{":
            depth += 1
        elif source[pos] == "}":
            depth -= 1
            if depth == 0:
                return source[start : pos + 1]
    raise ValueError("unclosed source function: " + marker)


def validate_candidate_row(path: str, row: dict, row_hash: str) -> None:
    expected = FILES[path]
    provenance = row.get("provenance", {})
    review = row.get("review", {})
    require(provenance.get("pinned_revision") == PIN, "candidate row pin mismatch: " + path)
    require(provenance.get("git_blob_sha") == expected["blob"], "candidate row blob mismatch: " + path)
    require(provenance.get("source_content_sha256") in (None, expected["sha256"]),
            "candidate row source hash mismatch: " + path)
    require(row_hash == expected["row"], "candidate row hash mismatch: " + path)
    require(review.get("semantic_signoff") is False and review.get("reviewer") is None,
            "candidate inventory row asserts a semantic review: " + path)
    require(review.get("status") in (
        "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
        "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
    ), "unexpected candidate row status: " + path)


def load_candidate_rows(workpack: Path) -> tuple[bytes, dict[str, tuple[dict, str]]]:
    archive_bytes = workpack.read_bytes()
    require(sha256(archive_bytes) == WORKPACK_SHA256, "candidate workpack ZIP hash mismatch")
    with zipfile.ZipFile(workpack) as archive:
        compressed = archive.read(DOSSIER_MEMBER)
    require(sha256(compressed) == DOSSIER_SHA256, "candidate dossier archive hash mismatch")

    found: dict[str, tuple[dict, str]] = {}
    for raw_row in gzip.decompress(compressed).splitlines():
        row = json.loads(raw_row)
        provenance = row.get("provenance", {})
        path = provenance.get("path")
        if provenance.get("repository") != "huderlem/porymap" or path not in FILES:
            continue
        require(path not in found, "duplicate candidate dossier row: " + path)
        found[path] = (row, sha256(raw_row))
    require(set(found) == set(FILES), "candidate dossier rows incomplete")

    for path, expected in FILES.items():
        row, row_hash = found[path]
        validate_candidate_row(path, row, row_hash)
    return archive_bytes, found


def verify_source_identity(path: str, data: bytes) -> bool:
    expected = FILES[path]
    return git_blob(data) == expected["blob"] and sha256(data) == expected["sha256"]


def verify_source_contract(sources: dict[str, str]) -> list[str]:
    tileset = sources["src/core/tileset.cpp"]
    header = sources["include/core/tileset.h"]
    api = sources["src/scriptapi/apimap.cpp"]
    editor = sources["src/ui/tileseteditor.cpp"]
    project = sources["src/project.cpp"]
    project_header = sources["include/project.h"]
    build = sources["porymap.pro"]
    license_text = sources["LICENSE.md"]

    save_tiles = source_function(tileset, "bool Tileset::saveMetatiles()")
    save_attrs = source_function(tileset, "bool Tileset::saveMetatileAttributes()")
    load_tiles = source_function(tileset, "bool Tileset::loadMetatiles()")
    load_attrs = source_function(tileset, "bool Tileset::loadMetatileAttributes()")
    save_all = source_function(tileset, "bool Tileset::save()")
    save_tiles_image = source_function(tileset, "bool Tileset::saveTilesImage()")
    assign = source_function(tileset, "Tileset &Tileset::operator=(const Tileset &other)")
    append_headers = source_function(tileset, "bool Tileset::appendToHeaders")
    append_graphics = source_function(tileset, "bool Tileset::appendToGraphics")
    append_metatiles = source_function(tileset, "bool Tileset::appendToMetatiles")
    api_save_tiles = source_function(api, "void MainWindow::saveMetatilesByMetatileId")
    api_save_attrs = source_function(api, "void MainWindow::saveMetatileAttributesByMetatileId")
    editor_save = source_function(editor, "bool TilesetEditor::save()")
    project_save = source_function(project, "bool Project::saveTilesets")
    create_tileset = source_function(project, "Tileset *Project::createNewTileset")

    checks = (
        ("public declarations expose the focal save/load methods",
         all(token in header for token in ("saveMetatiles()", "saveMetatileAttributes()", "save()"))),
        ("metatile bytes are serialized low byte first",
         "data.append(static_cast<char>(tile));" in save_tiles and
         "data.append(static_cast<char>(tile >> 8));" in save_tiles),
        ("metatile writer ignores QFile::write result then returns true",
         "file.write(data);" in save_tiles and
         "if (file.write" not in save_tiles and
         save_tiles.rfind("return true;") > save_tiles.index("file.write(data);") and
         "QIODevice::WriteOnly | QIODevice::Truncate" in save_tiles),
        ("attribute writer ignores QFile::write result then returns true",
         "file.write(data);" in save_attrs and
         "if (file.write" not in save_attrs and
         save_attrs.rfind("return true;") > save_attrs.index("file.write(data);") and
         "QIODevice::WriteOnly | QIODevice::Truncate" in save_attrs),
        ("metatile reader floors byte count to complete metatiles",
         "clearMetatiles();" in load_tiles and
         load_tiles.index("clearMetatiles();") < load_tiles.index("file.open") and
         "int numMetatiles = data.length() / bytesPerMetatile;" in load_tiles),
        ("attribute reader floors byte count to complete attributes",
         "int numMetatileAttrs = data.length() / attrSize;" in load_attrs),
        ("aggregate save attempts all four output families without rollback",
         all(f"if (!{call}()) success = false;" in save_all for call in (
             "savePalettes", "saveTilesImage", "saveMetatiles", "saveMetatileAttributes"))),
        ("script API discards direct metatile writer result",
         "if (tileset)\n        tileset->saveMetatiles();" in api_save_tiles and
         "if (!tileset->saveMetatiles())" not in api_save_tiles),
        ("script API discards attribute writer result",
         "if (tileset)\n        tileset->saveMetatileAttributes();" in api_save_attrs and
         "if (!tileset->saveMetatileAttributes())" not in api_save_attrs),
        ("tileset editor preserves dirty state on reported aggregate failure",
         "if (success) {\n        this->hasUnsavedChanges = false;" in editor_save),
        ("editor still applies swaps and emits after failed save",
         editor_save.index("applyMetatileSwapsToLayouts();") <
         editor_save.index("if (success)") and
         editor_save.index("emit this->tilesetsSaved") <
         editor_save.index("if (success)")),
        ("Project aggregates primary and secondary save results",
         "if (primaryTileset && !primaryTileset->save())" in project_save and
         "if (secondaryTileset && !secondaryTileset->save())" in project_save),
        ("new Tileset creation ignores its initial save result",
         "tileset->save();" in create_tileset and
         "if (!tileset->save())" not in create_tileset),
        ("generated source append helpers ignore write and flush results",
         all("file.write(dataString.toUtf8());" in method and
             "file.flush();" in method and
             "if (!file.write" not in method
             for method in (append_headers, append_graphics, append_metatiles))),
        ("tileset image dirty state clears only after image save succeeds",
         "if (!m_tilesImage.save(this->tilesImagePath, \"PNG\"))" in save_tiles_image and
         save_tiles_image.index("return false;") < save_tiles_image.index("m_hasUnsavedTilesImage = false;")),
        ("Tileset assignment copies image but not its dirty flag",
         "m_tilesImage = other.m_tilesImage.copy();" in assign and
         "m_hasUnsavedTilesImage = other.m_hasUnsavedTilesImage;" not in assign),
        ("project header declares Tileset save caller",
         "saveTilesets(Tileset*, Tileset*)" in project_header),
        ("qmake build includes original Tileset implementation",
         "src/core/tileset.cpp" in build and "include/core/tileset.h" in build),
        ("root license is LGPL text; no distribution conclusion is asserted",
         "GNU LESSER GENERAL PUBLIC LICENSE" in license_text),
    )
    for label, valid in checks:
        require(valid, "pinned source contract changed: " + label)
    return [label for label, _ in checks]


def validate_shortlist(shortlist: tuple[dict, ...] | list[dict]) -> None:
    expected_ids = [
        "porymap-tileset-persistence",
        "porymap-layout-blockdata-persistence",
        "firered-mapjson-authored-order",
        "mgba-matrix-savestate",
        "poryscript-generated-include",
    ]
    require([entry.get("rank") for entry in shortlist] == list(range(1, len(shortlist) + 1)),
            "shortlist ranks are not contiguous")
    require([entry.get("id") for entry in shortlist] == expected_ids,
            "shortlist identities/count changed")
    selected = [entry for entry in shortlist if entry.get("status") == "SELECTED_NEEDS_EVIDENCE"]
    require([entry.get("id") for entry in selected] == ["porymap-tileset-persistence"],
            "shortlist selection overlaps or no longer identifies the distinct Tileset package")
    require(all(entry.get("status") != "APPROVED" for entry in shortlist),
            "shortlist must not claim semantic approval")


def mutation_controls(rows: dict[str, tuple[dict, str]], sources: dict[str, str],
                      archive_bytes: bytes) -> int:
    rejected = 0
    changed_archive = archive_bytes[:-1] + bytes([archive_bytes[-1] ^ 1])
    try:
        require(sha256(changed_archive) == WORKPACK_SHA256, "candidate workpack ZIP hash mismatch")
    except ValueError:
        rejected += 1
    else:
        raise ValueError("mutated archive escaped")

    for path, field, value in (
        ("src/core/tileset.cpp", "git_blob_sha", "0" * 40),
        ("src/core/tileset.cpp", "pinned_revision", "0" * 40),
        ("src/core/tileset.cpp", "semantic_signoff", True),
    ):
        row = json.loads(json.dumps(rows[path][0]))
        if field == "semantic_signoff":
            row["review"][field] = value
        else:
            row["provenance"][field] = value
        try:
            provenance = row["provenance"]
            require(provenance["pinned_revision"] == PIN, "candidate row pin mismatch")
            require(provenance["git_blob_sha"] == FILES[path]["blob"], "candidate row blob mismatch")
            require(row["review"]["semantic_signoff"] is False, "candidate row gained semantic signoff")
        except ValueError:
            rejected += 1
        else:
            raise ValueError("mutated candidate row escaped: " + field)

    try:
        validate_candidate_row("src/core/tileset.cpp", rows["src/core/tileset.cpp"][0],
                               "0" * 64)
    except ValueError:
        rejected += 1
    else:
        raise ValueError("mutated candidate row hash escaped")

    for path, mutation in (
        ("src/core/tileset.cpp",
         ("file.write(data);", "if (file.write(data) != data.size()) return false;")),
        ("src/scriptapi/apimap.cpp",
         ("tileset->saveMetatiles();", "if (!tileset->saveMetatiles()) return;")),
    ):
        changed = dict(sources)
        old, new = mutation
        if path == "src/core/tileset.cpp":
            method = source_function(changed[path], "bool Tileset::saveMetatiles()")
            require(old in method, "source mutation anchor missing: " + path)
            changed[path] = changed[path].replace(method, method.replace(old, new, 1), 1)
        else:
            method = source_function(changed[path], "void MainWindow::saveMetatilesByMetatileId")
            require(old in method, "source mutation anchor missing: " + path)
            changed[path] = changed[path].replace(method, method.replace(old, new, 1), 1)
        try:
            verify_source_contract(changed)
        except ValueError:
            rejected += 1
        else:
            raise ValueError("source mutation escaped: " + path)

    changed_shortlist = [dict(entry) for entry in SHORTLIST]
    changed_shortlist[0]["id"] = "porymap-layout-blockdata-persistence"
    try:
        validate_shortlist(changed_shortlist)
    except ValueError:
        rejected += 1
    else:
        raise ValueError("overlap mutation escaped shortlist selection")
    try:
        validate_shortlist([*SHORTLIST, {
            "rank": 6,
            "id": "inflated-candidate",
            "status": "EXCLUDED_UNVERIFIED",
        }])
    except ValueError:
        rejected += 1
    else:
        raise ValueError("shortlist count mutation escaped")

    changed_bytes = (Path("src/core/tileset.cpp").read_bytes()
                     if Path("src/core/tileset.cpp").is_file() else b"")
    require(changed_bytes or sources["src/core/tileset.cpp"], "source fixture unavailable")
    altered = changed_bytes + b"\n" if changed_bytes else sources["src/core/tileset.cpp"].encode() + b"\n"
    if not verify_source_identity("src/core/tileset.cpp", altered):
        rejected += 1
    else:
        raise ValueError("full-byte source identity mutation escaped")
    return rejected


def compile_native_witness(sources: dict[str, str], harness: Path,
                           build_dir: Path) -> tuple[str, str, str]:
    require(shutil.which("strace") is not None, "strace is required for /dev/full syscall attribution")
    pkg = subprocess.check_output(["pkg-config", "--cflags", "--libs", "Qt6Core"], text=True).split()
    source = harness.read_text(encoding="utf-8")
    method_tiles = source_function(sources["src/core/tileset.cpp"], "bool Tileset::saveMetatiles()")
    method_attrs = source_function(sources["src/core/tileset.cpp"], "bool Tileset::saveMetatileAttributes()")
    generated = source.replace("@ORIGINAL_SAVE_METATILES@", method_tiles)
    generated = generated.replace("@ORIGINAL_SAVE_METATILE_ATTRIBUTES@", method_attrs)
    require("@ORIGINAL_" not in generated, "native harness source placeholders were not all replaced")
    build_dir.mkdir(parents=True, exist_ok=True)
    generated_path = build_dir / "tileset-native.cpp"
    binary = build_dir / "tileset-native"
    trace = build_dir / "strace.log"
    generated_path.write_text(generated, encoding="utf-8")
    command = [os.environ.get("CXX", "c++"), "-std=c++17", "-fPIC",
               str(generated_path), "-o", str(binary), *pkg]
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=90)
    run = subprocess.run(
        ["strace", "-f", "-yy", "-s", "256", "-e", "trace=write",
         "-o", str(trace), str(binary)],
        check=True, capture_output=True, text=True, timeout=30,
    )
    trace_text = trace.read_text(encoding="utf-8")
    failed_full = [line for line in trace_text.splitlines()
                   if "write(" in line and "/dev/full" in line and "= -1 ENOSPC" in line]
    require(len(failed_full) >= 2, "original methods did not produce two attributed /dev/full ENOSPC writes")
    output = run.stdout.strip()
    require(output == (
        "PHASE1_TILESET_NATIVE positive_metatiles=1 positive_attributes=1 "
        "missing_path_rejected=1 dev_full_metatiles_returned_true=1 "
        "dev_full_attributes_returned_true=1"
    ), "unexpected native Qt witness result")
    return output, shlex.join(command), "\n".join(failed_full)


def verify(root: Path, workpack: Path, harness: Path, build_dir: Path,
           output: Path, self_test: bool) -> dict:
    require(root.is_dir() and (root / ".git").exists(), "pinned Porymap Git checkout absent")
    require(git(root, "rev-parse", "HEAD") == PIN, "wrong pinned Porymap revision")
    archive_bytes, rows = load_candidate_rows(workpack)
    sources: dict[str, str] = {}
    records = []
    for path, expected in FILES.items():
        data = (root / path).read_bytes()
        require(verify_source_identity(path, data), "pinned source identity mismatch: " + path)
        require(git(root, "hash-object", path) == expected["blob"],
                "Git object and computed source blob differ: " + path)
        row, row_hash = rows[path]
        require(row_hash == expected["row"], "candidate row hash changed: " + path)
        status = row["review"]["status"]
        records.append({
            "path": path,
            "original_git_blob_sha1": expected["blob"],
            "full_source_sha256": sha256(data),
            "candidate_inventory_row_sha256": row_hash,
            "candidate_row_status": status,
            "scope": expected["role"],
            "semantic_disposition": "NEEDS_EVIDENCE",
            "independent_approval": False,
        })
        sources[path] = data.decode("utf-8")

    contract = verify_source_contract(sources)
    validate_shortlist(SHORTLIST)
    rejected = mutation_controls(rows, sources, archive_bytes) if self_test else 0
    native_output, compile_command, failed_writes = compile_native_witness(
        sources, harness, build_dir
    )
    result = {
        "status": "NEEDS_EVIDENCE",
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals_added": 0,
        "pinned_repository": "huderlem/porymap",
        "pinned_revision": PIN,
        "workpack_sha256": WORKPACK_SHA256,
        "candidate_dossier_gzip_sha256": DOSSIER_SHA256,
        "candidate_inventory_is_semantic_receipt": False,
        "shortlist": list(SHORTLIST),
        "verified_source_records": records,
        "verified_contracts": contract,
        "source_and_evidence_mutations_rejected": rejected,
        "native_qt_result": native_output,
        "native_qt_scope": "Unchanged original Tileset::saveMetatiles and saveMetatileAttributes bodies compiled with Qt 6 Core; minimal test-only model/config/logger stubs; real QFile and Linux /dev/full; not the full Porymap GUI.",
        "native_compile_command": compile_command,
        "attributed_failed_writes": failed_writes.splitlines(),
        "unresolved": [
            "No original independent semantic dossier/receipt exists in the candidate archive; its per-row hashes identify triage bytes only.",
            "The harness does not execute the full Tileset class, Project, TilesetEditor, script engine, FireRed project, or generated ROM.",
            "No proof of multi-file rollback, filesystem crash consistency, physical durability, gameplay compatibility, or distribution-license compliance.",
            "Direct model, PaletteUtil, config, generated asset, and UI/script runtime dependencies remain outside the compiled witness.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=Path("upstream-porymap"))
    parser.add_argument("--workpack", type=Path, default=Path("imports/XGBA_Phase1_v1.5_Complete_Workpack.zip"))
    parser.add_argument("--harness", type=Path, default=Path("tests/phase1_porymap_tileset_native.cpp"))
    parser.add_argument("--build-dir", type=Path, default=Path("/tmp/phase1-porymap-tileset-native"))
    parser.add_argument("--output", type=Path, default=Path("phase1-evidence/tileset-native.json"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    result = verify(args.source_root, args.workpack, args.harness, args.build_dir,
                    args.output, args.self_test)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.self_test:
        print(f"Tileset source closure, {result['source_and_evidence_mutations_rejected']} mutation rejects, and original-body Qt 6 witness PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
