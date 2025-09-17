#!/usr/bin/env python
"""Add ISO8601 timestamps to MELD REMD log files.

Reads remd_*.log (or any provided patterns) and writes a side-by-side
file remd_XXX.ts.log with each line prefixed by UTC and local timestamps.

Usage:
  python timestamp_log_lines.py                # process all remd_*.log
  python timestamp_log_lines.py remd_010.log   # process specific file
  python timestamp_log_lines.py --inplace      # overwrite originals (backup .bak)
  python timestamp_log_lines.py --glob "remd_*.log"  # custom glob

Notes:
- Keeps original ordering; does not attempt to parse step numbers.
- Idempotent: skips lines that already look timestamped unless --force.
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from typing import Iterable, List

STAMP_RE = re.compile(r"^\[\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z]")

def iter_files(patterns: List[str]) -> Iterable[str]:
    for pat in patterns:
        for path in sorted(glob.glob(pat)):
            if os.path.isfile(path):
                yield path

def stamp_line(line: str) -> str:
    if line.strip() == "":
        return line
    # Skip if already timestamped
    if STAMP_RE.match(line):
        return line
    now_utc = datetime.now(timezone.utc)
    utc_str = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Local time (without tz name to keep concise)
    local_dt = datetime.now().astimezone()
    local_str = local_dt.strftime("%Y-%m-%d %H:%M:%S%z")
    return f"[{utc_str}][{local_str}] {line}"

def process_file(path: str, inplace: bool, force: bool, stdout: bool=False) -> None:
    out_path = path if inplace else path.replace('.log', '.ts.log')
    backup_path = None
    if inplace:
        backup_path = path + '.bak'
        shutil.copy2(path, backup_path)
    tmp_path = out_path + '.tmp'
    total = 0
    stamped = 0
    with open(path, 'r', encoding='utf-8', errors='replace') as fin, open(tmp_path, 'w', encoding='utf-8') as fout:
        for line in fin:
            total += 1
            new_line = line if (not force and STAMP_RE.match(line)) else stamp_line(line)
            if new_line != line:
                stamped += 1
            fout.write(new_line)
            if stdout:
                sys.stdout.write(new_line)
    os.replace(tmp_path, out_path)
    print(f"[timestamp] {path} -> {out_path} (lines={total}, newly_stamped={stamped})")
    if inplace:
        print(f"[timestamp] backup original: {backup_path}")


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Add timestamps to MELD REMD logs.")
    p.add_argument('files', nargs='*', help='Explicit files to process (default: glob remd_*.log)')
    p.add_argument('--glob', dest='glob_pattern', default='remd_*.log', help='Glob pattern (default remd_*.log)')
    p.add_argument('--inplace', action='store_true', help='Overwrite original file (writes .bak backup)')
    p.add_argument('--force', action='store_true', help='Stamp even if line already appears timestamped')
    p.add_argument('--stdout', action='store_true', help='Echo stamped lines to stdout while processing')
    args = p.parse_args(argv)

    patterns = args.files if args.files else [args.glob_pattern]
    matched = list(iter_files(patterns))
    if not matched:
        print('[timestamp] No files matched; nothing to do.', file=sys.stderr)
        return 1
    for path in matched:
        process_file(path, inplace=args.inplace, force=args.force, stdout=args.stdout)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
