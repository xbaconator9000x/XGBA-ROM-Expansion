#!/usr/bin/env python3
"""Verify task-scoped pinned Poryscript/FireRed review evidence."""
import argparse
import gzip
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORD = (
    ROOT
    / "semantic-snapshots/independent-reviews/copilot-poryscript-abi/review.json"
)
DEFAULT_CLOSURE_RECORD = (
    ROOT
    / "semantic-snapshots/independent-reviews/copilot-poryscript-abi/closure-review.json"
)
PINS = {
    "huderlem/poryscript": "c32481161c767b25a3425fa9f1f8729927ff3d55",
    "pret/pokefirered": "ce6406d8c2eaf46d543c8a2606de0c3cb1951982",
    "pret/agbcc": "da598c1d918402c42c0c0d7128ba14567f3175e9",
    "mgba-emu/mgba": "fd9dc5c2cbf234365068855851107e762fc6211b",
}
REPOSITORY_ALIASES = {
    "p": "huderlem/poryscript",
    "f": "pret/pokefirered",
    "a": "pret/agbcc",
    "m": "mgba-emu/mgba",
}
EXPECTED_ARCHIVES = {
    "dossiers": {
        "path": "semantic-snapshots/current/candidate_review_dossiers.jsonl.gz",
        "bytes": 949448,
        "sha256": "1c7cc9d6d8da71ff95021b986ffde8a93b7369ca703dc1b6e321c65b5f0eb609",
        "git_blob_sha1": "3b982876c7d810a827af8c80c7e5d9231fdaa327",
    },
    "queue": {
        "path": "semantic-snapshots/current/semantic_review_queue.csv.gz",
        "bytes": 1051376,
        "sha256": "c50498b751ecbe38d7a5939e06fa85cf4e62d529a943983710d4c5b9095d2eff",
        "git_blob_sha1": "52fe1a9b8498dd4fa3ea0e6e0236ae1cdeda7268",
    },
}
PR20_WITNESS_ARTIFACT_SHA256 = (
    "37cc5d0e03fd481c61721816533b8869709b1a23b7b9bc6f76df701252f988e5"
)
PR36_WITNESS_ARTIFACT_SHA256 = (
    "0991fb3a015b27370dcc01994bbe597da382b671c30d0f6c30a9d52e11a8fa9a"
)
LOCAL_PROBE_SHA256 = {
    "fixture_sha256": "bfcb3889acda709bfac862c57de0cbbae7796605c5fd912ac906a6d101b1894e",
    "emitted_assembly_sha256": "15b063d131599e920d79181112080cea048d3398fb6cdf0a69d11f4430ee92a7",
    "unlinked_rodata_sha256": "37c32ab9ec8d289aa0f0c7ae4ed68f39e8a08b333b0a1014121cffa845bfcc49",
    "linked_rodata_sha256": "523ef7b38fd6cdae81782fbbb5b242e964f7a3f4c7838fa3023daf7feacec168",
}
VERDICTS = {"APPROVED", "REJECTED", "NEEDS_EVIDENCE"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def git_blob_sha1(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def validate_record(record):
    require(record.get("schema") == "copilot-poryscript-abi-review/v1",
            "unsupported review record schema")
    reviewer = record.get("reviewer", {})
    require(reviewer.get("identity") and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity"),
            "reviewer identity must be distinct from the original source interpreter")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE",
            "Phase 1 gate must remain FAIL_INCOMPLETE")
    require(accounting.get("approved_before") == 0 and
            accounting.get("new_approvals") == 0,
            "review must preserve the existing zero approval total")
    require(accounting.get("shared_queue_register_gate_modified") is False,
            "shared review queue, register, or gate must not be modified")

    sources = {}
    for source in record.get("source_evidence", []):
        repository = source.get("repository")
        require(repository in PINS, "source repository is not one of the pinned inputs")
        require(source.get("commit") == PINS[repository],
                "source commit does not match the immutable pin: " + str(repository))
        path = PurePosixPath(source.get("path", ""))
        require(path.parts and not path.is_absolute() and ".." not in path.parts,
                "source path must be a safe repository-relative path")
        key = (repository, path.as_posix())
        require(key not in sources, "duplicate source evidence identity: " + str(key))
        sources[key] = source

        for field in ("git_blob_sha1", "sha256"):
            digest = source.get(field, "")
            require(len(digest) == (40 if field == "git_blob_sha1" else 64) and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid " + field + " for " + path.as_posix())
        ranges = source.get("evidence_ranges", [])
        require(ranges, "source evidence must include exact line ranges")
        for item in ranges:
            start, end = item.get("start"), item.get("end")
            require(isinstance(start, int) and isinstance(end, int) and
                    1 <= start <= end, "invalid source evidence line range")
            digest = item.get("sha256", "")
            require(len(digest) == 64 and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid line-range SHA-256")

    require(sources, "review must cite immutable source evidence")
    for item in record.get("file_verdicts", []):
        key = (item.get("repository"), item.get("path"))
        require(key in sources, "per-file verdict lacks pinned source evidence")
        require(item.get("verdict") in VERDICTS, "invalid proposed per-file verdict")
        require(item.get("basis"), "per-file verdict must state its basis")

    original_witness = record.get("original_evidence", {}).get(
        "actual_cli_workflow", {}
    )
    require(original_witness.get("workflow_run_id") == 40506170513 and
            original_witness.get("job_id") == 122195911391 and
            original_witness.get("head_sha") ==
            "587132181ef728b635968dd091b1cf171e78f753" and
            original_witness.get("artifact_id") == 12735216391 and
            original_witness.get("artifact_zip_sha256") ==
            PR20_WITNESS_ARTIFACT_SHA256,
            "original PR #20 witness provenance changed")
    witness = record.get("actual_cli_witness", {})
    require(witness.get("status") == "success" and
            witness.get("actual_poryscript_cli_executed") is True and
            witness.get("actual_firered_preprocessor_used") is True and
            witness.get("negative_controls_passed") == 7 and
            witness.get("artifact_zip_sha256") ==
            PR20_WITNESS_ARTIFACT_SHA256,
            "actual CLI witness must retain its exact successful result")
    require(record.get("local_rerun", {}).get("status") ==
            "BLOCKED_MISSING_PINNED_CHECKOUTS_AND_GNU_ARM_BINUTILS",
            "local rerun blocker must be explicit")
    return sources


def validate_closure_record(record, archive_root=ROOT):
    require(record.get("schema") == "copilot-poryscript-abi-closure-review/v1",
            "unsupported closure record schema")
    reviewer = record.get("reviewer", {})
    require(reviewer.get("id") == "copilot-issue33-closure" and
            reviewer.get("identity") and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity") and
            reviewer.get("distinct_from_evidence_author") is True,
            "closure reviewer must be identified and distinct from the evidence author")
    require(reviewer.get("separate_human_attestation") is False and
            reviewer.get("authenticated_github_review_attribution") is False,
            "closure record must not claim missing external attestation")
    require(record.get("pins") == PINS,
            "closure source pins differ from the immutable assignments")
    require(record.get("repository_aliases") ==
            {repository: alias for alias, repository in REPOSITORY_ALIASES.items()},
            "closure repository aliases differ")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE" and
            accounting.get("approved_p0") == 0 and
            accounting.get("p0_total") == 338 and
            accounting.get("approved_total") == 0 and
            accounting.get("inventory_total") == 14834 and
            accounting.get("phase2_started") is False and
            accounting.get("shared_queue_register_gate_modified") is False,
            "closure must preserve the Phase 1 gate, approval totals, and scope")

    archives = record.get("original_machine_evidence", {})
    require(set(archives) == set(EXPECTED_ARCHIVES),
            "original dossier and queue archive identities are required")
    root = archive_root.resolve()
    for name, expected in EXPECTED_ARCHIVES.items():
        archive = archives[name]
        require(archive == expected,
                "original machine evidence identity differs from pinned " + name)
        path = PurePosixPath(archive.get("path", ""))
        require(path.parts and not path.is_absolute() and ".." not in path.parts,
                "machine evidence path must be repository-relative")
        resolved = root.joinpath(*path.parts).resolve(strict=True)
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError("machine evidence path escapes archive root: " +
                             path.as_posix()) from exc
        data = resolved.read_bytes()
        require(len(data) == archive.get("bytes") and
                hashlib.sha256(data).hexdigest() == archive.get("sha256") and
                git_blob_sha1(data) == archive.get("git_blob_sha1"),
                "original machine evidence bytes or digest changed: " + path.as_posix())

    coverage = record.get("coverage", {})
    file_rows = coverage.get("file_rows", [])
    require(coverage.get("source_dossier_rows") == 81 and len(file_rows) == 81,
            "closure must retain the 81 source/dossier inventory rows")
    require(coverage.get("whole_file_semantic_reviews") == 0 and
            coverage.get("all_file_rows_verdict") == "NEEDS_EVIDENCE" and
            coverage.get("all_file_rows_reviewer_id") == reviewer.get("id"),
            "per-file records must remain attributed and non-approving")

    files = {}
    for row in file_rows:
        require(isinstance(row, list) and len(row) == 7,
                "invalid per-file closure row")
        alias, source_path, blob, source_sha, dossier_line_sha, range_code, verdict = row
        repository = REPOSITORY_ALIASES.get(alias)
        path = PurePosixPath(source_path)
        require(repository is not None and path.parts and not path.is_absolute() and
                ".." not in path.parts,
                "unsafe or unknown per-file source identity")
        key = (repository, path.as_posix())
        require(key not in files, "duplicate per-file closure identity: " + str(key))
        require(verdict == "NEEDS_EVIDENCE",
                "only NEEDS_EVIDENCE per-file verdicts are allowed")
        require(range_code in {"H", "R"},
                "unknown per-file source coverage code")
        for field, digest, width in (
                ("Git blob", blob, 40), ("source SHA-256", source_sha, 64),
                ("dossier line SHA-256", dossier_line_sha, 64)):
            require(len(digest) == width and
                    all(c in "0123456789abcdef" for c in digest),
                    "invalid " + field + " for " + path.as_posix())
        files[key] = {
            "repository": repository,
            "path": path.as_posix(),
            "git_blob_sha1": blob,
            "sha256": source_sha,
            "dossier_record_line_sha256": dossier_line_sha,
            "coverage_code": range_code,
        }

    dossier_archive = archives["dossiers"]
    dossier_path = PurePosixPath(dossier_archive["path"])
    dossier_file = archive_root.joinpath(*dossier_path.parts)
    remaining = set(files)
    with gzip.open(dossier_file, "rb") as stream:
        for line in stream:
            dossier = json.loads(line)
            provenance = dossier.get("provenance", {})
            key = (provenance.get("repository"), provenance.get("path"))
            if key not in remaining:
                continue
            source = files[key]
            require(provenance.get("pinned_revision") == PINS[key[0]] and
                    provenance.get("git_blob_sha") == source["git_blob_sha1"],
                    "machine dossier source identity differs: " + str(key))
            require(hashlib.sha256(line).hexdigest() ==
                    source["dossier_record_line_sha256"],
                    "machine dossier record line changed: " + str(key))
            content_sha = provenance.get("source_content_sha256")
            require(content_sha is None or content_sha == source["sha256"],
                    "machine dossier source SHA-256 differs: " + str(key))
            machine_review = dossier.get("review", {})
            require(machine_review.get("semantic_signoff") is False and
                    machine_review.get("status") != "APPROVED",
                    "machine dossier must not be interpreted as approval: " + str(key))
            remaining.remove(key)
            if not remaining:
                break
    require(not remaining,
            "per-file receipt lacks its original machine dossier row: " +
            str(sorted(remaining)[:3]))

    ranges = {}
    for row in coverage.get("evidence_ranges", []):
        require(isinstance(row, list) and len(row) == 5,
                "invalid closure evidence range")
        alias, source_path, start, end, digest = row
        repository = REPOSITORY_ALIASES.get(alias)
        key = (repository, PurePosixPath(source_path).as_posix())
        require(repository is not None and key in files and
                isinstance(start, int) and isinstance(end, int) and
                1 <= start <= end and len(digest) == 64 and
                all(c in "0123456789abcdef" for c in digest),
                "invalid or unpinned line-range evidence")
        require((key, start, end) not in ranges,
                "duplicate line-range evidence: " + str(key))
        ranges[(key, start, end)] = digest
    range_files = {key for key, _, _ in ranges}
    for key, source in files.items():
        expected_code = "R" if key in range_files else "H"
        require(source["coverage_code"] == expected_code,
                "per-file coverage code does not match line evidence: " + str(key))
    require(len(ranges) == coverage.get("bounded_line_ranges") and
            len(range_files) == coverage.get("bounded_range_files"),
            "closure range counts do not match per-file evidence")

    for edge in coverage.get("dependency_edges", []):
        require(isinstance(edge, list) and len(edge) == 5,
                "invalid ABI dependency edge")
        from_repo, from_path, to_repo, to_path, relation = edge
        from_key = (REPOSITORY_ALIASES.get(from_repo),
                    PurePosixPath(from_path).as_posix())
        to_key = (REPOSITORY_ALIASES.get(to_repo),
                  PurePosixPath(to_path).as_posix())
        require(from_key in files and to_key in files and relation,
                "dependency edge endpoint lacks a per-file receipt")

    objection_ids = set()
    for objection in record.get("objections", []):
        identifier = objection.get("id")
        require(identifier and objection.get("status") == "UNRESOLVED" and
                objection.get("observation") and objection.get("resolution"),
                "every objection must retain its unresolved evidence and resolution")
        require(identifier not in objection_ids, "duplicate objection identity")
        objection_ids.add(identifier)
    objection_map = coverage.get("objection_map", {})
    require("all" in objection_map and all(
        identifier in objection_ids for values in objection_map.values()
        for identifier in values
    ), "per-file objection map references an unknown obligation")
    require(set(objection_map) == {"all", *REPOSITORY_ALIASES},
            "per-repository unresolved obligations are incomplete")

    historical = record.get("historical_witness", {})
    require(historical.get("run_id") == 41035493919 and
            historical.get("head_sha") == "2c2805ead909df69a491cea84feb7dd562758e9b" and
            historical.get("artifact_id") == 12968950310 and
            historical.get("negative_controls_passed") == 7 and
            historical.get("artifact_zip_sha256") ==
            PR36_WITNESS_ARTIFACT_SHA256,
            "historical exact-head witness provenance changed")
    probe = record.get("local_actual_cli_probe", {})
    require(probe.get("status") ==
            "PASS_ACTUAL_PINNED_CLI_PREPROCESSOR_GNU_ARM_OBJECT_FIXTURE" and
            probe.get("poryscript_commit") == PINS["huderlem/poryscript"] and
            probe.get("firered_commit") == PINS["pret/pokefirered"] and
            probe.get("relocation_type") == "R_ARM_ABS32" and
            probe.get("relocation_offsets") ==
            [1, 6, 11, 16, 21, 26, 35, 45, 53, 63, 71] and
            probe.get("negative_controls") ==
            {"overflow-operand": "PASS", "zero-operand": "PASS"} and
            probe.get("phase1_gate") == "FAIL_INCOMPLETE" and
            probe.get("approval_count_changed") is False,
            "actual CLI object-probe evidence is incomplete")
    for field, digest in LOCAL_PROBE_SHA256.items():
        require(probe.get(field) == digest,
                "local actual CLI probe digest changed: " + field)
    return files, ranges


FILE_INSPECTION_SCHEMAS = {
    "copilot-poryscript-abi-file-inspection/v1": {
        "reviewer_id": "copilot-issue33-file-inspection-followup",
        "reviewer_identity": (
            "@copilot (GitHub Copilot Coding Agent; issue #33 "
            "review-readiness follow-up)"
        ),
        "expected_files": {
            ("huderlem/poryscript", "emitter/emitter.go"),
            ("huderlem/poryscript", "parser/parser.go"),
            ("pret/pokefirered", "src/script.c"),
            ("mgba-emu/mgba", "src/gba/memory.c"),
        },
        "prior_head": "fc54588319aea2a798f2455fb594c367209f8b85",
    },
    "copilot-poryscript-abi-file-inspection/v2": {
        "reviewer_id": "copilot-issue33-firered-dispatch-followup",
        "reviewer_identity": (
            "@copilot (GitHub Copilot Coding Agent; issue #33 "
            "FireRed dispatch follow-up)"
        ),
        "expected_files": {
            ("pret/pokefirered", "asm/macros/map.inc"),
            ("pret/pokefirered", "data/script_cmd_table.inc"),
            ("pret/pokefirered", "src/scrcmd.c"),
            ("pret/pokefirered", "src/overworld.c"),
        },
        "prior_head": "18de5e859392906e1da4aed800daf15e497d63c5",
    },
    "copilot-poryscript-abi-file-inspection/v3": {
        "reviewer_id": "copilot-issue33-map-header-tranche",
        "reviewer_identity": (
            "@copilot (GitHub Copilot Coding Agent; issue #33 "
            "FireRed map-header review tranche)"
        ),
        "expected_files": {
            ("pret/pokefirered", "tools/mapjson/mapjson.cpp"),
            ("pret/pokefirered", "map_data_rules.mk"),
            ("pret/pokefirered", "data/maps.s"),
            ("pret/pokefirered", "include/global.fieldmap.h"),
            ("pret/pokefirered", "data/event_scripts.s"),
            ("pret/pokefirered", "data/maps/Route18/scripts.inc"),
            ("pret/pokefirered", "include/constants/map_scripts.h"),
        },
        "supplemental_ranges": {
            ("pret/pokefirered", "tools/mapjson/mapjson.cpp"): {
                (488, 503):
                    "920e139caac5559547514dfd7a5e1dab914dd706a93b82bfe2951b961c8f8ca8",
            },
            ("pret/pokefirered", "data/event_scripts.s"): {
                (27, 48):
                    "aa567342c19eac7ef6545263c4874dd0a503e62694fe25ec9870760c3d371743",
                (310, 316):
                    "503188023f089b34492a426af202154b59b44abfd09a447c9ced7a0151546be3",
            },
            ("pret/pokefirered", "data/maps/Route18/scripts.inc"): {
                (19, 28):
                    "fcbb6b48164630d0a171bd744e44f790cf0a54f8c7803a8cd00005627d9bbdf5",
            },
        },
        "source_dimensions": {
            ("pret/pokefirered", "tools/mapjson/mapjson.cpp"): (28254, 740),
            ("pret/pokefirered", "map_data_rules.mk"): (2402, 40),
            ("pret/pokefirered", "data/maps.s"): (489, 17),
            ("pret/pokefirered", "include/global.fieldmap.h"): (12127, 400),
            ("pret/pokefirered", "data/event_scripts.s"): (55643, 1362),
            ("pret/pokefirered", "data/maps/Route18/scripts.inc"): (660, 28),
            ("pret/pokefirered", "include/constants/map_scripts.h"): (443, 12),
        },
        "prior_head": "af2fa85f62ed9a3f965207b80068f83277177736",
    },
    "copilot-poryscript-abi-file-inspection/v4": {
        "reviewer_id": "copilot-issue33-poryscript-firered-followup",
        "reviewer_identity": (
            "@copilot (GitHub Copilot Coding Agent; issue #33 "
            "Poryscript–FireRed ABI follow-up)"
        ),
        "expected_files": {
            ("huderlem/poryscript", "ast/ast.go"),
            ("huderlem/poryscript", "emitter/branch.go"),
            ("huderlem/poryscript", "emitter/chunk.go"),
            ("huderlem/poryscript", "main.go"),
            ("huderlem/poryscript", "emitter/emitter_test.go"),
            ("huderlem/poryscript", "go.mod"),
            ("pret/pokefirered", "asm/macros/event.inc"),
            ("pret/pokefirered", "include/script.h"),
            ("pret/pokefirered", "include/global.h"),
            ("pret/pokefirered", "include/constants/vars.h"),
            ("pret/pokefirered", "include/event_data.h"),
            ("pret/pokefirered", "src/event_data.c"),
            ("pret/pokefirered", "tools/preproc/asm_file.cpp"),
            ("pret/pokefirered", "tools/preproc/asm_file.h"),
            ("pret/pokefirered", "tools/preproc/preproc.cpp"),
            ("pret/pokefirered", "tools/preproc/preproc.h"),
        },
        "prior_head": "d7636c7048d02cdc7b73df277258312744e9ddd9",
        "supplemental_ranges": {
            ("huderlem/poryscript", "ast/ast.go"): {
                (408, 462):
                    "edfb32347be0c56ad3b655699c1a8d7df52cb20c7fb4be02348ee2f20adb5655",
            },
            ("huderlem/poryscript", "emitter/branch.go"): {
                (1, 197):
                    "2dfddf0c1d059d8b3aa0db921e28a1509d3bbc2074390ab24a7655e1568aa594",
            },
            ("huderlem/poryscript", "emitter/emitter_test.go"): {
                (1626, 1850):
                    "56853cc49e4766285e2ed96ed516d8c1a8d652cb161bc02edc60ff2a65b2b2e8",
                (2183, 2596):
                    "590583b639434d63a88e1ad494625325f3ce943cff71af5c07caf622fd577c11",
            },
            ("huderlem/poryscript", "go.mod"): {
                (1, 3):
                    "23809cd3f1ae00603890a319e1c64438e5b4a161eca1a18719b342964a0a7a83",
            },
            ("pret/pokefirered", "asm/macros/event.inc"): {
                (22, 45):
                    "89ac6c4cbdf48e6446247106052fc9e7409774f918298a6b56e2f9b8219cb179",
                (237, 259):
                    "a2dd331e51be6ea5c7ea13d870aad637d1c5bf12456fe6750b0d432aacc09119",
                (1639, 1725):
                    "d5166ffdffc6cc9b0bb61b480eb8a4b660f41d0939db92e9afaa43407abf1f04",
            },
            ("pret/pokefirered", "include/script.h"): {
                (1, 10):
                    "93a9ec3dc085d0ec0f335fbd0ea1f52e82dcdad3fdcbb0f766e0096e5ec37689",
                (36, 50):
                    "c590fac047e8a4d863c8abb43020a5a1acd2ebe1cd8ec66f753df2be41791c71",
            },
            ("pret/pokefirered", "include/global.h"): {
                (1, 14):
                    "fb4bb8f0559a04660397d05c975902f3f5c62bd29f1ddd0d7e53a1daced68579",
            },
            ("pret/pokefirered", "include/constants/vars.h"): {
                (11, 24):
                    "5644f5aae085fd46b77f716ca569608db50c7a940de0a122c15e93d07d2cbd71",
                (131, 191):
                    "02acfce492f50ee73dd4e1342e0d356fb2c57ff7b18cb784ab2d7f7996b24cc1",
                (308, 337):
                    "753f3f5e9ef7cfd8e067bbe907e864c1de6da9960f4da58e298b6cdc61253b0f",
            },
            ("pret/pokefirered", "include/event_data.h"): {
                (1, 58):
                    "cb46a58f3d80da7a6a19c6bc512e2b9c92dea4fb537e5b375cd9829583449c34",
            },
            ("pret/pokefirered", "src/event_data.c"): {
                (242, 249):
                    "9bcf06beb5f675487b4a230d7d903a46ac3fdcf59febaae8e93d5778779feae5",
                (257, 310):
                    "0debb86864a6a8e92d07c7a4dff011d64e85d64217ed10854f2093d87da6315a",
            },
            ("pret/pokefirered", "tools/preproc/asm_file.cpp"): {
                (32, 124):
                    "f789e572a9ae6e771c7f46136b95bf93edf73a818b206600d130dedb542fd6a9",
                (126, 162):
                    "e5bd921fe2f5d31c342030bc86b113fc84fce8ee0426c37c4e1d109cf71b5a12",
                (186, 186):
                    "412ca345ccf75bf9c0806bce695be8de808b79984251a7a54d202cf6101dd451",
                (195, 241):
                    "3301f3105a4cfe9990c20c048cb56d38db85f3f9cc96c975960684589dbd4be7",
                (486, 509):
                    "73a269b7514a921e9833abc4b7ce798ca9d7093382b0f45be9e5af341c03d977",
                (512, 592):
                    "b34c069b1554dbe3495e3f07889e15e707500462960a9d9ade321c99739cf5d1",
                (594, 635):
                    "61e5596f249219277a618d8127878d4407d42eebb54183905f53d49e7b4670a3",
                (667, 792):
                    "cb6537e5db762f3bb3427f8fb40c01ab73faf2a69d27dc6116c47547e145e004",
            },
            ("pret/pokefirered", "tools/preproc/asm_file.h"): {
                (21, 80):
                    "8d7a1014e272436ac22013c655dc1e01778cf315e23939c4ebbb21c42ed68798",
            },
            ("pret/pokefirered", "tools/preproc/preproc.cpp"): {
                (49, 95):
                    "20428c08987526611486c55fc035d90231e1506556686eda4637cf1e79d98b5d",
                (109, 114):
                    "5eda9c9f00f3620f4c7b7a510e84c282c5340168cd78c40423e1a7084ac511fa",
                (122, 203):
                    "95cebab7721fcdb6004bda8f64c255e98e70741916c3f77f70c0f41e8090248e",
            },
            ("pret/pokefirered", "tools/preproc/preproc.h"): {
                (21, 54):
                    "f07eaac58288a0edc281a20269e371b52c250a747acbae81183268c1c70f90bb",
            },
        },
        "source_dimensions": {
            ("huderlem/poryscript", "ast/ast.go"): (13127, 462),
            ("huderlem/poryscript", "emitter/branch.go"): (7109, 197),
            ("huderlem/poryscript", "emitter/chunk.go"): (4759, 144),
            ("huderlem/poryscript", "main.go"): (4422, 155),
            ("huderlem/poryscript", "emitter/emitter_test.go"): (68343, 3585),
            ("huderlem/poryscript", "go.mod"): (47, 3),
            ("pret/pokefirered", "asm/macros/event.inc"): (56947, 1858),
            ("pret/pokefirered", "include/script.h"): (2589, 78),
            ("pret/pokefirered", "include/global.h"): (25663, 834),
            ("pret/pokefirered", "include/constants/vars.h"): (17306, 346),
            ("pret/pokefirered", "include/event_data.h"): (1675, 58),
            ("pret/pokefirered", "src/event_data.c"): (8913, 336),
            ("pret/pokefirered", "tools/preproc/asm_file.cpp"): (20838, 792),
            ("pret/pokefirered", "tools/preproc/asm_file.h"): (2496, 80),
            ("pret/pokefirered", "tools/preproc/preproc.cpp"): (5319, 203),
            ("pret/pokefirered", "tools/preproc/preproc.h"): (1936, 54),
        },
    },
    "copilot-poryscript-abi-file-inspection/v5": {
        "reviewer_id": "copilot-issue33-preproc-closure",
        "reviewer_identity": (
            "@copilot (GitHub Copilot Coding Agent; issue #6676248488 "
            "FireRed preprocessor dependency follow-up)"
        ),
        "expected_files": {
            ("pret/pokefirered", "asm/macros.inc"),
            ("pret/pokefirered", "include/characters.h"),
            ("pret/pokefirered", "tools/preproc/Makefile"),
            ("pret/pokefirered", "tools/preproc/c_file.cpp"),
            ("pret/pokefirered", "tools/preproc/c_file.h"),
            ("pret/pokefirered", "tools/preproc/char_util.h"),
            ("pret/pokefirered", "tools/preproc/charmap.cpp"),
            ("pret/pokefirered", "tools/preproc/charmap.h"),
            ("pret/pokefirered", "tools/preproc/io.cpp"),
            ("pret/pokefirered", "tools/preproc/io.h"),
            ("pret/pokefirered", "tools/preproc/string_parser.cpp"),
            ("pret/pokefirered", "tools/preproc/string_parser.h"),
            ("pret/pokefirered", "tools/preproc/utf8.cpp"),
            ("pret/pokefirered", "tools/preproc/utf8.h"),
        },
        "prior_head": "3d16cc671a80c531e789d53d467ce4961d3f436c",
        "source_dimensions": {
            ("pret/pokefirered", "asm/macros.inc"): (3596, 169),
            ("pret/pokefirered", "include/characters.h"): (12798, 349),
            ("pret/pokefirered", "tools/preproc/Makefile"): (467, 26),
            ("pret/pokefirered", "tools/preproc/c_file.cpp"): (9997, 419),
            ("pret/pokefirered", "tools/preproc/c_file.h"): (2032, 59),
            ("pret/pokefirered", "tools/preproc/char_util.h"): (2224, 71),
            ("pret/pokefirered", "tools/preproc/charmap.cpp"): (9442, 408),
            ("pret/pokefirered", "tools/preproc/charmap.h"): (1926, 64),
            ("pret/pokefirered", "tools/preproc/io.cpp"): (1352, 51),
            ("pret/pokefirered", "tools/preproc/io.h"): (143, 8),
            ("pret/pokefirered", "tools/preproc/string_parser.cpp"): (9159, 355),
            ("pret/pokefirered", "tools/preproc/string_parser.h"): (1846, 55),
            ("pret/pokefirered", "tools/preproc/utf8.cpp"): (3500, 92),
            ("pret/pokefirered", "tools/preproc/utf8.h"): (1288, 34),
        },
        "supplemental_ranges": {
            ("pret/pokefirered", "asm/macros.inc"): {
                (1, 169): "f350fb894c63be2dce0d67d217411571d13a93c3ab633958014e45dd2db0a31d",
            },
            ("pret/pokefirered", "include/characters.h"): {
                (1, 349): "6787db76f83c4f8426c5adbfa7aa061c46585db9522f1fef00ad888616199b98",
            },
            ("pret/pokefirered", "tools/preproc/Makefile"): {
                (1, 26): "8dd899f6dc23b17b584fe59dae16d916f5d00e247fb7197fbd5699fa3ac8a0ba",
            },
            ("pret/pokefirered", "tools/preproc/c_file.cpp"): {
                (1, 419): "4bc2a6784a04ba87514b75af49e8dd6acdcecd5b80c28c0b79543d74e9545985",
            },
            ("pret/pokefirered", "tools/preproc/c_file.h"): {
                (1, 59): "d30ee6a92258ff092e5e51f84b848dc9a539b7d014e00abe88397053d44b6cad",
            },
            ("pret/pokefirered", "tools/preproc/char_util.h"): {
                (1, 71): "f71849a0c787a3413cd1dbaab59070d35e37700422f13d02d9acc78b06ed91ff",
            },
            ("pret/pokefirered", "tools/preproc/charmap.cpp"): {
                (1, 408): "3e426f022990dc25c473e6a044fb827acdaab6ed5af660b7dff7f205e93d9b28",
            },
            ("pret/pokefirered", "tools/preproc/charmap.h"): {
                (1, 64): "976aeeef3e1999e5162e3c0f2ab507d8d55e0904a7bd303d077c15222ae09e97",
            },
            ("pret/pokefirered", "tools/preproc/io.cpp"): {
                (1, 51): "5bd5e2064e774ec3c3f42049a74282f59171178e2c4dab11340c7074feb5d27d",
            },
            ("pret/pokefirered", "tools/preproc/io.h"): {
                (1, 8): "bd96fa61912381e799899f92f4bde6a15262a9562d6f60faf6aa3b4fbdaae8f1",
            },
            ("pret/pokefirered", "tools/preproc/string_parser.cpp"): {
                (1, 355): "962525f41d143be967f1562ecc560cff8c59ffacd7c232dd8972773523376587",
            },
            ("pret/pokefirered", "tools/preproc/string_parser.h"): {
                (1, 55): "9a537b13bf7e39f165b1fe85a42b67a00f4d1d56e32e03bced1ac94a84b56a50",
            },
            ("pret/pokefirered", "tools/preproc/utf8.cpp"): {
                (1, 92): "a33f47c3c49edcaf3fdee38330c0ce694375d00fd23f81273d31f411607bde5a",
            },
            ("pret/pokefirered", "tools/preproc/utf8.h"): {
                (1, 34): "f96af5fd634b54f7578903272b8c7a67630d214ffcae569b24f9b60574707ee0",
            },
        },
    },
}


def validate_file_inspection_record(record, closure_record):
    schema_config = FILE_INSPECTION_SCHEMAS.get(record.get("schema"))
    require(schema_config is not None,
            "unsupported file-inspection record schema")
    expected_files = schema_config["expected_files"]
    reviewer = record.get("reviewer", {})
    require(reviewer.get("id") == schema_config["reviewer_id"] and
            reviewer.get("identity") == schema_config["reviewer_identity"] and
            reviewer.get("source_interpreter_identity") ==
            "xbaconator9000x (author of the original PR #20 witness implementation)" and
            reviewer.get("identity") != reviewer.get("source_interpreter_identity") and
            reviewer.get("distinct_from_source_interpreter") is True,
            "file-inspection reviewer identity is missing or not distinct")
    require(reviewer.get("authenticated_github_review_attribution") is False and
            reviewer.get("independent_human_attestation") is False and
            reviewer.get("attribution_blocker"),
            "file-inspection record must state its missing authenticated attribution")

    accounting = record.get("accounting", {})
    require(accounting.get("phase1_gate") == "FAIL_INCOMPLETE" and
            accounting.get("approved_p0") == 0 and
            accounting.get("p0_total") == 338 and
            accounting.get("approved_total") == 0 and
            accounting.get("inventory_total") == 14834 and
            accounting.get("whole_file_semantic_reviews") == 0 and
            accounting.get("new_qualifying_copilot_receipts") == 0 and
            accounting.get("phase2_started") is False and
            accounting.get("shared_queue_register_gate_modified") is False,
            "file-inspection record must remain non-approving and Phase 1 only")

    basis = record.get("basis", {})
    require(basis.get("prior_exact_head") == schema_config["prior_head"],
            "file-inspection prior head differs")
    if record["schema"] == "copilot-poryscript-abi-file-inspection/v1":
        require(basis.get("prior_workflow_run_id") == 41850174614 and
                basis.get("prior_review_record_job_id") == 126702487227 and
                basis.get("prior_actual_cli_job_id") == 126702487573 and
                basis.get("prior_run_note"),
                "prior exact-head validation provenance is incomplete")
    elif record["schema"] == "copilot-poryscript-abi-file-inspection/v2":
        require(basis.get("prior_successful_exact_head_run") == 41850174614 and
                basis.get("current_run_status_at_recording") ==
                "Latest PR workflow run 41891419634 was action_required with zero jobs; no push-triggered run was available.",
                "current exact-head CI blocker provenance is incomplete")
    elif record["schema"] == "copilot-poryscript-abi-file-inspection/v3":
        require(basis.get("prior_pr_run_id") == 41927842244 and
                basis.get("prior_pr_run_attempt") == 2 and
                basis.get("prior_review_record_job_id") == 126922717623 and
                basis.get("prior_actual_cli_job_id") == 126922862763 and
                basis.get("prior_pr_run_conclusion") == "success" and
                basis.get("push_run_status") == "NO_PUSH_TRIGGERED_RUN" and
                basis.get("prior_run_note"),
                "map-header tranche baseline CI provenance is incomplete")
    elif record["schema"] == "copilot-poryscript-abi-file-inspection/v4":
        require(basis.get("prior_pr_run_id") == 41944574482 and
                basis.get("prior_pr_run_status") == "action_required" and
                basis.get("prior_pr_run_jobs") == 0 and
                basis.get("prior_push_run_status") == "NO_PUSH_TRIGGERED_RUN" and
                basis.get("prior_run_note"),
                "Poryscript–FireRed tranche baseline CI provenance is incomplete")
    else:
        require(basis.get("prior_pr_workflow_run_id") == 41958394595 and
                basis.get("prior_pr_workflow_attempt") == 2 and
                basis.get("prior_pr_conclusion") == "success" and
                basis.get("prior_push_workflow_run_id") == 41958389068 and
                basis.get("prior_push_workflow_attempt") == 2 and
                basis.get("prior_exact_head") == schema_config["prior_head"] and
                basis.get("protocol_document_status") ==
                "EXPECTED_FILE_ABSENT_FROM_BRANCH_AND_MAIN" and
                basis.get("prior_run_note"),
                "preprocessor follow-up baseline or governing-protocol blocker is incomplete")

    closure_files, closure_ranges = validate_closure_record(closure_record)
    if record["schema"] in {
            "copilot-poryscript-abi-file-inspection/v4",
            "copilot-poryscript-abi-file-inspection/v5"}:
        expected_license_sources = (
            {("huderlem/poryscript", "LICENSE.md"),
             ("pret/pokefirered", "tools/preproc/LICENSE")}
            if record["schema"] == "copilot-poryscript-abi-file-inspection/v4"
            else {("pret/pokefirered", "tools/preproc/LICENSE")}
        )
        license_sources = {}
        for license_source in record.get("license_sources", []):
            license_key = (
                license_source.get("repository"), license_source.get("path")
            )
            closure_license = closure_files.get(license_key)
            require(license_key in expected_license_sources and
                    closure_license is not None and
                    license_source.get("commit") == PINS[license_key[0]] and
                    license_source.get("git_blob_sha1") ==
                    closure_license["git_blob_sha1"] and
                    license_source.get("sha256") == closure_license["sha256"] and
                    license_source.get("dossier_record_line_sha256") ==
                    closure_license["dossier_record_line_sha256"] and
                    license_source.get("assessment"),
                    "follow-up license-source identity differs from pinned dossier")
            require(license_key not in license_sources,
                    "duplicate follow-up license-source identity")
            license_sources[license_key] = license_source
        require(set(license_sources) == expected_license_sources,
                "follow-up pinned license-source identities differ")
    else:
        license_sources = {}
    if record["schema"] == "copilot-poryscript-abi-file-inspection/v5":
        basis = record["basis"]
        missing_license = {
            "repository": "pret/pokefirered",
            "path": "LICENSE",
            "commit": PINS["pret/pokefirered"],
            "status": "NOT_FOUND_AT_PIN",
            "assessment": (
                "The pinned repository contents API resolved no root LICENSE; "
                "observed tool-local license files do not establish licensing "
                "for asm/macros.inc or include/characters.h."
            ),
        }
        queue = basis.get("applied_queue", {})
        queue_path = ROOT / "docs/PHASE1_INDEPENDENT_SEMANTIC_REVIEW_QUEUE.md"
        queue_data = queue_path.read_bytes()
        require(record.get("license_search") == missing_license and
                basis.get("protocol_document_path") ==
                "docs/PHASE1_SYSTEM_BATCH_REVIEW_PROTOCOL_2026-10-27.md" and
                not (ROOT / basis["protocol_document_path"]).exists() and
                queue == {
                    "path": "docs/PHASE1_INDEPENDENT_SEMANTIC_REVIEW_QUEUE.md",
                    "git_blob_sha1": git_blob_sha1(queue_data),
                    "sha256": hashlib.sha256(queue_data).hexdigest(),
                } and queue.get("git_blob_sha1") ==
                "aa72c114de2694b92e3f1ef37c9fac7d18fd293b" and
                queue.get("sha256") ==
                "91e29885742be869d5eb382d2bff3190afc0e62ddf2777a9a6e1038d05bb8efb",
                "preprocessor license or governing-protocol provenance changed")
    files = record.get("files", [])
    require(len(files) == len(expected_files),
            "file-inspection receipt has an unexpected scoped file count")
    seen = set()
    for item in files:
        key = (item.get("repository"), item.get("path"))
        require(key in expected_files and key not in seen,
                "unknown or duplicate file-inspection identity: " + str(key))
        seen.add(key)
        require(item.get("commit") == PINS[key[0]],
                "file-inspection source pin differs: " + str(key))
        source = closure_files.get(key)
        require(source is not None and
                item.get("git_blob_sha1") == source["git_blob_sha1"] and
                item.get("sha256") == source["sha256"] and
                item.get("dossier_record_line_sha256") ==
                source["dossier_record_line_sha256"],
                "file-inspection source/dossier identity differs: " + str(key))
        require(item.get("extent") and
                item.get("whole_file_semantic_disposition") is False and
                item.get("verdict") == "NEEDS_EVIDENCE" and
                item.get("source_observations"),
                "file-inspection record must not claim whole-file disposition")
        if record["schema"] == "copilot-poryscript-abi-file-inspection/v3":
            require(item.get("complete_source_inspection") is True and
                    item.get("source_extent") == "COMPLETE_PINNED_FILE_READ" and
                    item.get("full_source_sha256") == source["sha256"] and
                    (item.get("byte_length"), item.get("line_count")) ==
                    schema_config["source_dimensions"][key],
                    "map-header handoff lacks complete source identity: " +
                    str(key))
            license_evidence = item.get("license_evidence", {})
            require(license_evidence.get("status") == "UNRESOLVED" and
                    license_evidence.get("unresolved"),
                    "map-header handoff must retain unresolved license review: " +
                    str(key))
        elif record["schema"] in {
                "copilot-poryscript-abi-file-inspection/v4",
                "copilot-poryscript-abi-file-inspection/v5"}:
            require(item.get("full_source_bytes_retrieved") is True and
                    (record["schema"] != "copilot-poryscript-abi-file-inspection/v5" or
                     item.get("complete_source_inspection") is True) and
                    (item.get("byte_length"), item.get("line_count")) ==
                    schema_config["source_dimensions"][key],
                    "follow-up lacks complete pinned source-byte identity: " +
                    str(key))
            license_evidence = item.get("license_evidence", {})
            require(license_evidence.get("status") == "UNRESOLVED" and
                    license_evidence.get("unresolved"),
                    "follow-up must retain unresolved license review: " + str(key))
            if (record["schema"] == "copilot-poryscript-abi-file-inspection/v4" and
                    license_evidence.get("path")):
                license_key = (key[0], license_evidence["path"])
                require(license_key in license_sources,
                        "follow-up license reference lacks a pinned source: " +
                        str(license_key))
            elif (record["schema"] == "copilot-poryscript-abi-file-inspection/v4" and
                  key[0] == "huderlem/poryscript"):
                require(False,
                        "Poryscript file lacks its pinned license-source reference")
            elif record["schema"] == "copilot-poryscript-abi-file-inspection/v5":
                license_path = license_evidence.get("path")
                if key[1].startswith("tools/preproc/"):
                    require(license_evidence.get("status") == "UNRESOLVED" and
                            license_path == "tools/preproc/LICENSE" and
                            ("pret/pokefirered", license_path) in license_sources and
                            license_evidence.get("unresolved"),
                            "preprocessor source lacks its unresolved license reference")
                else:
                    require(license_evidence.get("status") == "UNRESOLVED" and
                            license_path is None and
                            license_evidence.get("unresolved"),
                            "FireRed project source must retain its missing-license blocker")

        cited_ranges = {}
        for citation in item.get("evidence_ranges", []):
            start, end = citation.get("start"), citation.get("end")
            range_key = (key, start, end)
            require(range_key in closure_ranges and
                    closure_ranges[range_key] == citation.get("sha256"),
                    "file-inspection line evidence differs from closure: " +
                    str(range_key))
            cited_ranges[range_key] = citation["sha256"]
        expected_ranges = {
            range_key: digest for range_key, digest in closure_ranges.items()
            if range_key[0] == key
        }
        require(cited_ranges == expected_ranges and
                (cited_ranges or record["schema"] in {
                    "copilot-poryscript-abi-file-inspection/v4",
                    "copilot-poryscript-abi-file-inspection/v5"}),
                "file-inspection must cite every existing bounded range: " +
                str(key))
        if record["schema"] == "copilot-poryscript-abi-file-inspection/v3":
            expected_supplemental = schema_config["supplemental_ranges"].get(
                key, {}
            )
            supplemental = {
                (citation.get("start"), citation.get("end")):
                    citation.get("sha256")
                for citation in item.get("supplemental_evidence_ranges", [])
            }
            require(supplemental == expected_supplemental,
                    "map-header supplemental source evidence differs: " +
                    str(key))
        elif record["schema"] == "copilot-poryscript-abi-file-inspection/v4":
            expected_supplemental = schema_config["supplemental_ranges"].get(
                key, {}
            )
            supplemental = {
                (citation.get("start"), citation.get("end")):
                    citation.get("sha256")
                for citation in item.get("supplemental_evidence_ranges", [])
            }
            require(supplemental == expected_supplemental,
                    "Poryscript–FireRed supplemental source evidence differs: " +
                    str(key))
        elif record["schema"] == "copilot-poryscript-abi-file-inspection/v5":
            expected_supplemental = schema_config["supplemental_ranges"].get(key, {})
            supplemental = {
                (citation.get("start"), citation.get("end")):
                    citation.get("sha256")
                for citation in item.get("supplemental_evidence_ranges", [])
            }
            require(supplemental == expected_supplemental,
                    "preprocessor whole-file evidence differs: " + str(key))

        dependencies = item.get("dependency_links", [])
        require(dependencies, "file-inspection dependencies are required: " + str(key))
        for dependency in dependencies:
            target = (dependency.get("repository"), dependency.get("path"))
            require(target in closure_files and
                    dependency.get("direction") in {"inbound", "outbound"} and
                    dependency.get("relation"),
                    "file-inspection dependency lacks a pinned endpoint: " +
                    str(target))
        for objection in item.get("unresolved_obligations", []):
            require(any(entry.get("id") == objection and
                        entry.get("status") == "UNRESOLVED"
                        for entry in closure_record.get("objections", [])),
                    "file-inspection references a resolved or unknown objection")

    summary = record.get("summary", {})
    expected_source_count = len(expected_files)
    if record["schema"] == "copilot-poryscript-abi-file-inspection/v3":
        required_controls = {
            "NC-SOURCE-IDENTITY":
                "test_map_header_handoff_rejects_source_and_dossier_mutations",
            "NC-DOSSIER-IDENTITY":
                "test_map_header_handoff_rejects_source_and_dossier_mutations",
            "NC-RANGE-HASH":
                "test_map_header_handoff_rejects_range_and_dependency_mutations",
            "NC-DEPENDENCY-ENDPOINT":
                "test_map_header_handoff_rejects_range_and_dependency_mutations",
            "NC-VERDICT":
                "test_map_header_handoff_rejects_verdict_and_review_claim_mutations",
            "NC-ATTRIBUTION":
                "test_map_header_handoff_rejects_verdict_and_review_claim_mutations",
        }
        controls = {
            item.get("id"): item.get("test")
            for item in record.get("negative_controls", [])
        }
        require(controls == required_controls,
                "map-header handoff negative-control set is incomplete")
        require(record.get("review_handoff", {}).get("status") ==
                "READY_FOR_INDEPENDENT_REVIEW_NOT_APPROVAL" and
                record["review_handoff"].get("pending_requirements") ==
                ["authenticated_independent_reviewer",
                 "complete_semantic_objection_resolution",
                 "applicable_source_license_review",
                 "exact_head_pr_and_push_ci"],
                "map-header review handoff omits required independent review")
        require(summary.get("complete_source_files_read") == expected_source_count and
                summary.get("source_identity_records") == expected_source_count,
                "map-header handoff overstates complete source inspection")
    elif record["schema"] == "copilot-poryscript-abi-file-inspection/v4":
        required_controls = {
            "NC-SOURCE-IDENTITY":
                "test_followup_rejects_source_dossier_and_dimension_mutations",
            "NC-DOSSIER-IDENTITY":
                "test_followup_rejects_source_dossier_and_dimension_mutations",
            "NC-RANGE-HASH":
                "test_followup_rejects_range_and_scope_mutations",
            "NC-DEPENDENCY-ENDPOINT":
                "test_followup_rejects_range_and_scope_mutations",
            "NC-VERDICT":
                "test_followup_rejects_verdict_license_and_attribution_mutations",
            "NC-LICENSE-CLAIM":
                "test_followup_rejects_verdict_license_and_attribution_mutations",
            "NC-ATTRIBUTION":
                "test_followup_rejects_verdict_license_and_attribution_mutations",
        }
        controls = {
            item.get("id"): item.get("test")
            for item in record.get("negative_controls", [])
        }
        require(controls == required_controls,
                "Poryscript–FireRed negative-control set is incomplete")
        require(record.get("review_handoff", {}).get("status") ==
                "READY_FOR_INDEPENDENT_REVIEW_NOT_APPROVAL" and
                record["review_handoff"].get("pending_requirements") ==
                ["authenticated_independent_reviewer",
                 "whole_file_semantic_and_transitive_dependency_review",
                 "applicable_source_license_review",
                 "native_malformed_operand_and_table_boundary_evidence",
                 "exact_head_pr_and_push_ci"],
                "Poryscript–FireRed review handoff omits independent-review blockers")
        objections = record.get("objections", [])
        required_objections = {
            "O-PARSER-SHAPE", "O-CONDITION-SENTINEL", "O-BOUNDS",
            "O-INTEGRATION", "O-WHOLEFILE", "O-DEPENDENCIES",
            "O-LICENSING", "O-ATTESTATION",
        }
        require({item.get("id") for item in objections} == required_objections and
                all(item.get("status") == "UNRESOLVED" and
                    item.get("observation") and item.get("resolution")
                    for item in objections),
                "Poryscript–FireRed objections must remain explicit and unresolved")
        require(summary.get("selected_source_files") == expected_source_count and
                summary.get("complete_pinned_file_bytes_retrieved") ==
                expected_source_count,
                "Poryscript–FireRed source-byte count is incomplete")
        validation = record.get("validation", {})
        require(validation.get("local_source_status") ==
                "PASS_FILE_BYTES_AND_RANGES_NOT_SEMANTIC_APPROVAL" and
                validation.get("local_source_files_verified") ==
                expected_source_count and
                validation.get("local_source_checkout_identity") ==
                "FILE_BLOBS_ONLY" and
                validation.get("targeted_test_command") ==
                "python3 -m unittest discover -s tests -p "
                "'test_copilot_poryscript_abi_review.py' -v" and
                validation.get("targeted_tests_passed") == 22 and
                validation.get("actual_cli_gnu_arm_witness", "").startswith(
                    "NOT_RERUN;") and
                validation.get("exact_head_ci") == "PENDING_FOR_THIS_CHANGE",
                "Poryscript–FireRed validation provenance is incomplete")
    elif record["schema"] == "copilot-poryscript-abi-file-inspection/v5":
        required_controls = {
            "NC-SOURCE-IDENTITY":
                "test_preprocessor_handoff_rejects_source_and_dossier_mutations",
            "NC-WHOLE-FILE-HASH":
                "test_preprocessor_handoff_rejects_full_file_range_mutation",
            "NC-DEPENDENCY-ENDPOINT":
                "test_preprocessor_handoff_rejects_dependency_mutation",
            "NC-LICENSE-BLOCKER":
                "test_preprocessor_handoff_rejects_license_and_objection_mutations",
            "NC-VERDICT":
                "test_preprocessor_handoff_rejects_verdict_attribution_and_scope_mutations",
            "NC-UNKNOWN-CHARACTER":
                "Pinned native preprocessor rejects an unmapped UTF-8 character.",
            "NC-INVALID-UTF8":
                "Pinned native preprocessor rejects a truncated UTF-8 sequence.",
            "NC-CHARMAP-LIMIT":
                "Pinned native preprocessor rejects a 17-byte charmap sequence.",
        }
        controls = {
            item.get("id"): item.get("description", item.get("test"))
            for item in record.get("negative_controls", [])
        }
        require(controls == required_controls,
                "preprocessor negative-control set is incomplete")
        require(record.get("review_handoff", {}).get("status") ==
                "READY_FOR_INDEPENDENT_REVIEW_NOT_APPROVAL" and
                record["review_handoff"].get("pending_requirements") ==
                ["authenticated_independent_reviewer",
                 "missing_governing_batch_protocol",
                 "complete_transitive_caller_and_license_closure",
                 "bounded_malformed_input_and_integer-overflow_analysis",
                 "script-ABI relevance determination",
                 "exact_head_pr_and_push_ci"],
                "preprocessor handoff omits independent-review blockers")
        objection_ids = {
            item.get("id") for item in record.get("objections", [])
        }
        require(objection_ids == {
            "O-DECODER-BOUNDARY", "O-CFILE-IDENTIFIER-BOUNDARY",
            "O-CFILE-SIGNED-SHIFT", "O-CHARMAP-BACKSLASH",
            "O-TRANSITIVE-CLOSURE", "O-LICENSING", "O-PROTOCOL",
            "O-ABI-RELEVANCE", "O-ATTRIBUTION",
        } and all(item.get("status") == "UNRESOLVED" and
                  item.get("observation") and item.get("resolution")
                  for item in record.get("objections", [])),
                "preprocessor source objections must remain explicit")
        require(summary.get("selected_source_files") == expected_source_count and
                summary.get("complete_pinned_file_bytes_retrieved") ==
                expected_source_count and
                summary.get("complete_source_files_read") ==
                expected_source_count,
                "preprocessor source-byte and whole-file inspection counts differ")
        validation = record.get("validation", {})
        require(validation.get("host_preprocessor_build") ==
                "PASS_EXACT_PINNED_MAKEFILE_AND_SOURCE" and
                validation.get("negative_controls_passed") == 3 and
                validation.get("pinned_host_source_commit") ==
                PINS["pret/pokefirered"] and
                validation.get("actual_cli_gnu_arm_witness") ==
                "REUSED_PRIOR_EXACT_HEAD_EVIDENCE_NOT_RERUN" and
                validation.get("exact_head_ci") == "PENDING_FOR_THIS_CHANGE",
                "preprocessor host validation provenance is incomplete")

    retrieved_count = (
        summary.get("complete_pinned_file_bytes_retrieved")
        if record["schema"] in {
            "copilot-poryscript-abi-file-inspection/v4",
            "copilot-poryscript-abi-file-inspection/v5"}
        else summary.get("files_with_full_source_text_retrieved",
                         summary.get("files_with_complete_source_text_retrieved"))
    )
    require(seen == expected_files and
            retrieved_count == expected_source_count and
            summary.get("whole_file_semantic_reviews") == 0 and
            summary.get("new_copilot_reviewed_passed_files",
                        summary.get("new_files_with_whole_file_semantic_disposition")) == 0 and
            summary.get("new_qualifying_copilot_receipts", 0) == 0 and
            summary.get("new_approvals") == 0 and
            summary.get("phase1_gate") == "FAIL_INCOMPLETE",
            "file-inspection summary overstates review completion")
    return {
        "status": "PASS_FILE_PROVENANCE_NOT_SEMANTIC_APPROVAL",
        "files_with_full_source_text_retrieved": expected_source_count,
        "complete_source_files_read": (
            expected_source_count
            if record["schema"] in {
                "copilot-poryscript-abi-file-inspection/v3",
                "copilot-poryscript-abi-file-inspection/v5"}
            else 0
        ),
        "whole_file_semantic_reviews": 0,
        "new_qualifying_copilot_receipts": 0,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def verify_closure_sources(record, roots, source_files_only=False,
                           archive_root=ROOT):
    files, ranges = validate_closure_record(record, archive_root)
    commit_status = {}
    for repository, root in roots.items():
        require(repository in PINS, "unexpected closure source root: " + repository)
        if (root / ".git").exists():
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            )
            require(result.stdout.strip() == PINS[repository],
                    "upstream checkout HEAD differs for " + repository)
            commit_status[repository] = "VERIFIED_PINNED_COMMIT"
        else:
            require(source_files_only,
                    "source checkout lacks .git metadata; pass --source-files-only "
                    "to verify file blobs without claiming commit verification")
            commit_status[repository] = "FILE_BLOBS_ONLY"

    require(set(roots) == set(PINS),
            "closure validation requires all four pinned source roots")
    ranges_by_key = {}
    for (key, start, end), digest in ranges.items():
        ranges_by_key.setdefault(key, []).append({
            "start": start, "end": end, "sha256": digest,
        })
    for key, source in files.items():
        entry = dict(source)
        entry["evidence_ranges"] = ranges_by_key.get(key, [])
        verify_source_entry(entry, roots[key[0]])
    return {
        "status": "PASS_HASHED_CLOSURE_NOT_SEMANTIC_APPROVAL",
        "source_files_verified": len(files),
        "bounded_line_ranges_verified": len(ranges),
        "checkout_commits": commit_status,
        "whole_file_semantic_reviews": 0,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def verify_source_entry(source, root):
    path = PurePosixPath(source["path"])
    file_path = root.joinpath(*path.parts)
    require(file_path.is_file(), "missing pinned source file: " + str(file_path))
    data = file_path.read_bytes()
    require(git_blob_sha1(data) == source["git_blob_sha1"],
            "Git blob mismatch: " + source["repository"] + ":" + source["path"])
    require(hashlib.sha256(data).hexdigest() == source["sha256"],
            "file SHA-256 mismatch: " + source["repository"] + ":" + source["path"])
    lines = data.splitlines(keepends=True)
    for item in source.get("evidence_ranges", []):
        require(item["end"] <= len(lines), "line range exceeds source file: " + source["path"])
        excerpt = b"".join(lines[item["start"] - 1:item["end"]])
        require(hashlib.sha256(excerpt).hexdigest() == item["sha256"],
                "line-range SHA-256 mismatch: %s:%d-%d" %
                (source["path"], item["start"], item["end"]))


def verify_file_inspection_sources(record, closure_record, roots,
                                  source_files_only=False):
    result = validate_file_inspection_record(record, closure_record)
    if record.get("schema") not in {
            "copilot-poryscript-abi-file-inspection/v4",
            "copilot-poryscript-abi-file-inspection/v5"}:
        return result

    repositories = {item["repository"] for item in record["files"]}
    require(set(roots) == repositories,
            "follow-up source verification requires exactly its pinned repositories")
    checkout_commits = {}
    for repository, root in roots.items():
        if (root / ".git").exists():
            revision = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            require(revision == PINS[repository],
                   "upstream checkout HEAD differs for " + repository)
            checkout_commits[repository] = "VERIFIED_PINNED_COMMIT"
        else:
            require(source_files_only,
                   "source checkout lacks .git metadata; pass --source-files-only "
                   "to verify file blobs without claiming commit verification")
            checkout_commits[repository] = "FILE_BLOBS_ONLY"

    for item in record["files"]:
        entry = {
            "repository": item["repository"],
            "path": item["path"],
            "git_blob_sha1": item["git_blob_sha1"],
            "sha256": item["sha256"],
            "evidence_ranges": (
                item.get("evidence_ranges", []) +
                item.get("supplemental_evidence_ranges", [])
            ),
        }
        verify_source_entry(entry, roots[item["repository"]])
    result["source_files_verified"] = len(record["files"])
    result["checkout_commits"] = checkout_commits
    result["status"] = "PASS_FILE_BYTES_AND_RANGES_NOT_SEMANTIC_APPROVAL"
    return result


def verify_sources(record, roots, source_files_only=False):
    sources = validate_record(record)
    commit_status = {}
    for repository, root in roots.items():
        require(repository in PINS, "unexpected source root: " + repository)
        git_dir = root / ".git"
        if git_dir.exists():
            result = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "HEAD"],
                check=True, capture_output=True, text=True,
            )
            require(result.stdout.strip() == PINS[repository],
                    "upstream checkout HEAD differs for " + repository)
            commit_status[repository] = "VERIFIED"
        else:
            require(source_files_only,
                    "source checkout lacks .git metadata; pass --source-files-only "
                    "to verify file blobs without claiming commit verification")
            commit_status[repository] = "NOT_CHECKED_FILE_BLOBS_ONLY"

    verified = 0
    for (repository, _), source in sources.items():
        require(repository in roots, "missing source root for " + repository)
        verify_source_entry(source, roots[repository])
        verified += 1
    return {
        "status": "PASS_SOURCE_BLOBS_AND_LINE_RANGES",
        "source_files_verified": verified,
        "checkout_commits": commit_status,
        "approval_count_changed": False,
        "phase1_gate": "FAIL_INCOMPLETE",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=DEFAULT_RECORD)
    parser.add_argument("--closure-record", type=Path)
    parser.add_argument("--file-inspection-record", type=Path, action="append")
    parser.add_argument("--poryscript-root", type=Path)
    parser.add_argument("--firered-root", type=Path)
    parser.add_argument("--agbcc-root", type=Path)
    parser.add_argument("--mgba-root", type=Path)
    parser.add_argument("--source-files-only", action="store_true")
    args = parser.parse_args()
    record_path = args.closure_record or args.record
    record = json.loads(record_path.read_text(encoding="utf-8"))
    roots = {}
    if args.poryscript_root:
        roots["huderlem/poryscript"] = args.poryscript_root.resolve()
    if args.firered_root:
        roots["pret/pokefirered"] = args.firered_root.resolve()
    if args.agbcc_root:
        roots["pret/agbcc"] = args.agbcc_root.resolve()
    if args.mgba_root:
        roots["mgba-emu/mgba"] = args.mgba_root.resolve()
    if args.file_inspection_record:
        require(args.closure_record is not None,
                "--file-inspection-record requires --closure-record")
        results = []
        for inspection_path in args.file_inspection_record:
            inspection = json.loads(inspection_path.read_text(encoding="utf-8"))
            if inspection.get("schema") in {
                    "copilot-poryscript-abi-file-inspection/v4",
                    "copilot-poryscript-abi-file-inspection/v5"}:
                results.append(verify_file_inspection_sources(
                    inspection, record, roots, args.source_files_only
                ))
            else:
                results.append(validate_file_inspection_record(inspection, record))
        print(json.dumps(results, sort_keys=True))
        return
    if args.closure_record and roots:
        result = verify_closure_sources(record, roots, args.source_files_only)
    elif args.closure_record:
        validate_closure_record(record)
        result = {
            "status": "PASS_CLOSURE_RECORD_STRUCTURE_NOT_SEMANTIC_APPROVAL",
            "source_files_verified": 0,
            "approval_count_changed": False,
            "phase1_gate": "FAIL_INCOMPLETE",
        }
    elif roots:
        result = verify_sources(record, roots, args.source_files_only)
    else:
        validate_record(record)
        result = {
            "status": "PASS_RECORD_STRUCTURE_ONLY",
            "source_files_verified": 0,
            "approval_count_changed": False,
            "phase1_gate": "FAIL_INCOMPLETE",
        }
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
