"""
Script for simulating a simple straight microstrip line (resembling the P4-P5 bar).
This reuses logic from the main microstrip example.
"""

import os

# Set MKL thread limits BEFORE importing numpy/scipy to avoid hanging
os.environ["MKL_NUM_THREADS"] = "4"
os.environ["OMP_NUM_THREADS"] = "4"
os.environ["NUMEXPR_NUM_THREADS"] = "4"

import yaml
import numpy as np
import pypeec
import scisave

# Import helper functions from the existing example
try:
    from run_microstrip import (
        compute_conductor_resistivity,
        compute_dielectric_resistivity,
        visualize_voxel,
        visualize_solution,
        display_results,
        PATH_ROOT,
        FOLDER_EXAMPLE,
        FOLDER_CONFIG
    )
    from microstrip_yaml_generator import SandwichMicrostripGenerator
except ImportError:
    # Fallback if running from a different directory context
    import sys
    sys.path.append(os.path.dirname(__file__))
    from run_microstrip import (
        compute_conductor_resistivity,
        compute_dielectric_resistivity,
        visualize_voxel,
        visualize_solution,
        display_results,
        PATH_ROOT,
        FOLDER_EXAMPLE,
        FOLDER_CONFIG
    )
    from microstrip_yaml_generator import SandwichMicrostripGenerator

def create_straight_problem_definition(sweep_solver):
    """
    Define the problem structure for the straight line (2 ports + ground).
    """
    return {
        "material_def": {
            "conductor": {
                "domain_list": ["trace", "ground", "src", "sink"],
                "material_type": "electric",
                "orientation_type": "isotropic",
                "var_type": "lumped",
            },
            "dielectric": {
                "domain_list": ["substrate"],
                "material_type": "electric",
                "orientation_type": "isotropic",
                "var_type": "lumped",
            },
        },
        "source_def": {
            "src": {
                "domain_list": ["src"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
            "sink": {
                "domain_list": ["sink"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
            "ground_src": {
                "domain_list": ["ground"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
        },
        "sweep_solver": sweep_solver,
    }

def run_straight_line():
    print("Generating Straight Line Geometry YAML...")
    
    # Geometry parameters
    width_trace = 4.0e-6
    length_trace = 45.0e-6
    
    # Initialize Generator
    gen = SandwichMicrostripGenerator(
        resolution=width_trace / 4.0, 
        margin=2.0 * width_trace,
        thickness_ground=1.0e-6,
        thickness_substrate=4.0e-6,
        thickness_trace=2.0e-6
    )
    
    # --- Define Shapes ---
    # Center the line on X axis, starting at x=0
    # x_center = length/2, y_center = 0
    
    # 1. Trace
    gen.add_rect(x=length_trace/2.0, y=0.0, w=length_trace, h=width_trace, domain="trace")
    
    # 2. Ports
    term_w = 1.0e-6 
    
    # Src: x=0, y=0
    gen.add_rect(x=0.0, y=0.0, w=term_w, h=width_trace, domain="src")
    
    # Sink: x=length, y=0
    gen.add_rect(x=length_trace, y=0.0, w=term_w, h=width_trace, domain="sink")
    
    # --- Configure Rules ---
    # Simplified rules for just one trace domain
    gen.conflict_rules = [
        {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
        {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
        {"domain_resolve": ["substrate"], "domain_keep": ["trace", "src", "sink"]}
    ]
    
    gen.domain_connected = {
        "signal": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
        "ground": {"domain_group": [["ground"]], "connected": True}
    }
    
    # Write to file
    yaml_filename = "geometry_straight.yaml"
    yaml_path = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, yaml_filename)
    gen.write_file(yaml_path)

    # 2. Run Mesher
    print("Running Mesher...")
    voxel_filename = "voxel_straight.json.gz"
    file_voxel = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, voxel_filename)
    
    pypeec.run_mesher_file(
        file_geometry=yaml_path,
        file_voxel=file_voxel
    )
    
    # Load voxel data
    data_voxel_wrap = scisave.load_data(file_voxel)
    data_voxel = data_voxel_wrap["data"]

    # 2b. Visualize
    viz_path = os.path.join(PATH_ROOT, "straight_viz")
    file_viewer = os.path.join(PATH_ROOT, FOLDER_CONFIG, "viewer.yaml")
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    visualize_voxel(data_voxel, file_viewer, viz_path, name="geometry_straight")
    
    # 3. Define Physics
    freq_list = [
        0.01e9, 0.05e9,
        0.1e9, 0.2e9, 0.3e9, 0.4e9, 0.5e9, 0.6e9, 0.7e9, 0.8e9, 0.9e9,
        1.0e9, 2.0e9, 5.0e9
    ]
    eps_r = 4.4
    sigma_cu = 5.8e7
    
    sweep_solver = {}
    for i, freq in enumerate(freq_list):
        tag = f"sim_{int(freq/1e6)}MHz"
        init = list(sweep_solver.keys())[-1] if i > 0 else None
        
        rho_cu = compute_conductor_resistivity(sigma_cu, freq)
        rho_re_diel, rho_im_diel = compute_dielectric_resistivity(freq, eps_r)
            
        sweep_solver[tag] = {
            "init": init,
            "param": {
                "freq": freq,
                "material_val": {
                    "conductor": {"rho_re": rho_cu, "rho_im": 0.0},
                    "dielectric": {"rho_re": rho_re_diel, "rho_im": rho_im_diel},
                },
                "source_val": {
                    # Drive P1 (src) with 1V
                    "src": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Terminate P2 (sink) with 50 Ohm
                    "sink": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Ground
                    "ground_src": {"V_re": 0.0, "V_im": 0.0, "Z_re": 1e-6, "Z_im": 0.0}
                }
            }
        }
    
    # 4. Define Problem
    data_problem = create_straight_problem_definition(sweep_solver)
    
    # Save problem definition to file (for matrix extraction later)
    problem_path = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "problem_straight.yaml")
    with open(problem_path, 'w') as f:
        yaml.dump(data_problem, f, default_flow_style=None, sort_keys=False)
    print(f"Problem definition saved to {problem_path}")

    # 5. Load Tolerance
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)
    
    # Enable GPU acceleration if CuPy is available
    try:
        import cupy
        data_tolerance["dense_options"]["fft_options"]["library"] = "CuPy"
    except ImportError:
        pass

    # 6. Run Solver
    print("Running Solver...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)
    
    # 7. Display Results
    display_results(solution)

    # 8. Visualize Solution
    file_plotter = os.path.join(PATH_ROOT, FOLDER_CONFIG, "plotter.yaml")
    visualize_solution(
        solution,
        file_plotter,
        viz_path,
        tag_sweep=["sim_1000MHz"],
        tag_plot=["J_c_norm", "V_c_norm"],
        name="solution_straight"
    )

if __name__ == "__main__":
    run_straight_line()
