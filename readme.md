
### Conda environment (recommended)
1. Install Miniconda or Mambaforge.
2. Create env from provided spec:
   conda env create -f conda.yaml
3. Activate:
   conda activate d3-meld-env
4. (Optional) Ensure CUDA toolkit present if system drivers missing:
   conda install -c conda-forge cudatoolkit
5. Verify install (OpenMM + MPI bindings):
   python -c "import openmm, mpi4py, sys; print('OpenMM', openmm.__version__); print('openmm path', openmm.__file__); print('mpi4py OK')"
6. Run setup script:
   python run_meld.py
7. Launch REMD:
   launch_remd_multiplex --platform CUDA --debug

### Installing meld (Linux / macOS ONLY)
meld is not published for Windows on conda-forge. Use WSL2 or a Linux/macOS machine.
To enable meld support:
1. Edit conda.yaml and uncomment the line: - meld
2. Recreate (or create a new) environment:
   conda env create -f conda.yaml  # or: conda env update -f conda.yaml --prune
3. Re-run the verification step above.

(Do NOT explicitly install openmpi on Windows; mpi4py will select MS-MPI there automatically.)

### Deprecated example (removed)
Previously documented command (for reference only, not recommended to copy blindly):
  conda install -c conda-forge openmm openmpi mpi4py meld
This is now replaced by using the environment file; openmpi will be auto-resolved on Linux and should not be forced on Windows.

To run meld (after enabling it in the env):
- python run_meld.py
Two new folders will be created: Data and Logs

Ensure CUDA is available (driver + toolkit as needed). If building kernels on an HPC system you may need to set:
export OPENMM_CUDA_COMPILER=/path/to/cuda/bin/nvcc
Example:
export OPENMM_CUDA_COMPILER=/packages/apps/spack/18/opt/spack/gcc-12.1.0/cuda-11.8.0-a4e/bin/nvcc

A detailed sbatch script is given for reference (md.sh)

Finally to run the simulation:
launch_remd_multiplex --platform CUDA --debug

---
### Troubleshooting

Missing module: ModuleNotFoundError: No module named 'openmm'
1. Confirm active environment:
   conda info --envs  # The one with * must be d3-meld-env (or your chosen name)
2. If you accidentally created d3-meld-env-2, activate that exact name:
   conda activate d3-meld-env-2
3. List packages to verify openmm:
   conda list openmm
4. If not present, install:
   conda install -c conda-forge openmm
5. Ensure channel priority (conda-forge first). If not:
   conda config --add channels conda-forge
   conda config --set channel_priority flexible
6. Avoid mixing pip installations for openmm; prefer conda-forge binary.
7. Re-run verification command (step 5 above).

MPI issues (hangs or missing msmpi on Windows):
- Reinstall mpi4py only via conda-forge:
  conda install -c conda-forge --force-reinstall mpi4py

CUDA related errors (e.g., no CUDA platform):
- Check GPU visibility:
  nvidia-smi
- If missing, install matching cudatoolkit in env or rely on system drivers.

Recreating environment cleanly:
conda remove -n d3-meld-env --all
conda env create -f conda.yaml

Report versions for debugging:
python - <<"EOF"
import openmm, mpi4py, sys
print('Python', sys.version)
print('OpenMM', openmm.__version__, openmm.__file__)
import subprocess, json
print('mpi4py OK')
EOF

---
### Quick sanity check command (short form)
python -c "import openmm,mpi4py;print(openmm.__version__)"

