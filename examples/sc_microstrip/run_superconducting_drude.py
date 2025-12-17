"""
Script for simulating a superconducting microstrip using the full London-Drude model.
Includes temperature dependence and normal fluid losses.
"""

import os
import yaml
import numpy as np
import numpy.linalg as lna
import scipy.constants as cst
import pypeec
import scisave

# --- Simulation Parameters ---
FREQ_LIST = [100e6, 500e6, 1e9, 5e9, 10e9] # 100 MHz to 10 GHz

# --- Geometry Parameters ---
# Note: For kinetic inductance to be significant relative to geometric inductance,
# the film should be thin (comparable to lambda_L) or the path very narrow.
# Here we use a thinner trace than the standard example.
THICKNESS_TRACE = 0.25e-6  # 250 nm (Typical for SC films)
WIDTH_TRACE = 4.0e-6      # 4 um
MARG = 0.4
RESOLUTION = 32.0
LENGTH_TRACE = 50.0e-6    # 50 um
HEIGHT_SUBSTRATE = 1.0e-6  # 4 um

# --- Material Parameters (Niobium Example) ---
TC = 9.2                 # Critical Temperature (K)
T_OP = 4.2               # Operating Temperature (K)
LAMBDA_L0 = 4e-8         # Zero-temp London Penetration Depth (40 nm)
#LAMBDA_L0 = 1e-9         # Fake London Penetration Depth (1 nm)
SIGMA_N0 = 4.0e12        # Normal state conductivity at Tc (S/m) - approx
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
    sweep_pairs = []
    prev_tag = None
    
    for i, freq in enumerate(FREQ_LIST):
        tag_src = f"sim_{int(freq/1e6)}MHz"
        tag_sink = f"{tag_src}_sink"
        sweep_pairs.append((tag_src, tag_sink))
        
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

        source_drive_src = {
            "src": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
            "src_gnd": {"V_re": 0.0, "V_im": 0.0, "Z_re": 0.0, "Z_im": 0.0},
            "sink": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
            "sink_gnd": {"V_re": 0.0, "V_im": 0.0, "Z_re": 0.0, "Z_im": 0.0},
        }

        source_drive_sink = {
            "src": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
            "src_gnd": {"V_re": 0.0, "V_im": 0.0, "Z_re": 0.0, "Z_im": 0.0},
            "sink": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
            "sink_gnd": {"V_re": 0.0, "V_im": 0.0, "Z_re": 0.0, "Z_im": 0.0},
        }

        sweep_solver[tag_src] = {
            "init": prev_tag,
            "param": {
                "freq": freq,
                "material_val": material_val,
                "source_val": source_drive_src,
            },
        }

        sweep_solver[tag_sink] = {
            "init": tag_src,
            "param": {
                "freq": freq,
                "material_val": material_val,
                "source_val": source_drive_sink,
            },
        }

        prev_tag = tag_sink
    
    # 4. Run Solver
    data_problem = create_sc_problem(sweep_solver)
    file_tolerance = os.path.join(PATH_ROOT, FOLDER_CONFIG, "tolerance.yaml")
    with open(file_tolerance, 'r') as f:
        data_tolerance = yaml.safe_load(f)

    print("Running Solver...")
    solution = pypeec.run_solver_data(data_voxel, data_problem, data_tolerance)
    
    # 5. Extract Results
    print("\n--- Extraction Results ---")
    print(f"Temperature: {T_OP} K / {TC} K")
    print(f"{'Freq (MHz)':>15} | {'R_in (Ohm)':>15} | {'L_total (nH)':>15}")
    print("-" * 55)
    
    terminal_list = [
        {"src": "src", "sink": "src_gnd"},
        {"src": "sink", "sink": "sink_gnd"},
    ]

    # Use only sweeps with valid solver/condition status
    data_sweep_all = solution["data_sweep"]

    for tag_src, tag_sink in sweep_pairs:
        sweep_src = data_sweep_all.get(tag_src)
        sweep_sink = data_sweep_all.get(tag_sink)

        invalid_pair = False
        for tag, sweep_info in ((tag_src, sweep_src), (tag_sink, sweep_sink)):
            if sweep_info is None:
                print(f"Skipping {tag}: no sweep data found in solution.")
                invalid_pair = True
                continue

            if not (sweep_info.get("solution_ok", False)
                    and sweep_info.get("solver_ok", False)
                    and sweep_info.get("condition_ok", False)):
                print(
                    f"Skipping {tag}: solution_ok={sweep_info.get('solution_ok')} "
                    f"solver_ok={sweep_info.get('solver_ok')} "
                    f"condition_ok={sweep_info.get('condition_ok')}"
                )
                invalid_pair = True

        if invalid_pair:
            continue

        solution_single = {
            "status": True,
            "data_init": solution["data_init"],
            "data_sweep": {tag_src: sweep_src, tag_sink: sweep_sink},
        }

        sweep_order = [tag_src, tag_sink]
        terminal_data = matrix.get_extract(solution_single, sweep_order, terminal_list)

        # Extract single-port data (Port 1 against its local ground) using the source-driven sweep
        V1 = terminal_data["V_mat"][0, 0]
        I1 = terminal_data["I_mat"][0, 0]
        Z_in = V1 / I1
        
        freq = sweep_src.get("param", {}).get("freq", terminal_data["freq"])
        omega = 2 * np.pi * freq
        
        if omega > 0:
            L_total = Z_in.imag / omega
        else:
            L_total = 0.0
            
        print(f"{freq/1e6:15.1f} | {Z_in.real:15.4f} | {L_total*1e9:15.4f}")

        # Energy-based extraction for short superconducting lines
        integral_total = sweep_info.get("integral_total", {})
        W_e = integral_total.get("W_electric", 0.0)
        W_m = integral_total.get("W_magnetic", 0.0)
        energy_L_eq = 2.0 * W_m / (abs(I1) ** 2) if abs(I1) > 0 else np.nan
        energy_C_eq = 2.0 * W_e / (abs(V1) ** 2) if abs(V1) > 0 else np.nan

        if not np.isnan(energy_L_eq) and not np.isnan(energy_C_eq):
            L_per_m = energy_L_eq / LENGTH_TRACE
            C_per_m = energy_C_eq / LENGTH_TRACE
            Z0_energy = np.sqrt(L_per_m / C_per_m) if C_per_m > 0 else np.nan
            print(
                f"              (energy) Z0≈{Z0_energy:8.4f} Ω, L'={L_per_m*1e6:8.4f} µH/m"
            )

        # Two-port standard extraction (Z-matrix -> S-parameters -> Z0)
        if terminal_data["n_solution"] >= len(terminal_list):
            Z_mat = matrix.get_matrix(terminal_data)["Z_mat"]
            Zref = 50.0
            I_mat = np.eye(2, dtype=np.complex128)
            S_mat = (Z_mat - Zref * I_mat) @ lna.inv(Z_mat + Zref * I_mat)

            # Derive characteristic impedance via standard formula
            num = (1 + S_mat[0, 0]) ** 2 - S_mat[0, 1] ** 2
            den = (1 - S_mat[0, 0]) ** 2 - S_mat[0, 1] ** 2
            Z0_standard = Zref * np.sqrt(num / den)
            print(f"              (std)    Z0≈{Z0_standard.real:8.4f} Ω")
        else:
            print("              (std)    skipped (needs >=2 excitations)")

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