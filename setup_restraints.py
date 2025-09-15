"""Utility functions to construct MELD/OpenMM restraints from plaintext specs.

Highlights:
* Distance files may specify either fixed window restraints (no distance column)
  or explicit target-centered windows (last column = distance in nm).
* Blank lines separate competitive groups (pick 1 of N) for distances.
* Trailing non-empty group is now automatically included (improved vs. legacy).
* Residue indices in files are 1-based and converted to 0-based internally.
* Sequence elements must end with a 3-letter residue name (seq[i][-3:]).

Public API (backward-compatible names):
    get_dist_restraints(filename, s, scaler, ramp, seq)
    get_dist_restraints_protein(filename, s, scaler, ramp, seq)
    process_phi_dat_file(filename, s, seq)
    process_psi_file(filename, s, seq)
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Iterable
from openmm import unit as u

# ---------------- Distance restraint parsing ---------------- #

def _parse_distance_file(
    filename: str,
    s,
    scaler,
    ramp,
    seq: Iterable[str],
    has_explicit_distance: bool,
) -> List:
    """Generic parser for distance restraint specification files.

    Parameters
    ----------
    filename : str
        Path to specification file.
    s : MELD system wrapper
        Provides `.restraints` factory and `.index.atom` resolution.
    scaler : object
        MELD scaler applied to each created restraint.
    ramp : object
        Ramp scaler (may be constant) passed to MELD distance restraint.
    seq : iterable[str]
        Sequence container with 3-letter residue codes at end of each token.
    has_explicit_distance : bool
        If True, expect format: i atom_i j atom_j dist_nm.
        If False, expect format: i atom_i j atom_j (fixed window 0.8–1.0 nm).

    Returns
    -------
    list
        List of MELD restraint groups (each a competitive pick-1-of-N group).
    """
    path = Path(filename)
    if not path.is_file():
        raise FileNotFoundError(f"Distance restraint file not found: {filename}")

    groups: List = []
    current: List = []
    with path.open() as fh:
        for raw in fh:
            line = raw.strip()
            if not line:
                if current:
                    groups.append(s.restraints.create_restraint_group(current, 1))
                    current = []
                continue
            cols = line.split()
            if has_explicit_distance and len(cols) < 5:
                raise ValueError(f"Line expects 5 columns (i atom_i j atom_j dist) in {filename}: '{line}'")
            if not has_explicit_distance and len(cols) < 4:
                raise ValueError(f"Line expects 4 columns (i atom_i j atom_j) in {filename}: '{line}'")
            i = int(cols[0]) - 1
            name_i = cols[1]
            j = int(cols[2]) - 1
            name_j = cols[3]
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
            else:
                rest = s.restraints.create_restraint(
                    'distance', scaler, ramp,
                    r1=0.0 * u.nanometer,
                    r2=0.0 * u.nanometer,
                    r3=0.8 * u.nanometer,
                    r4=1.0 * u.nanometer,
                    k=350 * u.kilojoule_per_mole / u.nanometer ** 2,
                    atom1=s.index.atom(i, name_i, expected_resname=seq[i][-3:]),
                    atom2=s.index.atom(j, name_j, expected_resname=seq[j][-3:]),
                )
            current.append(rest)
    # Append trailing group if present
    if current:
        groups.append(s.restraints.create_restraint_group(current, 1))
    return groups


def get_dist_restraints(filename, s, scaler, ramp, seq):
    """Backward-compatible wrapper for fixed-distance-window restraints.

    See `_parse_distance_file` for details.
    """
    return _parse_distance_file(filename, s, scaler, ramp, seq, has_explicit_distance=False)


def get_dist_restraints_protein(filename, s, scaler, ramp, seq):
    """Backward-compatible wrapper for explicit distance restraints (protein)."""
    return _parse_distance_file(filename, s, scaler, ramp, seq, has_explicit_distance=True)


# ---------------- Torsion restraint parsing ---------------- #

def process_phi_dat_file(filename, s, seq):
    """Build phi torsion restraints (C_{i-1}-N_i-CA_i-C_i) from file.

    File columns: <ignored> res_index phi_min phi_max (degrees)
    Center = midpoint, delta = half-range.
    """
    torsion_rests = []
    tor_scaler = s.restraints.create_scaler('nonlinear', alpha_min=0.4, alpha_max=1.0, factor=4.0)
    with open(filename, 'r') as file:
        for raw in file:
            if not raw.strip():
                continue
            cols = raw.split()
            if len(cols) < 4:
                raise ValueError(f"Invalid phi line (need >=4 columns): '{raw.strip()}'")
            res = int(cols[1]) - 1
            phi_min = float(cols[2])
            phi_max = float(cols[3])
            phi_avg = (phi_max + phi_min) / 2.0
            phi_sd = abs(phi_avg - phi_min)
            torsion_rests.append(
                s.restraints.create_restraint(
                    'torsion',
                    tor_scaler,
                    phi=phi_avg * u.degree,
                    delta_phi=phi_sd * u.degree,
                    k=0.1 * u.kilojoule_per_mole / u.degree ** 2,
                    atom1=s.index.atom(res - 1, 'C', expected_resname=seq[res - 1][-3:]),
                    atom2=s.index.atom(res, 'N', expected_resname=seq[res][-3:]),
                    atom3=s.index.atom(res, 'CA', expected_resname=seq[res][-3:]),
                    atom4=s.index.atom(res, 'C', expected_resname=seq[res][-3:]),
                )
            )
    return torsion_rests


def process_psi_file(psi_filename, s, seq):
    """Build psi torsion restraints (N_i-CA_i-C_i-N_{i+1}) from file.

    File columns: <ignored> res_index psi_min psi_max (degrees)
    Center = midpoint, delta = half-range.
    """
    torsion_rests = []
    tor_scaler = s.restraints.create_scaler('nonlinear', alpha_min=0.4, alpha_max=1.0, factor=4.0)
    with open(psi_filename, 'r') as file:
        for raw in file:
            if not raw.strip():
                continue
            cols = raw.split()
            if len(cols) < 4:
                raise ValueError(f"Invalid psi line (need >=4 columns): '{raw.strip()}'")
            res = int(cols[1]) - 1
            psi_min = float(cols[2])
            psi_max = float(cols[3])
            psi_avg = (psi_max + psi_min) / 2.0
            psi_sd = abs(psi_avg - psi_min)
            torsion_rests.append(
                s.restraints.create_restraint(
                    'torsion',
                    tor_scaler,
                    phi=psi_avg * u.degree,
                    delta_phi=psi_sd * u.degree,
                    k=0.1 * u.kilojoule_per_mole / u.degree ** 2,
                    atom1=s.index.atom(res, 'N', expected_resname=seq[res][-3:]),
                    atom2=s.index.atom(res, 'CA', expected_resname=seq[res][-3:]),
                    atom3=s.index.atom(res, 'C', expected_resname=seq[res][-3:]),
                    atom4=s.index.atom(res + 1, 'N', expected_resname=seq[res + 1][-3:]),
                )
            )
    return torsion_rests