#!/usr/bin/env python3
"""Deterministic review-readiness packets from *machine* triage; never approval.

Include edges are lexical candidate links, NOT compiler-resolved dependencies.
The entire source blob must be independently reviewed before a prepared disposition.
"""
from __future__ import annotations
import argparse, collections, hashlib, json, re
from pathlib import Path, PurePosixPath

TOTAL = 14834
SCHEMA = 'xgba-phase1-review-readiness-v1'
PINS={'pret/pokefirered':'ce6406d8c2eaf46d543c8a2606de0c3cb1951982',
      'mgba-emu/mgba':'fd9dc5c2cbf234365068855851107e762fc6211b',
      'huderlem/porymap':'26b919d7ff4b54152de010abd5bf344af2ebe116',
      'huderlem/poryscript':'c32481161c767b25a3425fa9f1f8729927ff3d55',
      'pret/agbcc':'da598c1d918402c42c0c0d7128ba14567f3175e9'}
SHA40 = re.compile(r'^[0-9a-f]{40}$')
SHA64 = re.compile(r'^[0-9a-f]{64}$')

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode() + b'\n'

def valid_path(s):
    p = PurePosixPath(s)
    return bool(s) and not s.startswith('/') and all(x not in ('', '.', '..') for x in s.split('/')) and str(p) == s

def load_shards(directory):
    seen = {}; shards = []
    for file in sorted(directory.glob('batch-*.json')):
        d = json.loads(file.read_bytes())
        if (d.get('schema') != 'xgba-phase1-machine-triage-v1' or
            d.get('snapshot_gate') != 'FAIL_INCOMPLETE' or
            d.get('inventory_total') != TOTAL or
            d.get('prepared_register_baseline') != 113 or
            d.get('source_reverified') is not True):
            raise ValueError('Invalid machine shard metadata: '+file.name)
        rows = d.get('records')
        if not isinstance(rows, list) or len(rows) != d.get('selected_count'):
            raise ValueError('Invalid shard record count: '+file.name)
        m = re.fullmatch(r'batch-(\d{6})-(\d{6})\.json', file.name)
        if not m or int(m.group(1)) != d.get('offset') or int(m.group(2))-int(m.group(1))+1 != len(rows):
            raise ValueError('Noncanonical shard filename/offset: '+file.name)
        for r in rows:
            i = r.get('identity', {})
            key = (i.get('repository'), i.get('path'))
            s = r.get('whole_file_structure') or {}
            if (key in seen or not isinstance(key[0], str) or not isinstance(key[1], str) or
                not valid_path(key[1]) or i.get('pinned_commit') != PINS.get(key[0]) or
                not SHA40.fullmatch(str(i.get('git_blob_sha1', ''))) or
                not SHA64.fullmatch(str(s.get('whole_blob_sha256', ''))) or
                not SHA64.fullmatch(str(r.get('evidence', {}).get('dossier_sha256', ''))) or
                r.get('evidence', {}).get('source_blob_reverified_this_run') is not True or
                r.get('state') != 'MACHINE_TRIAGED_NEEDS_WHOLE_FILE_SEMANTIC_REVIEW' or
                r.get('prepared_whole_file_candidate') is not False or
                r.get('independent_approval') is not False or
                r.get('priority') not in ('P0','P1','P2','P3') or
                not isinstance(s.get('includes'), list)):
                raise ValueError('Duplicate, unverified or falsely approved record: '+str(key))
            for include in s['includes']:
                if not isinstance(include.get('line'), int) or include['line'] < 1 or not isinstance(include.get('include'), str):
                    raise ValueError('Invalid include anchor: '+str(key))
            seen[key] = r
        shards.append({'path':file.name,'count':len(rows),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    if not seen: raise ValueError('No verified shards')
    if len(seen) != sum(x['count'] for x in shards): raise ValueError('Cross-shard duplicate')
    return seen, shards

def validate_integrity(directory, shards, count):
    """Require the upstream exact-identity reconciliation before packet generation."""
    path = directory / f'integrity-000000-{count-1:06d}.json'
    if not path.is_file(): raise ValueError('Missing upstream source-reconciled integrity manifest')
    d = json.loads(path.read_bytes())
    if (d.get('phase1_gate') != 'FAIL_INCOMPLETE' or d.get('independent_approvals') != 0 or
        d.get('analyst_prepared_baseline') != 113 or
        d.get('unique_source_verified_machine_records') != count or
        d.get('shards') != [{'file':x['path'],'count':x['count'],'sha256':x['sha256']} for x in shards]):
        raise ValueError('Upstream source-reconciled integrity mismatch')
    return hashlib.sha256(path.read_bytes()).hexdigest()

def resolve_include(repo, source_path, inc, all_keys):
    """Only exact unique lexical paths; never pretend preprocessor search was proven."""
    if not inc or inc.startswith('/') or '\\' in inc or '..' in inc.split('/'):
        return 'invalid', []
    parent = str(PurePosixPath(source_path).parent)
    names = [inc, f'include/{inc}', f'{parent}/{inc}' if parent != '.' else inc]
    matches = sorted({(repo, n) for n in names if (repo,n) in all_keys})
    if len(matches) == 1: return 'lexical_candidate', matches
    if len(matches) > 1: return 'ambiguous', matches
    return 'unresolved', []

def packets(records, shards, max_packets=100, integrity_sha256=None):
    keys = set(records)
    links = collections.defaultdict(list)
    incoming = collections.Counter()
    for key, row in sorted(records.items()):
        for inc in row['whole_file_structure']['includes']:
            status, matches = resolve_include(key[0], key[1], inc['include'], keys)
            links[key].append({'line':inc['line'], 'include':inc['include'], 'resolution':status,
                               'candidate_targets':[{'repository':r,'path':p} for r,p in matches]})
            if status == 'lexical_candidate': incoming[matches[0]] += 1
    ranking = {'P0':0,'P1':1,'P2':2,'P3':3}
    ordered = sorted(records, key=lambda k:(ranking[records[k]['priority']],-incoming[k],k))
    out = []
    for key in ordered[:max_packets]:
        row = records[key]; i = row['identity']; s = row['whole_file_structure']
        unresolved = [x for x in links[key] if x['resolution'] != 'lexical_candidate']
        out.append({'identity':i, 'priority':row['priority'],
                    'whole_blob_sha256':s['whole_blob_sha256'],
                    'dossier_sha256':row['evidence']['dossier_sha256'],
                    'source_lines':s.get('source_lines'),
                    'candidate_incoming_include_edges':incoming[key],
                    'candidate_include_edges':links[key],
                    'unresolved_or_ambiguous_includes':len(unresolved),
                    'risk_flag_line_anchors':s.get('risk_flags_line_anchors', {}),
                    'review_tasks':['Independently read every line, including inactive branches and error paths',
                                    'Resolve all exported symbols and actual compiler include/search paths',
                                    'Verify native build/linker, save, emulator and editor consumers as applicable',
                                    'Distinguish source observations, inferred hazards and executed witnesses',
                                    'Obtain a genuine independent reviewer verdict tied to this exact blob'],
                    'state':'MACHINE_REVIEW_PACKET_NOT_WHOLE_FILE_SEMANTIC_DISPOSITION',
                    'independently_approved':False})
    return {'schema':SCHEMA, 'phase1_gate':'FAIL_INCOMPLETE', 'inventory_total':TOTAL,
            'verified_machine_triage_records':len(records), 'review_packets':len(out),
            'upstream_integrity_sha256':integrity_sha256,
            'prepared_whole_file_dispositions_added':0, 'independent_approvals_added':0,
            'limitations':['Only exact-path lexical include candidates are indexed',
                           'Includes absent from selected machine shards cannot be resolved',
                           'No preprocessor/compiler or whole-file semantic review is inferred'],
            'shards':shards,'packets':out}

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--shards',type=Path,default=Path('docs/phase1-machine-triage'))
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--max-packets',type=int,default=100)
    a=p.parse_args()
    if not 1 <= a.max_packets <= 1000:p.error('max-packets must be 1..1000')
    records, shards=load_shards(a.shards)
    integrity_sha256=validate_integrity(a.shards,shards,len(records))
    result=packets(records,shards,a.max_packets,integrity_sha256)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_bytes(canonical(result))
    print(json.dumps({'machine_records':len(records),'review_packets':len(result['packets']),
                      'semantic_dispositions_added':0,'independent_approvals_added':0,
                      'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()},sort_keys=True))
if __name__=='__main__':main()
