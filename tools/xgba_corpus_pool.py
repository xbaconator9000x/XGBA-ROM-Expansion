#!/usr/bin/env python3
"""R33 host-side lazy reader for ALL R32 sharded source-world resources.

Does not patch ROMs or execute scripts. Each input game retains its own map
group/number and each exported asset keeps its original source namespace.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from types import MappingProxyType

import xgba_resource_sidecar as sidecar

MAX_INDEX_BYTES=256*1024*1024
MAX_RESOURCES=250000
MAX_SHARDS=20000
DEFAULT_RESOURCE_BYTES=16*1024*1024
DEFAULT_STAGED_BYTES=16*1024*1024
DEFAULT_WINDOW_BYTES=16384
SOURCE=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z')
RESOURCE=re.compile(r'corpus\.[0-9a-f]{64}\Z')
SHA=re.compile(r'[0-9a-f]{64}\Z')
FILENAME=re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,159}\Z')


class PoolError(ValueError):
    pass


def _object(pairs):
    result={}
    for k,v in pairs:
        if k in result:raise PoolError('Duplicate index JSON key')
        result[k]=v
    return result


def _constant(value):
    raise PoolError('Unsupported JSON constant: '+value)


def _count(value,label,zero=False):
    if type(value) is not int or (value<0 if zero else value<=0):
        raise PoolError('Invalid '+label)
    return value


def _filename(value):
    if not isinstance(value,str) or not FILENAME.fullmatch(value):
        raise PoolError('Unsafe shard filename')
    return value


def _relpath(value):
    if not isinstance(value,str) or not value or value.startswith('/') or \
       '\0' in value or '\\' in value or any(x in ('','.', '..') for x in value.split('/')):
        raise PoolError('Unsafe original relative path')
    return value


def _id(source,path):
    return 'corpus.'+hashlib.sha256((source+'\0'+path).encode('utf8')).hexdigest()


class CorpusPool:
    """R32 R/O multi-shard pool; SHA-check every exposed payload before use.

    Index/manifest counts and provenance are checked eagerly, but asset data
    is loaded lazily. A bad reload never changes the previous live pool.
    """

    def __init__(self,index_path,*,max_resource_bytes=DEFAULT_RESOURCE_BYTES,
                 max_staged_bytes=DEFAULT_STAGED_BYTES,
                 max_window_bytes=DEFAULT_WINDOW_BYTES,chunk_size=65536):
        self.max_resource_bytes=_count(max_resource_bytes,'resource byte cap')
        self.max_staged_bytes=_count(max_staged_bytes,'staged byte cap')
        self.max_window_bytes=_count(max_window_bytes,'window byte cap')
        self.chunk_size=_count(chunk_size,'SHA verification chunk size')
        if self.chunk_size>sidecar.MAX_CHUNK_SIZE:
            raise PoolError('Invalid sidecar chunk size')
        self._resources={}
        self._maps={}
        self._sources={}
        self._manifests={}
        self._staged={}
        self.open(index_path)

    @property
    def resource_count(self):return len(self._resources)

    @property
    def source_ids(self):return tuple(self._sources)

    @property
    def shard_count(self):return len(self._manifests)

    @property
    def staged_bytes(self):return sum(len(v) for v in self._staged.values())

    @property
    def staged_ids(self):return tuple(self._staged)

    def close(self):
        self._resources={}
        self._maps={}
        self._sources={}
        self._manifests={}
        self._staged={}

    def open(self,index_path):
        path=Path(index_path).resolve(strict=True)
        if not path.is_file():raise PoolError('Index must be a file')
        with path.open('rb') as f:raw=f.read(MAX_INDEX_BYTES+1)
        if len(raw)>MAX_INDEX_BYTES:raise PoolError('Index exceeds size bound')
        try:
            doc=json.loads(raw.decode('utf8'),object_pairs_hook=_object,
                           parse_constant=_constant)
        except (UnicodeError,json.JSONDecodeError) as exc:
            raise PoolError('Invalid corpus JSON') from exc
        if not isinstance(doc,dict) or doc.get('format')!='xgba-whole-corpus-index' or \
           type(doc.get('version')) is not int or doc['version']!=1 or \
           doc.get('storage_mode')!='complete_sharded_sidecar':
            raise PoolError('Incompatible or inventory-only corpus')
        sources,shards=doc.get('source_reports'),doc.get('shards')
        if not isinstance(sources,list) or not 1<=len(sources)<=1000 or \
           not isinstance(shards,list) or len(shards)>MAX_SHARDS:
            raise PoolError('Invalid whole-corpus source/shard catalogue')
        manifests={}
        for shard in shards:
            if not isinstance(shard,dict):raise PoolError('Malformed shard')
            name=_filename(shard.get('manifest'))
            if name in manifests:raise PoolError('Duplicate shard filename')
            input_path=path.parent/name
            if input_path.is_symlink():raise PoolError('Symlinked shard manifest')
            m=sidecar.load_manifest(input_path)
            if m.data_path.parent!=path.parent:
                raise PoolError('Shard data outside corpus directory')
            if _filename(shard.get('data_file'))!=m.data_path.name or \
               _count(shard.get('resources'),'shard count')!=len(m.resources) or \
               _count(shard.get('payload_bytes'),'shard bytes',True)!=sum(
                   r.length for r in m.resources.values()):
                raise PoolError('Shard metadata mismatch')
            manifests[name]=m
        available={}
        original_maps={}
        source_ids={}
        covered={s:set() for s in manifests}
        total=0
        for src in sources:
            if not isinstance(src,dict):raise PoolError('Malformed source')
            world,digest=src.get('source_id'),src.get('source_snapshot_sha256')
            if not isinstance(world,str) or not SOURCE.fullmatch(world) or \
               not isinstance(digest,str) or not SHA.fullmatch(digest) or \
               world in source_ids:
                raise PoolError('Invalid or duplicate source identity')
            source_ids[world]=digest
            files,maps=src.get('resources'),src.get('original_maps')
            if not isinstance(files,list) or not isinstance(maps,list) or \
               _count(src.get('file_count'),'source file count')!=len(files):
                raise PoolError('Source catalogue count mismatch')
            paths=set()
            byte_count=0
            for item in files:
                if not isinstance(item,dict):raise PoolError('Malformed source item')
                rel=_relpath(item.get('path'))
                rid=item.get('resource_id')
                length=_count(item.get('bytes'),'source bytes',True)
                checksum=item.get('sha256')
                if not isinstance(rid,str) or not RESOURCE.fullmatch(rid) or \
                   rid!=_id(world,rel) or item.get('source_id')!=world or \
                   rid in available or rel in paths or \
                   not isinstance(checksum,str) or not SHA.fullmatch(checksum):
                    raise PoolError('Duplicate or non-original source resource identity')
                paths.add(rel)
                byte_count+=length
                total+=length
                if length:
                    shard_name=_filename(item.get('shard'))
                    m=manifests.get(shard_name)
                    if item.get('storage_status')!='verified_sidecar' or m is None:
                        raise PoolError('Missing stored input source resource')
                    if m.source_identity.id!=world or m.source_identity.sha256!=digest:
                        raise PoolError('Shard belongs to different source snapshot')
                    record=m.resources.get(rid)
                    if record is None or record.length!=length or \
                       record.sha256!=checksum or record.offset!=item.get('shard_offset'):
                        raise PoolError('Indexed source bytes do not match shard')
                    covered[shard_name].add(rid)
                    available[rid]=(world,rel,record,m)
                else:
                    if item.get('storage_status')!='verified_empty_source' or \
                       checksum!=hashlib.sha256(b'').hexdigest() or 'shard' in item:
                        raise PoolError('Malformed empty original source')
                    available[rid]=(world,rel,None,None)
            if _count(src.get('byte_count'),'source total bytes',True)!=byte_count:
                raise PoolError('Source total byte count mismatch')
            for m in maps:
                if not isinstance(m,dict) or m.get('source_id')!=world:
                    raise PoolError('Malformed source map')
                group=_count(m.get('group'),'original group',True)
                number=_count(m.get('map'),'original map number',True)
                if group>65535 or number>65535:
                    raise PoolError('Original map identity exceeds 16 bits')
                key=(world,group,number)
                if key in original_maps:raise PoolError('Duplicate original map identity')
                original_maps[key]=MappingProxyType(dict(m))

        if len(available)>MAX_RESOURCES:raise PoolError('Too many source resources')
        for name,m in manifests.items():
            if covered[name]!=set(m.resources):
                raise PoolError('Unindexed / orphaned sidecar resource')
        summary=doc.get('summary')
        if not isinstance(summary,dict) or summary.get('catalogued_files')!=len(available) or \
           summary.get('catalogued_bytes')!=total or \
           summary.get('source_count')!=len(source_ids) or \
           summary.get('original_map_count')!=len(original_maps) or \
           summary.get('runtime_compatible_resources')!=0:
            raise PoolError('Corpus counts or executable compatibility claim mismatch')

        # Audit original map identities against real source map-group bytes.
        # Never trust a new numbering scheme introduced only in the index.
        for src in sources:
            world=src['source_id']
            gid=_id(world,'data/maps/map_groups.json')
            original=available.get(gid)
            if original is None:
                if src['original_maps']:raise PoolError('Original map-group file missing')
                continue
            record=original[2]
            if record is None or record.length>2*1024*1024:
                raise PoolError('Missing or huge map-group source')
            try:
                raw=b''.join(sidecar.iter_resource_chunks(original[3],gid,self.chunk_size))
                groups=json.loads(raw.decode('utf8'),object_pairs_hook=_object,
                                  parse_constant=_constant)
                actual=[(g,n,name)
                        for g,group in enumerate(groups['group_order'])
                        for n,name in enumerate(groups[group])]
            except (UnicodeError,ValueError,KeyError,TypeError) as exc:
                raise PoolError('Invalid original map-group bytes') from exc
            expected=[(m['group'],m['map'],m['name']) for m in src['original_maps']]
            if actual!=expected:
                raise PoolError('Source original map IDs differ from indexed IDs')

        self._resources=available
        self._maps=original_maps
        self._sources=source_ids
        self._manifests=manifests
        self._staged={}
        return self

    def find(self,world,path):
        rel=_relpath(path)
        rid=_id(world,rel)
        entry=self._resources.get(rid)
        return rid if entry is not None and entry[:2]==(world,rel) else None

    def find_original_map(self,source_id,group,map_number):
        return self._maps.get((source_id,group,map_number))

    def source_of(self,rid):
        try:
            world,path,record,_=self._resources[rid]
        except KeyError as exc:
            raise PoolError('Unknown source resource') from exc
        return world,path,0 if record is None else record.length

    def read_window(self,rid,offset,length):
        """Verify *whole* v1 source digest before returning a 16-KiB window.

        v1 has no authenticated chunk hashes: every requested window rehashes
        the entire resource. This is safe but not yet high-throughput streaming.
        """
        length=_count(length,'window bytes',True)
        if length>self.max_window_bytes or type(offset) is not int or offset<0:
            raise PoolError('Window exceeds configured host bounds')
        try:
            _,_,record,m=self._resources[rid]
        except KeyError as exc:
            raise PoolError('Unknown source resource') from exc
        size=record.length if record is not None else 0
        if offset>size or length>size-offset:
            raise PoolError('Window outside resource')
        if record is None:return b''
        result=bytearray()
        pos=0
        for block in sidecar.iter_resource_chunks(m,rid,self.chunk_size):
            low=max(0,offset-pos)
            high=min(len(block),offset+length-pos)
            if high>low:result.extend(block[low:high])
            pos+=len(block)
        if pos!=size or len(result)!=length:
            raise PoolError('Source changed during verification')
        return bytes(result)

    def stage(self,rid):
        try:
            _,_,record,m=self._resources[rid]
        except KeyError as exc:
            raise PoolError('Unknown source resource') from exc
        size=record.length if record is not None else 0
        if size>self.max_resource_bytes:
            raise PoolError('Resource exceeds bounded host staging capacity')
        previous=self._staged.get(rid)
        used=self.staged_bytes-(len(previous) if previous is not None else 0)
        if size>self.max_staged_bytes-used:
            raise PoolError('Resource would exceed host memory budget')
        candidate=bytearray()
        if record is not None:
            for chunk in sidecar.iter_resource_chunks(m,rid,self.chunk_size):
                candidate.extend(chunk)
            if len(candidate)!=size:
                raise PoolError('Source changed during staging')
        # Commit only after complete SHA-256 validation.
        self._staged[rid]=bytes(candidate)
        return memoryview(self._staged[rid])

    def staged_resource(self,rid):
        try:return memoryview(self._staged[rid])
        except KeyError as exc:raise PoolError('Resource is not staged') from exc

    def unstage(self,rid):
        self._staged.pop(rid,None)
