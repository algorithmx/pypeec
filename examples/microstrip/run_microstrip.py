"""
Script for simulating a microstrip on a dielectric substrate.
The dielectric properties are modeled using complex resistivity.
This example demonstrates how to programmatically define frequency-dependent material properties.
"""

import os
import numpy as np
import scipy.constants as cst
import yaml
import pypeec
import scisave

# Path setup
PATH_ROOT = os.path.dirname(__file__)
FOLDER_EXAMPLE = "microstrip"
FOLDER_CONFIG = "config"



def compute_conductor_resistivity(conductivity, frequency=0.0):
    """
    Compute the resistivity of a conductor.

    Parameters
    ----------
    conductivity : float
        Conductivity in S/m.
    frequency : float
        Frequency in Hz.

    Returns
    -------
    float
        Resistivity (real part) in Ohm*m.
    """
    # Simple DC model: rho = 1/sigma
    # (Future expansion could include skin effect corrections)
    return 1.0 / conductivity


def compute_dielectric_resistivity(frequency, epsilon_r):
    """
    Compute the effective complex resistivity of a dielectric.

    The dielectric properties are modeled using complex resistivity
    to represent the displacement current term in the PEEC formulation.

    rho_eff = 1 / (j * w * eps0 * (eps_r - 1))
    rho_im = -1 / (w * eps0 * (eps_r - 1))

    Parameters
    ----------
    frequency : float
        Frequency in Hz.
    epsilon_r : float
        Relative permittivity.

    Returns
    -------
    tuple of float
        (rho_re, rho_im)
    """
    if frequency <= 0:
        # DC case: Dielectric acts as an insulator (high resistivity)
        return 1e12, 0.0

    w = 2 * np.pi * frequency
    rho_im = -1.0 / (w * cst.epsilon_0 * (epsilon_r - 1.0))
    rho_re = 0.0  # Lossless dielectric approximation

    return rho_re, rho_im


try:
    from microstrip_yaml_generator import SandwichMicrostripGenerator
except ImportError:
    from .microstrip_yaml_generator import SandwichMicrostripGenerator

def create_problem_definition(sweep_solver):
    """
    Define the problem structure mapping logical domains to material types and sources.

    Parameters
    ----------
    sweep_solver : dict
        Solver sweep configuration (frequency points and material/source values).

    Returns
    -------
    dict
        Problem definition compatible with ``pypeec.run_solver_data``.
    """
    return {
        "material_def": {
            "conductor": {
                "domain_list": [
                    "trace",
                    "trace_bottom",
                    "ground",
                    "src",
                    "sink",
                    "src_bottom",
                    "sink_bottom",
                ],
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
            "src_bottom": {
                "domain_list": ["src_bottom"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
            "sink_bottom": {
                "domain_list": ["sink_bottom"],
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


def visualize_voxel(data_voxel, viewer_config_path, output_path, name="geometry"):
    """
    Visualize the voxel structure using PyVista.

    Parameters
    ----------
    data_voxel : dict
        Voxel data returned by ``pypeec.run_mesher_data``.
    viewer_config_path : str
        Path to the viewer configuration YAML file.
    output_path : str
        Directory to save visualization images.
    name : str, optional
        Base name for output files (default: "geometry").
    """
    try:
        data_viewer = scisave.load_config(viewer_config_path)
    except Exception as ex:
        print(f"Viewer configuration could not be loaded ({ex}); skipping visualization.")
        return

    os.makedirs(output_path, exist_ok=True)

    try:
        # Configure top view (XY plane)
        for tag in data_viewer:
            if "data_options" in data_viewer[tag]:
                if "plot_view" in data_viewer[tag]["data_options"]:
                    data_viewer[tag]["data_options"]["plot_view"]["camera_elevation"] = 0.0

        print(f"Generating visualization images in {output_path}...")
        pypeec.run_viewer_data(
            data_voxel,
            data_viewer,
            tag_plot=["domain", "voxelization", "adjacent"],
            plot_mode="png",
            path=output_path,
            name=name,
        )
        print("Visualization saved as PNG files.")
    except Exception as ex:
        print(f"Viewer failed ({ex}); continuing without visualization.")


def visualize_solution(solution, plotter_config_path, output_path, tag_sweep=None, tag_plot=None, name="solution"):
    """
    Visualize the solution using PyVista.

    Parameters
    ----------
    solution : dict
        Solver solution dictionary.
    plotter_config_path : str
        Path to the plotter configuration YAML file.
    output_path : str
        Directory to save visualization images.
    tag_sweep : list, optional
        List of sweep tags to plot (e.g. ["sim_1000MHz"]).
    tag_plot : list, optional
        List of quantities to plot (e.g. ["J_c_norm", "V_c_norm"]).
    name : str, optional
        Base name for output files (default: "solution").
    """
    try:
        data_plotter = scisave.load_config(plotter_config_path)
    except Exception as ex:
        print(f"Plotter configuration could not be loaded ({ex}); skipping visualization.")
        return

    os.makedirs(output_path, exist_ok=True)

    try:
        # Configure top view (XY plane)
        for tag in data_plotter:
            if "data_options" in data_plotter[tag]:
                 # Only apply to PyVista plots
                if "plot_view" in data_plotter[tag]["data_options"]:
                    # Cannot set absolute top view via relative camera API.
                    pass

        print(f"Generating solution images in {output_path}...")
        pypeec.run_plotter_data(
            solution,
            data_plotter,
            tag_sweep=tag_sweep,
            tag_plot=tag_plot,
            plot_mode="png",
            path=output_path,
            name=name,
        )
        print("Solution visualization saved as PNG files.")
    except Exception as ex:
        print(f"Plotter failed ({ex}); continuing without visualization.")


def display_results(solution):
    """
    Display the solver results (status, power, losses).
    """
    print("\nSolver Status:", "OK" if solution['status'] else "FAILED")
    if solution['status']:
        print("\n--- Results ---")
        for tag, data in solution["data_sweep"].items():
            freq = data["freq"]
            
            # Extract source powers
            val_src = data["source_values"]["src"]
            val_sink = data["source_values"]["sink"]
            
            # Compute power: P = 0.5 * Re(V * I*)
            p_src = 0.5 * np.real(val_src["V"] * np.conj(val_src["I"]))
            p_sink = 0.5 * np.real(val_sink["V"] * np.conj(val_sink["I"]))
            
            # Calculate efficiency or loss
            print(f"Frequency: {freq/1e6:6.1f} MHz")
            print(f"  Source Power (Active): {p_src.real:.4e} W")
            print(f"  Sink Power (Load):     {p_sink.real:.4e} W")
            print(f"  Total Losses:          {data['integral_total']['P_total']:.4e} W")
            print("-" * 30)

def run_microstrip():
    # 1. Create Geometry (YAML generation)
    print("Generating Geometry YAML...")
    
    # Geometry parameters
    width_trace = 4.0e-6
    
    # Initialize Generator
    # We use automatic bounding box calculation with a margin to reduce the simulation volume.
    # Resolution set to width_trace / 4.0 (1.0um) for coarser mesh.
    gen = SandwichMicrostripGenerator(
        resolution=width_trace / 4.0, 
        margin=2.0 * width_trace,
        thickness_ground=1.0e-6,
        thickness_substrate=4.0e-6,
        thickness_trace=2.0e-6
    )
    
    # --- Define Shapes (reproducing the T-shape + bottom bar) ---
    # 1. Trace (T-shape)
    # Horizontal main line: center x = 40.5um, y = 0, w = 81um
    gen.add_rect(x=40.5e-6, y=0.0, w=81.0e-6, h=width_trace, domain="trace")
    
    # Vertical stub: center x = 43.0um, y = 14.0um, w = 4um, h = 28um
    gen.add_rect(x=43.0e-6, y=14.0e-6, w=width_trace, h=28.0e-6, domain="trace")
    
    # 2. Trace Bottom
    # Horizontal line: center x = 22.5um, y = -5.0um, w = 45um
    gen.add_rect(x=22.5e-6, y=-5.0e-6, w=45.0e-6, h=width_trace, domain="trace_bottom")
    
    # 3. Ports
    term_w = 1.0e-6 # Terminal width (for connection)
    
    # Src: x=0, y=0
    gen.add_rect(x=0.0, y=0.0, w=term_w, h=width_trace, domain="src")
    
    # Sink: x=81um, y=0
    gen.add_rect(x=81.0e-6, y=0.0, w=term_w, h=width_trace, domain="sink")
    
    # Sink Stub: x=43um, y=42um (tip of the vertical stub)
    # Vertical stub starts at y=14, h=28 -> ends at y=42
    gen.add_rect(x=43.0e-6, y=42.0e-6, w=width_trace, h=term_w, domain="sink_stub")

    # Src Bottom: x=0, y=-5um
    gen.add_rect(x=0.0, y=-5.0e-6, w=term_w, h=width_trace, domain="src_bottom")
    
    # Sink Bottom: x=45um, y=-5um
    gen.add_rect(x=45.0e-6, y=-5.0e-6, w=term_w, h=width_trace, domain="sink_bottom")
    
    # --- Configure Rules ---
    gen.conflict_rules = [
        {"domain_resolve": ["trace"], "domain_keep": ["src", "sink", "sink_stub"]},
        {"domain_resolve": ["trace_bottom"], "domain_keep": ["src_bottom", "sink_bottom"]},
        {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
        {"domain_resolve": ["substrate"], "domain_keep": ["trace", "trace_bottom", "src", "sink", "sink_stub", "src_bottom", "sink_bottom"]}
    ]
    
    gen.domain_connected = {
        "signal_top": {"domain_group": [["trace"], ["src", "sink", "sink_stub"]], "connected": True},
        "signal_bottom": {"domain_group": [["trace_bottom"], ["src_bottom", "sink_bottom"]], "connected": True},
        "ground": {"domain_group": [["ground"]], "connected": True}
    }
    
    # Use automatic bounds calculation based on the margin provided in __init__
    # gen.set_manual_bounds(-10.0e-6, -15.0e-6, 91.0e-6, 38.0e-6)
    
    # Write to file
    yaml_path = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "geometry.yaml")
    gen.write_file(yaml_path)

    # 2. Run Mesher
    # The mesher reads the generated YAML file
    print("Running Mesher from YAML...")
    
    # Use the file-based API
    file_voxel = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "voxel.json.gz") # Or .pkl
    
    # We need to pass absolute paths to pypeec
    pypeec.run_mesher_file(
        file_geometry=yaml_path,
        file_voxel=file_voxel
    )
    
    # Load the voxel data back for the solver (since run_solver_data expects dict)
    # Alternatively, we could use run_solver_file, but the example code below 
    # constructs the problem definition programmatically (data_problem).
    # So we load the voxel data we just generated.
    # Use scisave.load_data to load the file content
    data_voxel = scisave.load_data(file_voxel)
    # The data is wrapped in a metadata structure, extract the raw data.
    data_voxel = data_voxel["data"]

    # 2b. Visualize the voxel structure (optional)
    file_viewer = os.path.join(PATH_ROOT, FOLDER_CONFIG, "viewer.yaml")
    viz_path = os.path.join(PATH_ROOT, "microstrip_viz")
    
    # visualize_voxel expects the data dict, which we now have loaded
    visualize_voxel(data_voxel, file_viewer, viz_path)
    
    # 3. Define Physics Parameters
    # We define a frequency sweep. 
    # Note: Dielectric properties (effective resistivity) depend on frequency.
    freq_list = [1e6, 1e8, 1e9] # 1 MHz, 100 MHz, 1 GHz
    eps_r = 4.4 # Permittivity of FR4
    sigma_cu = 5.8e7 # Conductivity of Copper (S/m)
    
    # Prepare the sweep configuration
    sweep_solver = {}
    for i, freq in enumerate(freq_list):
        tag = f"sim_{int(freq/1e6)}MHz"
        
        # Determine previous solution for initialization (optional but good for convergence)
        init = list(sweep_solver.keys())[-1] if i > 0 else None
        
        # Calculate material properties
        rho_cu = compute_conductor_resistivity(sigma_cu, freq)
        rho_re_diel, rho_im_diel = compute_dielectric_resistivity(freq, eps_r)
            
        # Define sweep parameters
        sweep_solver[tag] = {
            "init": init,
            "param": {
                "freq": freq,
                "material_val": {
                    "conductor": {"rho_re": rho_cu, "rho_im": 0.0},
                    "dielectric": {"rho_re": rho_re_diel, "rho_im": rho_im_diel},
                },
                "source_val": {
                    # Source at trace start (P1): 1V with 50 Ohm impedance
                    "src": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Termination at trace end (P2): 0V (load) with 50 Ohm impedance
                    "sink": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Bottom bar port P4: 1V with 50 Ohm impedance
                    "src_bottom": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Bottom bar port P5: 0V (load) with 50 Ohm impedance
                    "sink_bottom": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    # Ground plane reference: 0V with low impedance (effectively grounded)
                    "ground_src": {"V_re": 0.0, "V_im": 0.0, "Z_re": 1e-6, "Z_im": 0.0}
                }
            }
        }
    
    # 4. Define Problem Structure
    # Maps the logical domains to material types and sources
    data_problem = create_problem_definition(sweep_solver)

    # 5. Load Tolerance Configuration and Configure for PARDISO
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)
    
    # Override factorization settings to use PARDISO exclusively
    # data_tolerance["factorization_options"]["library"] = "PARDISO"
    # data_tolerance["factorization_options"]["pardiso_options"]["thread_pardiso"] = -1  # Auto-detect cores
    # data_tolerance["factorization_options"]["pardiso_options"]["thread_mkl"] = -1      # Auto-detect cores
    
    print("\nSolver Configuration:")
    print(f"  Matrix Factorization: {data_tolerance['factorization_options']['library']}")
    print(f"  PARDISO Threads: {data_tolerance['factorization_options']['pardiso_options']['thread_pardiso']} (auto-detect)")
    print(f"  MKL Threads: {data_tolerance['factorization_options']['pardiso_options']['thread_mkl']} (auto-detect)\n")

    # 6. Run Solver
    print("Running Solver...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)
    
    # 7. Display Results
    display_results(solution)

    # 8. Visualize the Solution (optional)
    file_plotter = os.path.join(PATH_ROOT, FOLDER_CONFIG, "plotter.yaml")
    # Re-use the same visualization directory
    viz_path = os.path.join(PATH_ROOT, "microstrip_viz")
    
    visualize_solution(
        solution,
        file_plotter,
        viz_path,
        tag_sweep=["sim_1000MHz"],  # Plot only the 1 GHz case
        tag_plot=["J_c_norm", "V_c_norm"],  # Plot Current Density and Potential
    )

if __name__ == "__main__":
    run_microstrip()
