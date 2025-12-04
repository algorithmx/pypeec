# Advanced Superconducting Wire Simulation with London-Drude Theory

This guide provides a comprehensive approach to simulating superconducting structures in PyPEEC using the London-Drude two-fluid model. This method captures both the kinetic inductance and the losses associated with normal fluid quasiparticles at finite temperatures.

## Theory: The Two-Fluid Model

To accurately model a superconductor, we use the London-Drude model which decomposes the total conductivity $\sigma_{\text{total}}$ into two parallel components: the normal fluid ($\sigma_n$) and the superfluid ($\sigma_s$).

$$ \sigma_{\text{total}}(\omega, T) = \sigma_n(\omega, T) + \sigma_s(\omega, T) $$

### 1. Normal Fluid Conductivity ($\sigma_n$)
The normal electrons (quasiparticles) contribute to loss. Their density decreases as temperature drops below the critical temperature $T_c$.

$$ \sigma_n(\omega, T) = \left(\frac{T}{T_c}\right)^4 \sigma_{n0}(\omega) $$

Where $\sigma_{n0}(\omega)$ is the normal state conductivity at $T_c$. For many metals, this can be approximated by the Drude model:
$$ \sigma_{n0}(\omega) = \frac{\sigma_0}{1 + j\omega\tau} \approx \sigma_0 \quad (\text{for } \omega \tau \ll 1) $$

### 2. Superfluid Conductivity ($\sigma_s$)
The Cooper pairs form the superfluid, which is lossless but possesses inertia, giving rise to **kinetic inductance**.

$$ \sigma_s(\omega, T) = \frac{1}{j\omega \mu_0 \lambda_L(T)^2} $$

The temperature-dependent London penetration depth $\lambda_L(T)$ is defined as:

$$ \lambda_L(T) = \frac{\lambda_{L0}}{\sqrt{1 - (T/T_c)^4}} $$

Where $\lambda_{L0}$ is the penetration depth at zero temperature.

### 3. Surface Impedance ($Z_s$)
For surface-based formulations (or when extracting effective properties), the surface impedance is related to the complex conductivity. In the limit where $\sigma_1 \ll \sigma_2$ (typical for good superconductors):

$$ Z_s \approx j\omega \mu_0 \lambda_L(T) $$

This corresponds to a surface inductance $L_{\square} = \mu_0 \lambda_L(T)$.

> **Note**: Simply setting $\sigma \to \infty$ (PEC) results in $Z_s \to 0$, effectively ignoring the kinetic inductance. This leads to significant errors in inductance extraction for superconducting circuits.

## Implementation Guide

The following script `run_superconducting_drude.py` implements the full temperature-dependent London-Drude model.

### Material Parameters
Common values for superconducting materials:

| Material | $T_c$ (K) | $\lambda_{L0}$ (nm) |
| :--- | :--- | :--- |
| **Aluminum (Al)** | 1.20 | ~50 |
| **Niobium (Nb)** | 9.20 | ~32-40 |
| **Tantalum (Ta)** | 4.45 | ~90 |
| **NbTiN** | 14.0 | ~300 |

### Python Implementation

Save the following code as `examples/microstrip/run_superconducting_drude.py`.

```python
"""
Script for simulating a superconducting microstrip using the full London-Drude model.
Includes temperature dependence and normal fluid losses.
"""

import os
import yaml
import numpy as np
import scipy.constants as cst
import pypeec
import scisave

# --- Simulation Parameters ---
FREQ_LIST = [100e6, 500e6, 1e9, 5e9, 10e9] # 100 MHz to 10 GHz

# --- Geometry Parameters ---
# Note: For kinetic inductance to be significant relative to geometric inductance,
# the film should be thin (comparable to lambda_L) or the path very narrow.
# Here we use a thinner trace than the standard example.
THICKNESS_TRACE = 0.1e-6  # 100 nm (Typical for SC films)
WIDTH_TRACE = 2.0e-6      # 2 um
LENGTH_TRACE = 50.0e-6    # 50 um

# --- Material Parameters (Niobium Example) ---
TC = 9.2                  # Critical Temperature (K)
T_OP = 4.2                # Operating Temperature (K)
LAMBDA_L0 = 40e-9         # Zero-temp London Penetration Depth (40 nm)
SIGMA_N0 = 1.0e7          # Normal state conductivity at Tc (S/m) - approx
SIGMA_GND = 5.8e7         # Ground plane conductivity (Copper)

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
    w_eff = max(omega, 1e-3)
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
                "domain_list": ["ground"],
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
        resolution=WIDTH_TRACE / 4.0,  # XY resolution
        margin=2.0 * WIDTH_TRACE,
        thickness_ground=1.0e-6,
        thickness_substrate=4.0e-6,
        thickness_trace=THICKNESS_TRACE
    )
    
    gen.add_rect(x=LENGTH_TRACE/2.0, y=0.0, w=LENGTH_TRACE, h=WIDTH_TRACE, domain="trace")
    term_w = 1.0e-6 
    gen.add_rect(x=0.0, y=0.0, w=term_w, h=WIDTH_TRACE, domain="src")
    gen.add_rect(x=LENGTH_TRACE, y=0.0, w=term_w, h=WIDTH_TRACE, domain="sink")
    
    gen.conflict_rules = [
        {"domain_resolve": ["trace"], "domain_keep": ["src", "sink"]},
        {"domain_resolve": ["ground"], "domain_keep": ["substrate"]},
        {"domain_resolve": ["substrate"], "domain_keep": ["trace", "src", "sink"]}
    ]
    gen.domain_connected = {
        "signal": {"domain_group": [["trace"], ["src", "sink"]], "connected": True},
        "ground": {"domain_group": [["ground"]], "connected": True}
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
    
    for i, freq in enumerate(FREQ_LIST):
        tag = f"sim_{int(freq/1e6)}MHz"
        init = list(sweep_solver.keys())[-1] if i > 0 else None
        
        omega = 2 * np.pi * freq
        
        # Calculate Superconductor Properties
        sigma_sc = compute_london_drude_conductivity(omega, T_OP, TC, LAMBDA_L0, SIGMA_N0)
        
        # Convert conductivity to resistivity (rho = 1/sigma)
        rho_sc = 1.0 / sigma_sc
        
        # Normal Ground
        rho_re_gnd = compute_conductor_resistivity(SIGMA_GND, freq)
        
        # Dielectric
        rho_re_diel, rho_im_diel = compute_dielectric_resistivity(freq, eps_r)
            
        sweep_solver[tag] = {
            "init": init,
            "param": {
                "freq": freq,
                "material_val": {
                    "conductor_sc":  {"rho_re": rho_sc.real, "rho_im": rho_sc.imag},
                    "conductor_gnd": {"rho_re": rho_re_gnd, "rho_im": 0.0},
                    "dielectric":    {"rho_re": rho_re_diel, "rho_im": rho_im_diel},
                },
                "source_val": {
                    "src": {"V_re": 1.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    "sink": {"V_re": 0.0, "V_im": 0.0, "Z_re": 50.0, "Z_im": 0.0},
                    "ground_src": {"V_re": 0.0, "V_im": 0.0, "Z_re": 1e-6, "Z_im": 0.0}
                }
            }
        }
    
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
    
    terminal_list = [{"src": "src", "sink": "ground_src"}]
    
    for tag in sweep_solver.keys():
        terminal_data = matrix.get_extract(solution, [tag], terminal_list)
        
        V1 = terminal_data["V_mat"][0, 0]
        I1 = terminal_data["I_mat"][0, 0]
        Z_in = V1 / I1
        
        freq = terminal_data["freq"]
        omega = 2 * np.pi * freq
        
        if omega > 0:
            L_total = Z_in.imag / omega
        else:
            L_total = 0.0
            
        print(f"{freq/1e6:15.1f} | {Z_in.real:15.4f} | {L_total*1e9:15.4f}")

if __name__ == "__main__":
    run_simulation()
```

## Mesh Resolution Warning

When simulating superconductors using volumetric PEEC, accurate results depend on the mesh resolution relative to the London penetration depth ($\lambda_L$) and the film thickness ($t$).

1.  **Thin Films ($t \approx \lambda_L$)**: If the film thickness is comparable to $\lambda_L$ (e.g., 100 nm), a single voxel layer in the Z-direction is usually sufficient if the bulk conductivity calculated above is applied. The current is effectively uniform.
2.  **Thick Films ($t \gg \lambda_L$)**: If the film is much thicker than $\lambda_L$, the current is confined to a thin surface layer (Meissner effect). Using a coarse volumetric mesh with bulk conductivity will **incorrectly distribution current uniformly**, leading to errors in inductance.
    *   **Mitigation**: Use a mesh resolution comparable to $\lambda_L$ near the surface (computationally expensive) OR use an effective resistivity normalized to the voxel thickness as described in advanced surface impedance formulations.
