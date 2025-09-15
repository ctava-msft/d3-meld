"""Utility functions to build MELD/OpenMM distance and backbone torsion restraints
from simple plaintext specification files.

Conventions:
- Residue indices in input files are 1-based; converted here to 0-based.
- Blank lines in distance files delimit competitive (pick-1-of-N) restraint groups.
- seq is an iterable whose elements end with a 3-letter residue name (seq[i][-3:]).
"""

from openmm import unit as u

def get_dist_restraints(filename, s, scaler, ramp, seq):
    """Parse a distance specification file without explicit target distances.

    File format (groups separated by blank lines):
        i atom_i j atom_j
    Each line creates a flat-bottom harmonic distance restraint with fixed bounds:
        (r1=0, r2=0, r3=0.8 nm, r4=1.0 nm), k=350 kJ/mol/nm^2.
    Blank line => current accumulated restraints become a competitive 1-of-N group.

    Args:
        filename (str): Path to distance file.
        s: MELD/OpenMM system wrapper providing restraints & index helpers.
        scaler: Previously created scaler object.
        ramp: Previously created ramp object.
        seq: Sequence container; seq[i][-3:] yields 3-letter residue name.

    Returns:
        list: List of restraint group objects.

    Note:
        If the file does not end with a blank line, the last group is NOT appended
        (existing behavior preserved; potential improvement).
    """
    dists = []
    rest_group = []
    lines = open(filename).read().splitlines()
    lines = [line.strip() for line in lines]
    for line in lines:
        if not line:
            dists.append(s.restraints.create_restraint_group(rest_group, 1))
            rest_group = []
        else:
            cols = line.split()
            i = int(cols[0])-1
            name_i = cols[1]
            j = int(cols[2])-1
            name_j = cols[3]
            rest = s.restraints.create_restraint('distance', scaler, ramp,
                                                 r1=0.0*u.nanometer, r2=0.0*u.nanometer, r3=0.8*u.nanometer, r4=1.0*u.nanometer,
                                                 k=350*u.kilojoule_per_mole/u.nanometer **2,
                                                 atom1=s.index.atom(i,name_i, expected_resname=seq[i][-3:]),
                                                 atom2=s.index.atom(j,name_j, expected_resname=seq[j][-3:]))
            rest_group.append(rest)
    return dists

def get_dist_restraints_protein(filename, s, scaler, ramp, seq):
    """Parse a distance specification file with explicit target distances.

    File format:
        i atom_i j atom_j distance_nm
    Creates a distance restraint with a narrow well centered at distance:
        r1=0, r2=distance-0.1, r3=distance, r4=distance+0.1 (nm).

    Grouping & behavior regarding trailing blank line identical to get_dist_restraints.
    """
    dists = []
    rest_group = []
    lines = open(filename).read().splitlines()
    lines = [line.strip() for line in lines]
    for line in lines:
        if not line:
            dists.append(s.restraints.create_restraint_group(rest_group, 1))
            rest_group = []
        else:
            cols = line.split()
            i = int(cols[0])-1
            name_i = cols[1]
            j = int(cols[2])-1
            name_j = cols[3]
            dist = float(cols[4])
            rest = s.restraints.create_restraint('distance', scaler, ramp,
                                                 r1=0.0*u.nanometer, r2=(dist-0.1)*u.nanometer, r3=dist*u.nanometer, r4=(dist+0.1)*u.nanometer,
                                                 k=350*u.kilojoule_per_mole/u.nanometer **2,
                                                 atom1=s.index.atom(i,name_i, expected_resname=seq[i][-3:]),
                                                 atom2=s.index.atom(j,name_j, expected_resname=seq[j][-3:]))
            rest_group.append(rest)
    return dists

def process_phi_dat_file(filename,s,seq):
    """Build phi (C_{i-1}-N_i-CA_i-C_i) torsion restraints from a file.

    File line format (columns):
        <ignored> res_index phi_min phi_max
    Angles in degrees. res_index is 1-based.
    The restraint center = (phi_min + phi_max)/2 with half-range as delta.

    Skips validation: will fail if res_index == 1 (needs residue i-1).
    """
    torsion_rests = []
    tor_scaler = s.restraints.create_scaler('nonlinear', alpha_min=0.4, alpha_max=1.0, factor=4.0)
    with open(filename, 'r') as file:
        for line in file:
            cols = line.split()
            res = int(cols[1]) - 1
            phi_min = float(cols[2])
            phi_max = float(cols[3])
            phi_avg = (phi_max + phi_min) / 2.
            phi_sd = abs(phi_avg - phi_min)
            # Create torsional restraint
            phi_rest = s.restraints.create_restraint(
                'torsion',
                tor_scaler,
                phi=phi_avg * u.degree,
                delta_phi=phi_sd * u.degree,
                k=0.1 * u.kilojoule_per_mole / u.degree ** 2,
                atom1=s.index.atom(res - 1, 'C', expected_resname=seq[res - 1][-3:]),
                atom2=s.index.atom(res, 'N', expected_resname=seq[res][-3:]),
                atom3=s.index.atom(res, 'CA', expected_resname=seq[res][-3:]),
                atom4=s.index.atom(res, 'C', expected_resname=seq[res][-3:])
            )
            # Append the created torsional restraint to the list
            torsion_rests.append(phi_rest)
    return torsion_rests

def process_psi_file(psi_filename,s,seq):
    """Build psi (N_i-CA_i-C_i-N_{i+1}) torsion restraints from a file.

    File line format:
        <ignored> res_index psi_min psi_max
    Uses midpoint and half-range as center & tolerance.

    Will raise if res_index is the last residue (needs i+1).
    """
    torsion_rests = []
    tor_scaler = s.restraints.create_scaler('nonlinear', alpha_min=0.4, alpha_max=1.0, factor=4.0)
    with open(psi_filename, 'r') as file:
        for line in file:
            cols = line.split()
            res = int(cols[1]) - 1
            psi_min = float(cols[2])
            psi_max = float(cols[3])
            psi_avg = (psi_max + psi_min) / 2.0
            psi_sd = abs(psi_avg - psi_min)
            # Create torsion restraint
            psi_rest = s.restraints.create_restraint('torsion', tor_scaler,
                                                     phi=psi_avg * u.degree, delta_phi=psi_sd * u.degree,
                                                     k=0.1 * u.kilojoule_per_mole/u.degree**2,
                                                     atom1=s.index.atom(res, 'N', expected_resname=seq[res][-3:]),
                                                     atom2=s.index.atom(res, 'CA', expected_resname=seq[res][-3:]),
                                                     atom3=s.index.atom(res, 'C', expected_resname=seq[res][-3:]),
                                                     atom4=s.index.atom(res + 1, 'N', expected_resname=seq[res + 1][-3:]))
            torsion_rests.append(psi_rest)
    return torsion_rests