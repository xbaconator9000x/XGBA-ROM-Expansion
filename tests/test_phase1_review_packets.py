import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from phase1_review_packets import load_shards, resolve_include, packets, validate_integrity, PINS

SHA=PINS['pret/pokefirered']
DIG='b'*64

def record(path, includes=None, priority='P0'):
    return {'identity':{'repository':'pret/pokefirered','path':path,'pinned_commit':SHA,'git_blob_sha1':SHA},
            'evidence':{'dossier_sha256':DIG,'source_blob_reverified_this_run':True},
            'priority':priority,'state':'MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW',
            'prepared_whole_file_candidate':False,'independent_approval':False,
            'whole_file_structure':{'whole_blob_sha256':DIG,'source_lines':4,'includes':includes or []}}

class TestReviewPackets(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
    def shard(self,records,start=0):
        name=f'batch-{start:06d}-{start+len(records)-1:06d}.json'
        d={'schema':'xgba-phase1-machine-triage-v1','snapshot_gate':'FAIL_INCOMPLETE',
           'inventory_total':14834,'prepared_register_baseline':113,'source_reverified':True,
           'selected_count':len(records),'offset':start,'records':records}
        (self.root/name).write_text(json.dumps(d))
    def test_lexical_include_is_not_proven_semantics(self):
        a=record('src/a.c',[{'line':2,'include':'x.h'}]); b=record('include/x.h')
        self.shard([a,b]); rows,shards=load_shards(self.root)
        out=packets(rows,shards,10)
        self.assertEqual(out['independent_approvals_added'],0)
        self.assertEqual(out['prepared_whole_file_dispositions_added'],0)
        self.assertEqual(next(p for p in out['packets'] if p['identity']['path']=='src/a.c')['candidate_include_edges'][0]['resolution'],'lexical_candidate')
    def test_ambiguous_include_fails_open_never(self):
        keys={('pret/pokefirered','src/x.h'),('pret/pokefirered','include/x.h')}
        status,targets=resolve_include('pret/pokefirered','src/a.c','x.h',keys)
        self.assertEqual(status,'ambiguous'); self.assertEqual(len(targets),2)
    def test_traversal_is_rejected(self):
        self.assertEqual(resolve_include('pret/pokefirered','src/a.c','../x.h',set())[0],'invalid')
    def test_forged_approval_rejected(self):
        a=record('src/a.c'); a['independent_approval']=True; self.shard([a])
        with self.assertRaises(ValueError):load_shards(self.root)
    def test_wrong_blob_rejected(self):
        a=record('src/a.c'); a['identity']['git_blob_sha1']='fake'; self.shard([a])
        with self.assertRaises(ValueError):load_shards(self.root)
    def test_cross_shard_duplicate_rejected(self):
        a=record('src/a.c'); self.shard([a],0); self.shard([a],1)
        with self.assertRaises(ValueError):load_shards(self.root)
    def test_unverified_source_rejected(self):
        a=record('src/a.c'); a['evidence']['source_blob_reverified_this_run']=False; self.shard([a])
        with self.assertRaises(ValueError):load_shards(self.root)
    def test_integrity_manifest_missing_rejected(self):
        self.shard([record('src/a.c')]); rows,shards=load_shards(self.root)
        with self.assertRaises(ValueError):validate_integrity(self.root,shards,len(rows))
    def test_integrity_manifest_forgery_rejected(self):
        self.shard([record('src/a.c')]); rows,shards=load_shards(self.root)
        (self.root/'integrity-000000-000000.json').write_text(json.dumps({
            'phase1_gate':'FAIL_INCOMPLETE','independent_approvals':0,
            'analyst_prepared_baseline':113,'unique_source_verified_machine_records':1,
            'shards':[{'file':shards[0]['path'],'count':1,'sha256':'0'*64}]}))
        with self.assertRaises(ValueError):validate_integrity(self.root,shards,len(rows))
    def test_noncanonical_offset_rejected(self):
        a=record('src/a.c'); self.shard([a]); p=next(self.root.glob('batch-*'))
        d=json.loads(p.read_text());d['offset']=2;p.write_text(json.dumps(d))
        with self.assertRaises(ValueError):load_shards(self.root)

if __name__=='__main__':unittest.main()
