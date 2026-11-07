#!/usr/bin/env python3
"""Verify pinned Porymap AdvanceMap import sources and run the original parser with Qt6."""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import pathlib
import shlex
import subprocess
import tempfile
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIN = "26b919d7ff4b54152de010abd5bf344af2ebe116"
WORKPACK_SHA256 = "5de8d2880a520aa4a80bf0a5b968ba6d19bb0a6a388260a08bd3906b2b4a5cb4"
CANDIDATE_ARCHIVE_SHA256 = "fe7785c38c7cbd80256ff591dabf1308f06f51f6324b44a743b8b087defd27ac"
CANDIDATE_MEMBER = "evidence/candidate_review_dossiers.jsonl.gz"

FILES = {
    "src/core/advancemapparser.cpp": {
        "blob": "04348e96abd21579f202ed67d7f927ab626738aa",
        "sha256": "be8c875a173fc04848ed9b221bc248521a316cc0796e209607f45578c4bd3413",
        "row": "9adc90a245ed763594113879443b257095e0c3002d481c19da9bfc94c6b27e31",
        "role": "Focal full-file scope: legacy .map, .bvd, and palette byte decoding; validation, error flags, dimensions, tileset mapping, metatile conversion, and returned ownership.",
        "coverage": "focal",
    },
    "include/core/advancemapparser.h": {
        "blob": "c3cb76cb7c0e6e58d01743f6c06774fa0a635411",
        "sha256": "9f9d45a8bc67ac56d90e90b6d64eeeaba70644039c52781c4a2683cd72da3e45",
        "row": "626532a3ee3d3a94da2769eff5d40bf45034673b2d7e45db33434f335d9d952a",
        "role": "Focal complete public API declarations for all three AdvanceMap import methods and error/output contracts.",
        "coverage": "focal",
    },
    "src/mainwindow.cpp": {
        "blob": "08ce1a7a599ef825967717b69626984cdc6d772b",
        "sha256": "b1b7d6738bfa9a3c574ddfcdd774187783fa81cfc86889e1aa4b80cad93525d1",
        "row": "fd88d9c7b68d181efc93e9f746306ad8e167dd3a0eeb16410dd6d6cfd412d1f8",
        "role": "Caller context only: MainWindow imports a parsed .map into the current editor; no full-file semantic review claimed.",
        "coverage": "context",
    },
    "src/ui/tileseteditor.cpp": {
        "blob": "723a2afdeb89c1752e9811a07715462c2279c645",
        "sha256": "a85e7827754d3f08cec5ebe90aa7a737958524ac379d563adfd269d1b7557ced",
        "row": "940f1b1723b84449dbc3f20648e057643c96d9be19a08e9fa210746193a35ee7",
        "role": "Caller context only: Tileset editor owns and consumes imported Metatile pointers; distinct from the existing Tileset writer witness.",
        "coverage": "context",
    },
    "src/core/paletteutil.cpp": {
        "blob": "76a3d0c4551972f0349913ed5c7e90510f5cde38",
        "sha256": "7102959c495e9bb6429cb1efef607392762d2f3d167fcc1d1016cfaa8067ca7c",
        "row": "f57b9288a100a782a5804eb9291030da5b9da5f7249dff98d9466c4f74394366",
        "role": "Caller context only: routes non-JASC palette files to AdvanceMapParser; palette utility behavior is not re-reviewed.",
        "coverage": "context",
    },
    "include/core/paletteutil.h": {
        "blob": "34e9ae3ff80c86a51f09d575968de3c6e4577073",
        "sha256": "a00910820306f5b4d718b8353abcccc3ded192ec23add08823c1c4b0c85bb545",
        "row": "54171feeb462e142b45e1621ff71b06abff55c299f5952395e804e2ccd506fcc",
        "role": "Caller declaration context only; no complete PaletteUtil semantic scope claimed.",
        "coverage": "context",
    },
    "include/project.h": {
        "blob": "50d3307cf618f4cd5e9603bdbe3e0ea8d9b5e354",
        "sha256": "7cc2225207fe2ddbbc463b91f24997f651141d84f7a79f3d8897daf6071c9b51",
        "row": "0a5103fa34ee62748f39cbcbd0d50c3bb9ccabc824cf9813ca53bd5118cc69eb",
        "role": "Dependency context: ordered tileset labels, allowed label sets, default-label declarations, and metatile-count limits.",
        "coverage": "context",
    },
    "src/project.cpp": {
        "blob": "d43b0949303433111d4478ad76117c2b3445dd13",
        "sha256": "225b20f5305ae428eda2e7fda28dcc405cdeae041ce8e1176b3a7d7bd548d93b",
        "row": "b6b90abf56f02452537a9b096fa191ead9ee7360dd19d72c6f5486834bed02d7",
        "role": "Dependency context: implements configured/fallback primary and secondary tileset labels; prior writer/map work is not repeated.",
        "coverage": "context",
    },
    "include/config.h": {
        "blob": "539c5f3d416d22d847020cd324726b33725e5437",
        "sha256": "2a7a2621675e70b007fbc71f004a3cb0c44914f0a9c366ab974570ca8e2053ad",
        "row": "0a3502a018360a2eb9fadb4890fd861c5de750e181daa56eca2083dd6ad50bde",
        "role": "Dependency context: game-version and global triple-layer configuration declarations.",
        "coverage": "context",
    },
    "src/config.cpp": {
        "blob": "9264f99bb18e0a725ef023f514c00df529d1d28d",
        "sha256": "fe8b6e3e4780ae8a63321d157d6fea43f438af3ab7a7fc697a9f9a2b43d4419d",
        "row": "0107235fca6f03579e911aa555b30492c7dfa39a854fbcbced2989476dce2953",
        "role": "Dependency context: project/game configuration initializes version-dependent metatile attribute and triple-layer settings.",
        "coverage": "context",
    },
    "include/core/metatile.h": {
        "blob": "eba4afedbdd0ae682dca472d941a966df31285d3",
        "sha256": "aff69ca0f21364eb5ec13d990903f24fd2b5f296a41f9dbd2a3a44247a7c104f",
        "row": "b8c09969c5c86fe467551ec4542bdd7d0939bde3b78324304ad852995e2259c7",
        "role": "Dependency context: Metatile representation and versioned attribute API used by .bvd import.",
        "coverage": "context",
    },
    "src/core/metatile.cpp": {
        "blob": "00fff2ba4bd1f3d85c7be3356fa6bf0bb0d8fc70",
        "sha256": "998902fda64648a3ae7ad5b96305b658ac1adbde0cb5218cfc67fcf27960f9c7",
        "row": "fc7bd3aeabcda751a0529abaa51c2f381e75a5c3edc61727973cf4178dd2bbaf",
        "role": "Dependency context: vanilla RSE/FRLG attribute widths and decoding. The native parser harness stubs this transformation.",
        "coverage": "context",
    },
    "include/core/maplayout.h": {
        "blob": "3095574b79604307ee31cc3fa0d111bd2cef242a",
        "sha256": "0e92db0736800b5669fba82b972bec7d00fcfc1f8f36bfcb11f7d7ed38f390ea",
        "row": "e518511da45c05420a73bdca128fae807e881e74e319722436779cf3c2c02945",
        "role": "Dependency context: imported layout fields, Blockdata, and downstream save/model APIs.",
        "coverage": "context",
    },
    "include/core/blockdata.h": {
        "blob": "a1e45b63783fa2aecceee6fadbb33f1e1935b6b8",
        "sha256": "e3b1898ffff20b15cc33114c6c423d405c75de0213c5342dfced11db729041db",
        "row": "a48dd6ea66e58e3b0378d31307aeb44a45656b183940673ae69b16635260b769",
        "role": "Dependency context: compact imported block data container and access semantics.",
        "coverage": "context",
    },
    "include/core/tile.h": {
        "blob": "11fd6a99cfff18dc0d06185b3342a7b107acebb9",
        "sha256": "90c4fb23620e7dd42b6ed108ace7d1bb392e287d837fa7a87740a1f37ecb3af7",
        "row": "8d597f012d434892d49f3ed7ddddafa60507ebce15aae123b6c7119c4d7d24c9",
        "role": "Dependency context: raw tile representation constructed from .bvd words.",
        "coverage": "context",
    },
    "porymap.pro": {
        "blob": "53d8055ecfe5d88afb6f183b82d4a3472727ad4f",
        "sha256": "cff608e64a2d610ea029d199c2be3b50b7941437b62c80fa3eaffdba70de2996",
        "row": "93059d533a8cc5a5cc0fbe774b64bd8bf83ff107344a870cace53d6d96cf35e2",
        "role": "Build context: compiles the original parser and declares Qt Core/GUI application modules.",
        "coverage": "context",
    },
    "LICENSE.md": {
        "blob": "65c5ca88a67c30becee01c5a8816d964b03862f9",
        "sha256": "da7eabb7bafdf7d3ae5e9f223aa5bdc1eece45ac569dc21b3b037520b4464768",
        "row": "a620cf8ec560f8bf6f54e9d96403ec1cb204f3ddad7fef812ce7893059396986",
        "role": "License context only: pinned Porymap root LGPL text is not a distribution-compliance conclusion.",
        "coverage": "context",
    },
}

ANCHORS = {
    "src/core/advancemapparser.cpp": (
        b"Layout *AdvanceMapParser::parseLayout",
        b"if (in.length() < 20 || in.length() % 2 != 0)",
        b"int numMetatiles = mapWidth * mapHeight;",
        b"QList<Metatile*> AdvanceMapParser::parseMetatiles",
        b"Metatile::getDefaultAttributesSize(version)",
        b"AdvanceMapParser::parsePalette",
        b"in.length() % 4 != 0",
        b"palette.append(qRgb(red, green, blue));",
    ),
    "include/core/advancemapparser.h": (
        b"Layout *parseLayout(const QString &filepath, bool *error, const Project *project);",
        b"QList<Metatile*> parseMetatiles(const QString &filepath, bool *error, bool primaryTileset);",
        b"QList<QRgb> parsePalette(const QString &filepath, bool *error);",
    ),
    "src/mainwindow.cpp": (
        b"AdvanceMapParser::parseLayout(filepath, &error, editor->project)",
    ),
    "src/ui/tileseteditor.cpp": (
        b"AdvanceMapParser::parseMetatiles(filepath, &error, primary)",
    ),
    "src/core/paletteutil.cpp": (
        b"AdvanceMapParser::parsePalette(filepath, error)",
    ),
    "src/project.cpp": (
        b"QString Project::getDefaultPrimaryTilesetLabel() const",
        b"QString Project::getDefaultSecondaryTilesetLabel() const",
    ),
    "src/core/metatile.cpp": (
        b"Metatile::setAttributes(uint32_t data, BaseGameVersion version)",
        b"return (version == BaseGameVersion::pokefirered) ? 4 : 2;",
    ),
    "porymap.pro": (
        b"src/core/advancemapparser.cpp",
        b"include/core/advancemapparser.h",
        b"QT       += core gui",
    ),
    "LICENSE.md": (
        b"GNU LESSER GENERAL PUBLIC LICENSE",
    ),
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def read_candidate_rows(workpack: pathlib.Path) -> dict[str, tuple[dict, str]]:
    archive_bytes = workpack.read_bytes()
    require(sha256(archive_bytes) == WORKPACK_SHA256, "candidate workpack ZIP hash mismatch")
    with zipfile.ZipFile(workpack) as archive:
        compressed = archive.read(CANDIDATE_MEMBER)
    require(sha256(compressed) == CANDIDATE_ARCHIVE_SHA256,
            "candidate inventory gzip hash mismatch")
    rows = {}
    for raw in gzip.decompress(compressed).splitlines():
        row = json.loads(raw)
        provenance = row.get("provenance", {})
        path = provenance.get("path")
        if provenance.get("repository") != "huderlem/porymap" or path not in FILES:
            continue
        require(path not in rows, "duplicate pinned candidate row: " + path)
        rows[path] = (row, sha256(raw))
    require(set(rows) == set(FILES), "candidate inventory rows incomplete")
    for path, (row, row_hash) in rows.items():
        expected = FILES[path]
        provenance = row.get("provenance", {})
        review = row.get("review", {})
        require(provenance.get("pinned_revision") == PIN, "candidate pin mismatch: " + path)
        require(provenance.get("git_blob_sha") == expected["blob"],
                "candidate blob mismatch: " + path)
        require(provenance.get("source_content_sha256") in (None, expected["sha256"]),
                "candidate source hash mismatch: " + path)
        require(row_hash == expected["row"], "candidate row hash mismatch: " + path)
        require(review.get("semantic_signoff") is False and review.get("reviewer") is None,
                "candidate row asserts semantic review: " + path)
        require(review.get("status") in (
            "CANDIDATE_ONLY_SOURCE_HASH_VERIFIED",
            "INVENTORIED_NOT_SEMANTICALLY_REVIEWED",
        ), "unexpected candidate status: " + path)
    return rows


def verify_sources(upstream: pathlib.Path) -> dict[str, bytes]:
    require((upstream / ".git").exists(), "expected pinned Porymap checkout")
    revision = subprocess.check_output(
        ["git", "-C", str(upstream), "rev-parse", "HEAD"], text=True
    ).strip()
    require(revision == PIN, "wrong Porymap revision")
    sources = {}
    for path, expected in FILES.items():
        raw = (upstream / path).read_bytes()
        require(git_blob(raw) == expected["blob"], "Git blob mismatch: " + path)
        require(sha256(raw) == expected["sha256"], "full-byte SHA-256 mismatch: " + path)
        sources[path] = raw
    for path, anchors in ANCHORS.items():
        raw = sources[path]
        for anchor in anchors:
            require(anchor in raw, "source contract anchor missing: " + path + ": " + repr(anchor))
    return sources


def reject_source_mutation(path: str, original: bytes) -> None:
    changed = original + b"\nXGBA_PHASE1_MUTATION\n"
    try:
        require(
            git_blob(changed) == FILES[path]["blob"] and
            sha256(changed) == FILES[path]["sha256"],
            "mutated source unexpectedly matched",
        )
    except ValueError:
        return
    raise AssertionError("source mutation accepted: " + path)


def validate_evidence(evidence: dict, expected_harness_sha256: str) -> None:
    require(evidence["source_pin"] == PIN, "evidence source pin mismatch")
    require(evidence["source_files"] == {
        path: {
            "git_blob_sha1": item["blob"],
            "full_source_sha256": item["sha256"],
            "candidate_row_sha256": item["row"],
            "role": item["role"],
            "coverage": item["coverage"],
            "reviewer": "Copilot Coding Agent",
            "independent_review_receipt": None,
            "disposition": "NEEDS_EVIDENCE",
        }
        for path, item in FILES.items()
    }, "evidence per-file records mismatch")
    require(evidence["candidate_inventory"]["archive_sha256"] == CANDIDATE_ARCHIVE_SHA256,
            "evidence candidate archive mismatch")
    require(evidence["candidate_inventory"]["row_sha256"] == {
        path: item["row"] for path, item in FILES.items()
    }, "evidence candidate row identities mismatch")
    require(evidence["candidate_inventory"]["is_semantic_dossier"] is False,
            "candidate inventory presented as semantic dossier")
    require(evidence["original_semantic_dossier"]["available"] is False,
            "missing original semantic dossier not preserved")
    require(evidence["native"]["compiler"] == "g++" and
            evidence["native"]["qt"] == "Qt6Core+Qt6Gui" and
            evidence["native"]["original_cpp"] == FILES["src/core/advancemapparser.cpp"]["sha256"],
            "native compilation identity mismatch")
    require(evidence["native"]["harness_sha256"] == expected_harness_sha256,
            "native harness hash mismatch")
    require(evidence["native"]["normal_returncode"] == 0 and
            "ADVANCEMAP_IMPORT_NATIVE positive_layout=1 positive_rse=1" in
            evidence["native"]["normal_stdout"],
            "native positive/negative controls failed")
    overflow = evidence["native"]["overflow"]
    require(overflow["returncode"] != 0 and
            "signed integer overflow" in overflow["stderr"],
            "expected original-source dimension overflow was not observed")
    require(evidence["disposition"] == "NEEDS_EVIDENCE" and
            evidence["phase1_gate"] == "FAIL_INCOMPLETE" and
            evidence["independent_approvals"] == 0,
            "non-approving disposition invariant changed")
    require(evidence["source_mutation_rejections"] == len(FILES) and
            evidence["source_contract_mutation_rejections"] ==
            sum(len(anchors) for anchors in ANCHORS.values()),
            "source mutation controls incomplete")


def reject_evidence_mutation(evidence: dict, expected_harness_sha256: str, mutate) -> None:
    changed = copy.deepcopy(evidence)
    mutate(changed)
    try:
        validate_evidence(changed, expected_harness_sha256)
    except (ValueError, KeyError, TypeError):
        return
    raise AssertionError("evidence mutation accepted")


def compile_and_run(upstream: pathlib.Path, harness: pathlib.Path, output: pathlib.Path) -> dict:
    flags = shlex.split(
        subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "Qt6Core", "Qt6Gui"], text=True
        )
    )
    with tempfile.TemporaryDirectory(prefix="phase1-advancemap-") as temp:
        temp_path = pathlib.Path(temp)
        stubs = temp_path / "stubs"
        stubs.mkdir()
        (stubs / "project.h").write_text(
            """#pragma once
#include <QList>
#include <QSet>
#include <QString>
enum class BaseGameVersion { pokeemerald, pokefirered };
struct ProjectConfigStub { bool tripleLayerMetatilesEnabled = false; };
extern ProjectConfigStub projectConfig;
class Project {
public:
    QList<QString> tilesetLabelsOrdered{QStringLiteral("PRIMARY_A"), QStringLiteral("SECONDARY_A")};
    QSet<QString> primaryTilesetLabels{QStringLiteral("PRIMARY_A"), QStringLiteral("PRIMARY_DEFAULT")};
    QSet<QString> secondaryTilesetLabels{QStringLiteral("SECONDARY_A"), QStringLiteral("SECONDARY_DEFAULT")};
    static int getNumMetatilesPrimary() { return 2; }
    static int getNumMetatilesSecondary() { return 2; }
    QString getDefaultPrimaryTilesetLabel() const { return QStringLiteral("PRIMARY_DEFAULT"); }
    QString getDefaultSecondaryTilesetLabel() const { return QStringLiteral("SECONDARY_DEFAULT"); }
};
""",
            encoding="utf-8",
        )
        (stubs / "log.h").write_text(
            "#pragma once\n#include <QString>\ninline void logError(const QString &) {}\n",
            encoding="utf-8",
        )
        (stubs / "metatile.h").write_text(
            """#pragma once
#include <QList>
#include <QtGlobal>
#include <cstdint>
#include "project.h"
struct Tile {
    uint16_t value = 0;
    Tile() = default;
    explicit Tile(uint16_t raw) : value(raw) {}
};
class Metatile {
public:
    QList<Tile> tiles;
    uint32_t attributes = 0;
    BaseGameVersion version = BaseGameVersion::pokeemerald;
    static int getDefaultAttributesSize(BaseGameVersion game) {
        return game == BaseGameVersion::pokefirered ? 4 : 2;
    }
    void setAttributes(uint32_t raw, BaseGameVersion game) {
        attributes = raw;
        version = game;
    }
};
""",
            encoding="utf-8",
        )
        (stubs / "maplayout.h").write_text(
            """#pragma once
#include <QFile>
#include <QList>
#include <QString>
#include "metatile.h"
using Blockdata = QList<uint16_t>;
constexpr int DEFAULT_BORDER_WIDTH = 2;
constexpr int DEFAULT_BORDER_HEIGHT = 2;
class Layout {
public:
    int width = 0, height = 0, border_width = 0, border_height = 0;
    QString tileset_primary_label, tileset_secondary_label;
    Blockdata blockdata, border;
};
""",
            encoding="utf-8",
        )
        harness_binary = temp_path / "advancemap-import-native"
        command = [
            "g++", "-std=c++17", "-O0", "-g", "-fPIC",
            "-fsanitize=undefined,signed-integer-overflow", "-fno-sanitize-recover=all",
            "-I" + str(stubs),
            "-I" + str(upstream / "include/core"),
            str(harness),
            str(upstream / "src/core/advancemapparser.cpp"),
            "-o", str(harness_binary),
            *flags,
        ]
        subprocess.run(command, check=True, timeout=120)
        normal = subprocess.run(
            [str(harness_binary)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        overflow = subprocess.run(
            [str(harness_binary), "--overflow"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        require(normal.returncode == 0, "native AdvanceMap controls failed: " + normal.stderr)
        require(overflow.returncode != 0, "overflow fixture did not trigger UBSan")
        require("signed integer overflow" in overflow.stderr,
                "UBSan did not identify expected signed dimension overflow")
        output.parent.mkdir(parents=True, exist_ok=True)
        return {
            "compiler": "g++",
            "qt": "Qt6Core+Qt6Gui",
            "sanitizer": "undefined,signed-integer-overflow",
            "original_cpp": FILES["src/core/advancemapparser.cpp"]["sha256"],
            "normal_returncode": normal.returncode,
            "normal_stdout": normal.stdout,
            "normal_stderr": normal.stderr,
            "overflow": {
                "returncode": overflow.returncode,
                "stdout": overflow.stdout,
                "stderr": overflow.stderr,
            },
            "harness_sha256": sha256(harness.read_bytes()),
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--porymap", required=True, type=pathlib.Path)
    parser.add_argument("--output", required=True, type=pathlib.Path)
    parser.add_argument("--workpack", type=pathlib.Path, default=ROOT / "imports/XGBA_Phase1_v1.5_Complete_Workpack.zip")
    parser.add_argument("--harness", type=pathlib.Path, default=ROOT / "tests/phase1_porymap_advancemap_import.cpp")
    args = parser.parse_args()

    rows = read_candidate_rows(args.workpack)
    sources = verify_sources(args.porymap)
    source_negatives = 0
    for path, raw in sources.items():
        reject_source_mutation(path, raw)
        source_negatives += 1
    contract_negatives = 0
    for path, anchors in ANCHORS.items():
        for anchor in anchors:
            changed = sources[path].replace(anchor, b"XGBA_PHASE1_SOURCE_MUTATION", 1)
            require(changed != sources[path], "source anchor mutation no-op")
            try:
                require(anchor in changed, "mutated source retained required anchor")
            except ValueError:
                contract_negatives += 1

    native = compile_and_run(args.porymap, args.harness, args.output)
    evidence = {
        "schema": "phase1-porymap-advancemap-import-v1",
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
            "note": "The pinned workpack supplies only automated candidate-inventory rows, not original independent semantic dossiers or review receipts.",
        },
        "source_files": {
            path: {
                "git_blob_sha1": item["blob"],
                "full_source_sha256": item["sha256"],
                "candidate_row_sha256": item["row"],
                "role": item["role"],
                "coverage": item["coverage"],
                "reviewer": "Copilot Coding Agent",
                "independent_review_receipt": None,
                "disposition": "NEEDS_EVIDENCE",
            }
            for path, item in FILES.items()
        },
        "native": native,
        "source_mutation_rejections": source_negatives,
        "source_contract_mutation_rejections": contract_negatives,
        "limits": [
            "Original parser code is compiled unchanged against Qt6Core and Qt6Gui, with test-only stubs for Project, Layout, Tile, Metatile, and logging.",
            "The harness does not execute the full GUI, real Project/Metatile attribute conversion, import ownership transitions, or subsequent game build/runtime.",
            "The detected signed overflow is a bounded malformed-input observation, not a product fix or an assertion about all inputs.",
            "Candidate inventory hashes establish source identity only; no original semantic dossier, independent receipt, legal conclusion, or approval is present.",
        ],
    }
    harness_sha256 = sha256(args.harness.read_bytes())
    validate_evidence(evidence, harness_sha256)

    evidence_negatives = 0
    for mutate in (
        lambda value: value.__setitem__("source_pin", "0" * 40),
        lambda value: value["candidate_inventory"].__setitem__("archive_sha256", "0" * 64),
        lambda value: value["candidate_inventory"]["row_sha256"].__setitem__(
            "src/core/advancemapparser.cpp", "0" * 64
        ),
        lambda value: value["candidate_inventory"].__setitem__("is_semantic_dossier", True),
        lambda value: value["original_semantic_dossier"].__setitem__("available", True),
        lambda value: value["source_files"]["src/core/advancemapparser.cpp"].__setitem__(
            "independent_review_receipt", {"decision": "APPROVED"}
        ),
        lambda value: value["source_files"]["src/core/advancemapparser.cpp"].__setitem__(
            "disposition", "APPROVED"
        ),
        lambda value: value["native"].__setitem__("harness_sha256", "0" * 64),
        lambda value: value["native"].__setitem__("compiler", "fake"),
        lambda value: value["native"].__setitem__("normal_returncode", 1),
        lambda value: value["native"].__setitem__("normal_stdout", ""),
        lambda value: value["native"]["overflow"].__setitem__("stderr", ""),
        lambda value: value.__setitem__("disposition", "APPROVED"),
        lambda value: value.__setitem__("phase1_gate", "PASS"),
        lambda value: value.__setitem__("independent_approvals", 1),
    ):
        reject_evidence_mutation(evidence, harness_sha256, mutate)
        evidence_negatives += 1

    evidence["evidence_mutation_rejections"] = evidence_negatives
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "ADVANCEMAP_IMPORT_EVIDENCE_PASS "
        f"source_files={len(FILES)} focal_files=2 native_scenarios=10 "
        f"source_mutations={source_negatives} contract_mutations={contract_negatives} "
        f"evidence_mutations={evidence_negatives} "
        "observed_signed_overflow=1 approvals=0 gate=FAIL_INCOMPLETE"
    )


if __name__ == "__main__":
    main()
