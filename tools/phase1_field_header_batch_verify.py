#!/usr/bin/env python3
"""Fail-closed exact-blob and whole-header line-inventory verifier.

No semantic approvals, reviewer signatures or gate counts are written.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

PIN = "ce6406d8c2eaf46d543c8a2606de0c3cb1951982"
MANIFEST = Path("docs/phase1-disposition-candidates/batch-20261027-field-interfaces.json")
DOCS = MANIFEST.parent
MARKERS = ("## Exhaustive non-comment source-line inventory", "## Exhaustive nonblank source inventory")


def inventory(source: str) -> str:
    return "\n".join(
        f"- L{i}: `{line.strip().replace(chr(96), chr(39))}`"
        for i, line in enumerate(source.splitlines(), 1)
        if line.strip() and not line.strip().startswith(("//", "/*", "*"))
    )


def extracted_inventory(document: str) -> str:
    for marker in MARKERS:
        needle = marker + "\n\n"
        if document.count(needle) == 1:
            return document.split(needle, 1)[1].split("\n## ", 1)[0].strip()
    raise ValueError("Missing or ambiguous exhaustive source inventory")


def check_inventory(source: str, document: str) -> None:
    if extracted_inventory(document) != inventory(source):
        raise ValueError("Pinned source and line-anchored candidate inventory disagree")


def check_entries(entries: list) -> None:
    if len(entries) != 25:
        raise ValueError("Expected exactly 25 distinct field-header candidates")
    seen_paths, seen_docs = set(), set()
    for e in entries:
        if set(e) != {"source_repository", "source_commit", "path", "git_blob_sha1", "document"}:
            raise ValueError("Invalid manifest keys")
        if e["source_repository"] != "pret/pokefirered" or e["source_commit"] != PIN:
            raise ValueError("Unpinned or wrong upstream source")
        if not re.fullmatch(r"include/[A-Za-z0-9_]+\.h", e["path"]):
            raise ValueError("Invalid source path")
        if not re.fullmatch(r"00(?:[5-7][0-9]|8[0-3])-firered-[a-z0-9-]+\.md", e["document"]):
            raise ValueError("Invalid candidate document name")
        if not re.fullmatch(r"[0-9a-f]{40}", e["git_blob_sha1"]):
            raise ValueError("Invalid Git blob SHA")
        if e["path"] in seen_paths or e["document"] in seen_docs:
            raise ValueError("Duplicate pinned source identity or candidate document")
        seen_paths.add(e["path"])
        seen_docs.add(e["document"])


def self_test() -> None:
    src = "#ifndef X\n#define X\nvoid f(void);\n#endif\n"
    doc = "## Exhaustive non-comment source-line inventory\n\n" + inventory(src) + "\n\n## Dependencies"
    check_inventory(src, doc)
    negatives = [
        lambda: check_inventory(src.replace("f(void)", "g(void)"), doc),
        lambda: check_inventory(src, doc.replace("L3", "L4")),
        lambda: extracted_inventory(doc.replace("## Exhaustive non-comment source-line inventory", "## Other")),
    ]
    for bad in negatives:
        try:
            bad()
        except ValueError:
            continue
        raise AssertionError("A corrupted source inventory unexpectedly passed")
    entry = {"source_repository": "pret/pokefirered", "source_commit": PIN,
             "path": "include/x.h", "git_blob_sha1": "0" * 40, "document": "0059-firered-x.md"}
    try:
        check_entries([entry] * 25)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate/invalid manifest unexpectedly passed")
    print("Field-header verifier negative controls PASS (4/4)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if args.source_root is None:
        parser.error("--source-root is required outside self-test")
    root = args.source_root.resolve()
    rev = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if rev != PIN:
        raise ValueError(f"Source checkout mismatch: {rev} != {PIN}")
    entries = json.loads(MANIFEST.read_text(encoding="utf-8"))
    check_entries(entries)
    register = (DOCS / "README.md").read_text(encoding="utf-8")
    for e in entries:
        p = root / e["path"]
        sha = subprocess.check_output(["git", "-C", str(root), "hash-object", str(p)], text=True).strip()
        if sha != e["git_blob_sha1"]:
            raise ValueError(f"Git blob mismatch: {e['path']}: {sha}")
        doc = (DOCS / e["document"]).read_text(encoding="utf-8")
        if PIN not in doc or e["git_blob_sha1"] not in doc:
            raise ValueError(f"Missing source pin in {e['document']}")
        check_inventory(p.read_text(encoding="utf-8"), doc)
        identity = f"| `pret/pokefirered:{e['path']}` |"
        if register.count(identity) != 1 or register.count(f"({e['document']})") != 1:
            raise ValueError(f"Missing or duplicated register identity: {e['path']}")
    print(f"FIELD_HEADER_PINNED_SOURCE_PASS count={len(entries)} git_blobs=25 line_inventories=25")
    print("PHASE1_GATE=FAIL_INCOMPLETE independent_approvals_not_granted")


if __name__ == "__main__":
    main()
