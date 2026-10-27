#!/usr/bin/env python3
"""Fail-closed bulk machine triage. Never an analyst disposition or approval."""
import argparse,csv,gzip,hashlib,json,re,subprocess
from pathlib import Path
TOTAL=14834
PINS={'pret/pokefirered':'ce6406d8c2eaf46d543c8a2606de0c3cb1951982','mgba-emu/mgba':'fd9dc5c2cbf234365068855851107e762fc6211b','huderlem/porymap':'26b919d7ff4b54152de010abd5bf344af2ebe116','huderlem/poryscript':'c32481161c767b25a3425fa9f1f8729927ff3d55','pret/agbcc':'da598c1d918402c42c0c0d7128ba14567f3175e9'}
HEX40=re.compile(r'^[0-9a-f]{40}$')
HEX64=re.compile(r'^[0-9a-f]{64}$')
REG=re.compile(r'^\| '+chr(96)+r'(?P<repo>[^:]+/[^:]+):(?P<path>[^'+chr(96)+r']+)'+chr(96)+r' \|',re.M)
INCLUDE=re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]')
HAZARDS={'rom_address':rb'\b(?:romMask|romSize|GBA_BASE_ROM\w*)\b','pointer_arithmetic':rb'\b(?:uintptr_t|reinterpret_cast|memcpy|memmove|offsetof)\b','save_state':rb'\b(?:serialize|deserialize|SaveSector|EEPROM|SRAM|Flash)\b','script_layout':rb'\b(?:ScrCmd_|scriptPtr|map_script|MapConnection|gMapLayouts)\b','build_linker':rb'\b(?:SECTIONS|OBJCOPY|ld_script|incbin)\b'}
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
def digest(b):return hashlib.sha256(b).hexdigest()
def git_blob(b):return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()
def source_bytes(root,repo,pin,path,expected):
    checkout=root/repo.split('/')[-1]
    def git(*args):return subprocess.check_output(['git','-C',str(checkout),*args]).strip()
    if git('rev-parse','HEAD').decode()!=pin:raise ValueError('Pinned checkout mismatch: '+repo)
    if git('rev-parse','HEAD:'+path).decode()!=expected:raise ValueError('Pinned tree path/blob mismatch: '+repo+':'+path)
    data=subprocess.check_output(['git','-C',str(checkout),'cat-file','blob',expected])
    if git_blob(data)!=expected:raise ValueError('Git blob hash mismatch: '+repo+':'+path)
    return data
def structure(data):
    lines=data.splitlines();inc=[];conditional=[];flags={}
    for i,line in enumerate(lines,1):
        s=line.decode('utf-8','surrogateescape');m=INCLUDE.match(s)
        if m:inc.append({'line':i,'include':m.group(1)})
        if re.match(r'^\s*#\s*(?:if|ifdef|ifndef|elif|else|endif)\b',s):conditional.append(i)
    for name,pattern in HAZARDS.items():
        hits=[i for i,line in enumerate(lines,1) if re.search(pattern,line,re.I)]
        if hits:flags[name]=hits
    return {'source_lines':len(lines),'nonblank_lines':sum(bool(x.strip()) for x in lines),'whole_blob_sha256':digest(data),'all_lines_sha256':digest(b'\n'.join(lines)),'includes':inc,'conditional_directive_lines':conditional,'risk_flags_line_anchors':flags,'limits':['Structural anchors are not parsed semantics or execution proof','Whole-file independent semantic review still required']}
def read_queue(root):
    with gzip.open(root/'semantic_review_queue.csv.gz','rt',encoding='utf-8',newline='') as f:q=list(csv.DictReader(f))
    if len(q)!=TOTAL or len({(r['repo'],r['path']) for r in q})!=TOTAL:raise ValueError('Queue inventory size or uniqueness failure')
    for r in q:
        if r['repo'] not in PINS or not HEX40.fullmatch(r['blob_sha']) or not HEX64.fullmatch(r['evidence_sha256']):raise ValueError('Invalid queue identity')
    return q
def checked_dossiers(root,queue):
    records={}
    with gzip.open(root/'candidate_review_dossiers.jsonl.gz','rt',encoding='utf-8') as f:
        for i,line in enumerate(f):
            if i>=TOTAL:raise ValueError('Extra dossier')
            d=json.loads(line);r=queue[i];p=d['provenance']
            if digest(canonical(d))!=r['evidence_sha256']:raise ValueError('Dossier SHA-256 mismatch at '+str(i))
            if (p['repository'],p['pinned_revision'],p['path'],p['git_blob_sha'])!=(r['repo'],PINS[r['repo']],r['path'],r['blob_sha']):raise ValueError('Dossier provenance mismatch at '+str(i))
            if d.get('review',{}).get('semantic_signoff') is not False:raise ValueError('Unexpected dossier signoff')
            records[(r['repo'],r['path'])]=d
    if len(records)!=TOTAL:raise ValueError('Missing dossier records')
    return records
def select(queue,already,limit,offset):
    order={'P0':0,'P1':1,'P2':2,'P3':3}
    pool=[r for r in queue if (r['repo'],r['path']) not in already]
    pool.sort(key=lambda r:(order.get(r['priority'],4),-int(r['incoming_includes']),-int(r['lexical_match_count']),r['repo'],r['path']))
    result=pool[offset:offset+limit]
    if len(result)!=limit:raise ValueError('Requested batch exceeds available unique files')
    return result
def build(root,register,out,limit,offset,source_root=None):
    gate=json.loads((root/'phase1_mapping_gate.json').read_text())
    if gate.get('decision')!='FAIL_INCOMPLETE' or gate.get('approved_semantic_dispositions')!=0:raise ValueError('Authoritative gate changed: stop for review')
    queue=read_queue(root);dossiers=checked_dossiers(root,queue)
    prepared={(m.group('repo'),m.group('path')) for m in REG.finditer(register.read_text())}
    if len(prepared)!=113:raise ValueError('Prepared candidate register changed; reconcile before bulk triage')
    if not prepared.issubset({(r['repo'],r['path']) for r in queue}):raise ValueError('Register source not in pinned manifest')
    chosen=select(queue,prepared,limit,offset);records=[]
    for r in chosen:
        d=dossiers[(r['repo'],r['path'])];m=d['machine_assessment'];p=d['provenance']
        item={'identity':{'repository':r['repo'],'pinned_commit':PINS[r['repo']],'path':r['path'],'git_blob_sha1':r['blob_sha']},'evidence':{'dossier_sha256':r['evidence_sha256'],'snapshot_provenance_verified':True,'source_blob_reverified_this_run':source_root is not None},'priority':r['priority'],'machine_triage':{'lexical_rule_counts':m['rule_counts'],'symbol_samples':m['symbol_samples'],'include_samples':m['include_samples'],'incoming_include_candidates':m['incoming_include_candidates'],'unresolved_include_candidates':m['unresolved_include_candidates']},'whole_file_structure':None,'state':'MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW','prepared_whole_file_candidate':False,'independent_approval':False,'review_obligations':['Review entire pinned file and all exported symbols','Resolve indirect/generated dependencies and external consumers','Trace compiled/runtime/save/editor compatibility and counterexamples','Obtain genuine independent reviewer decision']}
        if source_root is not None:
            data=source_bytes(source_root,r['repo'],PINS[r['repo']],r['path'],r['blob_sha'])
            if str(len(data))!=str(p['tracked_bytes']):raise ValueError('Pinned byte count mismatch: '+r['path'])
            item['whole_file_structure']=structure(data)
        records.append(item)
    if len({(r['identity']['repository'],r['identity']['path']) for r in records})!=len(records):raise ValueError('Duplicate batch output')
    result={'schema':'xgba-phase1-machine-triage-v1','snapshot_gate':'FAIL_INCOMPLETE','inventory_total':TOTAL,'prepared_register_baseline':len(prepared),'selected_count':len(records),'offset':offset,'source_reverified':source_root is not None,'records':records}
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(canonical(result)+b'\n')
    if json.loads(out.read_text())!=result:raise ValueError('Output round-trip failed')
    print(json.dumps({'selected':len(records),'prepared_unchanged':len(prepared),'approved_unchanged':0,'source_reverified':source_root is not None,'output_sha256':digest(out.read_bytes())},sort_keys=True))
def main():
    a=argparse.ArgumentParser()
    a.add_argument('--snapshot',type=Path,default=Path('semantic-snapshots/current'))
    a.add_argument('--register',type=Path,default=Path('docs/phase1-disposition-candidates/README.md'))
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--limit',type=int,default=200)
    a.add_argument('--offset',type=int,default=0)
    a.add_argument('--source-root',type=Path)
    x=a.parse_args()
    if not 1<=x.limit<=2000 or x.offset<0:a.error('limit 1..2000, offset nonnegative')
    build(x.snapshot,x.register,x.output,x.limit,x.offset,x.source_root)
if __name__=='__main__':main()
