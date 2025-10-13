# Four-File MELD Run Analysis

## Executive Summary

**YES**, the MELD program will run with just these 4 files:
1. `25-105_CA_dist_bias.dat`
2. `129-340_CA_dist_bias.dat`
3. `af3_tleap.pdb`
4. `af3_tleap_sequence.dat`

**All 4 files ARE being used** by the program as configured.

---

## File Usage Analysis

### 1. **af3_tleap.pdb** ✅ REQUIRED & USED
- **Purpose**: Protein structure template for system building
- **Used by**: `setup_meld.py` line 87-88
  ```python
  templates = glob.glob(cfg.pdb_file)
  p = meld.AmberSubSystemFromPdbFile(templates[0])
  ```
- **Configuration**: `config.py` default = `"af3_tleap.pdb"`
- **Location**: `_inputs/af3_tleap.pdb`
- **Status**: ✅ Exists and will be found by `_resolve_input_path()`

### 2. **af3_tleap_sequence.dat** ✅ REQUIRED & USED
- **Purpose**: Amino acid sequence (space-separated residue identifiers)
- **Used by**: `setup_meld.py` line 81-82
  ```python
  sequence_path = _resolve_input_path(cfg.sequence_file, description="Sequence file")
  sequence = parse.get_sequence_from_AA1(filename=str(sequence_path))
  ```
- **Configuration**: `config.py` default = `"af3_tleap_sequence.dat"`
- **Location**: `_inputs/af3_tleap_sequence.dat`
- **Status**: ✅ Exists and will be found by `_resolve_input_path()`

### 3. **25-105_CA_dist_bias.dat** ✅ USED (when restraints enabled)
- **Purpose**: Distance restraints for protein region 25-105
- **Used by**: `setup_meld.py` line 162-180 (distance restraints loop)
  ```python
  for dist_file in cfg.dist_files:
      dist_path = _resolve_input_path(dist_file, description="Distance restraint file")
      dist_rests = get_dist_restraints_protein(str(dist_path), s, dist_scaler, ramp, seq)
  ```
- **Configuration**: `config.py` default includes this in `DIST_FILES`
  ```python
  dist_files=[...from os.getenv("DIST_FILES", "25-105_CA_dist_bias.dat,129-340_CA_dist_bias.dat")...]
  ```
- **Location**: `_inputs/25-105_CA_dist_bias.dat`
- **Status**: ✅ Exists and will be used if `ENABLE_RESTRAINTS=true` (default)

### 4. **129-340_CA_dist_bias.dat** ✅ USED (when restraints enabled)
- **Purpose**: Distance restraints for protein region 129-340
- **Used by**: Same as above - second file in `dist_files` list
- **Configuration**: `config.py` default includes this in `DIST_FILES`
- **Location**: `_inputs/129-340_CA_dist_bias.dat`
- **Status**: ✅ Exists and will be used if `ENABLE_RESTRAINTS=true` (default)

---

## Files Referenced but NOT in Your List

### ⚠️ phi.dat and psi.dat (OPTIONAL, will warn if missing)
- **Default config references**: 
  - `PHI_FILE=phi.dat`
  - `PSI_FILE=psi.dat`
- **Status**: These files do NOT exist in `_inputs/`
- **Impact**: The code will print warnings but **continue without errors**:
  ```python
  if cfg.phi_file:
      try:
          phi_path = _resolve_input_path(cfg.phi_file, description="Phi torsion file")
      except FileNotFoundError as exc:
          print(f"Warning: {exc}")  # ← Just a warning, continues
  ```
  (See `setup_meld.py` lines 131-144 and 146-161)

---

## Configuration Deep Dive

### Actual Configuration (from `.env` file)

Your `.env` file correctly configures:

```bash
SEQUENCE_FILE=af3_tleap_sequence.dat           # ✅ YOU HAVE THIS
PDB_FILE=af3_tleap.pdb                          # ✅ YOU HAVE THIS
N_REPLICAS=30
N_STEPS=1500
BLOCK_SIZE=50
TIMESTEPS=25000
MINIMIZE_STEPS=20000
```

Distance files come from `config.py` defaults:
```python
dist_files = [
    "25-105_CA_dist_bias.dat",                  # ✅ YOU HAVE THIS
    "129-340_CA_dist_bias.dat"                  # ✅ YOU HAVE THIS
]
enable_restraints = True                        # Uses distance files
```

Optional files (will warn if missing, but OK):
```python
phi_file = "phi.dat"                            # ⚠️ Missing (warns only)
psi_file = "psi.dat"                            # ⚠️ Missing (warns only)
```

### File Resolution Logic

The `_resolve_input_path()` function in `setup_meld.py` (lines 36-66) searches for files in:
1. Current working directory
2. Script directory
3. `_inputs/` subdirectory (where your 4 files are!)
4. With automatic Windows backslash handling

All 4 of your files will be found automatically in `_inputs/`.

---

## Execution Flow

### Phase 1: Setup (`setup_meld.py`)
1. ✅ Load sequence from `af3_tleap_sequence.dat`
2. ✅ Build system from `af3_tleap.pdb`
3. ⚠️ Try to load phi.dat (warns if missing, continues)
4. ⚠️ Try to load psi.dat (warns if missing, continues)
5. ✅ Load distance restraints from both `.dat` files
6. ✅ Create `Data/data_store.dat`

### Phase 2: Launch (`launch_remd.py`)
1. Load existing `Data/data_store.dat`
2. Run REMD simulation
3. No direct file access - uses persisted data store

---

## Testing Recommendations

### Minimal Test (verify 4-file sufficiency)

```bash
# Clean slate
rm -rf Data/

# Run setup with just your 4 files
python setup_meld.py
```

**Expected output**:
- ✅ "Added X distance restraints from '25-105_CA_dist_bias.dat'..."
- ✅ "Added X distance restraints from '129-340_CA_dist_bias.dat'..."
- ⚠️ "Warning: Phi file not configured; skipping phi restraints." (or similar)
- ⚠️ "Warning: Psi file not configured; skipping psi restraints." (or similar)
- ✅ "No torsion restraints added." (expected - phi/psi missing)
- ✅ Data store created successfully

### Verify File Usage

Add this diagnostic to confirm file loading:

```bash
# Before running, add debug output
export MELD_DEBUG=1

# Or check the logs after running setup_meld.py
grep -i "distance restraint" output.log
grep -i "sequence" output.log
```

---

## Potential Issues & Mitigations

### Issue 1: Missing phi.dat/psi.dat warnings
**Severity**: Low (just warnings)
**Mitigation**: Either:
- Ignore (program continues)
- Create empty/dummy files (not recommended)
- Set `PHI_FILE=""` and `PSI_FILE=""` in a `.env` file to suppress lookups

### Issue 2: Restraints completely disabled
**Severity**: Medium (simulation runs but may not converge as expected)
**Check**: Ensure `ENABLE_RESTRAINTS=true` (default)

### Issue 3: Wrong working directory
**Severity**: High (files not found)
**Mitigation**: Run from repository root where `_inputs/` is visible

---

## Verification Commands

```bash
# 1. Verify all 4 files exist
ls -la _inputs/*.dat _inputs/*.pdb

# 2. Check configuration defaults
python -c "from config import load_simulation_config; c=load_simulation_config(); print(f'seq={c.sequence_file}, pdb={c.pdb_file}, dist={c.dist_files}')"

# 3. Dry-run file resolution
python -c "
from setup_meld import _resolve_input_path
for f in ['af3_tleap.pdb', 'af3_tleap_sequence.dat', '25-105_CA_dist_bias.dat', '129-340_CA_dist_bias.dat']:
    try:
        resolved = _resolve_input_path(f, description=f)
        print(f'✅ {f} -> {resolved}')
    except FileNotFoundError as e:
        print(f'❌ {f} -> NOT FOUND')
"

# 4. Test setup (creates Data/ directory)
python setup_meld.py 2>&1 | tee setup_test.log

# 5. Verify data store created
ls -lh Data/data_store.dat
```

---

## Conclusion

✅ **The 4 files you identified are sufficient and correct.**

✅ **All 4 files are actively used** during the setup phase.

⚠️ **phi.dat and psi.dat are referenced but optional** - their absence generates warnings but does not prevent execution.

🎯 **Recommended action**: Run `python setup_meld.py` and verify it completes successfully with expected distance restraint output and only warnings about missing phi/psi files.

---

## Summary Table

| File | Required? | Used? | Location | Purpose |
|------|-----------|-------|----------|---------|
| `af3_tleap.pdb` | ✅ YES | ✅ YES | `_inputs/` | Structure template |
| `af3_tleap_sequence.dat` | ✅ YES | ✅ YES | `_inputs/` | Amino acid sequence |
| `25-105_CA_dist_bias.dat` | ✅ YES* | ✅ YES | `_inputs/` | Distance restraints (region 1) |
| `129-340_CA_dist_bias.dat` | ✅ YES* | ✅ YES | `_inputs/` | Distance restraints (region 2) |
| `phi.dat` | ⚠️ Optional | ⚠️ If exists | N/A | Phi torsion restraints |
| `psi.dat` | ⚠️ Optional | ⚠️ If exists | N/A | Psi torsion restraints |

\* Required when `ENABLE_RESTRAINTS=true` (default)
