C:\Users\christava\AppData\Local\miniforge3\python.exe extract_from_netcdf.py --replica 10 --output trajectory.10.dcd
Found 51 block files
Loading topology from Data\trajectory.pdb...
Processing 51 block files for replica 10...
First block structure:
  Dimensions: {'n_replicas': 30, 'n_replica_pairs': 29, 'n_atoms': 3988, 'cartesian': 3, 'timesteps': 1, 'n_discrete_parameters': 0, 'n_continuous_parameters': 0, 'n_mappings': 0, 'n_alignments': 0, 'n_energy_groups': 7}
  Variables: ['positions', 'velocities', 'box_vectors', 'alphas', 'energies', 'group_energies', 'permutation_vectors', 'energy_matrix', 'acceptance_probabilities', 'discrete_parameters', 'continuous_parameters', 'mappings', 'rdc_alignments']
  Positions shape: (30, 3988, 3, 1)
  Processed 10/51 blocks, 55 frames extracted
  Processed 20/51 blocks, 210 frames extracted
  Processed 30/51 blocks, 465 frames extracted
  Processed 40/51 blocks, 820 frames extracted
  Processed 50/51 blocks, 1275 frames extracted

✅ Extracted 1326 frames total
Positions array shape: (1326, 3988, 3)
Saving to trajectory.10.dcd...
✅ Successfully saved trajectory to trajectory.10.dcd
   File size: 60.55 MB


C:\Users\christava\AppData\Local\miniforge3\python.exe extract_from_netcdf.py --replica 20 --output trajectory.20.dcd
Found 51 block files
Loading topology from Data\trajectory.pdb...
Processing 51 block files for replica 20...
First block structure:
  Dimensions: {'n_replicas': 30, 'n_replica_pairs': 29, 'n_atoms': 3988, 'cartesian': 3, 'timesteps': 1, 'n_discrete_parameters': 0, 'n_continuous_parameters': 0, 'n_mappings': 0, 'n_alignments': 0, 'n_energy_groups': 7}
  Variables: ['positions', 'velocities', 'box_vectors', 'alphas', 'energies', 'group_energies', 'permutation_vectors', 'energy_matrix', 'acceptance_probabilities', 'discrete_parameters', 'continuous_parameters', 'mappings', 'rdc_alignments']
  Positions shape: (30, 3988, 3, 1)
  Processed 10/51 blocks, 55 frames extracted
  Processed 20/51 blocks, 210 frames extracted
  Processed 30/51 blocks, 465 frames extracted
  Processed 40/51 blocks, 820 frames extracted
  Processed 50/51 blocks, 1275 frames extracted

✅ Extracted 1326 frames total
Positions array shape: (1326, 3988, 3)
Saving to trajectory.20.dcd...
✅ Successfully saved trajectory to trajectory.20.dcd
   File size: 60.55 MB

30

 C:\Users\christava\AppData\Local\miniforge3\python.exe extract_from_netcdf.py --replica 30 --output trajectory.30.dcd
Found 51 block files
Loading topology from Data\trajectory.pdb...
Processing 51 block files for replica 30...
First block structure:
  Dimensions: {'n_replicas': 30, 'n_replica_pairs': 29, 'n_atoms': 3988, 'cartesian': 3, 'timesteps': 1, 'n_discrete_parameters': 0, 'n_continuous_parameters': 0, 'n_mappings': 0, 'n_alignments': 0, 'n_energy_groups': 7}
  Variables: ['positions', 'velocities', 'box_vectors', 'alphas', 'energies', 'group_energies', 'permutation_vectors', 'energy_matrix', 'acceptance_probabilities', 'discrete_parameters', 'continuous_parameters', 'mappings', 'rdc_alignments']
  Positions shape: (30, 3988, 3, 1)
Warning: Could not process block Data\Blocks\block_000000.nc: Replica 30 out of range (max: 29)        
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 65, in extract_replica_from_blocks
    raise ValueError(f"Replica {replica_idx} out of range (max: {n_replicas-1})")
ValueError: Replica 30 out of range (max: 29)
Warning: Could not process block Data\Blocks\block_000001.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000002.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000003.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000004.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000005.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000006.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000007.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000008.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000009.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000010.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000011.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000012.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000013.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000014.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000015.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000016.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000017.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^
  File "src\\netCDF4\\_netCDF4.pyx", line 5079, in netCDF4._netCDF4.Variable.__getitem__
  File "src\\netCDF4\\_netCDF4.pyx", line 6049, in netCDF4._netCDF4.Variable._get
IndexError: index exceeds dimension bounds
Warning: Could not process block Data\Blocks\block_000018.nc: index exceeds dimension bounds
Traceback (most recent call last):
  File "C:\Users\christava\Documents\src\github.com\ctava-msft\customers-top\mayo-top\d3-meld\extract_from_netcdf.py", line 68, in extract_replica_from_blocks
    replica_data = positions_var[replica_idx, :, :, :]
                   ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^