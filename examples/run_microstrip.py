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


def get_rect_coords(cx, cy, width, height):
    """Generate coordinates for a rectangle centered at (cx, cy)."""
    hw = width / 2.0
    hh = height / 2.0
    return [
        [cx - hw, cy - hh],
        [cx + hw, cy - hh],
        [cx + hw, cy + hh],
        [cx - hw, cy + hh],
    ]


def make_shape(layer, shape_type, **data):
    """Helper to create a shape dictionary."""
    return {
        "shape_layer": [layer],
        "shape_operation": "add",
        "shape_type": shape_type,
        "shape_data": data,
    }


def create_microstrip_geometry(
    length_p1_to_stub=43.0e-6,
    length_stub_to_p2=38.0e-6,
    length_stub_p3=28.0e-6,
    length_p4_to_p5=45.0e-6,
    width_trace=4.0e-6,
    thickness_ground=1.0e-6,
    thickness_substrate=1.0e-6,
    thickness_trace=1.0e-6,
    substrate_margin=10.0e-6,
    gap_bottom_bar=1.0e-6,
    resolution=(1.0e-6, 1.0e-6, 0.5e-6),
):
    """
    Generate a Pypeec geometry dictionary for a T-shaped microstrip line with a bottom bar.

    Geometry layout (in the x-y plane):

    - T-shape top trace: horizontal arm from P1 to P2 with vertical stub P3.
    - Bottom bar trace: horizontal line from P4 to P5, below the T-shape.
    - Ground plane and substrate cover the entire structure.

    Parameters
    ----------
    length_p1_to_stub : float
        Horizontal distance from terminal P1 to the center of the vertical stub (left arm).
    length_stub_to_p2 : float
        Horizontal distance from the stub center to terminal P2 (right arm).
    length_stub_p3 : float
        Vertical height of the stub from the main line to terminal P3.
    length_p4_to_p5 : float
        Horizontal length of the bottom bar trace from P4 to P5.
    width_trace : float
        Width of all signal traces (T-shape and bottom bar).
    thickness_ground : float
        Thickness (z) of the ground plane layer.
    thickness_substrate : float
        Thickness (z) of the dielectric substrate layer.
    thickness_trace : float
        Thickness (z) of the signal trace layer.
    substrate_margin : float
        Margin around the traces for the substrate and ground plane extent.
    gap_bottom_bar : float
        Vertical gap between the main T-shape trace and the bottom bar.
    resolution : tuple or float
        Voxel grid resolution (dx, dy, dz) or isotropic float.

    Returns
    -------
    dict
        Geometry definition compatible with ``pypeec.run_mesher_data``.
    """

    # Grid parameters
    if isinstance(resolution, (float, int)):
        dx = dy = dz = float(resolution)
    else:
        dx, dy, dz = resolution

    # Calculate layer counts (ensure at least 1 layer)
    n_gnd = max(1, int(round(thickness_ground / dz)))
    n_sub = max(1, int(round(thickness_substrate / dz)))
    n_top = max(1, int(round(thickness_trace / dz)))

    # Define the layer stack (z direction)
    layer_stack = [
        {"n_layer": n_gnd, "tag_layer": "layer_gnd"},
        {"n_layer": n_sub, "tag_layer": "layer_sub"},
        {"n_layer": n_top, "tag_layer": "layer_top"},
    ]

    # ----- 2D layout in the (x, y) plane -----
    # Place P1 at x=0, y=0, main line along +x, stub upwards (+y)
    L1 = float(length_p1_to_stub)
    L2 = float(length_stub_to_p2)
    L_main = L1 + L2
    L_stub = float(length_stub_p3)
    L_bottom = float(length_p4_to_p5)

    # Main-line rectangle (P1 to P2) and vertical stub (P3)
    # Use explicit rectangles so that all microstrip ends are perfectly rectangular.
    term_len = 2 * dx  # terminal length (two voxels to ensure overlap)

    # Horizontal main line (centered at y = 0)
    coord_main_rect = get_rect_coords(L_main / 2.0, 0.0, L_main, width_trace)

    # Vertical stub: bottom edge on main line (y = 0), height = L_stub
    coord_stub_rect = get_rect_coords(L1, L_stub / 2.0, width_trace, L_stub)

    # Ports P1 and P2 on the main line (T-shape) - rectangular terminals
    coord_p1_rect = get_rect_coords(0.0, 0.0, term_len, width_trace)
    coord_p2_rect = get_rect_coords(L_main, 0.0, term_len, width_trace)

    # Bottom bar (P4 to P5) - positioned below the main line
    hw = float(width_trace) / 2.0
    bottom_bar_y = -hw - float(gap_bottom_bar) - hw
    coord_bottom_rect = get_rect_coords(L_bottom / 2.0, bottom_bar_y, L_bottom, width_trace)

    # P4 and P5 terminals on bottom bar (rectangular)
    coord_p4_rect = get_rect_coords(0.0, bottom_bar_y, term_len, width_trace)
    coord_p5_rect = get_rect_coords(L_bottom, bottom_bar_y, term_len, width_trace)

    # Bounding rectangle for ground and substrate
    # The substrate and ground should be a plate covering the entire microstrip structure
    margin = float(substrate_margin)
    x_min = -margin
    x_max = max(L_main, L_bottom) + margin
    y_min = bottom_bar_y - margin
    y_max = L_stub + margin
    
    coord_rect = [
        [x_min, y_min],
        [x_max, y_min],
        [x_max, y_max],
        [x_min, y_max],
    ]

    # ----- Shape definitions -----
    geometry_shape = {
        # Ground plate: simple rectangular plate
        "ground": [
            make_shape("layer_gnd", "polygon", buffer=0.0, coord_shell=coord_rect, coord_holes=[])
        ],
        # Substrate region: simple rectangular dielectric between ground and traces
        "substrate": [
            make_shape("layer_sub", "polygon", buffer=0.0, coord_shell=coord_rect, coord_holes=[])
        ],
        # T-shaped microstrip conductor (P1–P2 with stub P3) on the top layer
        # Built from rectangles so that all ends are perfectly rectangular.
        "trace": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_main_rect, coord_holes=[]),
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_stub_rect, coord_holes=[]),
        ],
        # Bottom bar microstrip (P4–P5) on the same top layer, isolated from the ground plane
        "trace_bottom": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_bottom_rect, coord_holes=[])
        ],
        # Ports P1 and P2 (signal terminals on T-shape) - rectangular for clean-cut edges
        "src": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_p1_rect, coord_holes=[])
        ],
        "sink": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_p2_rect, coord_holes=[])
        ],
        # Ports P4 and P5 (terminals on bottom bar) - rectangular for clean-cut edges
        "src_bottom": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_p4_rect, coord_holes=[])
        ],
        "sink_bottom": [
            make_shape("layer_top", "polygon", buffer=0.0, coord_shell=coord_p5_rect, coord_holes=[])
        ],
    }
    
    # Construct the complete data structure
    data_geometry = {
        "mesh_type": "shape",
        "data_voxelize": {
            "param": {
                "dx": dx, "dy": dy, "dz": dz,
                "cz": 0.0,
                "simplify": 1.0e-8,
                "construct": None,
                "xy_min": None, "xy_max": None
            },
            "layer_stack": layer_stack,
            "geometry_shape": geometry_shape
        },
        "data_point": {
            "check_cloud": False,
            "filter_cloud": False,
            "pts_cloud": []
        },
        "data_resampling": {
            "use_reduce": False,
            "use_resample": False,
            "resampling_factor": [1, 1, 1]
        },
        "data_conflict": {
            "resolve_rules": True,
            "resolve_random": False,
            "conflict_rules": [
                {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
                {"domain_resolve": ["trace_bottom"], "domain_keep": ["src_bottom", "sink_bottom"]},
                {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
                {"domain_resolve": ["substrate"], "domain_keep": ["trace", "trace_bottom", "src", "sink", "src_bottom", "sink_bottom"]}
            ]
        },
        "data_integrity": {
            "check_integrity": True,
            "domain_connected": {
                "signal_top": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
                "signal_bottom": {"domain_group": [["trace_bottom"], ["src_bottom", "sink_bottom"]], "connected": True},
                "ground": {"domain_group": [["ground"]], "connected": True}
            },
            "domain_adjacent": {}
        }
    }
    
    return data_geometry


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
                "material_type": "electric",  # Dielectric is treated as electric material with complex rho
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
    """
    Define the problem structure mapping logical domains to material types and sources.

    Parameters
    ----------
    sweep_solver : dict
        Solver sweep configuration (frequency points and material/source values).
    base_problem_path : str or None, optional
        Path to a JSON/YAML problem template. If provided, the
        programmatically generated problem definition is merged
        into the loaded template (overriding overlapping keys).

    Returns
    -------
    dict
        Problem definition compatible with ``pypeec.run_solver_data``.
    """
    data_problem = {
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
                "material_type": "electric",  # Dielectric is treated as electric material with complex rho
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

    if base_problem_path is not None:
        base_problem = scisave.load_config(base_problem_path)
        data_problem_merged = copy.deepcopy(base_problem)
        _deep_update(data_problem_merged, data_problem)
        return data_problem_merged

    return data_problem


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
    # 1. Create Geometry
    # We generate the geometry definition programmatically using our helper function
    print("Generating Geometry...")
    # Geometry dimensions follow the sketch (values in meters)
    width_trace = 4.0e-6
    data_geometry = create_microstrip_geometry(
        length_p1_to_stub=43.0e-6,
        length_stub_to_p2=38.0e-6,
        length_stub_p3=28.0e-6,
        length_p4_to_p5=45.0e-6,
        width_trace=width_trace,
        thickness_ground=1.0e-6,
        thickness_substrate=1.0e-6,
        thickness_trace=1.0e-6,
        resolution=width_trace / 8.0,
    )

    # 2. Run Mesher
    # The mesher discretizes the geometry into voxels.
    print("Running Mesher...")
    data_voxel = pypeec.run_mesher_data(data_geometry)

    # 2b. Visualize the voxel structure (optional)
    file_viewer = os.path.join(PATH_ROOT, FOLDER_CONFIG, "viewer.yaml")
    viz_path = os.path.join(PATH_ROOT, "microstrip_viz")
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

    # 5. Load Tolerance Configuration
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)

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
