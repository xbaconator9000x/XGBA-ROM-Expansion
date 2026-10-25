#!/usr/bin/env python3
"""Verify detached Ed25519 reviewer attestations for Phase 1 file dispositions.

The current trust registry is deliberately empty. A reviewer name in a CSV,
a source hash, or an automated dossier is NOT independent review evidence.
No trusted reviewer keys are provisioned by this script.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

TRUST_FILE = Path("semantic-snapshots/review-trust/trusted_reviewers.json")
TRUST_SCHEMA = "xgba.phase1.trusted_reviewers.v1"
STATEMENT_SCHEMA = "xgba.phase1.independent_file_review.v1"
SIGNED_FIELDS = (
    "repo", "path", "git_blob_sha", "evidence_sha256", "status",
    "semantic_rationale", "contract_ids", "reviewer",
)
OWNER = "xbaconator9000x"
LOGIN = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def statement_bytes(disposition):
    """Canonical, versioned and scope-bound bytes signed by the reviewer."""
    return (json.dumps(
        {"schema": STATEMENT_SCHEMA,
         "disposition": {field: disposition.get(field, "") for field in SIGNED_FIELDS}},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ) + "\n").encode("utf-8")


def load_trust(path=TRUST_FILE):
    """Fail closed on a missing/malformed registry or a changed public key."""
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if doc.get("schema") != TRUST_SCHEMA or not isinstance(doc.get("reviewers"), list):
        raise ValueError("Invalid independent reviewer trust registry")
    trusted = {}
    for entry in doc["reviewers"]:
        login = entry.get("github_login")
        relpath = entry.get("public_key_path")
        digest = entry.get("public_key_sha256")
        if (not isinstance(login, str) or not LOGIN.fullmatch(login)
                or login.casefold() == OWNER.casefold() or login.casefold() in trusted):
            raise ValueError("Invalid, duplicate, or repository-owner reviewer identity")
        if not isinstance(relpath, str):
            raise ValueError("Invalid reviewer key path")
        keypath = Path(relpath)
        if (keypath.is_absolute() or ".." in keypath.parts
                or keypath.parts[:3] != ("semantic-snapshots", "review-trust", "keys")
                or keypath.suffix != ".pem"):
            raise ValueError("Reviewer key must be a pinned PEM under review-trust/keys")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError("Invalid reviewer public key SHA-256")
        if hashlib.sha256(keypath.read_bytes()).hexdigest() != digest:
            raise ValueError("Reviewer public key does not match trust manifest")
        trusted[login.casefold()] = keypath
    return trusted


def verify_attestation(disposition, trusted):
    """Return (verified, reason); never infer approval from claimed reviewer text."""
    login = disposition.get("reviewer", "")
    if not isinstance(login, str) or not LOGIN.fullmatch(login):
        return False, "Invalid independent reviewer login"
    if login.casefold() == OWNER.casefold():
        return False, "Repository owner cannot independently review their own work"
    keypath = trusted.get(login.casefold())
    if keypath is None:
        return False, "Reviewer has no independently provisioned trusted public key"
    encoded = disposition.get("review_signature_b64", "")
    if not isinstance(encoded, str):
        return False, "Missing detached reviewer signature"
    try:
        signature = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return False, "Invalid detached reviewer signature encoding"
    if len(signature) != 64:
        return False, "Invalid Ed25519 signature length"
    with tempfile.TemporaryDirectory(prefix="xgba-review-") as tmp:
        statement = Path(tmp) / "statement.json"
        sigfile = Path(tmp) / "signature.bin"
        statement.write_bytes(statement_bytes(disposition))
        sigfile.write_bytes(signature)
        try:
            result = subprocess.run(
                ["openssl", "pkeyutl", "-verify", "-rawin", "-pubin",
                 "-inkey", str(keypath), "-in", str(statement),
                 "-sigfile", str(sigfile)],
                capture_output=True, timeout=15, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False, "Independent signature verifier unavailable"
    if result.returncode != 0:
        return False, "Reviewer signature does not cover this exact disposition"
    return True, "Verified detached reviewer signature against provisioned key"


def self_test():
    """Isolated synthetic crypto fixtures, never real semantic review approvals."""
    with tempfile.TemporaryDirectory(prefix="xgba-review-fixture-") as tmp:
        tmp = Path(tmp)
        private = tmp / "fixture-private.pem"
        public = tmp / "fixture-public.pem"
        subprocess.run(["openssl", "genpkey", "-algorithm", "Ed25519",
                        "-out", str(private)], check=True, capture_output=True)
        subprocess.run(["openssl", "pkey", "-in", str(private),
                        "-pubout", "-out", str(public)],
                       check=True, capture_output=True)
        row = {
            "repo": "pret/pokefirered", "path": "src/script.c",
            "git_blob_sha": "a" * 40, "evidence_sha256": "b" * 64,
            "status": "mapped_dependencies",
            "semantic_rationale": "Synthetic independent review fixture, not an approval.",
            "contract_ids": "FIXTURE_ONLY", "reviewer": "fixture-reviewer",
        }
        statement = tmp / "statement.json"
        signature = tmp / "signature.bin"
        statement.write_bytes(statement_bytes(row))
        subprocess.run(["openssl", "pkeyutl", "-sign", "-rawin",
                        "-inkey", str(private), "-in", str(statement),
                        "-out", str(signature)], check=True, capture_output=True)
        row["review_signature_b64"] = base64.b64encode(signature.read_bytes()).decode()
        trusted = {"fixture-reviewer": public}
        assert verify_attestation(row, trusted)[0]
        assert not verify_attestation(row, {})[0]
        for field in SIGNED_FIELDS:
            tampered = dict(row)
            tampered[field] = str(row[field]) + "_changed"
            assert not verify_attestation(tampered, trusted)[0], field
        tampered = dict(row, review_signature_b64="invalid")
        assert not verify_attestation(tampered, trusted)[0]
        tampered = dict(row, reviewer=OWNER)
        assert not verify_attestation(tampered, trusted)[0]
    print("Phase 1 detached review attestation: signed fixture and 11 fail-closed controls PASS")


if __name__ == "__main__":
    self_test()
