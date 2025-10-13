# Code Reference Guide: Where Each File Is Used

This document provides exact line numbers and code snippets showing where each of the 4 essential files is used.

---

## File 1: `af3_tleap_sequence.dat`

### Configuration: `config.py`
**Line 72** (default):
```python
sequence_file=os.getenv("SEQUENCE_FILE", "af3_tleap_sequence.dat"),
```

**Line 2 of `.env`** (actual):
```bash
SEQUENCE_FILE=af3_tleap_sequence.dat
```

### Usage: `setup_meld.py`

**Lines 81-82** - File loading:
```python
sequence_path = _resolve_input_path(cfg.sequence_file, description="Sequence file")
sequence = parse.get_sequence_from_AA1(filename=str(sequence_path))
```

**Lines 100-104** - Processing:
```python
seq = sequence.split()
for i in range(len(seq)):
    if seq[i][-3:] == 'HIE':
        seq[i] = 'HIS'
print(seq)
```

**Usage throughout** - Passed to restraint functions:
- Line 142: `process_phi_dat_file(str(phi_path), s, seq)`
- Line 156: `process_psi_file(str(psi_path), s, seq)`
- Line 173: `get_dist_restraints_protein(str(dist_path), s, dist_scaler, ramp, seq)`

### Purpose
Provides the ordered list of amino acid residues. Used to:
1. Validate structure matches expected sequence
2. Convert file-based residue indices to internal atom indices
3. Ensure restraints reference correct residue types (via `seq[i][-3:]`)

---

## File 2: `af3_tleap.pdb`

### Configuration: `config.py`
**Line 73** (default):
```python
pdb_file=os.getenv("PDB_FILE", "af3_tleap.pdb"),
```

**Line 3 of `.env`** (actual):
```bash
PDB_FILE=af3_tleap.pdb
```

### Usage: `setup_meld.py`

**Lines 87-88** - File loading and glob expansion:
```python
templates = glob.glob(cfg.pdb_file)
if not templates and not Path(cfg.pdb_file).is_absolute():
    alt_templates = []
    for base in _INPUT_SEARCH_DIRS:
        alt_templates.extend(glob.glob(str(base / cfg.pdb_file)))
    templates = list(dict.fromkeys(alt_templates))
if not templates:
    raise FileNotFoundError(f"PDB file pattern '{cfg.pdb_file}' did not match any files.")
```

**Line 95** - System creation:
```python
p = meld.AmberSubSystemFromPdbFile(templates[0])
```

**Lines 96-104** - System building with force field:
```python
build_options = meld.AmberOptions(
    forcefield="ff14sbside",
    implicit_solvent_model='gbNeck2',
    use_big_timestep=False,
    cutoff=1.8 * u.nanometers,
    remove_com=False,
    enable_amap=False,
    amap_beta_bias=1.0,
)
builder = meld.AmberSystemBuilder(build_options)
s = builder.build_system([p]).finalize()
```

### Purpose
Provides 3D atomic coordinates and topology for the protein structure. MELD uses this to:
1. Initialize OpenMM molecular system
2. Define atom positions for all residues
3. Set up force field (ff14sbside with gbNeck2 implicit solvent)
4. Calculate initial energy and forces

---

## File 3: `25-105_CA_dist_bias.dat`

### Configuration: `config.py`
**Line 76** (default, first element):
```python
dist_files=[f.strip() for f in os.getenv("DIST_FILES", "25-105_CA_dist_bias.dat,129-340_CA_dist_bias.dat").split(',') if f.strip()],
```

### Usage: `setup_meld.py`

**Lines 162-180** - Loading in distance restraint loop:
```python
# Distance restraints (competitive groups via get_dist_restraints_protein)
for dist_file in cfg.dist_files:
    if not dist_file:
        continue
    try:
        dist_path = _resolve_input_path(dist_file, description="Distance restraint file")
    except FileNotFoundError as exc:
        print(f"Warning: {exc}")
        continue
    try:
        dist_scaler = s.restraints.create_scaler('constant')
        dist_rests = get_dist_restraints_protein(str(dist_path), s, dist_scaler, ramp, seq)
        if dist_rests:
            n_keep = int(cfg.distance_keep_fraction * len(dist_rests))
            n_keep = max(1, min(len(dist_rests), n_keep))
            s.restraints.add_selectively_active_collection(dist_rests, n_keep)
            print(f"Added {len(dist_rests)} distance restraints from '{dist_path}' (keeping {n_keep}).")
        else:
            print(f"No restraints parsed from '{dist_path}'.")
    except (IOError, ValueError) as e:
        print(f"Warning: Failed processing distance file '{dist_path}': {e}")
```

### Parser: `setup_restraints.py`

**Function `get_dist_restraints_protein()` calls `_parse_distance_file()`**:

**Lines 59-70** - File reading and validation:
```python
path = Path(filename)
if not path.is_file():
    raise FileNotFoundError(f"Distance restraint file not found: {filename}")

# First pass: read all lines so we can attempt auto-offset detection.
raw_lines = path.read_text().splitlines()
index_pairs = []  # store (i_raw, j_raw)
parsed_lines = []  # store tuples for second pass
malformed = 0
malformed_examples = []
for raw in raw_lines:
    stripped = raw.strip()
    if not stripped:
        parsed_lines.append((None, raw))  # delimiter marker
        continue
```

**Lines 94-104** - Auto-offset detection:
```python
offset = 0
if auto_offset and index_pairs:
    all_indices = [v for pair in index_pairs for v in pair]
    min_idx = min(all_indices)
    max_idx = max(all_indices)
    if min_idx > 1 and (max_idx - min_idx + 1) == n_seq:
        offset = min_idx - 1
        if verbose:
            print(f"Info: Applying auto offset of {offset} to residue indices in {filename} (range {min_idx}-{max_idx}, seq_len={n_seq}).")
```

**Lines 114-145** - Restraint creation with explicit distance target:
```python
for entry, raw in parsed_lines:
    if entry is None:
        if current:
            groups.append(s.restraints.create_restraint_group(current, 1))
            current = []
        continue
    i_raw, j_raw, cols = entry
    # Apply offset then convert to 0-based
    i = i_raw - 1 - offset
    j = j_raw - 1 - offset
    name_i = cols[1]
    name_j = cols[3]
    
    # ... validation ...
    
    try:
        if has_explicit_distance:
            dist = float(cols[4])
            rest = s.restraints.create_restraint(
                'distance', scaler, ramp,
                r1=0.0 * u.nanometer,
                r2=(dist - 0.1) * u.nanometer,
                r3=dist * u.nanometer,
                r4=(dist + 0.1) * u.nanometer,
                k=350 * u.kilojoule_per_mole / u.nanometer ** 2,
                atom1=s.index.atom(i, name_i, expected_resname=seq[i][-3:]),
                atom2=s.index.atom(j, name_j, expected_resname=seq[j][-3:]),
            )
        # ... add to current group ...
```

### File Format
Expected format (5 columns):
```
res_i atom_i res_j atom_j distance_nm
```

Example:
```
25 CA 30 CA 0.85
26 CA 31 CA 0.92
...
```

**Note**: Residue indices are 1-based in file, converted to 0-based internally. Auto-offset detection handles absolute numbering (e.g., if file has 129-340 but sequence is 151 residues, offset of 128 is automatically applied).

### Purpose
Defines distance constraints between specific atom pairs in protein region spanning residues 25-105. Each blank line separates competitive groups where only one restraint is active at a time (MELD's "pick 1 of N" mechanism).

---

## File 4: `129-340_CA_dist_bias.dat`

### Configuration: Same as File 3
**Line 76** (default, second element):
```python
dist_files=[f.strip() for f in os.getenv("DIST_FILES", "25-105_CA_dist_bias.dat,129-340_CA_dist_bias.dat").split(',') if f.strip()],
```

### Usage: Identical to File 3
Processed in the **same loop** as File 3 (lines 162-180 of `setup_meld.py`), second iteration.

### Parser: Same as File 3
Uses the same `_parse_distance_file()` function in `setup_restraints.py`.

### File Format: Same as File 3
```
res_i atom_i res_j atom_j distance_nm
```

### Purpose
Defines distance constraints between specific atom pairs in protein region spanning residues 129-340. Same competitive group mechanism as File 3.

---

## Configuration Summary

### From `.env` (active configuration)
```bash
SEQUENCE_FILE=af3_tleap_sequence.dat
PDB_FILE=af3_tleap.pdb
N_REPLICAS=30
N_STEPS=1500
BLOCK_SIZE=50
TIMESTEPS=25000
MINIMIZE_STEPS=20000
```

### From `config.py` (defaults used when not in `.env`)
```python
# Distance files (not in .env, so use default)
dist_files = ['25-105_CA_dist_bias.dat', '129-340_CA_dist_bias.dat']

# Restraint settings
enable_restraints = True              # Applies distance/torsion restraints
torsion_keep_fraction = 0.9          # Keep 90% of torsion restraints active
distance_keep_fraction = 0.9         # Keep 90% of distance restraints active

# Ramp scaler (gradually increase restraint strength)
ramp_start_time = 1
ramp_end_time = 200
ramp_start_weight = 0.001
ramp_end_weight = 1.0
ramp_factor = 4.0
```

---

## File Resolution Logic

### Function: `_resolve_input_path()` in `setup_meld.py` (lines 36-66)

**Search order**:
1. Exact path (if absolute)
2. Current working directory
3. Script directory (`setup_meld.py` location)
4. `_inputs/` subdirectory (relative to each of above)

**Windows path handling** (lines 43-50):
```python
normalized_value = original_value.strip()
if os.sep != '\\':
    normalized_value = normalized_value.replace('\\', '/')
if normalized_value:
    lower_value = normalized_value.lower()
    for prefix in ("_inputs", "inputs"):
        if lower_value.startswith(prefix):
            remainder = normalized_value[len(prefix):]
            if remainder and remainder[0] not in ('/', '\\'):
                normalized_value = normalized_value[:len(prefix)] + '/' + remainder
            break
```

**Result for your setup**:
- `af3_tleap.pdb` → Found at `_inputs/af3_tleap.pdb`
- `af3_tleap_sequence.dat` → Found at `_inputs/af3_tleap_sequence.dat`
- `25-105_CA_dist_bias.dat` → Found at `_inputs/25-105_CA_dist_bias.dat`
- `129-340_CA_dist_bias.dat` → Found at `_inputs/129-340_CA_dist_bias.dat`

---

## Data Flow Diagram

```
.env file
    ↓
config.py (load_simulation_config)
    ↓
setup_meld.py (main execution)
    ↓
    ├─ _resolve_input_path() searches:
    │      1. Current dir
    │      2. Script dir
    │      3. _inputs/ subdir  ← YOUR FILES FOUND HERE
    │
    ├─ File 2: af3_tleap.pdb
    │      ↓
    │   meld.AmberSubSystemFromPdbFile()
    │      ↓
    │   OpenMM system with atoms + coordinates
    │
    ├─ File 1: af3_tleap_sequence.dat
    │      ↓
    │   parse.get_sequence_from_AA1()
    │      ↓
    │   List of residue names ['ASP', 'HIS', 'GLY', ...]
    │
    ├─ File 3: 25-105_CA_dist_bias.dat
    │      ↓
    │   setup_restraints._parse_distance_file()
    │      ↓
    │   List of distance restraint objects
    │      ↓
    │   s.restraints.add_selectively_active_collection()
    │
    └─ File 4: 129-340_CA_dist_bias.dat
           ↓
        setup_restraints._parse_distance_file()
           ↓
        List of distance restraint objects
           ↓
        s.restraints.add_selectively_active_collection()
           ↓
           ↓
        ALL FILES PROCESSED
           ↓
        vault.DataStore.save_system()
           ↓
        Data/data_store.dat created
           ↓
        SETUP COMPLETE ✓
```

---

## Verification Command

To trace file usage in real-time, add debug output:

```python
# Add after line 81 in setup_meld.py
print(f"[DEBUG] Loaded sequence from: {sequence_path}")

# Add after line 95
print(f"[DEBUG] Loaded PDB from: {templates[0]}")

# Add in the distance file loop (after line 166)
print(f"[DEBUG] Processing distance file: {dist_path}")
```

Or use the provided verification script:
```bash
python verify_four_files.py
```

---

## Quick Reference: Line Numbers

| File | Configuration | Loading | Processing |
|------|---------------|---------|------------|
| `af3_tleap_sequence.dat` | `config.py:72` | `setup_meld.py:81-82` | `setup_meld.py:100-104` |
| `af3_tleap.pdb` | `config.py:73` | `setup_meld.py:87-95` | `setup_meld.py:96-107` |
| `25-105_CA_dist_bias.dat` | `config.py:76` | `setup_meld.py:162-180` | `setup_restraints.py:59-175` |
| `129-340_CA_dist_bias.dat` | `config.py:76` | `setup_meld.py:162-180` | `setup_restraints.py:59-175` |

---

## Optional Files (Referenced but Not Required)

| File | Config | Handling |
|------|--------|----------|
| `phi.dat` | `config.py:74` | `setup_meld.py:131-144` (try/except with warning) |
| `psi.dat` | `config.py:75` | `setup_meld.py:146-161` (try/except with warning) |

Both wrapped in `try`/`except FileNotFoundError` blocks that print warnings but continue execution.
