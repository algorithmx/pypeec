"""
Extract the impedance/inductance matrix for the straight microstrip line example.
"""

import os
import yaml
import numpy as np
import scisave
import pypeec
from pypeec.utils import matrix

# Path setup
PATH_ROOT = os.path.dirname(__file__)
FOLDER_EXAMPLE = "."
FOLDER_CONFIG = "../config"

def run_straight_matrix_extraction():
    # 1. Load Voxel Data
    file_voxel = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "voxel_straight.json.gz")
    if not os.path.exists(file_voxel):
        print("Voxel file not found. Please run 'python run_straight_line.py' first.")
        return

    print(f"Loading voxel data from {file_voxel}...")
    data_voxel_wrap = scisave.load_data(file_voxel)
    data_voxel = data_voxel_wrap["data"]

    # 2. Load Problem Definition
    file_problem = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "problem_straight.yaml")
    print(f"Loading problem definition from {file_problem}...")
    with open(file_problem, 'r') as f:
        data_problem = yaml.safe_load(f)

    # 3. Load Tolerance
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    print(f"Loading tolerance from {file_tolerance}...")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)

    # 4. Run Solver (we run it again here to ensure we have the solution object for extraction, 
    #    unless we saved the solution to disk in the main script, which we didn't).
    #    Note: In a real workflow, we would save the solution to a file and load it here.
    #    Since the previous script didn't save solution.pkl, we re-run.
    print("Running PEEC Solver for Matrix Extraction...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)

    if not solution['status']:
        print("Solver FAILED.")
        return

    # 5. Extract Matrix
    # For a 2-port line (Input P1, Output P2), we typically want to characterize it.
    # However, our sweep in run_straight_line.py only excited Port 1 (sim_1000MHz).
    # To extract a full 2x2 matrix (or even 1x1 Zin), we need appropriate excitations.
    
    # The matrix extraction utility requires N independent excitations for an N-port system
    # to fully solve for the Z matrix.
    # Our current problem definition only has ONE excitation per frequency (Port 1 driven).
    # This means we can only extracting the input impedance at Port 1 accurately 
    # if we assume Port 2 is loaded as defined (50 ohm).
    
    # To do a proper parameter extraction (e.g. Z-matrix of the 2-port network), 
    # we would need to modify the problem to have 2 sweeps:
    # 1. Drive Port 1, Short/Open Port 2
    # 2. Short/Open Port 1, Drive Port 2
    
    # However, let's just extract the input impedance seen at Port 1 for the current setup.
    # We will define a 1-port extraction "terminal_list".
    
    print("Extracting Input Impedance at Port 1...")
    
    sweep_list = ["sim_1000MHz"]
    
    terminal_list = [
        {"src": "src", "sink": "ground_src"}, 
        # We can also monitor Port 2 voltage/current
        # {"src": "sink", "sink": "ground_src"}, 
    ]
    
    terminal_data = matrix.get_extract(solution, sweep_list, terminal_list)
    
    # Get V and I at Port 1
    V1 = terminal_data["V"][0, 0] # Port 0, Sweep 0
    I1 = terminal_data["I"][0, 0]
    
    Z_in = V1 / I1
    print(f"\nFrequency: 1 GHz")
    print(f"Input Impedance Z_in: {Z_in:.4f} Ohms")
    print(f"  Real: {Z_in.real:.4f}")
    print(f"  Imag: {Z_in.imag:.4f}")

if __name__ == "__main__":
    run_straight_matrix_extraction()
