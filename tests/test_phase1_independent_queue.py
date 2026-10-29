"""Fail-closed queue mutation controls; no independent semantic signoff."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from tools.phase1_independent_queue_validate import validate

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "gate": "semantic-snapshots/current/phase1_mapping_gate.json",
    "queue": "semantic-snapshots/independent-reviews/queue.json",
    "curated": "semantic-snapshots/curated/p0_semantic_review_candidates_2026-10-26.json",
    "intake": "semantic-snapshots/independent-reviews/curated-p0-intake-20261029.json",
}


class QueueBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {key: json.loads((ROOT / path).read_text()) for key, path in FILES.items()}

    def check(self, mutated):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for key, path in FILES.items():
                dest = root / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(json.dumps(mutated[key]))
            return validate(root)

    def test_positive(self):
        self.assertEqual(self.check(copy.deepcopy(self.original)), [])

    def test_seventeen_fail_closed_mutations(self):
        edits = [
            ("wrong total", lambda d: d["queue"].update(total_target=14833)),
            ("false total approval", lambda d: d["queue"].update(total_approved=1)),
            ("false group approval", lambda d: d["queue"]["priority"][0].update(approved=1)),
            ("wrong P0 group", lambda d: d["queue"]["priority"][1].update(target=310)),
            ("wrong group order", lambda d: d["queue"]["priority"].reverse()),
            ("false gate success", lambda d: d["gate"].update(decision="PASS")),
            ("false gate approval", lambda d: d["gate"].update(approved_semantic_dispositions=1)),
            ("wrong inventory", lambda d: d["gate"].update(verified_source_manifest_entries=14833)),
            ("false curated approval", lambda d: d["curated"].update(independent_review_approvals=1)),
            ("missing curated file", lambda d: d["curated"]["candidate_files"].pop()),
            ("duplicate source identity", lambda d: d["curated"]["candidate_files"].__setitem__(1, copy.deepcopy(d["curated"]["candidate_files"][0]))),
            ("wrong pinned blob", lambda d: d["curated"]["candidate_files"][0].update(expected_git_blob_sha1="unverified")),
            ("invented reviewer", lambda d: d["intake"]["records"][0].update(independent_reviewer="imaginary")),
            ("invented approval", lambda d: d["intake"]["records"][0].update(independent_review_verdict="APPROVED")),
            ("changed intake SHA", lambda d: d["intake"]["records"][0]["identity"].update(git_blob_sha1="0"*40)),
            ("missing intake record", lambda d: d["intake"]["records"].pop()),
            ("unverified source blob", lambda d: d["intake"]["records"][1].update(source_hash_validation="REGISTRY_PIN_ONLY")),
        ]
        for name, edit in edits:
            with self.subTest(name=name):
                doc = copy.deepcopy(self.original)
                edit(doc)
                self.assertTrue(self.check(doc), "mutation incorrectly accepted: " + name)


if __name__ == "__main__":
    unittest.main()
