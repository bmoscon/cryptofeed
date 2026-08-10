'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import pathlib
import re


BANNED = re.compile(r'get_event_loop|ensure_future|run_until_complete|run_forever|set_event_loop_policy|set_event_loop\(|\batexit\b')
ALLOWLIST = {}


def test_no_legacy_loop_management():
    root = pathlib.Path(__file__).parents[2] / 'cryptofeed'
    violations = []
    for path in sorted(root.rglob('*.py')):
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            match = BANNED.search(line)
            if not match:
                continue
            pattern = match.group(0).strip('(').strip()
            if path.name in ALLOWLIST.get(pattern, set()):
                continue
            violations.append(f'{path.relative_to(root.parent)}:{lineno}: {line.strip()}')
    assert not violations, 'legacy loop management patterns found:\n' + '\n'.join(violations)
