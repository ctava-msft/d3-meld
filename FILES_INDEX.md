# Files Created - Index

This document lists all files created during the trajectory extraction project.

## Main Extraction Tools

### `extract_from_netcdf.py`
**Purpose**: Main trajectory extraction script  
**Usage**: Extracts trajectory data from NetCDF block files without requiring MELD installation  
**Features**:
- Reads NetCDF blocks directly
- Converts to DCD format
- Supports single replica extraction
- Includes inspection mode
- Works on Windows and Linux

```powershell
python extract_from_netcdf.py --replica 10 --output trajectory.10.dcd
```

---

### `validate_trajectories.py`
**Purpose**: Validation tool for extracted DCD files  
**Usage**: Validates trajectory integrity and reports statistics  
**Features**:
- Loads and validates DCD files
- Checks for NaN/Inf values
- Reports frame and atom counts
- Generates position statistics
- Samples multiple frames

```powershell
python validate_trajectories.py --all
```

---

### `batch_extract.ps1`
**Purpose**: PowerShell batch extraction script  
**Usage**: Automates extraction of multiple replicas  
**Features**:
- Extracts predefined set of replicas
- Progress reporting
- Success/failure tracking
- File size reporting
- Summary statistics

```powershell
.\batch_extract.ps1
```

---

## Documentation Files

### `EXTRACTION_REPORT.md`
**Purpose**: Complete extraction guide and results report  
**Contents**:
- Mission summary
- Environment setup
- Solution approach
- Usage examples
- Validation results
- Next steps
- Troubleshooting

**Audience**: Users needing step-by-step guide

---

### `EXTRACTION_SUMMARY.md`
**Purpose**: Technical details and methodology  
**Contents**:
- Problem analysis
- Data structure details
- Solution implementation
- Technical advantages
- Future improvements
- Conda environment details

**Audience**: Technical users and developers

---

### `VALIDATION_SUMMARY.md`
**Purpose**: Comprehensive validation report  
**Contents**:
- Individual file validation results
- Data integrity assessment
- Known issues (Frame 663 anomaly)
- Quality metrics
- Post-processing recommendations
- Analysis guidelines

**Audience**: Data analysts and researchers

---

### `README.md` (Updated)
**Purpose**: Main repository documentation  
**Updates**:
- Added Quick Start section
- Added Method 1: Direct NetCDF Extraction
- Updated Method 2: MELD Native Extraction
- Added validation instructions
- Added documentation references
- Corrected replica index ranges (0-29)

**Audience**: All users

---

### `FILES_INDEX.md` (This file)
**Purpose**: Index of all created files  
**Contents**: This document

**Audience**: Project overview and navigation

---

## Legacy/Alternative Tools (Not Used in Final Solution)

### `direct_extract_trajectory.py`
**Status**: Created but not used  
**Reason**: Required MELD module to unpickle DataStore  
**Alternative**: `extract_from_netcdf.py` reads NetCDF directly

---

## Output Files (Created Successfully)

### Trajectory Files

| File | Replica | Size | Frames | Status |
|------|---------|------|--------|--------|
| `trajectory.10.dcd` | 10 | 82.84 MB | 1,326 | ✅ |
| `trajectory.20.dcd` | 20 | 82.84 MB | 1,326 | ✅ |
| `trajectory.30.dcd` | 29 | 82.84 MB | 1,326 | ✅ |
| `trajectory.40.dcd` | 0 | 82.84 MB | 1,326 | ✅ |
| `trajectory.50.dcd` | 5 | 82.84 MB | 1,326 | ✅ |

**Total**: 414.2 MB of trajectory data

---

## File Organization

```
d3-meld/
├── extract_from_netcdf.py          # Main extraction tool ⭐
├── validate_trajectories.py        # Validation tool ⭐
├── batch_extract.ps1                # Batch extraction script
├── direct_extract_trajectory.py    # Alternative (not used)
│
├── EXTRACTION_REPORT.md            # Complete guide ⭐
├── EXTRACTION_SUMMARY.md           # Technical details
├── VALIDATION_SUMMARY.md           # Validation results ⭐
├── FILES_INDEX.md                  # This file
├── readme.md                       # Updated README ⭐
│
├── trajectory.10.dcd               # Output: Replica 10 ✅
├── trajectory.20.dcd               # Output: Replica 20 ✅
├── trajectory.30.dcd               # Output: Replica 29 ✅
├── trajectory.40.dcd               # Output: Replica 0 ✅
├── trajectory.50.dcd               # Output: Replica 5 ✅
│
└── Data/
    ├── trajectory.pdb              # Topology file
    ├── data_store.dat              # MELD DataStore
    └── Blocks/
        ├── block_000000.nc         # NetCDF blocks
        ├── block_000001.nc
        └── ...
```

⭐ = Most important files

---

## Recommended Reading Order

For **Users** extracting trajectories:
1. `README.md` - Quick Start section
2. `EXTRACTION_REPORT.md` - Complete guide
3. `VALIDATION_SUMMARY.md` - Check quality

For **Developers** understanding the solution:
1. `EXTRACTION_SUMMARY.md` - Technical approach
2. `extract_from_netcdf.py` - Source code
3. `VALIDATION_SUMMARY.md` - Data quality

For **Analysts** analyzing trajectories:
1. `VALIDATION_SUMMARY.md` - Data quality and issues
2. `EXTRACTION_REPORT.md` - Post-processing examples
3. Trajectory files (*.dcd)

---

## Key Commands Reference

### Extract Single Replica
```powershell
python extract_from_netcdf.py --replica 10 --output trajectory.10.dcd
```

### Extract Multiple Replicas
```powershell
.\batch_extract.ps1
```

### Validate Trajectories
```powershell
python validate_trajectories.py --all
```

### Inspect NetCDF
```powershell
python extract_from_netcdf.py --replica 0 --output test.dcd --inspect
```

### List Created Files
```powershell
Get-ChildItem -Filter "trajectory.*.dcd" | Format-Table Name, Length, LastWriteTime
```

---

## Next Steps

1. **Analysis**: Use MDTraj, VMD, or PyMOL to analyze trajectories
2. **Clean Data**: Remove frame 663 if needed (see VALIDATION_SUMMARY.md)
3. **Calculations**: RMSD, RMSF, clustering, contact analysis
4. **Visualization**: Create movies, plots, structural analysis
5. **Publication**: Use cleaned data for scientific results

---

**Project Status**: ✅ Complete  
**Date**: September 30, 2025  
**Total Extraction Time**: ~5 minutes per replica (25 minutes total)
