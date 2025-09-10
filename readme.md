
## Recipe
1. Install Miniconda
2. Create env from provided spec:
   conda env create -f conda.yaml
3. Activate:
   conda activate d3-meld-env
4. Run meld setup script:
   python run_meld.py
5. Run simulation in nohup:
   nohup bash -lc "./run_local.sh --gpus 0,1" > launcher_$(date +%Y%m%d_%H%M%S).log 2>&1 &

## Troubleshooting
- Check GPU visibility:
  nvidia-smi