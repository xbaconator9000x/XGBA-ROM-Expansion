#!/usr/bin/env python3
"""Fail-closed duplicate/count/link check for analyst whole-file candidates.

This does not alter the authoritative semantic mapping gate or grant approvals.
"""
import argparse
import re
import tempfile
from pathlib import Path

ENTRY = re.compile(r'^\|\s*\x60(?P<identity>[^\x60]+)\x60\s*\|\s*\[[^\]]+\]\((?P<doc>[^)]+\.md)\)\s*\|\s*pending independent review\s*\|\s*$')
COUNT = re.compile(r'\*\*Count:\s*(\d+)\s+distinct pinned upstream whole-file identities prepared')


def validate_register(content: str, directory: Path) -> int:
    rows = [line for line in content.splitlines() if line.startswith('| \x60'.replace('\\x60', chr(96)))]
    if not rows:
        raise ValueError('No registered candidates')
    seen = set()
    for row in rows:
        match = ENTRY.fullmatch(row)
        if match is None:
            raise ValueError(f'Unrecognized register row: {row}')
        identity = match.group('identity')
        if ':' not in identity or '/' not in identity.split(':', 1)[0]:
            raise ValueError(f'Malformed identity: {identity}')
        if identity in seen:
            raise ValueError(f'Duplicate whole-file identity: {identity}')
        seen.add(identity)
        doc = match.group('doc')
        if Path(doc).name != doc:
            raise ValueError(f'Non-local candidate link: {doc}')
        if not (directory / doc).is_file():
            raise ValueError(f'Missing candidate document: {doc}')
    declared = COUNT.search(content)
    if declared is None:
        raise ValueError('Missing declared distinct count')
    if int(declared.group(1)) != len(seen):
        raise ValueError(f'Declared {declared.group(1)} distinct files, found {len(seen)}')
    return len(seen)


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        (directory / 'a.md').write_text('a', encoding='utf-8')
        (directory / 'b.md').write_text('b', encoding='utf-8')
        sample = (
            '| \x60pret/pokefirered:foo\x60 | [A](a.md) | pending independent review |\n'
            '| \x60pret/pokefirered:bar\x60 | [B](b.md) | pending independent review |\n'
            '**Count: 2 distinct pinned upstream whole-file identities prepared**'
        ).replace('\\x60', chr(96))
        assert validate_register(sample, directory) == 2
        for bad in (
            sample.replace(':bar', ':foo'),
            sample.replace('Count: 2', 'Count: 3'),
            sample.replace('b.md', 'missing.md'),
        ):
            try:
                validate_register(bad, directory)
            except ValueError:
                pass
            else:
                raise AssertionError('Negative control unexpectedly passed')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        self_test()
        print('Register negative controls PASS (3/3)')
        return
    directory = Path(__file__).resolve().parents[1] / 'docs' / 'phase1-disposition-candidates'
    count = validate_register((directory / 'README.md').read_text(encoding='utf-8'), directory)
    print(f'Register integrity PASS: {count} distinct prepared; no independent approval inferred')


if __name__ == '__main__':
    main()
