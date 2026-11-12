#!/usr/bin/env python3
"""R37 conservative static script-dependency graph for binary Emerald-family ROMs.

This tool never executes imported scripts. It recognizes only opcode layouts
verified against pinned pret/pokeemerald script_cmd_table.inc/event macros.
At unknown opcodes, missing bytes or malformed control flow, stop and report.
The original bytes, source map group/map and file identity are never changed.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import struct
import sys

import xgba_r36_binary_pages as r36
import xgba_r34_binary_maps as r34

PROFILE = 'pret-pokeemerald-731ad5bf-original-command-layout-subset'
MAX_ROOTS = 200000
MAX_STEPS_PER_ROOT = 96
MAX_TOTAL_STEPS = 750000
MAX_BRANCHES_PER_ROOT = 24
MAX_DETAIL_RECORDS = 18000
MAX_EXAMPLES = 48
MAX_ROM = 64 * 1024 * 1024

# Proven against pret/pokeemerald data/script_cmd_table.inc and asm/macros/event.inc.
# Format: B byte, H little-endian halfword, I little-endian u32, P pointer u32.
# Lengths of variable-size commands, such as TRAINERBATTLE, are not guessed.
# mode: next/end/goto/call/conditional_goto/conditional_call/native/unknown_end.
# dependency selects which decoded operands represent flags, vars, items etc.
SPECS = {}

def _cmd(op, name, operands='', mode='next', *, flags=(), vars=(), items=(),
         trainers=(), specials=(), pointers=(), warps=False):
    SPECS[op] = dict(name=name, fmt=operands, mode=mode, flags=flags,
                     vars=vars, items=items, trainers=trainers,
                     specials=specials, pointers=pointers, warps=warps)

for op,name in ((0,'nop'),(1,'nop1'),(2,'end'),(3,'return'),
                (12,'returnram'),(13,'endram'),(27,'waitstate'),
                (45,'dotimebasedevents'),(46,'gettime'),(48,'waitse'),
                (50,'waitfanfare'),(53,'fadedefaultbgm'),
                (66,'getplayerxy'),(67,'getpartysize'),
                (90,'faceplayer'),(93,'dotrainerbattle'),
                (94,'gotopostbattlescript'),(95,'gotobeatenscript'),
                (102,'waitmessage'),(104,'closemessage'),
                (105,'lockall'),(106,'lock'),(107,'releaseall'),
                (108,'release'),(109,'waitbuttonpress')):
    _cmd(op,name,mode='end' if op in (2,3,12,13) else 'next')
_cmd(4,'call','P','call',pointers=(0,))
_cmd(5,'goto','P','goto',pointers=(0,))
_cmd(6,'goto_if','BP','conditional_goto',pointers=(1,))
_cmd(7,'call_if','BP','conditional_call',pointers=(1,))
_cmd(8,'gotostd','B','end')
_cmd(9,'callstd','B')
_cmd(10,'gotostd_if','BB','conditional_std')
_cmd(11,'callstd_if','BB')
_cmd(14,'setmysteryeventstatus','B')
_cmd(15,'loadword','BI',pointers=(1,))
_cmd(16,'loadbyte','BB')
_cmd(17,'setptr','BP',pointers=(1,))
_cmd(18,'loadbytefromptr','BP',pointers=(1,))
_cmd(19,'setptrbyte','BP',pointers=(1,))
_cmd(20,'copylocal','BB')
_cmd(21,'copybyte','PP',pointers=(0,1))
for op,name in ((22,'setvar'),(23,'addvar'),(24,'subvar'),(25,'copyvar'),(26,'setorcopyvar')):
    _cmd(op,name,'HH',vars=(0,1) if op in (25,26) else (0,))
_cmd(27,'compare_local_to_local','BB')
_cmd(28,'compare_local_to_value','BB')
_cmd(29,'compare_local_to_ptr','BP',pointers=(1,))
_cmd(30,'compare_ptr_to_local','PB',pointers=(0,))
_cmd(31,'compare_ptr_to_value','PB',pointers=(0,))
_cmd(32,'compare_ptr_to_ptr','PP',pointers=(0,1))
_cmd(33,'compare_var_to_value','HH',vars=(0,))
_cmd(34,'compare_var_to_var','HH',vars=(0,1))
_cmd(35,'callnative','P','native',pointers=(0,))
_cmd(36,'gotonative','P','native',pointers=(0,))
_cmd(37,'special','H',specials=(0,))
_cmd(38,'specialvar','HH',vars=(0,),specials=(1,))
_cmd(39,'waitstate')
_cmd(40,'delay','H')
_cmd(41,'setflag','H',flags=(0,))
_cmd(42,'clearflag','H',flags=(0,))
_cmd(43,'checkflag','H',flags=(0,))
_cmd(47,'playse','H')
_cmd(49,'playfanfare','H')
_cmd(51,'playbgm','HB')
_cmd(52,'savebgm','H')
_cmd(54,'fadenewbgm','H')
_cmd(55,'fadeoutbgm','B')
_cmd(56,'fadeinbgm','B')
for op,name in ((57,'warp'),(58,'warpsilent'),(59,'warpdoor'),
                (61,'warpteleport'),(62,'setwarp'),(63,'setdynamicwarp'),
                (64,'setdivewarp'),(65,'setholewarp')):
    _cmd(op,name,'BBBHH',warps=True)
_cmd(60,'warphole','BB',warps=True)
for op,name in ((68,'additem'),(69,'removeitem'),(70,'checkitemspace'),
                (71,'checkitem'),(73,'addpcitem'),(74,'checkpcitem')):
    _cmd(op,name,'HH',items=(0,))
_cmd(72,'checkitemtype','H',items=(0,))
for op,name in ((75,'adddecoration'),(76,'removedecoration'),
                (77,'checkdecor'),(78,'checkdecorspace')):
    _cmd(op,name,'H')
_cmd(79,'applymovement','HP',pointers=(1,))
_cmd(80,'applymovementat','HPBB',pointers=(1,))
_cmd(81,'waitmovement','H')
_cmd(82,'waitmovementat','HBB')
_cmd(83,'removeobject','H')
_cmd(84,'removeobjectat','HBB')
_cmd(85,'addobject','H')
_cmd(86,'addobjectat','HBB')
_cmd(87,'setobjectxy','HHH')
_cmd(88,'showobjectat','HBB')
_cmd(89,'hideobjectat','HBB')
_cmd(91,'turnobject','HB')
# opcode 0x5c TRAINERBATTLE is intentionally not decoded: layout varies by type.
for op,name in ((96,'checktrainerflag'),(97,'settrainerflag'),(98,'cleartrainerflag')):
    _cmd(op,name,'H',trainers=(0,))
_cmd(99,'setobjectxyperm','HHH')
_cmd(100,'copyobjectxytoperm','H')
_cmd(101,'setobjectmovementtype','HB')
_cmd(103,'message','P',pointers=(0,))
_cmd(110,'yesnobox','BB')
_cmd(111,'multichoice','BBBB')
_cmd(112,'multichoicedefault','BBBBB')

FORMATS = {'B': (1,'<B'), 'H':(2,'<H'), 'I':(4,'<I'), 'P':(4,'<I')}

class ScriptError(ValueError):
    pass


def _validate_root(root, length):
    if not isinstance(root,dict) or type(root.get('source_rom_offset')) is not int or \
       not 0<=root['source_rom_offset']<length or type(root.get('group')) is not int or \
       type(root.get('map')) is not int or not isinstance(root.get('kind'),str):
        raise ScriptError('Invalid R36 script entrypoint')


def _pointer(v, length):
    # Emerald-family ROM pointer including the 0x09000000 mirrored ROM bank.
    if 0x08000000<=v<0x0a000000 and v-0x08000000<length:
        return v-0x08000000
    return None


def _one(raw, offset):
    if not 0<=offset<len(raw):return None
    opcode=raw[offset]
    spec=SPECS.get(opcode)
    if spec is None:return {'offset':offset,'opcode':opcode,'status':'unsupported_opcode'}
    size=1+sum(FORMATS[x][0] for x in spec['fmt'])
    if offset+size>len(raw):return {'offset':offset,'opcode':opcode,'status':'truncated_command'}
    args=[];position=offset+1
    for field in spec['fmt']:
        n,fmt=FORMATS[field]
        args.append(struct.unpack_from(fmt,raw,position)[0]);position+=n
    return {'offset':offset,'opcode':opcode,'name':spec['name'],
            'size':size,'args':args,'status':'recognized',
            'mode':spec['mode']}


def analyze_root(raw,entry,*,max_commands=MAX_STEPS_PER_ROOT,
                 max_branches=MAX_BRANCHES_PER_ROOT):
    """Conservative CFG discovery; no state changes, script execution or macro guessing."""
    _validate_root(entry,len(raw))
    if type(max_commands) is not int or not 1<=max_commands<=MAX_STEPS_PER_ROOT:
        raise ScriptError('Invalid per-root instruction budget')
    if type(max_branches) is not int or not 1<=max_branches<=MAX_BRANCHES_PER_ROOT:
        raise ScriptError('Invalid branch budget')
    root=entry['source_rom_offset']
    pending=deque([root]);queued={root};visited=set()
    counts=Counter();deps={k:set() for k in ('flags','vars','items','trainers','specials')}
    targets=set();outside=set();samples=[]
    instructions=0;branches=0
    while pending:
        if instructions>=max_commands:
            counts['instruction_budget_reached']+=1;break
        pc=pending.popleft()
        if pc in visited:continue
        visited.add(pc)
        cmd=_one(raw,pc)
        if cmd is None:
            counts['out_of_rom_pc']+=1;continue
        if cmd['status']!='recognized':
            counts[cmd['status']]+=1
            if len(samples)<5:samples.append({'rom_offset':pc,'opcode':cmd['opcode'],'reason':cmd['status']})
            continue
        instructions+=1
        counts['recognized_commands']+=1
        spec=SPECS[cmd['opcode']]
        args=cmd['args']; mode=cmd['mode']
        counts['category_'+('native' if mode=='native' else ('warp' if spec['warps'] else 'command'))]+=1
        for dep in deps:
            for i in spec[dep]:deps[dep].add(args[i])
        if spec['warps']:
            counts['warp_references']+=1
        if spec['pointers']:
            for i in spec['pointers']:
                value=args[i]
                if value!=0 and _pointer(value,len(raw)) is None:
                    counts['opaque_or_invalid_pointer_literals']+=1
        if mode=='native':
            counts['native_engine_callback_dependency']+=1
        if mode in ('goto','call','conditional_goto','conditional_call'):
            ptr=args[-1];target=_pointer(ptr,len(raw))
            if target is None:
                counts['invalid_branch_target']+=1
                if len(samples)<5:samples.append({'rom_offset':pc,'opcode':cmd['opcode'],'reason':'invalid_branch_target'})
            else:
                targets.add(target)
                if target not in visited and target not in queued:
                    if branches>=max_branches:counts['branch_budget_reached']+=1
                    else:
                        pending.append(target);queued.add(target);branches+=1
        if mode in ('next','call','conditional_goto','conditional_call','conditional_std','native'):
            nxt=pc+cmd['size']
            if nxt<len(raw) and nxt not in queued and nxt not in visited:
                pending.append(nxt);queued.add(nxt)
            elif nxt>=len(raw):counts['truncated_next_command']+=1
        elif mode=='end':
            counts['terminal_commands']+=1
        # goto jumps unconditionally; never infer fallthrough.
    ended=counts['terminal_commands']>0 and not pending
    status=('bounded_or_uncertain' if pending or counts['instruction_budget_reached'] or
            counts['branch_budget_reached'] or counts['unsupported_opcode'] or
            counts['invalid_branch_target'] or counts['truncated_command'] or
            counts['out_of_rom_pc'] else 'syntactically_terminated' if ended else 'syntactically_partial')
    return {'root_offset':root,'recognized_commands':instructions,
            'status':status,'counts':dict(sorted(counts.items())),
            'dependencies':{k:sorted(v) for k,v in deps.items()},
            'branch_targets':sorted(targets), 'examples':samples}


def analyze_rom(raw, roots, *, max_roots=MAX_ROOTS,
                max_total_commands=MAX_TOTAL_STEPS,
                detail_limit=MAX_DETAIL_RECORDS):
    if not isinstance(raw,(bytes,bytearray,memoryview)) or len(raw)>MAX_ROM:
        raise ScriptError('Invalid input ROM or size')
    if not isinstance(roots,list) or len(roots)>max_roots:
        raise ScriptError('R36 root budget exceeded')
    if type(max_total_commands) is not int or max_total_commands<1 or \
       type(detail_limit) is not int or not 0<=detail_limit<=MAX_DETAIL_RECORDS:
        raise ScriptError('Invalid reporting budget')
    by_offset=defaultdict(list)
    for root in roots:
        _validate_root(root,len(raw))
        by_offset[root['source_rom_offset']].append(root)
    count=Counter();cmds=0
    all_deps={k:set() for k in ('flags','vars','items','trainers','specials')}
    status=Counter();reason=Counter();examples=[];details=[]
    for i,off in enumerate(sorted(by_offset)):
        if cmds>=max_total_commands:
            count['roots_not_scanned_due_to_budget']=len(by_offset)-i
            break
        root=by_offset[off][0]
        result=analyze_root(raw,root,max_commands=min(MAX_STEPS_PER_ROOT,max_total_commands-cmds))
        cmds+=result['recognized_commands']
        status[result['status']]+=1
        count['root_origins_references']+=len(by_offset[off])
        count['branch_target_links']+=len(result['branch_targets'])
        for k,v in result['counts'].items():reason[k]+=v
        for k,v in result['dependencies'].items():all_deps[k].update(v)
        if result['examples'] and len(examples)<MAX_EXAMPLES:
            examples.append({'group':root['group'],'map':root['map'],
                             'kind':root['kind'],'root_offset':off,
                             'first_issue':result['examples'][0]})
        if len(details)<detail_limit:
            details.append({'source_rom_offset':off,
                            'origin_references':len(by_offset[off]),
                            'origin_sample':{'group':root['group'],'map':root['map'],
                                             'kind':root['kind']},
                            **result})
    return {'profile':PROFILE,'source_rom_sha256':hashlib.sha256(raw).hexdigest(),
            'unscanned_unique_entrypoints_due_to_budget':count['roots_not_scanned_due_to_budget'],
            'details_truncated':len(details)<sum(status.values()),
            'source_rom_bytes':len(raw),'entrypoint_references':len(roots),
            'unique_entrypoints':len(by_offset),
            'entrypoints_scanned':sum(status.values()),
            'recognized_commands':cmds,'status_counts':dict(sorted(status.items())),
            'command_reason_counts':dict(sorted(reason.items())),
            'dependencies':{k:sorted(v) for k,v in all_deps.items()},
            'issue_examples':examples,'roots':details,
            'analysis_executed_scripts':False,
            'unrecognized_opcode_behavior_inferred':False,
            'custom_engine_compatibility_proven':False,
            'cross_world_script_runtime_implemented':False}


def verified_rom_bytes(pool):
    """Build-time only: recover verified bytes from R36, not guest EWRAM.

    R36 independently checks entire shard and original ROM digests on open;
    this recovery verifies the reconstructed SHA-256 before decoding anything.
    This is not a streaming guest execution path and does not expand GBA RAM.
    """
    if not isinstance(pool,r36.PagedBinaryPool) or not 0<pool.rom_bytes<=MAX_ROM:
        raise ScriptError('Unsupported or oversized binary-page source')
    out=bytearray()
    digest=hashlib.sha256()
    for offset in range(0,pool.rom_bytes,r36.PAGE_SIZE):
        n=min(r36.PAGE_SIZE,pool.rom_bytes-offset)
        block=pool.read_rom(offset,n)
        if len(block)!=n:raise ScriptError('Truncated verified R36 page')
        digest.update(block)
        out.extend(block)
    if digest.hexdigest()!=pool.source_sha256:
        raise ScriptError('Reconstructed ROM identity does not match R36 source')
    return bytes(out)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('rom',nargs='?',help='Optional private original GBA ROM (verify identity only)')
    p.add_argument('--page-index',required=True,help='R36 private page index')
    p.add_argument('--private-out',required=True)
    p.add_argument('--counts-only',help='Optional safe aggregate report for CI, no bytes/offsets')
    args=p.parse_args(argv)
    try:
        index=r36.PagedBinaryPool(args.page_index)
        raw=verified_rom_bytes(index)
        if args.rom is not None:
            source=Path(args.rom)
            with source.open('rb') as f:
                h=hashlib.sha256();length=0
                for block in iter(lambda:f.read(1024*1024),b''):
                    h.update(block);length+=len(block)
            if length!=len(raw) or h.hexdigest()!=index.source_sha256:
                raise ScriptError('Optional input ROM does not match original R36 pages')
        result=analyze_rom(raw,index.script_roots['original_script_entrypoints'])
        dst=Path(args.private_out)
        if dst.exists():raise ScriptError('Refuse to overwrite existing private report')
        dst.write_text(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n',encoding='utf8')
        compact={k:result[k] for k in ('profile','source_rom_sha256','source_rom_bytes',
                   'entrypoint_references','unique_entrypoints','entrypoints_scanned',
                   'recognized_commands','status_counts','command_reason_counts')}
        compact['dependency_counts']={k:len(v) for k,v in result['dependencies'].items()}
        compact['script_compatibility_proven']=False
        if args.counts_only:Path(args.counts_only).write_text(json.dumps(compact,indent=2,sort_keys=True)+'\n')
        print(json.dumps(compact,sort_keys=True))
        return 0
    except (OSError,ValueError,TypeError) as exc:
        print('XGBA_R37_SCRIPT_ANALYSIS_FAIL_CLOSED: '+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__':raise SystemExit(main())
