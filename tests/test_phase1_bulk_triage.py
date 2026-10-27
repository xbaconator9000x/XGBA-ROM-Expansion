"""Negative controls for Phase 1 pinned bulk machine triage."""
import hashlib,json,sys,tempfile,unittest,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import phase1_bulk_triage as t
class Tests(unittest.TestCase):
 def test_git_blob(self):
  self.assertEqual(t.git_blob(b'abc'),'f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f')
 def test_structure(self):
  b=b'#include "x.h"\n#ifdef X\nvoid f(void);\n#endif\n';s=t.structure(b)
  self.assertEqual(s['source_lines'],4)
  self.assertEqual(s['includes'],[{'line':1,'include':'x.h'}])
  self.assertEqual(s['conditional_directive_lines'],[2,4])
  self.assertEqual(s['whole_blob_sha256'],hashlib.sha256(b).hexdigest())
 def test_deterministic_selection_and_resume(self):
  q=[dict(repo='r',path=str(i),priority=p,incoming_includes='0',lexical_match_count='0') for i,p in [(1,'P2'),(2,'P0'),(3,'P1'),(4,'P0')]]
  self.assertEqual([x['path'] for x in t.select(q,{('r','2')},2,0)],['4','3'])
  self.assertEqual([x['path'] for x in t.select(q,{('r','2')},1,1)],['3'])
 def test_exact_git_tree_and_blob_verification(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);checkout=root/'pokefirered';checkout.mkdir()
   subprocess.run(['git','-C',str(checkout),'init','-q'],check=True)
   (checkout/'src').mkdir();(checkout/'src'/'a.c').write_bytes(b'int f(void) { return 7; }\n')
   subprocess.run(['git','-C',str(checkout),'add','.'],check=True)
   subprocess.run(['git','-C',str(checkout),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','-qm','fixture'],check=True)
   pin=subprocess.check_output(['git','-C',str(checkout),'rev-parse','HEAD'],text=True).strip()
   blob=t.git_blob(b'int f(void) { return 7; }\n')
   self.assertEqual(t.source_bytes(root,'pret/pokefirered',pin,'src/a.c',blob),b'int f(void) { return 7; }\n')
   with self.assertRaisesRegex(ValueError,'tree path/blob mismatch'):t.source_bytes(root,'pret/pokefirered',pin,'src/a.c','f'*40)
   with self.assertRaisesRegex(ValueError,'Pinned checkout mismatch'):t.source_bytes(root,'pret/pokefirered','0'*40,'src/a.c',blob)
 def test_gate_change_fails_closed(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'phase1_mapping_gate.json').write_text(json.dumps({'decision':'PASS_MAPPING_ONLY','approved_semantic_dispositions':0}))
   with self.assertRaisesRegex(ValueError,'gate changed'):t.build(root,root/'register',root/'out',1,0)
 def test_invalid_batch_bounds(self):
  with self.assertRaises(ValueError):t.select([],set(),1,0)
 def test_canonical_hash_stable(self):
  self.assertEqual(t.canonical({'b':2,'a':1}),b'{"a":1,"b":2}')
if __name__=='__main__':unittest.main()
