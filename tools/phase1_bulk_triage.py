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
BINARY_EXTENSIONS={'.bin':'opaque_binary','.elf':'compiled_binary','.o':'compiled_binary','.a':'compiled_binary','.jpg':'image_binary','.jpeg':'image_binary','.gif':'image_binary','.bmp':'image_binary','.wav':'audio_binary','.mid':'audio_binary','.ogg':'audio_binary','.zip':'archive_binary'}
TEXT_SOURCE_EXT={'.c','.h','.cpp','.hpp','.cc','.s','.asm','.py','.sh','.ld','.go','.rs'}
TEXT_DATA_EXT={'.json','.md','.txt','.mk','.yaml','.yml','.toml','.ini','.csv','.inc','.xml','.qrc','.pro','.cmake','.js','.ts','.html','.css','.map'}
def valid_png(data):
    """Conservative PNG container validation; does not certify decoded pixels."""
    import struct,zlib
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):return False
    pos=8;first=True;seen_idat=False;seen_plte=False;idat_finished=False
    color_type=None;bit_depth=None
    while pos+12<=len(data):
        n=struct.unpack('>I',data[pos:pos+4])[0]
        if n>len(data)-pos-12:return False
        tag=data[pos+4:pos+8];payload=data[pos+8:pos+8+n]
        crc=struct.unpack('>I',data[pos+8+n:pos+12+n])[0]
        if not all(65<=b<=90 or 97<=b<=122 for b in tag) or not 65<=tag[2]<=90:return False
        if zlib.crc32(tag+payload)&0xffffffff!=crc:return False
        if first:
            if tag!=b'IHDR' or n!=13:return False
            width,height=struct.unpack('>II',payload[:8])
            bit_depth,color_type,compression,filter_method,interlace=payload[8:]
            allowed={0:(1,2,4,8,16),2:(8,16),3:(1,2,4,8),4:(8,16),6:(8,16)}
            if not width or not height or bit_depth not in allowed.get(color_type,()):return False
            if compression!=0 or filter_method!=0 or interlace not in (0,1):return False
            first=False
        elif tag==b'IHDR':
            return False
        elif tag==b'PLTE':
            if seen_plte or seen_idat or color_type in (0,4) or n==0 or n%3 or n>768:return False
            if color_type==3 and n//3>1<<bit_depth:return False
            seen_plte=True
        elif tag==b'IDAT':
            if idat_finished or (color_type==3 and not seen_plte):return False
            seen_idat=True
        elif tag==b'IEND':
            return n==0 and seen_idat and pos+12==len(data)
        else:
            if tag[0]<97:return False  # Unknown critical chunk cannot be interpreted.
            if seen_idat:idat_finished=True
        pos+=12+n
    return False
def valid_gba_header(data):
    return (len(data)>=0xc0 and data[0xb2]==0x96
            and data[0xbd]==((-sum(data[0xa0:0xbd])-0x19)&0xff))
def file_kind(path,data):
    ext=Path(path).suffix.lower()
    if ext=='.png' or data.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'image_png' if valid_png(data) else 'unknown_binary'
    if ext=='.gba':
        return 'compiled_rom' if valid_gba_header(data) else 'unknown_binary'
    if ext in BINARY_EXTENSIONS:
        return BINARY_EXTENSIONS[ext] if (b'\x00' in data or any(x>127 for x in data)) else 'unknown_binary'
    if b'\x00' in data:return 'unknown_binary'
    try:data.decode('utf-8')
    except UnicodeDecodeError:return 'unknown_binary'
    if ext in TEXT_SOURCE_EXT:return 'text_source'
    if ext in TEXT_DATA_EXT or Path(path).name in ('Makefile','CMakeLists.txt','LICENSE','README','.gitignore','.gitattributes'):return 'authored_text'
    return 'unknown_binary'
def typed_structure(path,data):
    kind=file_kind(path,data)
    if kind in ('text_source','authored_text'):
        result=structure(data)
        result['file_kind']=kind
        result['structure_schema']='xgba-phase1-typed-structure-v2'
        return result
    return {'structure_schema':'xgba-phase1-typed-structure-v2','file_kind':kind,'byte_length':len(data),'whole_blob_sha256':digest(data),'format_signature_hex':data[:16].hex(),'source_lines':None,'nonblank_lines':None,'all_lines_sha256':None,'includes':[],'conditional_directive_lines':[],'risk_flags_line_anchors':{},'limits':['Binary bytes are not source-code lines','Format-specific producer/consumer and layout review required','Extension/signature alone does not prove binary semantics']}
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
            item['whole_file_structure']=typed_structure(r['path'],data)
            if item['whole_file_structure']['file_kind'] not in ('text_source','authored_text'):
                item['machine_triage']={'lexical_evidence_applicable':False,'unverified_dependency_hints':{'incoming_include_candidates':m['incoming_include_candidates'],'unresolved_include_candidates':m['unresolved_include_candidates']},'limits':['Dossier lexical and symbol samples suppressed for non-text file kind; dossier SHA preserved']}
            else:
                item['machine_triage']['lexical_evidence_applicable']=True
        records.append(item)
    if len({(r['identity']['repository'],r['identity']['path']) for r in records})!=len(records):raise ValueError('Duplicate batch output')
    result={'schema':'xgba-phase1-machine-triage-v2','snapshot_gate':'FAIL_INCOMPLETE','inventory_total':TOTAL,'prepared_register_baseline':len(prepared),'selected_count':len(records),'offset':offset,'source_reverified':source_root is not None,'records':records}
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
