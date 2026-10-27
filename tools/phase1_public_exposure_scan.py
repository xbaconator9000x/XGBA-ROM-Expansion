#!/usr/bin/env python3
"""Read-only public repository exposure scan; never print matched content."""
import argparse
import gzip
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path

MAX_BLOB = 60_000_000
MAX_MEMBER = 100_000_000
MAX_TOTAL = 1_000_000_000
MAX_FINDINGS = 500

def git(*args):
    return subprocess.check_output(['git', *args], stderr=subprocess.PIPE)

def patterns(data):
    text = data.decode('utf-8', 'replace')
    findings = set()
    low = text.lower()
    if ('chat' + 'gpt') in low or '<|im_start|>' in text or 'user knowledge memories' in low:
        findings.add('dialogue_marker')
    if (re.search(r'"role"\s*:\s*"user"', text, re.I) and
            re.search(r'"role"\s*:\s*"assistant"', text, re.I)):
        findings.add('dialogue_role_pair')
    if (re.search(r'(?m)^\s*user\s*:\s+\S', text, re.I) and
            re.search(r'(?m)^\s*assistant\s*:\s+\S', text, re.I)):
        findings.add('dialogue_label_pair')
    if re.search(r'(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|AKIA[0-9A-Z]{16}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)', text):
        findings.add('credential_signature')
    if re.search(r'\bsk-[A-Za-z0-9_-]{30,}\b', text):
        findings.add('api_key_signature')
    return sorted(findings)

def scan():
    stats = {'unique_blobs': 0, 'archive_members': 0, 'compressed_members': 0,
             'skipped_oversize': 0, 'scan_errors': 0, 'commits_checked': 0}
    findings = []
    visited = set()
    total_expanded = [0]

    def issue(kind, label, blob):
        if len(findings) < MAX_FINDINGS:
            findings.append({'kind': kind, 'location': label[:300], 'blob': blob})

    def inspect(data, label, blob, depth=0):
        if len(data) > MAX_MEMBER or total_expanded[0] + len(data) > MAX_TOTAL:
            stats['skipped_oversize'] += 1
            issue('uninspected_size_limit', label, blob)
            return
        total_expanded[0] += len(data)
        if depth < 3 and zipfile.is_zipfile(io.BytesIO(data)):
            try:
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    for member in archive.infolist():
                        if member.is_dir():
                            continue
                        stats['archive_members'] += 1
                        child = label + '!' + member.filename
                        if member.file_size > MAX_MEMBER:
                            stats['skipped_oversize'] += 1
                            issue('uninspected_size_limit', child, blob)
                            continue
                        with archive.open(member) as stream:
                            raw = stream.read(MAX_MEMBER + 1)
                        inspect(raw, child, blob, depth + 1)
                return
            except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
                stats['scan_errors'] += 1
                issue('archive_read_error:' + type(exc).__name__, label, blob)
                return
        if depth < 3 and data.startswith(b'\x1f\x8b'):
            try:
                with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
                    raw = stream.read(MAX_MEMBER + 1)
                stats['compressed_members'] += 1
                inspect(raw, label + '!gzip', blob, depth + 1)
                return
            except (OSError, EOFError, ValueError) as exc:
                stats['scan_errors'] += 1
                issue('gzip_read_error:' + type(exc).__name__, label, blob)
                return
        if re.search(r'(?:chat.?export|conversation|transcript|chat.?gpt)', label, re.I):
            issue('suspicious_filename', label, blob)
        if b'\x00' in data[:4096]:
            return
        for kind in patterns(data):
            issue(kind, label, blob)

    lines = git('rev-list', '--objects', '--all').decode().splitlines()
    for line in lines:
        sha, _, path = line.partition(' ')
        if sha in visited:
            continue
        visited.add(sha)
        if git('cat-file', '-t', sha).strip() != b'blob':
            continue
        size = int(git('cat-file', '-s', sha))
        if size > MAX_BLOB:
            stats['skipped_oversize'] += 1
            issue('uninspected_blob_size', path or '(unnamed)', sha)
            continue
        data = git('cat-file', 'blob', sha)
        stats['unique_blobs'] += 1
        inspect(data, path or '(unnamed)', sha)
    for sha in git('rev-list', '--all').decode().splitlines():
        stats['commits_checked'] += 1
        message = git('log', '-1', '--format=%B', sha)
        for kind in patterns(message):
            issue('commit_' + kind, '(commit message)', sha)
    return {'schema': 'xgba-public-exposure-readonly-v1',
            'status': 'FINDINGS_REQUIRE_REVIEW' if findings else 'NO_SIGNATURES_FOUND_IN_SCANNED_SCOPE',
            'scope': 'Git objects reachable from fetched refs, nested ZIP/gzip members and commit messages; excludes unreachable objects, PR comments and Actions logs',
            'stats': stats, 'findings': findings,
            'findings_truncated': len(findings) >= MAX_FINDINGS,
            'expanded_bytes': total_expanded[0]}

def selftest():
    assert 'dialogue_role_pair' in patterns(b'{"role":"' + b'user"}\n{"role":"' + b'assistant"}')
    assert 'credential_signature' in patterns(b'ghp_' + b'A' * 36)
    assert not patterns(b'ordinary source file: int main(void) { return 0; }')
    print('Exposure scanner synthetic controls PASS')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=Path('audit-output/public-exposure-scan.json'))
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        selftest()
        return
    result = scan()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'stats': result['stats'],
                      'finding_count': len(result['findings'])}, sort_keys=True))
    if result['findings'] or result['stats']['skipped_oversize'] or result['stats']['scan_errors']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
