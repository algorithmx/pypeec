### **Documentation: `problem.yaml` Guide**

The `problem.yaml` file is the core configuration for the **pypeec solver**. It defines the physics of the problem, including material properties, source excitations, and the frequency sweep configuration.

#### **1. File Structure Overview**
The file is a YAML document containing three required top-level sections:
*   **`material_def`**: Defines the physical characteristics of materials (e.g., copper, air, ferrite).
*   **`source_def`**: Defines the excitation sources (voltage or current) applied to specific domains.
*   **`sweep_solver`**: Defines the simulation steps (frequencies) and the specific values for materials and sources at those steps.

---

#### **2. Material Definition (`material_def`)**
This section maps geometry domains (from your mesh) to material types.

**Structure:**
```yaml
"material_def":
    "material_name":  # User-defined name (e.g., "copper", "core")
        "domain_list": ["domain1", "domain2"]  # List of geometry domains
        "material_type": "electric" | "magnetic" | "electromagnetic"
        "orientation_type": "isotropic" | "anisotropic"
        "var_type": "lumped" | "distributed"
```

**Fields:**
*   **`domain_list`**: A list of strings matching the domain names defined in your geometry/mesh file.
*   **`material_type`**:
    *   `"electric"`: Has conductivity (Resistivity $\rho$). Susceptibility $\chi = 0$.
    *   `"magnetic"`: Has magnetic properties (Susceptibility $\chi$). Conductivity $\sigma = 0$.
    *   `"electromagnetic"`: Has both conductivity and magnetic susceptibility.
*   **`orientation_type`**:
    *   `"isotropic"`: Properties are the same in all directions (scalar value).
    *   `"anisotropic"`: Properties differ in x, y, z directions (vector value).
*   **`var_type`**:
    *   `"lumped"`: Homogeneous material. One value applies to the entire domain.
    *   `"distributed"`: Inhomogeneous material. Values vary per voxel (requires an array of values).

---

#### **3. Source Definition (`source_def`)**
This section defines where excitations are applied. Sources can only be applied to "electric" domains.

**Structure:**
```yaml
"source_def":
    "source_name":  # User-defined name (e.g., "src_in", "voltage_src")
        "domain_list": ["domain_src"]
        "source_type": "current" | "voltage"
        "var_type": "lumped" | "distributed"
```

**Fields:**
*   **`source_type`**:
    *   `"current"`: Defines a current source $I$ with an internal admittance $Y$.
    *   `"voltage"`: Defines a voltage source $V$ with an internal impedance $Z$.
*   **`var_type`**: Same as in material definition (usually `"lumped"` for simple sources).

---

#### **4. Sweep Solver (`sweep_solver`)**
This section defines the actual simulation points. You can define multiple simulations (e.g., DC, AC_1kHz, AC_1MHz).

**Structure:**
```yaml
"sweep_solver":
    "simulation_name":  # e.g., "sim_dc", "sim_ac"
        "init": null | "previous_sim_name"  # Initial guess for iterative solver
        "param":
            "freq": 0.0  # Frequency in Hz
            "material_val": { ... }
            "source_val": { ... }
```

**Fields:**
*   **`init`**: The name of a previous simulation to use as an initial guess. Use `null` if no initial guess is needed.
*   **`freq`**: The operating frequency in Hertz. Use `0.0` for DC.

**`material_val`**:
Defines the numerical values for the materials declared in `material_def`.
*   **Electric Materials**: Require `rho_re` (Real Resistivity) and `rho_im` (Imaginary Resistivity).
    *   $\rho = \rho_{re} + j \cdot \rho_{im}$
*   **Magnetic Materials**: Require `chi_re` (Real Susceptibility) and `chi_im` (Imaginary Susceptibility).
    *   $\chi = \chi_{re} - j \cdot \chi_{im}$
*   **Electromagnetic**: Requires all four (`rho` and `chi`).

**`source_val`**:
Defines the numerical values for sources declared in `source_def`.
*   **Current Source**:
    *   `I_re`, `I_im`: Source Current (Real/Imaginary) in Amps.
    *   `Y_re`, `Y_im`: Internal Admittance in Siemens ($1/\Omega$).
*   **Voltage Source**:
    *   `V_re`, `V_im`: Source Voltage (Real/Imaginary) in Volts.
    *   `Z_re`, `Z_im`: Internal Impedance in Ohms ($\Omega$).

**Data Formats for Values:**
*   **Lumped Isotropic**: Single scalar value (e.g., `1.75e-8`).
*   **Lumped Anisotropic**: List of 3 values `[x, y, z]`.
*   **Distributed Isotropic**: List of $N$ values (where $N$ is the number of voxels in the domain).
*   **Distributed Anisotropic**: List of lists `(N, 3)`.

---

#### **5. What is Computed?**
The solver uses the **Partial Element Equivalent Circuit (PEEC)** method to solve Maxwell's equations in the integral form.

**The System Solves For:**
1.  **Electric Currents ($I_{fc}$)**: Currents flowing through the faces of electric voxels.
2.  **Electric Potentials ($V_{vc}$)**: Scalar potentials at the centers of electric voxels.
3.  **Magnetic Fluxes ($I_{fm}$)**: Magnetic flux flowing through the faces of magnetic voxels.
4.  **Magnetic Potentials ($V_{vm}$)**: Magnetic scalar potentials at the centers of magnetic voxels.
5.  **Source Variables**: Currents and voltages at the source terminals.

**Physics Modeled:**
*   **Resistive & Inductive effects**: Captured via the electric circuit equations (KVL/KCL).
*   **Magnetic effects**: Captured via the magnetic circuit equations (reluctance/permeance).
*   **Couplings**: Inductive and potential couplings between all elements in the mesh.

**Example Snippet:**
```yaml
"sweep_solver":
    "sim_ac":
        "init": null
        "param":
            "freq": 1000.0
            "material_val":
                "copper": {"rho_re": 1.72e-8, "rho_im": 0.0}
            "source_val":
                "src_in": {"V_re": 1.0, "V_im": 0.0, "Z_re": 0.001, "Z_im": 0.0}
```

---

#### **6. Matrix Extraction & Circuit Fitting**
Pypeec provides utilities to extract the N-port impedance matrix ($Z$) of a system and fit it to an equivalent circuit model (L/R).

**Concept:**
To extract an $N \times N$ impedance matrix for an $N$-port system, you must perform $N$ linearly independent simulations (sweeps). In each sweep, you typically excite one port while leaving others open (for Z-parameters) or shorted (for Y-parameters), though the solver handles the linear algebra for you if you provide the terminal data.

**Step-by-Step Guide:**

1.  **Define Terminals in `problem.yaml`**:
    Ensure your `source_def` includes all the ports you want to extract.
    ```yaml
    "source_def":
        "port1_src": { ... }
        "port1_sink": { ... }
        "port2_src": { ... }
        "port2_sink": { ... }
    ```

2.  **Configure Sweeps**:
    Define a separate simulation in `sweep_solver` for each excitation case.
    ```yaml
    "sweep_solver":
        "sim_port1": { ... } # Excite port 1
        "sim_port2": { ... } # Excite port 2
    ```

3.  **Use the Python API for Extraction**:
    Create a Python script (e.g., `run_matrix.py`) to process the results using `pypeec.utils.matrix`.

    ```python
    from pypeec.utils import matrix

    # 1. Define the mapping from source names to logical terminals
    terminal_list = [
        {"src": "port1_src", "sink": "port1_sink"},
        {"src": "port2_src", "sink": "port2_sink"},
    ]

    # 2. Define which sweeps correspond to the extraction
    sweep_list = ["sim_port1", "sim_port2"]

    # 3. Extract raw terminal data (Voltage/Current)
    # data_solution is the output from pypeec.run_solver_data()
    terminal_data = matrix.get_extract(data_solution, sweep_list, terminal_list)

    # 4. Compute the Impedance Matrix
    z_matrix_data = matrix.get_matrix(terminal_data)
    ```

**Output Interpretation:**
The `z_matrix_data` dictionary contains:
*   **`Z_mat`**: The complex impedance matrix ($Z = R + j\omega L$).
*   **`R_mat`**: The resistance matrix ($Re(Z)$).
*   **`L_mat`**: The inductance matrix ($Im(Z) / \omega$).
*   **`k_L_mat`**: Inductive coupling coefficients.

**Circuit Fitting:**
The extracted `R_mat` and `L_mat` correspond to a series R-L circuit model at the simulated frequency.
*   **Self-Impedance ($Z_{ii}$)**: Modeled as a resistor $R_{ii}$ in series with an inductor $L_{ii}$.
*   **Mutual Impedance ($Z_{ij}$)**: Modeled as a mutual inductance $M_{ij} = L_{ij}$ (and potentially mutual resistance).

For wideband models, you must run this extraction at multiple frequencies and perform curve fitting (e.g., Vector Fitting) on the resulting $Z(f)$ data, which is outside the scope of the core pypeec solver but can be done using the extracted data.

---

#### **7. Setting Frequency-Dependent Material Properties**

In **pypeec**, material properties (permittivity, conductivity, permeability) are **not defined as functions of frequency** directly within the solver. Instead, the solver operates on a **per-sweep basis**.

To simulate frequency-dependent materials (e.g., for a Debye or Drude model, or measured data), you must explicitly calculate the material parameters for each frequency point you wish to simulate and define a separate sweep for each.

**The Mechanism:**
The `problem.yaml` file defines a `sweep_solver` section where multiple simulations (`sim_1`, `sim_2`, etc.) are defined. Each simulation has its own:
*   **Frequency** (`freq`)
*   **Material Values** (`material_val`)

The solver treats each sweep independently (except for the initial guess `init`). This means you can change the material properties for every single frequency point.

**How to Implement It:**

**Option A: Manual Definition (Small number of points)**
If you only have a few frequency points, you can manually define them in `problem.yaml`:

```yaml
"sweep_solver":
    "sim_1kHz":
        "param":
            "freq": 1000.0
            "material_val":
                "ferrite_core": {"chi_re": 2000.0, "chi_im": 50.0} # High permeability at low freq
    "sim_1MHz":
        "param":
            "freq": 1.0e+6
            "material_val":
                "ferrite_core": {"chi_re": 1500.0, "chi_im": 200.0} # Lower permeability, higher loss
```

**Option B: Programmatic Generation (Recommended)**
For complex frequency dependencies (e.g., 100 points following a specific dispersion model), you should generate the `problem.yaml` (or the dictionary passed to the solver) using Python.

**Example Python Script:**

```python
import numpy as np
import pypeec

# 1. Define your frequency vector
freq_vec = np.logspace(3, 8, 20) # 1kHz to 100MHz

# 2. Define your material model function
def get_ferrite_chi(f):
    # Example: Simple relaxation model
    chi_static = 2000.0
    f_relax = 1e6
    chi_complex = chi_static / (1 + 1j * f / f_relax)
    return chi_complex.real, -chi_complex.imag # Note: pypeec uses chi = re - j*im

# 3. Construct the sweep_solver dictionary programmatically
sweep_solver_config = {}

for i, f in enumerate(freq_vec):
    sim_name = f"sim_{i}"
    chi_re, chi_im = get_ferrite_chi(f)
    
    sweep_solver_config[sim_name] = {
        "init": f"sim_{i-1}" if i > 0 else None, # Use previous solution as guess
        "param": {
            "freq": float(f),
            "material_val": {
                "core_material": {
                    "chi_re": float(chi_re), 
                    "chi_im": float(chi_im)
                },
                "copper": {
                    "rho_re": 1.72e-8, 
                    "rho_im": 0.0
                }
            },
            "source_val": { ... }
        }
    }

# 4. Run the solver with this generated config
# (Assuming you have loaded data_geometry and data_tolerance)
data_problem = {
    "material_def": { ... },
    "source_def": { ... },
    "sweep_solver": sweep_solver_config
}

pypeec.run_solver_data(data_voxel=..., data_problem=data_problem, ...)
```

**Complex Permittivity & Permeability:**

*   **Conductivity / Permittivity**:
    Pypeec uses **Resistivity ($\rho$)**. If you have complex permittivity $\epsilon = \epsilon' - j\epsilon''$, you must convert it to equivalent complex resistivity.
    *   $\sigma_{eff} = \omega \epsilon'' + j\omega(\epsilon' - \epsilon_0)$ (This depends on the exact formulation, but usually PEEC is formulated with conductivity).
    *   In `pypeec`, `rho` is defined as $\rho = \rho_{re} + j\rho_{im}$.
    *   **Note**: Pypeec is primarily a Magneto-Quasi-Static (MQS) solver. It models **conduction currents** well. Displacement currents (dielectrics) are often neglected or modeled as capacitive effects in the circuit extraction phase, not typically as a bulk material property in the MQS volume integral formulation unless specifically supported (the code shows `electric` materials defined by `rho`).

*   **Magnetic Permeability**:
    Pypeec uses **Susceptibility ($\chi$)**.
    *   $\mu = \mu_0 (1 + \chi)$
    *   Input: `chi_re` and `chi_im`.
    *   Definition: $\chi = \chi_{re} - j \chi_{im}$ (Note the minus sign convention for loss).

**Summary:**
There is no built-in "function" support in YAML. You must discretize your frequency range and provide the specific material constants for each frequency point in the `sweep_solver` configuration.

#### **8. Conversion from Standard Material Parameters**

If you have standard material properties (Conductivity $\sigma$, Permittivity $\epsilon$, Permeability $\mu$), you must convert them to the `rho` and `chi` parameters expected by pypeec.

**1. Electric Parameters ($\rho$)**
Pypeec expects a complex resistivity $\rho$.
*   **Input**: `rho_re`, `rho_im`
*   **Definition**: $\rho = \rho_{re} + j \cdot \rho_{im}$

Given:
*   Conductivity $\sigma$ (S/m)
*   Relative Permittivity $\epsilon_r = \epsilon_r' - j\epsilon_r''$
*   Frequency $\omega = 2\pi f$

The effective complex conductivity $\sigma_{eff}$ (including polarization current but excluding vacuum displacement) is:
$$ \sigma_{eff} = \sigma + j\omega\epsilon_0(\epsilon_r - 1) $$

The resistivity to input is the inverse of this effective conductivity:
$$ \rho = \frac{1}{\sigma_{eff}} = \frac{1}{\sigma + \omega\epsilon_0\epsilon_r'' + j\omega\epsilon_0(\epsilon_r' - 1)} $$

*   **For a good conductor** ($\sigma \gg \omega\epsilon$):
    $$ \rho \approx \frac{1}{\sigma} $$
    Set `rho_re` = $1/\sigma$, `rho_im` = 0.

*   **For a lossy dielectric** ($\sigma \approx 0$):
    $$ \rho = \frac{1}{j\omega\epsilon_0(\epsilon_r - 1)} $$

**2. Magnetic Parameters ($\chi$)**
Pypeec expects a complex susceptibility $\chi$.
*   **Input**: `chi_re`, `chi_im`
*   **Definition**: $\chi = \chi_{re} - j \cdot \chi_{im}$

Given:
*   Relative Permeability $\mu_r = \mu_r' - j\mu_r''$

The susceptibility is defined as $\chi = \mu_r - 1$.
$$ \chi = (\mu_r' - 1) - j\mu_r'' $$

Map these to the input fields:
*   `chi_re` = $\mu_r' - 1$
*   `chi_im` = $\mu_r''$ (Must be positive for passive materials)


