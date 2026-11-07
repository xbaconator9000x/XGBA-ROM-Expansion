#!/usr/bin/env python3
"""Verify pinned Porymap validators, their callers, and the bounded Qt witness."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import pathlib
import re
import shlex
import shutil
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
CANDIDATE_ARCHIVE_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
CANDIDATE_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"

FILES = {
    "src/core/validator.cpp": {
        "blob": "2b0fcf0b5ce61e4baa9141b05d6fb4cd4e9f087e",
        "sha256": "0112d5d372ba6180b5a1681e299225d1b8a8d26d0d4029eeddade10ee1675346",
        "row": "42033ffbdbfda93c5ab5c8889fd4c424415d6f1c14d587a94bd4339718501e43",
        "role": "Focal full-file implementation scope: IdentifierValidator regexes, PrefixValidator validation/fixup/validity semantics, and all methods implemented here.",
        "coverage": "focal-whole-file",
    },
    "include/core/validator.h": {
        "blob": "46b916ce2c5b20373db43f9e0e1775a1d4e160b8",
        "sha256": "3068855e704739ea84b5473860f1e418e0679e4c87bb8368339f70ed51eda6d7",
        "row": "62ff3588f1ed1eac7f4f908ab42018aa05e2a2f0107bc9277f561d4f3cd7496e",
        "role": "Focal full-file API scope: PrefixValidator, IdentifierValidator and UppercaseValidator declarations, constructors, contracts, and declared setPrefix member.",
        "coverage": "focal-whole-file",
    },
    "src/ui/newdefinedialog.cpp": {
        "blob": "9ac3a3ff2d5e1768edd3af00ce220191525d0f50",
        "sha256": "c6a645de9dc5efc623c25e973737c26774d25651b6056ac12640e8e4e54f6640",
        "row": "401d87a34484f43a3db6987d2120b700efc61ca3ea4566861fea2d06ae5083f6",
        "role": "Caller context only: NewDefineDialog uses an unprefixed IdentifierValidator.",
        "coverage": "context-only",
    },
    "src/ui/newmapgroupdialog.cpp": {
        "blob": "8c3c923fcf0111f8c049ac47057ced16af01b465",
        "sha256": "878161a5bad3ea41d5112ad6a3baa9bc291ecf8153dbd3006bd2e101f67c9594",
        "row": "f42bb2fdbb29f1e459ab99083e1a4c5ae758ea1680a1bf9d29e8dbb9bb9aaabb",
        "role": "Caller context only: NewMapGroupDialog uses an unprefixed IdentifierValidator.",
        "coverage": "context-only",
    },
    "src/ui/newlocationdialog.cpp": {
        "blob": "37552cf04f37afe669f4bc7f4e6bae7f9f961a39",
        "sha256": "31dacb4329054f26679257b8eead908b758a71ba5a9c76f6d1d15dfbf14713b7",
        "row": "39be6a9037936f44aa1f3813e52556821044f2fd9736774327e373003fb9780f",
        "role": "Caller context only: NewLocationDialog applies a configured map-section prefix.",
        "coverage": "context-only",
    },
    "src/ui/newtilesetdialog.cpp": {
        "blob": "8749b63e28218adef3b17c43fbb8cefc836a76e4",
        "sha256": "e7ba28724606e1328458681c448ecfa4749dfab9517a4708e6ccd93e6574c6df",
        "row": "8d181f807dbbc98c5890eb1a680d5c35d30da29cf78175cd6beb1a5600381050",
        "role": "Caller context only: NewTilesetDialog applies a configured tileset symbol prefix.",
        "coverage": "context-only",
    },
    "src/ui/newlayoutdialog.cpp": {
        "blob": "de20bb290b7847314ae931279bb9ebe4430b34bf",
        "sha256": "69f3589c365f858f5400730b45e6ed3c2d2765937ace5932f5a4027dad93dae6",
        "row": "809a340ba9936c7501a52361f7425afe80f573bc04482543e0bb6118f4b9fc27",
        "role": "Caller context only: NewLayoutDialog shares one IdentifierValidator between layout name and ID fields.",
        "coverage": "context-only",
    },
    "src/editor.cpp": {
        "blob": "34112f6355b13d9381de7188624c36e5efeba151",
        "sha256": "a505ba77243efdcaa2da8cce448e97ce80aa355145fb567290cb6d549bead270",
        "row": "bdee490bd8de75bfc2306ca7264737becb5196580ce0b3241a00292ed1119d24",
        "role": "Caller context only: group-base-label entry constructs an unprefixed IdentifierValidator.",
        "coverage": "context-only",
    },
    "src/ui/newmapdialog.cpp": {
        "blob": "c8a028025bf1a9aabb8fd96cccf3d0a76214bb0e",
        "sha256": "04cf3279c1dc02697c8af03aa19bf1c515010605c789619c60a11baa29630dac",
        "row": "ad399234177122e2df573a6b5eb09263b79deed968c7db3c151d54250f1e40a5",
        "role": "Caller context only: NewMapDialog installs an IdentifierValidator on name, group, and layout-ID inputs.",
        "coverage": "context-only",
    },
    "src/ui/maplistmodels.cpp": {
        "blob": "ba4e9a792be958f7b93d70807f92d2919464deaf",
        "sha256": "c56c7525d39b00468f7ba6841ad8c8ed03d957602e79d5f5186fa82ff466e477",
        "row": "9de71a51ff6afc219634e6f1cdaafa801bc0c4419d97eb93b0e906309dcd7387",
        "role": "Caller context only: GroupNameDelegate constructs an IdentifierValidator for inline editing.",
        "coverage": "context-only",
    },
    "src/ui/tileseteditor.cpp": {
        "blob": "723a2afdeb89c1752e9811a07715462c2279c645",
        "sha256": "a85e7827754d3f08cec5ebe90aa7a737958524ac379d563adfd269d1b7557ced",
        "row": "940f1b1723b84449dbc3f20648e057643c96d9be19a08e9fa210746193a35ee7",
        "role": "Caller context only: metatile-label editor enables empty identifiers.",
        "coverage": "context-only",
    },
    "src/ui/colorinputwidget.cpp": {
        "blob": "6ed587aa92f3a69ebecab1ee6a7993c7c026f5dd",
        "sha256": "4c6697837de61cfe63c1a6aff1b0ce088a32b8d47e86253f215c61e4dc170037",
        "row": "ba68d86ff30b37f10e9e7d45b480d98d94add86d6170c4329cffed550f033fab",
        "role": "Caller context only: ColorInputWidget attaches the inline UppercaseValidator.",
        "coverage": "context-only",
    },
    "porymap.pro": {
        "blob": "53d8055ecfe5d88afb6f183b82d4a3472727ad4f",
        "sha256": "cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996",
        "row": "93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2",
        "role": "Build context only: includes validator.cpp/header in the application and enables Qt Core/GUI.",
        "coverage": "context-only",
    },
    "LICENSE.md": {
        "blob": "65c5ca88a67c30becee01c5a8816d964b03862f9",
        "sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
        "row": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
        "role": "Root license context only: Porymap declares LGPL text; no distribution-compliance conclusion is made.",
        "coverage": "context-only",
    },
}

ANCHORS = {
    "src/core/validator.cpp": (
        b"QRegularExpression(\"[A-Za-z_]+[\\\\w]*\")",
        b"QRegularExpression(\"(^$|[A-Za-z_]+[\\\\w]*)\")",
        b"QValidator::State PrefixValidator::validate",
        b"if (missingPrefix(input))",
        b"void PrefixValidator::fixup",
        b"bool PrefixValidator::isValid",
    ),
    "include/core/validator.h": (
        b"class PrefixValidator : public QRegularExpressionValidator",
        b"void setPrefix(const QString &prefix);",
        b"class IdentifierValidator : public PrefixValidator",
        b"class UppercaseValidator : public QValidator",
    ),
    "src/ui/newdefinedialog.cpp": (
        b"ui->lineEdit_Name->setValidator(new IdentifierValidator(this));",
    ),
    "src/ui/newmapgroupdialog.cpp": (
        b"ui->lineEdit_Name->setValidator(new IdentifierValidator(this));",
    ),
    "src/ui/newlocationdialog.cpp": (
        b"new IdentifierValidator(namePrefix, this)",
    ),
    "src/ui/newtilesetdialog.cpp": (
        b"new IdentifierValidator(this->symbolPrefix, this)",
    ),
    "src/ui/newlayoutdialog.cpp": (
        b"auto validator = new IdentifierValidator(this);",
    ),
    "src/editor.cpp": (
        b"lineEdit->setValidator(new IdentifierValidator(lineEdit));",
    ),
    "src/ui/newmapdialog.cpp": (
        b"auto validator = new IdentifierValidator(this);",
    ),
    "src/ui/maplistmodels.cpp": (
        b"editor->setValidator(new IdentifierValidator(parent));",
    ),
    "src/ui/tileseteditor.cpp": (
        b"validator->setAllowEmpty(true);",
        b"ui->lineEdit_MetatileLabel->setValidator(validator);",
    ),
    "src/ui/colorinputwidget.cpp": (
        b"static const UppercaseValidator uppercaseValidator;",
        b"ui->lineEdit_Hex->setValidator(&uppercaseValidator);",
    ),
    "porymap.pro": (
        b"src/core/validator.cpp",
        b"include/core/validator.h",
        b"QT       += core gui",
    ),
    "LICENSE.md": (
        b"GNU LESSER GENERAL PUBLIC LICENSE",
    ),
}

FOCAL_SOURCES = {"include/core/validator.h", "src/core/validator.cpp"}
CALLER_SOURCES = {
    path for path, item in FILES.items() if item["coverage"] == "context-only"
    and path.endswith((".cpp", ".cc", ".cxx", ".h", ".hpp"))
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def load_candidate_rows(workpack: pathlib.Path) -> dict[str, tuple[dict, str]]:
    raw_zip = workpack.read_bytes()
    require(sha256(raw_zip) == WORKPACK_SHA256, "candidate workpack ZIP hash mismatch")
    with zipfile.ZipFile(workpack) as archive:
        compressed = archive.read(CANDIDATE_MEMBER)
    require(sha256(compressed) == CANDIDATE_ARCHIVE_SHA256,
            "candidate inventory gzip hash mismatch")

    rows = {}
    for raw_row in gzip.decompress(compressed).splitlines():
        row = json.loads(raw_row)
        provenance = row.get("provenance", {})
        path = provenance.get("path")
        if provenance.get("repository") != "huderlem/porymap" or path not in FILES:
            continue
        require(path not in rows, "duplicate candidate inventory row: " + path)
        rows[path] = (row, sha256(raw_row))
    require(set(rows) == set(FILES), "candidate inventory rows incomplete")

    for path, (row, row_hash) in rows.items():
        expected = FILES[path]
        provenance = row.get("provenance", {})
        review = row.get("review", {})
        require(provenance.get("pinned_revision") == PIN, "candidate pin mismatch: " + path)
        require(provenance.get("git_blob_sha") == expected["blob"],
                "candidate blob mismatch: " + path)
        require(provenance.get("source_content_sha256") in (None, expected["sha256"]),
                "candidate content hash mismatch: " + path)
        require(row_hash == expected["row"], "candidate row hash mismatch: " + path)
        require(review.get("semantic_signoff") is False and review.get("reviewer") is None,
                "candidate row claims semantic review: " + path)
        require(review.get("status") in (
            "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
        ), "unexpected inventory status: " + path)
    return rows


def verify_sources(upstream: pathlib.Path) -> dict[str, bytes]:
    require((upstream / ".git").exists(), "expected pinned Porymap checkout")
    revision = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    require(revision == PIN, "wrong Porymap source revision")

    sources = {}
    for path, expected in FILES.items():
        raw = (upstream / path).read_bytes()
        require(git_blob(raw) == expected["blob"], "Git blob mismatch: " + path)
        require(sha256(raw) == expected["sha256"], "full-byte SHA-256 mismatch: " + path)
        sources[path] = raw
    for path, anchors in ANCHORS.items():
        for anchor in anchors:
            require(anchor in sources[path],
                    "required dependency/source anchor missing: " + path + ": " + repr(anchor))
    return sources


def verify_prefix_setter_boundary(upstream: pathlib.Path, validator_sources: list[str]) -> dict:
    files = list((upstream / "src").rglob("*")) + list((upstream / "include").rglob("*"))
    definitions = []
    definition = re.compile(rb"\bvoid\s+PrefixValidator\s*::\s*setPrefix\s*\(")
    call = re.compile(rb"\bsetPrefix\s*\(")
    calls = []
    for path in files:
        if path.suffix not in {".cpp", ".cc", ".cxx", ".h", ".hpp"}:
            continue
        relative = str(path.relative_to(upstream))
        raw = path.read_bytes()
        if definition.search(raw):
            definitions.append(relative)
        if relative in validator_sources and relative != "include/core/validator.h":
            if call.search(raw) and not definition.search(raw):
                calls.append(relative)
    require(not definitions,
            "PrefixValidator::setPrefix implementation unexpectedly exists: " + repr(definitions))
    require(not calls,
            "in-tree PrefixValidator::setPrefix call site unexpectedly exists: " + repr(calls))
    return {"matches": sorted(definitions), "call_sites": sorted(calls)}


def verify_caller_closure(upstream: pathlib.Path) -> list[str]:
    symbol = re.compile(rb"\b(?:PrefixValidator|IdentifierValidator|UppercaseValidator)\b")
    matches = []
    for root in ("src", "include"):
        for path in (upstream / root).rglob("*"):
            if path.suffix not in {".cpp", ".cc", ".cxx", ".h", ".hpp"}:
                continue
            if symbol.search(path.read_bytes()):
                matches.append(str(path.relative_to(upstream)))
    matches.sort()
    expected = FOCAL_SOURCES | CALLER_SOURCES
    require(set(matches) == expected,
            "validator class reference closure changed: " + repr(matches))
    return matches


def reject_source_mutation(path: str, original: bytes) -> None:
    changed = original + b"\nXGBA_VALIDATOR_SOURCE_MUTATION\n"
    try:
        require(git_blob(changed) == FILES[path]["blob"] and
                sha256(changed) == FILES[path]["sha256"],
                "mutated source unexpectedly matched")
    except ValueError:
        return
    raise AssertionError("source mutation accepted: " + path)


def compile_and_run(upstream: pathlib.Path, harness: pathlib.Path) -> dict:
    flags = shlex.split(
        subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Core", "Qt6Gui"], text=True
        )
    )
    moc_candidates = []
    if shutil.which("moc"):
        moc_candidates.append(shutil.which("moc"))
    qt_libexec = subprocess.check_output(
        ["pkg-config", "--variable=libexecdir", "Qt6Core"], text=True
    ).strip()
    if qt_libexec:
        moc_candidates.append(str(pathlib.Path(qt_libexec) / "moc"))
    qt_host_bins = subprocess.check_output(
        ["qmake6", "-query", "QT_HOST_BINS"], text=True
    ).strip()
    if qt_host_bins:
        moc_candidates.append(str(pathlib.Path(qt_host_bins) / "moc"))
    moc_path = next((candidate for candidate in moc_candidates if pathlib.Path(candidate).is_file()), None)
    require(moc_path is not None, "Qt6 moc executable not found")
    moc = subprocess.check_output([moc_path, "-v"], text=True).strip()
    with tempfile.TemporaryDirectory(prefix="phase1-porymap-validator-") as temp:
        temp_path = pathlib.Path(temp)
        moc_cpp = temp_path / "moc_validator.cpp"
        binary = temp_path / "validator-native"
        subprocess.run(
            [moc_path, "-I" + str(upstream / "include/core"),
             str(upstream / "include/core/validator.h"), "-o", str(moc_cpp)],
            check=True,
            timeout=30,
        )
        command = [
            "g++", "-std=c++17", "-O0", "-g", "-fPIC",
            "-I" + str(upstream / "include/core"),
            str(harness),
            str(upstream / "src/core/validator.cpp"),
            str(moc_cpp),
            "-o", str(binary),
            *flags,
        ]
        subprocess.run(command, check=True, timeout=120)
        run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=30)
        require(run.returncode == 0, "native validator controls failed: " + run.stderr)
        require("VALIDATOR_NATIVE plain_ids=1 prefix_states=1 fixup=1" in run.stdout,
                "native validator success marker missing")

        link_probe_binary = temp_path / "validator-link-probe"
        link_command = [
            "g++", "-std=c++17", "-O0", "-fPIC",
            "-I" + str(upstream / "include/core"),
            str(ROOT / "tests/phase1_porymap_validator_link_probe.cpp"),
            str(upstream / "src/core/validator.cpp"),
            str(moc_cpp),
            "-o", str(link_probe_binary),
            *flags,
        ]
        link_probe = subprocess.run(
            link_command, capture_output=True, text=True, timeout=120
        )
        require(link_probe.returncode != 0, "declared setPrefix unexpectedly linked")
        require("PrefixValidator::setPrefix" in link_probe.stderr,
                "link probe failed for an unexpected reason: " + link_probe.stderr)

        return {
            "compiler": "g++",
            "qt": "Qt6Core+Qt6Gui",
            "moc": moc,
            "original_cpp_sha256": FILES["src/core/validator.cpp"]["sha256"],
            "original_header_sha256": FILES["include/core/validator.h"]["sha256"],
            "normal_returncode": run.returncode,
            "normal_stdout": run.stdout,
            "normal_stderr": run.stderr,
            "declared_setter_link_returncode": link_probe.returncode,
            "declared_setter_link_stderr": link_probe.stderr,
        }


def validate_evidence(evidence: dict) -> None:
    require(evidence["source_pin"] == PIN, "evidence pin mismatch")
    require(evidence["candidate_inventory"]["archive_sha256"] == CANDIDATE_ARCHIVE_SHA256 and
            evidence["candidate_inventory"]["is_semantic_dossier"] is False,
            "candidate inventory provenance mismatch")
    require(evidence["candidate_inventory"]["row_sha256"] == {
        path: item["row"] for path, item in FILES.items()
    }, "candidate inventory row identities mismatch")
    require(evidence["original_semantic_dossier"]["available"] is False,
            "missing original dossier not preserved")
    require(set(evidence["files"]) == set(FILES), "per-file handoff identities incomplete")
    for path, item in evidence["files"].items():
        expected = FILES[path]
        require(item["git_blob_sha1"] == expected["blob"] and
                item["full_source_sha256"] == expected["sha256"] and
                item["candidate_row_sha256"] == expected["row"] and
                item["role"] == expected["role"] and
                item["coverage"] == expected["coverage"] and
                item["reviewer"] is None and
                item["independent_review_receipt"] is None and
                item["disposition"] == "NEEDS_EVIDENCE",
                "per-file identity/disposition mismatch: " + path)
    native = evidence["native"]
    require(native["original_cpp_sha256"] == FILES["src/core/validator.cpp"]["sha256"] and
            native["original_header_sha256"] == FILES["include/core/validator.h"]["sha256"],
            "native source identity mismatch")
    require(native["normal_returncode"] == 0 and
            "VALIDATOR_NATIVE plain_ids=1 prefix_states=1 fixup=1" in native["normal_stdout"],
            "native positive/negative result missing")
    require(native["declared_setter_link_returncode"] != 0 and
            "PrefixValidator::setPrefix" in native["declared_setter_link_stderr"],
            "declared-but-undefined setPrefix boundary missing")
    require(evidence["set_prefix_definition_search"]["matches"] == [],
            "setPrefix definition absence not preserved")
    require(evidence["set_prefix_definition_search"]["call_sites"] == [],
            "setPrefix call-site absence not preserved")
    require(evidence["set_prefix_definition_search"]["symbol"] ==
            "PrefixValidator::setPrefix" and
            evidence["set_prefix_definition_search"]["scope"] ==
            "all .cpp/.cc/.cxx/.h/.hpp files under pinned src/ and include/",
            "setPrefix definition search scope mismatch")
    require(evidence["caller_closure"]["matches"] ==
            sorted(FOCAL_SOURCES | CALLER_SOURCES) and
            evidence["caller_closure"]["scope"] ==
            "all .cpp/.cc/.cxx/.h/.hpp files under pinned src/ and include/",
            "validator caller closure mismatch")
    require(evidence["phase1_gate"] == "FAIL_INCOMPLETE" and
            evidence["independent_approvals"] == 0 and
            evidence["disposition"] == "NEEDS_EVIDENCE",
            "non-approving invariant changed")
    require(evidence["source_mutation_rejections"] == len(FILES),
            "source mutation coverage incomplete")


def reject_evidence_mutation(evidence: dict, mutate) -> None:
    changed = copy.deepcopy(evidence)
    mutate(changed)
    try:
        validate_evidence(changed)
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError("evidence mutation accepted")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", required=True, type=pathlib.Path)
    parser.add_argument("--workpack", type=pathlib.Path,
                        default=ROOT / "imports/XGBA_Phase1_v1.5_Complete_Workpack.zip")
    parser.add_argument("--harness", type=pathlib.Path,
                        default=ROOT / "tests/phase1_porymap_validator_native.cpp")
    parser.add_argument("--output", required=True, type=pathlib.Path)
    args = parser.parse_args()

    rows = load_candidate_rows(args.workpack)
    sources = verify_sources(args.porymap)
    caller_matches = verify_caller_closure(args.porymap)
    setter_boundary = verify_prefix_setter_boundary(args.porymap, caller_matches)
    source_negatives = 0
    for path, data in sources.items():
        reject_source_mutation(path, data)
        source_negatives += 1

    native = compile_and_run(args.porymap, args.harness)
    files = {
        path: {
            "git_blob_sha1": item["blob"],
            "full_source_sha256": item["sha256"],
            "candidate_row_sha256": item["row"],
            "role": item["role"],
            "coverage": item["coverage"],
            "reviewer": None,
            "independent_review_receipt": None,
            "disposition": "NEEDS_EVIDENCE",
        }
        for path, item in FILES.items()
    }
    evidence = {
        "schema": "phase1-porymap-validator-native-v1",
        "source_pin": PIN,
        "disposition": "NEEDS_EVIDENCE",
        "phase1_gate": "FAIL_INCOMPLETE",
        "independent_approvals": 0,
        "candidate_inventory": {
            "workpack_sha256": WORKPACK_SHA256,
            "archive_sha256": CANDIDATE_ARCHIVE_SHA256,
            "member": CANDIDATE_MEMBER,
            "is_semantic_dossier": False,
            "row_sha256": {path: row_hash for path, (_, row_hash) in rows.items()},
        },
        "original_semantic_dossier": {
            "available": False,
            "archive_sha256": None,
            "note": "The imported workpack contains candidate-inventory rows only; no original independent semantic dossier or reviewer receipt was found.",
        },
        "files": files,
        "set_prefix_definition_search": {
            "scope": "all .cpp/.cc/.cxx/.h/.hpp files under pinned src/ and include/",
            "symbol": "PrefixValidator::setPrefix",
            "matches": setter_boundary["matches"],
            "call_sites": setter_boundary["call_sites"],
        },
        "caller_closure": {
            "scope": "all .cpp/.cc/.cxx/.h/.hpp files under pinned src/ and include/",
            "matches": caller_matches,
        },
        "native": native,
        "source_mutation_rejections": source_negatives,
        "source_observations": [
            "IdentifierValidator enforces an ASCII letter/underscore start; its tail uses Qt regular-expression \\w.",
            "PrefixValidator reports a recoverable missing prefix as Intermediate and prepends the prefix in fixup.",
            "Header declares PrefixValidator::setPrefix, but no pinned implementation or in-tree caller exists; an explicit native link probe fails on that symbol.",
        ],
        "limits": [
            "Original validator.cpp and moc-generated metaobject are compiled with Qt6Core/Qt6Gui; tests call validators directly, not actual GUI input events.",
            "Caller files are source-context records and are not whole-file semantic reviews.",
            "The public setPrefix link failure is bounded to the pinned source tree and probe; no upstream code is changed.",
            "The candidate archive is not an original semantic dossier, and there is no independent attributable review receipt.",
            "No distribution or legal compliance conclusion is made from the pinned root license text.",
        ],
    }
    validate_evidence(evidence)

    evidence_negatives = 0
    for mutate in (
        lambda value: value.__setitem__("source_pin", "0" * 40),
        lambda value: value["candidate_inventory"].__setitem__("archive_sha256", "0" * 64),
        lambda value: value["candidate_inventory"].__setitem__("is_semantic_dossier", True),
        lambda value: value["candidate_inventory"]["row_sha256"].__setitem__(
            "src/core/validator.cpp", "0" * 64
        ),
        lambda value: value["original_semantic_dossier"].__setitem__("available", True),
        lambda value: value["files"]["src/core/validator.cpp"].__setitem__(
            "git_blob_sha1", "0" * 40
        ),
        lambda value: value["files"]["src/core/validator.cpp"].__setitem__(
            "candidate_row_sha256", "0" * 64
        ),
        lambda value: value["files"].pop("src/ui/newmapdialog.cpp"),
        lambda value: value["files"]["src/core/validator.cpp"].__setitem__(
            "reviewer", "copilot"
        ),
        lambda value: value["files"]["src/core/validator.cpp"].__setitem__(
            "independent_review_receipt", {"decision": "APPROVED"}
        ),
        lambda value: value["files"]["src/core/validator.cpp"].__setitem__(
            "disposition", "APPROVED"
        ),
        lambda value: value["native"].__setitem__("normal_returncode", 1),
        lambda value: value["native"].__setitem__("normal_stdout", ""),
        lambda value: value["native"].__setitem__("declared_setter_link_returncode", 0),
        lambda value: value["native"].__setitem__("declared_setter_link_stderr", ""),
        lambda value: value["set_prefix_definition_search"].__setitem__(
            "matches", ["src/core/validator.cpp"]
        ),
        lambda value: value["set_prefix_definition_search"].__setitem__(
            "call_sites", ["src/ui/newlocationdialog.cpp"]
        ),
        lambda value: value["caller_closure"].__setitem__("matches", []),
        lambda value: value.__setitem__("phase1_gate", "PASS"),
        lambda value: value.__setitem__("independent_approvals", 1),
    ):
        reject_evidence_mutation(evidence, mutate)
        evidence_negatives += 1

    evidence["evidence_mutation_rejections"] = evidence_negatives
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(
        "PORYMAP_VALIDATOR_EVIDENCE_PASS "
        f"pinned_files={len(FILES)} focal_files=2 native_controls=16 "
        f"undefined_setter_link_failure=1 source_mutations={source_negatives} "
        f"evidence_mutations={evidence_negatives} approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()
