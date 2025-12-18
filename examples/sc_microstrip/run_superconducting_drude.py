"""
Script for simulating a superconducting microstrip using the full London-Drude model.
Includes temperature dependence and normal fluid losses.
"""

import os
import scilogger
import yaml
import logging
import numpy as np
import numpy.linalg as lna
import scipy.constants as cst
import pypeec
import scisave
# Set default logging level to WARNING before importing pypeec
LOGGER = scilogger.get_logger(__name__, "pypeec")
LOGGER.setLevel("WARNING")

# --- Simulation Parameters ---
FREQ_LIST = [500e6, 1e9] # 100 MHz to 10 GHz

# --- Geometry Parameters ---
# Note: For kinetic inductance to be significant relative to geometric inductance,
# the film should be thin (comparable to lambda_L) or the path very narrow.
# Here we use a thinner trace than the standard example.
THICKNESS_TRACE = 0.5e-6
WIDTH_TRACE = 4.0e-6
MARG = 0.2
RESOLUTION = 16.0
LENGTH_TRACE = 50.0e-6
HEIGHT_SUBSTRATE = 1.0e-6

# --- Material Parameters (Niobium Example) ---
TC = 9.2                 # Critical Temperature (K)
T_OP = 4.2               # Operating Temperature (K)
#LAMBDA_L0 = 4e-8         # Zero-temp London Penetration Depth (40 nm)
LAMBDA_L0 = 1e-9         # Fake London Penetration Depth (1 nm)
SIGMA_N0 = 4.0e7        # Normal state conductivity at Tc (S/m) - approx
SIGMA_GND = 1e20         # Ground plane conductivity (PEC)

# --- Imports ---
try:
    from run_microstrip import (
        compute_dielectric_resistivity,
        compute_conductor_resistivity,
        PATH_ROOT, FOLDER_EXAMPLE, FOLDER_CONFIG
    )
    from microstrip_yaml_generator import SandwichMicrostripGenerator
    from pypeec.utils import matrix
except ImportError:
    import sys
    sys.path.append(os.path.dirname(__file__))
    from run_microstrip import (
        compute_dielectric_resistivity,
        compute_conductor_resistivity,
        PATH_ROOT, FOLDER_EXAMPLE, FOLDER_CONFIG
    )
    from microstrip_yaml_generator import SandwichMicrostripGenerator
    from pypeec.utils import matrix

def compute_london_drude_conductivity(omega, T, Tc, lambda_l0, sigma_n0):
    """
    Compute total complex conductivity using London-Drude Two-Fluid Model.
    
    Returns:
        sigma_total (complex): Total conductivity S/m
    """
    if T >= Tc:
        # Normal state only
        return sigma_n0
    
    t_ratio_4 = (T / Tc) ** 4
    
    # 1. Normal Fluid Contribution (Lossy)
    # sigma_n = (T/Tc)^4 * sigma_n0
    sigma_n = t_ratio_4 * sigma_n0
    
    # 2. Superfluid Contribution (Kinetic Inductance)
    # lambda_L(T) = lambda_L0 / sqrt(1 - (T/Tc)^4)
    lambda_l_sq = (lambda_l0 ** 2) / (1.0 - t_ratio_4)
    
    # sigma_s = 1 / (j * w * mu0 * lambda^2)
    # We use a small epsilon for frequency to avoid division by zero at DC
    w_eff = max(omega, 1e-6)
    sigma_s = 1.0 / (1j * w_eff * cst.mu_0 * lambda_l_sq)
    
    return sigma_n + sigma_s


def create_sc_problem(sweep_solver):
    return {
        "material_def": {
            "conductor_sc": {
                "domain_list": ["trace", "src", "sink"],
                "material_type": "electric",
                "orientation_type": "isotropic",
                "var_type": "lumped",
            },
            "conductor_gnd": {
                "domain_list": ["ground", "src_gnd", "sink_gnd"],
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
            "src_gnd": {
                "domain_list": ["src_gnd"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
            "sink_gnd": {
                "domain_list": ["sink_gnd"],
                "source_type": "voltage",
                "var_type": "lumped",
            },
        },
        "sweep_solver": sweep_solver,
    }


def run_simulation():
    print(f"--- Superconducting Microstrip Simulation (London-Drude) ---")
    print(f"Material: Nb (Tc={TC}K, Lambda0={LAMBDA_L0*1e9}nm)")
    print(f"Operating Temp: {T_OP}K")
    
    # 1. Generate Geometry (Thinner trace for SC)
    print("Generating Geometry...")
    # Adjust resolution for thin trace
    resolution = THICKNESS_TRACE  # Need fine mesh for thin film
    # NOTE: In a real scenario, you might want even finer mesh or specialized elements
    
    gen = SandwichMicrostripGenerator(
        resolution=WIDTH_TRACE / RESOLUTION,  # XY resolution
        margin= MARG * WIDTH_TRACE,
        thickness_ground=1.0e-6,
        thickness_substrate=HEIGHT_SUBSTRATE,
        thickness_trace=THICKNESS_TRACE
    )
    
    gen.add_rect(x=LENGTH_TRACE/2.0, y=0.0, w=LENGTH_TRACE, h=WIDTH_TRACE, domain="trace")
    term_w = 1.0e-6 
    gen.add_rect(x=0.0, y=0.0, w=term_w, h=WIDTH_TRACE, domain="src")
    gen.add_rect(x=LENGTH_TRACE, y=0.0, w=term_w, h=WIDTH_TRACE, domain="sink")
    
    # Add ground terminals
    gen.add_rect(x=0.0, y=0.0, w=term_w, h=WIDTH_TRACE, domain="src_gnd", layer="layer_gnd")
    gen.add_rect(x=LENGTH_TRACE, y=0.0, w=term_w, h=WIDTH_TRACE, domain="sink_gnd", layer="layer_gnd")
    
    gen.conflict_rules = [
        {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
        {"domain_resolve": ["ground"], "domain_keep": ["src_gnd", "sink_gnd", "substrate"]},
        {"domain_resolve": ["substrate"], "domain_keep": ["trace", "src", "sink"]}
    ]
    gen.domain_connected = {
        "signal": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
        "ground": {"domain_group": [["ground"], ["src_gnd", "sink_gnd"]], "connected": True}
    }
    
    yaml_path = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, "geometry_drude.yaml")
    gen.write_file(yaml_path)

    # 2. Run Mesher
    print("Running Mesher...")
    voxel_filename = "voxel_drude.json.gz"
    file_voxel = os.path.join(PATH_ROOT, FOLDER_EXAMPLE, voxel_filename)
    
    # Note: Ideally, z-resolution should match thickness. 
    # The generator uses 'resolution' param primarily for XY. 
    # Ensure the mesh generator handles thin Z layers correctly.
    pypeec.run_mesher_file(file_geometry=yaml_path, file_voxel=file_voxel)
    data_voxel = scisave.load_data(file_voxel)["data"]

    # 3. Define Frequency Sweep
    eps_r = 4.4
    sweep_solver = {}
    sweep_list = []
    prev_tag = None
    
    for i, freq in enumerate(FREQ_LIST):
        tag_src = f"sim_{int(freq/1e6)}MHz"
        sweep_list.append(tag_src)
        
        omega = 2 * np.pi * freq
        
        # Calculate Superconductor Properties
        sigma_sc = compute_london_drude_conductivity(omega, T_OP, TC, LAMBDA_L0, SIGMA_N0)
        
        # Convert conductivity to resistivity (rho = 1/sigma)
        rho_sc = 1.0 / sigma_sc
        
        # Normal Ground
        rho_re_gnd = compute_conductor_resistivity(SIGMA_GND, freq)
        
        # Dielectric
        rho_re_diel, rho_im_diel = compute_dielectric_resistivity(freq, eps_r)
        
        material_val = {
            "conductor_sc":  {"rho_re": rho_sc.real, "rho_im": rho_sc.imag},
            "conductor_gnd": {"rho_re": rho_re_gnd, "rho_im": 0.0},
            "dielectric":    {"rho_re": rho_re_diel, "rho_im": rho_im_diel},
        }

        all_zero = {"V_re": 0.0, "V_im": 0.0, "Z_re": 0.0, "Z_im": 0.0}
        Z0 = {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0}
        V_excitation = {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0}
        sweep_solver[tag_src] = {
            "init": prev_tag,
            "param": {
                "freq": freq,
                "material_val": material_val,
                "source_val": {
                    "src": V_excitation, "sink": Z0,
                    "src_gnd": all_zero, "sink_gnd": all_zero,
                },
            },
        }

        prev_tag = tag_src
    
    # 4. Run Solver
    data_problem = create_sc_problem(sweep_solver)
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)

    print("Running Solver...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)
    
    # 5. Extract Results
    print(f"\n--- Extraction Results ---")
    print(f"Temperature: {T_OP} K / {TC} K")
    print(f"{'Freq (MHz)':>10} | {'Z0_std':>10} | {'L\'_nrg':>10} | {'C\'_nrg':>10} | {'L\'_T':>10} | {'C\'_T':>10}")
    print(f"{'':>10} | {'(Ohm)':>10} | {'(uH/m)':>10} | {'(pF/m)':>10} | {'(uH/m)':>10} | {'(pF/m)':>10}")
    print("-" * 85)
    
    terminal_list = [
        {"src": "src", "sink": "src_gnd"},
        {"src": "sink", "sink": "sink_gnd"},
    ]

    # Use only sweeps with valid solver/condition status
    data_sweep_all = solution["data_sweep"]

    for tag_src in sweep_list:
        sweep_src = data_sweep_all.get(tag_src)

        if sweep_src is None:
            print(f"Skipping {tag_src}: no sweep data found in solution.")
            continue

        if not (sweep_src.get("solution_ok", False)
                and sweep_src.get("solver_ok", False)
                and sweep_src.get("condition_ok", False)):
            print(
                f"Skipping {tag_src}: solution_ok={sweep_src.get('solution_ok')} "
                f"solver_ok={sweep_src.get('solver_ok')} "
                f"condition_ok={sweep_src.get('condition_ok')}"
            )
            continue

        solution_single = {
            "status": True,
            "data_init": solution["data_init"],
            "data_sweep": {tag_src: sweep_src},
        }

        sweep_order = [tag_src]
        terminal_data = matrix.get_extract(solution_single, sweep_order, terminal_list)
        
        # Apply symmetry to generate the second port excitation data
        # [0, 1] -> Original data (Port 1 driven)
        # [1, 0] -> Swapped data (Port 2 driven, assuming symmetry)
        terminal_data = matrix.get_symmetry(terminal_data, [[0, 1], [1, 0]])

        # Extract single-port data (Port 1 against its local ground) using the source-driven sweep
        V1 = terminal_data["V_mat"][0, 0]
        I1 = terminal_data["I_mat"][0, 0]
        Z_in = V1 / I1
        
        freq = sweep_src.get("param", {}).get("freq", terminal_data["freq"])
        omega = 2 * np.pi * freq
        
        # Energy-based extraction for short superconducting lines
        integral_total = sweep_src.get("integral_total", {})
        S_total = integral_total.get("S_total", 0.0)
        W_e = integral_total.get("W_electric", 0.0)
        
        if omega > 0:
            Q_reactive = S_total.imag
            W_m_inferred = W_e + Q_reactive / (2 * omega)
        else:
            W_m_inferred = 0.0
        
        I_ref = abs(I1)
        V_ref = abs(V1)

        energy_L_eq = 2.0 * W_m_inferred / (I_ref ** 2) if I_ref > 0 else np.nan
        energy_C_eq = 2.0 * W_e / (V_ref ** 2) if V_ref > 0 else np.nan

        Z0_energy_val = np.nan
        L_per_m = np.nan
        C_per_m = np.nan

        if not np.isnan(energy_L_eq) and not np.isnan(energy_C_eq) and energy_L_eq > 0 and energy_C_eq > 0:
            L_per_m = energy_L_eq / LENGTH_TRACE
            C_per_m = energy_C_eq / LENGTH_TRACE
            Z0_energy_val = np.sqrt(L_per_m / C_per_m)

        # Two-port standard extraction (Z-matrix -> S-parameters -> Z0)
        Z0_std_val = np.nan
        L_per_m_T = np.nan
        C_per_m_T = np.nan

        if terminal_data["n_solution"] >= len(terminal_list):
            Z_mat = matrix.get_matrix(terminal_data)["Z_mat"]
            Zref = 50.0
            I_mat = np.eye(2, dtype=np.complex128)
            S_mat = (Z_mat - Zref * I_mat) @ lna.inv(Z_mat + Zref * I_mat)

            # Derive characteristic impedance via standard formula
            num = (1 + S_mat[0, 0]) ** 2 - S_mat[0, 1] ** 2
            den = (1 - S_mat[0, 0]) ** 2 - S_mat[0, 1] ** 2
            Z0_standard = Zref * np.sqrt(num / den)
            Z0_std_val = Z0_standard.real

            # T-Network Extraction (Lumped Model)
            if omega > 0:
                Z11_im = Z_mat[0, 0].imag
                Z12_im = Z_mat[0, 1].imag
                
                # C_total = -1 / (omega * Im(Z12))
                if abs(Z12_im) > 1e-12:
                    C_total = -1.0 / (omega * Z12_im)
                    C_per_m_T = C_total / LENGTH_TRACE
                
                # L_arm = (Im(Z11) - Im(Z12)) / omega
                L_arm = (Z11_im - Z12_im) / omega
                # Total Inductance = 2 * L_arm (series)
                L_per_m_T = (2 * L_arm) / LENGTH_TRACE

        # Print Row
        str_freq = f"{freq/1e6:10.1f}"
        str_z0_std = f"{Z0_std_val:10.4f}" if not np.isnan(Z0_std_val) else f"{'NaN':>10}"
        
        str_l_nrg = f"{L_per_m*1e6:10.4f}" if not np.isnan(L_per_m) else f"{'NaN':>10}"
        str_c_nrg = f"{C_per_m*1e12:10.4f}" if not np.isnan(C_per_m) else f"{'NaN':>10}"
        
        str_l_t = f"{L_per_m_T*1e6:10.4f}" if not np.isnan(L_per_m_T) else f"{'NaN':>10}"
        str_c_t = f"{C_per_m_T*1e12:10.4f}" if not np.isnan(C_per_m_T) else f"{'NaN':>10}"
        
        print(f"{str_freq} | {str_z0_std} | {str_l_nrg} | {str_c_nrg} | {str_l_t} | {str_c_t}")

    # --- Optional Visualization (voxel + solution) ---
    def visualize_voxel(data_voxel, viewer_config_path, output_path, name="geometry"):
        try:
            data_viewer = scisave.load_config(viewer_config_path)
        except Exception as ex:
            print(f"Viewer configuration could not be loaded ({ex}); skipping visualization.")
            return

        os.makedirs(output_path, exist_ok=True)

        try:
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
        try:
            data_plotter = scisave.load_config(plotter_config_path)
        except Exception as ex:
            print(f"Plotter configuration could not be loaded ({ex}); skipping visualization.")
            return

        os.makedirs(output_path, exist_ok=True)

        try:
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

    # Perform visualization using project's viewer/plotter configs (if available)
    try:
        file_viewer = os.path.join(PATH_ROOT, FOLDER_CONFIG, "viewer.yaml")
        file_plotter = os.path.join(PATH_ROOT, FOLDER_CONFIG, "plotter.yaml")
        viz_path = os.path.join(PATH_ROOT, "microstrip_drude_viz")

        # Offscreen rendering for headless environments
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

        # Visualize the mesh/voxel
        visualize_voxel(data_voxel, file_viewer, viz_path, name="geometry_drude")

        # Visualize the solution for the highest frequency (if present)
        visualize_solution(
            solution,
            file_plotter,
            viz_path,
            tag_sweep=[list(sweep_solver.keys())[-1]] if len(sweep_solver) > 0 else None,
            tag_plot=["J_c_norm", "V_c_norm"],
            name="solution_drude",
        )
    except Exception as ex:
        print(f"Visualization step encountered an error ({ex}); skipping visuals.")

if __name__ == "__main__":
    run_simulation()