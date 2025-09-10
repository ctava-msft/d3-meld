
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
nohup bash -lc "conda activate d3-meld-env && launch_remd_multiplex --platform CUDA --debug" > remd.log 2>&1 &

Windows (PowerShell or CMD):
- python -m venv .venv
- .\.venv\Scripts\activate
- pip install -r requirements.txt

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

