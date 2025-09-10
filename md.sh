#!/bin/bash
#SBATCH --job-name=meld_pep
#SBATCH -N 1
#SBATCH -c 16
#SBATCH -t 7-00:00:00             # time in d-hh:mm:s
#SBATCH -p general                # partition
#SBATCH -q public                 # QOS
#SBATCH -G a100:1
#SBATCH --mem=40G
#SBATCH -o slurm.%j.out         # file to save job's STDOUT (%j = JobId)
#SBATCH -e slurm.%j.err         # file to save job's STDERR (%j = JobId)
#SBATCH --export=NONE           # Purge the job-submitting shell environmet

module purge

module load mamba/latest

source activate meld_new

module load cuda-11.8.0-gcc-12.1.0

export OPENMM_CUDA_COMPILER=/packages/apps/spack/18/opt/spack/gcc-12.1.0/cuda-11.8.0-a4e/bin/nvcc

#python_meld pdb_to_fasta.py
#python_meld bias_old.py
#python_meld run_meld.py

if [ -e Logs/remd_000.log ]; then                                       #If there is a remd.log we are conitnuing a killed simulation
    prepare_restart --prepare-run                                       #so we need to prepare_restart
fi

launch_remd_multiplex --platform CUDA --debug

source deactivate
