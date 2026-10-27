"""Self-contained fail-closed artifact recovery controls (synthetic records only)."""
import copy
import hashlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from phase1_recover_triage_artifacts import PINS, verify


def digest(data):
    return hashlib.sha256(data).hexdigest()


def make_fixture(root):
    manifest = {
        'schema': 'xgba-phase1-artifact-recovery-v1',
        'repo': 'xbaconator9000x/XGBA-ROM-Expansion',
        'source_workflow_head': 'a' * 40,
        'phase1_gate': 'FAIL_INCOMPLETE', 'independent_approvals': 0,
        'analyst_prepared_baseline': 113, 'prior_committed_total': 3000,
        'start': 3000, 'end_exclusive': 4000, 'shards': [],
    }
    repo = next(iter(PINS))
    for i in range(4):
        offset = 3000 + 250 * i
        filename = f'batch-{offset:06d}-{offset + 249:06d}.json'
        records = []
        for j in range(250):
            path = f'synthetic/path/{offset+j}.c'
            records.append({
                'identity': {'repository': repo, 'pinned_commit': PINS[repo],
                             'path': path, 'git_blob_sha1': 'b' * 40},
                'evidence': {'source_blob_reverified_this_run': True,
                             'snapshot_provenance_verified': True,
                             'dossier_sha256': 'c' * 64},
                'whole_file_structure': {'whole_blob_sha256': 'd' * 64,
                                         'all_lines_sha256': 'e' * 64,
                                         'source_lines': 1, 'includes': [],
                                         'conditional_directive_lines': []},
                'state': 'MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW',
                'prepared_whole_file_candidate': False, 'independent_approval': False,
            })
        doc = {'schema': 'xgba-phase1-machine-triage-v1',
               'snapshot_gate': 'FAIL_INCOMPLETE', 'inventory_total': 14834,
               'prepared_register_baseline': 113, 'selected_count': 250,
               'offset': offset, 'source_reverified': True, 'records': records}
        content = json.dumps(doc, sort_keys=True).encode()
        artifact_id = 100 + i
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(filename, content)
        raw = stream.getvalue()
        (root / f'github-actions-artifact-{artifact_id}.zip').write_bytes(raw)
        manifest['shards'].append({'artifact_id': artifact_id, 'filename': filename,
                                   'offset': offset, 'count': 250,
                                   'zip_sha256': digest(raw), 'content_sha256': digest(content)})
    return manifest


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.manifest = make_fixture(self.root)

    def test_valid_synthetic_shards(self):
        result = verify(self.manifest, self.root)
        self.assertEqual(len(result), 4)
        self.assertEqual(len({r[0] for r in result}), 4)

    def test_manifest_fail_closed(self):
        for name, change in (
            ('gate', lambda m: m.update(phase1_gate='PASS')),
            ('approval', lambda m: m.update(independent_approvals=1)),
            ('source head', lambda m: m.update(source_workflow_head='bad')),
            ('offset', lambda m: m['shards'][1].update(offset=3000)),
            ('zip digest', lambda m: m['shards'][0].update(zip_sha256='0'*64)),
            ('json digest', lambda m: m['shards'][0].update(content_sha256='0'*64)),
            ('missing shard', lambda m: m['shards'].pop()),
        ):
            with self.subTest(name=name):
                m = copy.deepcopy(self.manifest)
                change(m)
                with self.assertRaises(ValueError):
                    verify(m, self.root)

    def test_duplicate_identity_even_with_recomputed_digests(self):
        m = copy.deepcopy(self.manifest)
        shard = m['shards'][1]
        path = self.root / f"github-actions-artifact-{shard['artifact_id']}.zip"
        with zipfile.ZipFile(path) as z:
            doc = json.loads(z.read(shard['filename']))
        doc['records'][0]['identity']['path'] = 'synthetic/path/3000.c'
        content = json.dumps(doc, sort_keys=True).encode()
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr(shard['filename'], content)
        raw = stream.getvalue()
        path.write_bytes(raw)
        shard['zip_sha256'] = digest(raw)
        shard['content_sha256'] = digest(content)
        with self.assertRaisesRegex(ValueError, 'Duplicate identity'):
            verify(m, self.root)


if __name__ == '__main__':
    unittest.main()
