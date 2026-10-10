#!/usr/bin/env python3
"""Merge pcov dumps (one JSON per request) into a line coverage report.

Usage: php_report.py <dump dir> <www dir> [--fail-under PERCENT] [--xml FILE]

pcov reports, per included file, every executable line with 1 (executed) or
-1 (not executed). Lines are merged across requests. PHP files under <www dir>
that no request ever loaded count with all their executable lines uncovered
(approximated by non-blank, non-comment lines), so dead files are visible.
"""
import glob
import json
import os
import re
import sys


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    dumps, www = argv[1], argv[2]
    fail_under = 0.0
    xml = None
    for i, arg in enumerate(argv):
        if arg == '--fail-under':
            fail_under = float(argv[i + 1])
        if arg == '--xml':
            xml = argv[i + 1]

    executable = {}
    covered = {}
    for path in glob.glob(os.path.join(dumps, '*.json')):
        try:
            with open(path) as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            continue
        for file, lines in data.items():
            executable.setdefault(file, set())
            covered.setdefault(file, set())
            for line, state in lines.items():
                if state in (1, -1):
                    executable[file].add(int(line))
                if state == 1:
                    covered[file].add(int(line))

    # files never loaded
    for root, _dirs, files in os.walk(www):
        for name in files:
            if not name.endswith('.php') or name == 'AltoRouter.php':
                continue
            full = os.path.join(root, name)
            key = '/var/www/' + os.path.relpath(full, www).replace(os.sep, '/')
            if key in executable:
                continue
            count = 0
            with open(full, encoding='utf-8', errors='replace') as handle:
                for line in handle:
                    stripped = line.strip()
                    if stripped and not stripped.startswith(('//', '#', '*', '/*', '<?php', '?>')):
                        count += 1
            executable[key] = set(range(1, count + 1))
            covered[key] = set()

    total_exec = total_cov = 0
    rows = []
    for file in sorted(executable):
        if file.endswith('AltoRouter.php') or file.endswith('coverage-prepend.php'):
            continue
        e, c = len(executable[file]), len(covered[file])
        total_exec += e
        total_cov += c
        pct = 100.0 * c / e if e else 100.0
        missing = sorted(executable[file] - covered[file])
        rows.append((file.replace('/var/www/', ''), e, c, pct, missing))
    width = max(len(r[0]) for r in rows) if rows else 10
    print(f"{'PHP file'.ljust(width)}  lines  covered   %   missing")
    for name, e, c, pct, missing in rows:
        shown = ', '.join(str(m) for m in missing[:12]) + (' ...' if len(missing) > 12 else '')
        print(f"{name.ljust(width)}  {e:5d}  {c:7d}  {pct:5.1f}  {shown}")
    total = 100.0 * total_cov / total_exec if total_exec else 100.0
    print(f"{'TOTAL'.ljust(width)}  {total_exec:5d}  {total_cov:7d}  {total:5.1f}")
    if xml:
        with open(xml, 'w') as handle:
            handle.write('<?xml version="1.0"?>\n<coverage line-rate="%.4f">\n' % (total / 100.0))
            for name, e, c, pct, _missing in rows:
                handle.write('  <file name="%s" lines="%d" covered="%d" rate="%.4f"/>\n' % (name, e, c, pct / 100.0))
            handle.write('</coverage>\n')
    if total < fail_under:
        print(f"FAIL: PHP coverage {total:.1f}% is below {fail_under}%")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
