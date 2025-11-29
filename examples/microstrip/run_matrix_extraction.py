"""
Extract the impedance/inductance matrix for the 5-port microstrip example.
This script:
1. Loads the geometry (voxel data).
2. Loads the problem definition from `problem.yaml` (5-port setup).
3. Runs the PEEC solver.
4. Extracts the 5x5 Inductance Matrix using the utils.
"""

import os
import sys
import yaml
import numpy as np
import scisave
import pypeec
from pypeec.utils import matrix

# Path setup
PATH_ROOT = os.path.dirname(__file__)
FOLDER_EXAMPLE = "."
FOLDER_CONFIG = "../config"

def run_matrix_extraction():
    # ---------------------------------------------------------
    # 1. Load Voxel Data (Geometry)
    # ---------------------------------------------------------
    # Note: We assume `run_microstrip.py` has been run at least once 
    # to generate `geometry.yaml` and `voxel.json.gz`.
    # If not, we could invoke the generator here, but let's assume the file exists.
    file_voxel = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "voxel.json.gz")
    if not os.path.exists(file_voxel):
        print("Voxel file not found. Please run 'python run_microstrip.py' first to generate geometry.")
        return

    print(f"Loading voxel data from {file_voxel}...")
    data_voxel_wrap = scisave.load_data(file_voxel)
    data_voxel = data_voxel_wrap["data"]

    # ---------------------------------------------------------
    # 2. Load Problem Definition (5-port setup)
    # ---------------------------------------------------------
    file_problem = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "problem.yaml")
    print(f"Loading problem definition from {file_problem}...")
    with open(file_problem, 'r') as f:
        data_problem = yaml.safe_load(f)

    # ---------------------------------------------------------
    # 3. Load Solver Tolerance
    # ---------------------------------------------------------
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    print(f"Loading tolerance config from {file_tolerance}...")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)

    # ---------------------------------------------------------
    # 4. Run Solver
    # ---------------------------------------------------------
    print("Running PEEC Solver...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)

    if not solution['status']:
        print("Solver FAILED.")
        return

    # ---------------------------------------------------------
    # 5. Extract Inductance Matrix
    # ---------------------------------------------------------
    print("Extracting Inductance Matrix...")

    # Define the list of sweeps that correspond to our port excitations
    # Order must match the columns of the desired matrix
    sweep_list = ["sim_p1", "sim_p2", "sim_p3", "sim_p4", "sim_p5"]

    # Define the terminals (Ports) for matrix extraction
    # Each terminal is a pair of (Source, Sink). 
    # Since we defined our ports with respect to the global ground ("ground_ref"),
    # the "sink" for each port measurement is "ground_ref".
    # However, the matrix utility expects source and sink *domains* in the solution.
    # Our problem.yaml defined current sources at 'port_pX'.
    # The utils.matrix.get_extract extracts V and I.
    # For an N-port system referenced to ground, we typically want V_port - V_ground.
    
    terminal_list = [
        {"src": "port_p1", "sink": "ground_ref"},
        {"src": "port_p2", "sink": "ground_ref"},
        {"src": "port_p3", "sink": "ground_ref"},
        {"src": "port_p4", "sink": "ground_ref"},
        {"src": "port_p5", "sink": "ground_ref"},
    ]

    # Extract raw terminal V, I data
    # This returns matrices of size (n_ports, n_sweeps)
    terminal_data = matrix.get_extract(solution, sweep_list, terminal_list)

    # Compute Z, R, L matrices using least squares
    # This handles the conversion from the raw V,I data to the Z matrix
    result_matrix = matrix.get_matrix(terminal_data)

    # ---------------------------------------------------------
    # 6. Display Results
    # ---------------------------------------------------------
    print("\n" + "="*40)
    print(f"Extraction Results (Freq: {result_matrix['freq']/1e9:.2f} GHz)")
    print("="*40)

    print("\nInductance Matrix [nH]:")
    # Scale to nH for readability
    L_nH = result_matrix["L_mat"] * 1e9
    print(np.array2string(L_nH, precision=3, suppress_small=True))

    print("\nResistance Matrix [mOhm]:")
    # Scale to mOhm
    R_mOhm = result_matrix["R_mat"] * 1e3
    print(np.array2string(R_mOhm, precision=3, suppress_small=True))

    print("\nCoupling Coefficients (Inductive) [%]:")
    k_L = result_matrix["k_L_mat"] * 100
    print(np.array2string(k_L, precision=1, suppress_small=True))

if __name__ == "__main__":
    run_matrix_extraction()
