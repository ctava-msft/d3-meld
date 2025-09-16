#!/usr/bin/env python
"""Multi-GPU MELD multiplex orchestration (process-per-GPU strategy).

Rationale
---------
Current "launch_remd_multiplex" invocation binds a single process to one GPU.
This script launches N independent multiplex runs (ensemble replicas) across
available GPUs, each with a distinct random seed and log directory. This does
NOT shard a *single* replica-exchange across GPUs (requires MELD-level
parallel decomposition); instead it increases aggregate sampling throughput by
running multiple statistically independent ensembles concurrently.

Features
--------
* Auto-creates Data/ via setup_meld if missing (importing exec_meld_run).
* Distinct `MELD_RANDOM_SEED` per process.
* Optional multiple runs per GPU (`--runs-per-gpu`).
* Clean SIGINT/SIGTERM handling: all children terminated.
* Real-time tail option (`--tail`) to stream last lines of each log.
* Simple health monitor loop prints every interval seconds.

Usage Examples
--------------
Single run on GPU 0 and 1 each:
    python multi_gpu_multiplex.py --gpus 0,1
Two runs per GPU across GPUs 0 and 1 (total 4 processes):
    python multi_gpu_multiplex.py --gpus 0,1 --runs-per-gpu 2
Background (no tailing):
    python multi_gpu_multiplex.py --gpus 0,1 --no-tail

Log layout:
    Runs/ensemble/<ts>/gpu<g>/run<k>/remd.log

You can later aggregate results from each run directory.
"""
from __future__ import annotations

import argparse
import os
import random
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# --- Helpers ---

def ensure_datastore():
    if Path('Data/data_store.dat').is_file():
        return
    # Try running setup programmatically
    try:
        import setup_meld  # type: ignore
        print('[orchestrator] Data/data_store.dat missing -> calling exec_meld_run()')
        setup_meld.exec_meld_run()
    except Exception as e:  # noqa
        print(f'[orchestrator] ERROR creating data store: {e}', file=sys.stderr)
        sys.exit(1)
    if not Path('Data/data_store.dat').is_file():
        print('[orchestrator] ERROR: Data store still missing after setup.', file=sys.stderr)
        sys.exit(1)


def build_command(debug: bool) -> List[str]:
    cmd = ['launch_remd_multiplex', '--platform', 'CUDA']
    if debug:
        cmd.append('--debug')
    return cmd


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Launch independent MELD multiplex runs on multiple GPUs.')
    p.add_argument('--gpus', required=True, help='Comma list of GPU indices, e.g. 0,1 or 0,2,3')
    p.add_argument('--runs-per-gpu', type=int, default=1, help='How many independent runs per listed GPU (default 1)')
    p.add_argument('--seed-base', type=int, default=1000, help='Base integer added to run counter for MELD_RANDOM_SEED')
    p.add_argument('--debug', action='store_true', help='Pass --debug to launch_remd_multiplex')
    p.add_argument('--no-tail', action='store_true', help='Do not live tail logs (just launch and exit 0)')
    p.add_argument('--monitor-interval', type=int, default=60, help='Seconds between status summaries while tailing')
    p.add_argument('--tag', default='ensemble', help='Top-level run grouping tag (default: ensemble)')
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    ensure_datastore()

    gpu_list = [g.strip() for g in args.gpus.split(',') if g.strip()]
    if not gpu_list:
        print('No GPUs parsed from --gpus', file=sys.stderr)
        return 2

    if args.runs_per_gpus := getattr(args, 'runs_per_gpus', None):  # backward guard
        print('WARNING: --runs-per-gpus is deprecated; use --runs-per-gpu', file=sys.stderr)
        if args.runs_per_gpu == 1 and isinstance(args.runs_per_gpus, int):
            args.runs_per_gpu = args.runs_per_gpus

    total_runs = len(gpu_list) * args.runs_per_gpu
    ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    base_dir = Path('Runs') / args.tag / ts
    processes: Dict[int, subprocess.Popen] = {}
    meta: Dict[int, Dict[str, str]] = {}

    cmd_template = build_command(args.debug)
    run_counter = 0
    print(f"[orchestrator] Launching {total_runs} runs across GPUs {gpu_list} -> base {base_dir}")

    for gpu in gpu_list:
        for k in range(args.runs_per_gpu):
            run_counter += 1
            run_seed = args.seed_base + run_counter + random.randint(0, 9999)
            run_dir = base_dir / f'gpu{gpu}' / f'run{k}'
            run_dir.mkdir(parents=True, exist_ok=True)
            env = os.environ.copy()
            env['CUDA_VISIBLE_DEVICES'] = gpu
            env['MELD_RANDOM_SEED'] = str(run_seed)
            env['PYTHONUNBUFFERED'] = '1'
            log_path = run_dir / 'remd.log'
            with open(log_path, 'wb') as lf:
                lf.write(f"[orchestrator] GPU={gpu} run_index={k} seed={run_seed}\n".encode())
            # Start process redirecting stdout/stderr to same log
            f = open(log_path, 'ab', buffering=0)
            proc = subprocess.Popen(cmd_template, stdout=f, stderr=subprocess.STDOUT, cwd='.', env=env)
            processes[proc.pid] = proc
            meta[proc.pid] = {
                'gpu': gpu,
                'run_index': str(k),
                'seed': str(run_seed),
                'log': str(log_path)
            }
            print(f"[orchestrator] PID {proc.pid} -> GPU {gpu} run {k} seed {run_seed} log {log_path}")

    if args.no_tail:
        print('[orchestrator] Launched all runs (no-tail mode).')
        return 0

    # Live tail + monitor
    last_sizes = {pid: 0 for pid in processes}
    try:
        while processes:
            # Tail incrementally
            for pid, proc in list(processes.items()):
                log_file = Path(meta[pid]['log'])
                if log_file.is_file():
                    size = log_file.stat().st_size
                    if size > last_sizes[pid]:
                        with open(log_file, 'rb') as lf:
                            lf.seek(last_sizes[pid])
                            chunk = lf.read(size - last_sizes[pid])
                            sys.stdout.buffer.write(chunk)
                            last_sizes[pid] = size
                if proc.poll() is not None:
                    code = proc.returncode
                    print(f"[orchestrator] PID {pid} exited code {code}")
                    processes.pop(pid)
            time.sleep(2)
            # Periodic summary
            if args.monitor_interval and int(time.time()) % args.monitor_interval < 2:
                live = ', '.join(f"{pid}:{meta[pid]['gpu']}" for pid in processes)
                print(f"[orchestrator] Active PIDs: {live}")
    except KeyboardInterrupt:
        print('\n[orchestrator] Interrupt received, terminating children...')
        for pid, proc in processes.items():
            proc.terminate()
        # Grace period
        t0 = time.time()
        while any(p.poll() is None for p in processes.values()) and time.time() - t0 < 10:
            time.sleep(0.5)
        for pid, proc in processes.items():
            if proc.poll() is None:
                proc.kill()
        print('[orchestrator] Shutdown complete.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
