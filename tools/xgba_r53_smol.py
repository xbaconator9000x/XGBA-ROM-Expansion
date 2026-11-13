#!/usr/bin/env python3
"""Bounded original pokeemerald-expansion Smol graphics codec (modes 1-6).

This is an independent host implementation of the documented compressed
bitstream format used by Heart & Soul and related Emerald-derived games.
Reference semantics: PokemonHnS-Development/pokehns-expansion,
src/decompress.c, include/decompress.h, source 167aa6d537b109bb229c231ddce4616974c4da71.
Independent external cross-check: PokeDaisy v1.4.0's HnS icon SHA-1 witness.
No original ROM bytes are committed to XGBA.

Mode 1 is raw Smol 16-bit symbols plus literal/run instructions. Modes 2-6
are tANS-compressed symbols and/or instruction bytes, with modes 3 and 6
delta-coding each symbol's nibbles. All output is bounded and validated.
"""
from __future__ import annotations
import struct

class SmolError(ValueError):
    pass

def _u32(source, off):
    if off < 0 or off + 4 > len(source):
        raise SmolError("Truncated Smol word")
    return struct.unpack_from("<I", source, off)[0]

def _frequency_table(src, offset):
    freq=[0]*16
    for i in range(3):
        word=_u32(src,offset+4*i)
        for j in range(5):
            freq[i*5+j]=(word>>(6*j))&63
        freq[15]|=((word>>30)&3)<<(2*i)
    if sum(freq)!=64:
        raise SmolError("Smol tANS table frequency sum is not 64")
    result=[]
    for symbol,count in enumerate(freq):
        for j in range(count,2*count):
            k=0
            while (j<<k)<64:
                k+=1
                if k>6:raise SmolError("Smol invalid tANS table")
            result.append((symbol,k,(j<<k)-64,(1<<k)-1))
    if len(result)!=64:
        raise SmolError("Smol invalid tANS occupancy")
    return result

class _Bits:
    def __init__(self,src,at,words,initial):
        if not words or at+4*words>len(src):
            raise SmolError("Missing or truncated Smol tANS bitstream")
        self.src=src
        self.at=at
        self.words=words
        self.index=0
        self.shift=0
        self.bits=_u32(src,at)
        self.state=initial

    def read(self,table):
        if not 0<=self.state<64:
            raise SmolError("Smol tANS state outside 64-element table")
        symbol,k,y,mask=table[self.state]
        self.state=y+((self.bits>>self.shift)&mask)
        self.shift+=k
        if self.shift>=32:
            self.index+=1
            self.shift-=32
            if self.index>=self.words:
                if self.shift:
                    raise SmolError("Smol tANS stream ended with a partial code")
                self.bits=0
            else:
                self.bits=_u32(self.src,self.at+self.index*4)
                if self.shift:
                    self.state+=(self.bits&((1<<self.shift)-1))<<(k-self.shift)
        return symbol

def _instructions(lo,syms,outbytes):
    if outbytes%2:raise SmolError("Smol output must be 16-bit aligned")
    limit=outbytes//2
    words=[]
    i=0
    sym=0
    while i<len(lo):
        length=lo[i]&127
        extended=bool(lo[i]&128)
        i+=1
        if extended:
            if i>=len(lo):raise SmolError("Truncated Smol extended length")
            length|=lo[i]<<7
            i+=1
        if i>=len(lo):raise SmolError("Truncated Smol offset")
        offset=lo[i]&127
        extended=bool(lo[i]&128)
        i+=1
        if extended:
            if i>=len(lo):raise SmolError("Truncated Smol extended offset")
            offset|=lo[i]<<7
            i+=1
        if length:
            if sym>=len(syms) or not offset or len(words)+1+length>limit:
                raise SmolError("Impossible Smol run")
            words.append(syms[sym]);sym+=1
            if offset>len(words):
                raise SmolError("Smol backreference outside decoded data")
            for _ in range(length):
                words.append(words[-offset])
        else:
            if sym+offset>len(syms) or len(words)+offset>limit:
                raise SmolError("Smol literal count exceeds original size")
            words.extend(syms[sym:sym+offset]);sym+=offset
    if len(words)!=limit:
        raise SmolError("Smol output length differs from authenticated source header")
    return struct.pack("<"+str(len(words))+"H",*words)

def decode(src,offset=0,*,max_output=65536):
    """Decode original Smol tile data. Returns bytes; never guesses formats."""
    if not isinstance(src,(bytes,bytearray)) or offset<0 or offset+8>len(src):
        raise SmolError("Smol header out of range")
    h0=_u32(src,offset)
    h1=_u32(src,offset+4)
    mode=h0&15
    if mode not in (1,2,3,4,5,6):
        raise SmolError("Unsupported Smol mode")
    total=((h0>>4)&0x3fff)*4
    sym_count=(h0>>18)&0x3fff
    lo_count=(h1>>19)&0x1fff
    stream_words=(h1>>6)&0x1fff
    if not (32<=total<=max_output and total%32==0 and
            0<sym_count<=16383 and 0<lo_count<=8191):
        raise SmolError("Smol output or symbol count out of bounds")
    lo_coded=mode in (4,5,6)
    sym_coded=mode in (2,3,5,6)
    delta=mode in (3,6)
    freq_size=(12 if lo_coded else 0)+(12 if sym_coded else 0)
    ptr=offset+8
    bits=_Bits(src,ptr+freq_size,stream_words,h1&63) if (lo_coded or sym_coded) else None
    if lo_coded:
        tab=_frequency_table(src,ptr);ptr+=12
        lo=bytearray(lo_count)
        for i in range(lo_count):
            lo[i]=bits.read(tab)|(bits.read(tab)<<4)
    if sym_coded:
        tab=_frequency_table(src,ptr);ptr+=12
        syms=[]
        previous=0
        for _ in range(sym_count):
            value=0
            for shift in (0,4,8,12):
                digit=bits.read(tab)
                if delta:
                    previous=(previous+digit)&15
                    digit=previous
                value|=digit<<shift
            syms.append(value)
    ptr=offset+8+freq_size+4*stream_words
    if not sym_coded:
        if ptr+2*sym_count>len(src):
            raise SmolError("Truncated Smol literal symbols")
        syms=list(struct.unpack_from("<"+str(sym_count)+"H",src,ptr))
        ptr+=2*sym_count
    if not lo_coded:
        if ptr+lo_count>len(src):
            raise SmolError("Truncated Smol instructions")
        lo=src[ptr:ptr+lo_count]
    return _instructions(lo,syms,total)
