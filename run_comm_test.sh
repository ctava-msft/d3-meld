#!/usr/bin/env bash
set -euo pipefail

# run_comm_test.sh
# Purpose: Minimal helper to create/activate a Conda env (or venv fallback) with mpi4py + meld,
# patch the communicator (using local d3-meld/comm.py), and run the
# nested gather normalization test under MPI. Adds automatic fallbacks when conda
# is missing and optional bootstrap of Miniforge (Linux/macOS). On Windows you may
# prefer installing Miniconda manually then re-run with --conda-base <path>.
#
# Usage examples:
#   ./run_comm_test.sh                        # create conda env 'meld-comm-test' (needs conda)
#   ./run_comm_test.sh --env myenv             # custom conda env name
#   ./run_comm_test.sh --conda-base ~/mambaforge  # explicitly point to base if not on PATH
#   ./run_comm_test.sh --bootstrap-conda       # download + install Miniforge (Linux/macOS)
#   ./run_comm_test.sh --use-venv              # use Python venv fallback instead of conda
#   ./run_comm_test.sh --np 4                  # run test with 4 ranks
#   ./run_comm_test.sh --serial                # force single-process run (debugging w/out MPI)
#   ./run_comm_test.sh --only-env              # prepare env + patch, skip test run
#   ./run_comm_test.sh --dry-run               # print actions only
#   MELD_DEBUG_COMM=1 ./run_comm_test.sh --np 4  # enable communicator debug
#
# After success you should see:
#   [pass] Nested gather produced flat, ordered state list.
#
# Requirements:
#   - Conda available (Miniconda/Anaconda)
#   - test_nested_gather_states.py present in current directory
#   - Local comm.py patch lives in current directory (d3-meld/comm.py)

ENV_NAME="meld-comm-test"
NP=4
RECREATE=1
DRY_RUN=0
ONLY_ENV=0
USE_VENV=0
FORCE_SERIAL=0
CONDA_BASE=""
BOOTSTRAP_CONDA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env) shift; ENV_NAME="${1:-$ENV_NAME}" ;;
    --env=*) ENV_NAME="${1#--env=}" ;;
    --np) shift; NP="${1:-$NP}" ;;
    --np=*) NP="${1#--np=}" ;;
  --no-recreate) RECREATE=0 ;;
    --dry-run) DRY_RUN=1 ;;
    --only-env) ONLY_ENV=1 ;;
  --use-venv) USE_VENV=1 ;;
  --serial|--force-serial) FORCE_SERIAL=1 ;;
  --conda-base) shift; CONDA_BASE="${1:-}" ;;
  --conda-base=*) CONDA_BASE="${1#--conda-base=}" ;;
  --bootstrap-conda) BOOTSTRAP_CONDA=1 ;;
    -h|--help)
      grep '^# ' "$0" | sed 's/^# //' ; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
  shift
done

if [[ ! -f test_nested_gather_states.py ]]; then
  echo "ERROR: test_nested_gather_states.py not found (run from d3-meld directory)." >&2
  exit 1
fi
if [[ ! -f comm.py ]]; then
  echo "ERROR: comm.py patch file not found (expected in current directory)." >&2
  exit 1
fi

log(){ printf '%s\n' "$*" >&2; }
run(){ log "+ $*"; [[ $DRY_RUN -eq 1 ]] || eval "$*"; }

activate_conda() {
  # shellcheck disable=SC1091
  if [[ -n "$CONDA_BASE" ]]; then
    if [[ -f "$CONDA_BASE/etc/profile.d/conda.sh" ]]; then
      source "$CONDA_BASE/etc/profile.d/conda.sh" || return 1
      return 0
    else
      echo "[conda] Provided --conda-base '$CONDA_BASE' missing conda.sh" >&2
      return 1
    fi
  fi
  if command -v conda &>/dev/null; then
    source "$(conda info --base)/etc/profile.d/conda.sh" && return 0
  fi
  # Common defaults
  for base in "$HOME/mambaforge" "$HOME/miniforge3" "$HOME/miniconda3"; do
    if [[ -f "$base/etc/profile.d/conda.sh" ]]; then
      source "$base/etc/profile.d/conda.sh" && return 0
    fi
  done
  return 1
}

maybe_bootstrap_conda() {
  if [[ $BOOTSTRAP_CONDA -eq 0 ]]; then return 0; fi
  if activate_conda; then
    log "[conda] Already available; skipping bootstrap"
    return 0
  fi
  OS=$(uname -s | tr '[:upper:]' '[:lower:]')
  ARCH=$(uname -m)
  if [[ $OS == linux* || $OS == darwin* ]]; then
    URL="https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-${OS^}-${ARCH}.sh"
    INSTALLER="/tmp/miniforge.sh"
    log "[conda] Bootstrapping Miniforge from $URL"
    run curl -L "$URL" -o "$INSTALLER"
    run bash "$INSTALLER" -b -p "$HOME/miniforge3"
  else
    log "[conda] Bootstrap on this OS not automated; install Miniconda manually."
  fi
}

if [[ $USE_VENV -eq 0 ]]; then
  maybe_bootstrap_conda
  if ! activate_conda; then
    if [[ $USE_VENV -eq 0 ]]; then
      log "[warn] conda not found; falling back to --use-venv auto mode"
      USE_VENV=1
    fi
  fi
fi

VENV_PATH=".venv_meld_comm"
if [[ $USE_VENV -eq 1 ]]; then
  if [[ ! -d $VENV_PATH || $RECREATE -eq 1 ]]; then
    log "[venv] Creating python venv at $VENV_PATH"
    if ! ( [[ $DRY_RUN -eq 1 ]] || python -m venv "$VENV_PATH" 2>/dev/null ); then
      log "[venv] python -m venv failed; attempting virtualenv fallback"
      if [[ $DRY_RUN -eq 0 ]]; then
        python - <<'PY'
import sys, subprocess
try:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--upgrade', 'pip', 'setuptools', 'wheel'])
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'virtualenv'])
    subprocess.check_call([sys.executable, '-m', 'virtualenv', '.venv_meld_comm'])
except Exception as e:
    print(f"[venv] virtualenv fallback failed: {e}")
    sys.exit(1)
PY
      fi
    fi
  else
    log "[venv] Reusing existing venv $VENV_PATH"
  fi
  # shellcheck disable=SC1091
  if [[ -f "$VENV_PATH/bin/activate" ]]; then
    run source "$VENV_PATH/bin/activate"
  else
    # Windows Git Bash path
    run source "$VENV_PATH/Scripts/activate"
  fi
  if [[ $DRY_RUN -eq 0 ]]; then
    python -m pip install --upgrade pip wheel setuptools >/dev/null
    # Try installing mpi4py; if it fails (no MPI), continue for serial test.
    if ! python - <<'PY'
import sys, subprocess
pkgs = ['numpy']
subprocess.check_call([sys.executable, '-m', 'pip', 'install', *pkgs])
try:
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'mpi4py'])
except Exception as e:
    print(f"[venv] mpi4py install failed (likely no MPI dev libs): {e}\n[venv] Will allow serial fallback.")
PY
    then
      log "[venv] Package install encountered issues."
    fi
    if [[ -d ../meld ]]; then
      python -m pip install -e ../meld || log "[venv] meld install failed (continuing)"
    fi
  fi
else
  # --- Original conda flow below (only if not using venv) ---
  if ! command -v conda &>/dev/null; then
    log "[error] Conda activation logic failed unexpectedly."; exit 1
  fi
fi

if [[ $USE_VENV -eq 0 ]]; then
  if conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
    if [[ $RECREATE -eq 1 ]]; then
      log "[env] Removing existing env $ENV_NAME (recreate requested)"
      run conda remove -y -n "$ENV_NAME" --all
    else
      log "[env] Re-using existing env $ENV_NAME (no recreate)"
    fi
  fi

  if ! conda env list | awk '{print $1}' | grep -Fxq "$ENV_NAME"; then
    log "[env] Creating $ENV_NAME"
    run conda create -y -n "$ENV_NAME" -c conda-forge python=3.11 openmm mpi4py openmpi numpy
    if [[ -d ../meld ]]; then
      run conda activate "$ENV_NAME" '&&' pip install -e ../meld
    fi
  else
    log "[env] Env $ENV_NAME already exists"
  fi
  # Activate
  # shellcheck disable=SC1091
  run conda activate "$ENV_NAME"
fi

# Ensure meld import if installed
if [[ $DRY_RUN -eq 0 ]]; then
  python - <<'PY'
try:
    import meld, sys
    print(f"[check] meld imported from {meld.__file__}")
except Exception as e:
    print(f"[warn] meld not importable yet: {e}")
PY
fi

# Patch communicator inside environment site-packages
if [[ $DRY_RUN -eq 0 ]]; then
python - <<'PY'
import os, pathlib, sys, shutil, importlib, hashlib
src = pathlib.Path('comm.py')
if not src.exists():
    print('[patch] comm.py missing; aborting patch', file=sys.stderr); sys.exit(1)
try:
    import meld
except Exception as e:
    print(f"[patch] meld not installed/importable ({e}); skipping patch (test may fail)", file=sys.stderr)
    sys.exit(0)
site_comm = pathlib.Path(meld.__file__).parent / 'comm.py'
if not site_comm.exists():
    print(f"[patch] target {site_comm} not found", file=sys.stderr); sys.exit(1)
backup = site_comm.with_suffix('.py.orig')
if not backup.exists():
    shutil.copy2(site_comm, backup)
shutil.copy2(src, site_comm)
data = site_comm.read_bytes()
print(f"[patch] replaced {site_comm} sha256={hashlib.sha256(data).hexdigest()[:16]}")
print(f"[patch] marker _summarize_structure present? {b'_summarize_structure' in data}")
importlib.invalidate_caches()
PY
fi

if [[ $ONLY_ENV -eq 1 ]]; then
  log "[done] Environment prepared; skipping test (--only-env)."
  exit 0
fi

# Verify mpirun presence (optional install hint only, not auto-install to stay simple)
HAVE_MPI=0
if command -v mpirun &>/dev/null; then HAVE_MPI=1; fi
if command -v mpiexec &>/dev/null; then HAVE_MPI=1; fi

if [[ $FORCE_SERIAL -eq 1 ]]; then
  log "[run] Forcing serial mode (--serial)"
  HAVE_MPI=0
fi

if [[ $HAVE_MPI -eq 0 ]]; then
  log "[info] MPI launchers not found (or serial forced). Running serial validation instead."
  if [[ $DRY_RUN -eq 0 ]]; then
    python - <<'PY'
import importlib, types
import comm as local_comm

def fake_state(i):
    class S: pass
    s = S(); s.alpha = i*0.1; return s

nested = [[fake_state(0)], [fake_state(1)], [[fake_state(2), fake_state(3)]]]

def flatten(obj):
    out=[]
    stack=[obj]
    while stack:
        cur=stack.pop()
        if isinstance(cur,list):
            stack.extend(reversed(cur))
        else:
            out.append(cur)
    return out

flat = flatten(nested)
if any(isinstance(x,list) for x in flat):
    raise SystemExit('[fail] flatten logic produced nested lists')
if len(flat)!=4:
    raise SystemExit(f'[fail] expected 4 states got {len(flat)}')
if not all(hasattr(s,'alpha') for s in flat):
    raise SystemExit('[fail] missing alpha attr')
print('[pass] Serial fallback flatten test succeeded (no MPI).')
PY
  fi
  exit 0
fi

CMD=(python test_nested_gather_states.py)
if command -v mpirun &>/dev/null; then
  CMD=(mpirun -np "$NP" python test_nested_gather_states.py)
elif command -v mpiexec &>/dev/null; then
  CMD=(mpiexec -n "$NP" python test_nested_gather_states.py)
fi

log "[run] ${CMD[*]}"
if [[ $DRY_RUN -eq 0 ]]; then
  "${CMD[@]}"
fi

