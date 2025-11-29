# Circuit Parameter Extraction in pypeec

Based on the investigation of the codebase, specifically the `pypeec/utils/matrix.py` module and the `examples/microstrip` directory, here is how the code supports the extraction of circuit parameters for a multi-port conductor device.

### Overview

The extraction process relies on a **method of moments** approach where the impedance matrix ($Z$) is derived by solving a system of linear equations based on the results of multiple simulation sweeps.

The core logic resides in `pypeec/utils/matrix.py`, which provides functions to:
1.  **Extract** terminal voltages and currents from simulation results.
2.  **Solve** for the impedance matrix ($Z$) using a least-squares approach.
3.  **Parse** the impedance matrix into Resistance ($R$), Inductance ($L$), and Coupling ($k$) matrices.

## Theoretical Background

The extraction utility models the electromagnetic device as an $N$-port **Linear Time-Invariant (LTI)** network described by an Impedance Matrix ($Z$) at a specific frequency $\omega$.

$$ [V] = [Z] \cdot [I] $$

Where:
*   $[V]$ is the vector of potential differences across the ports ($V_{src} - V_{sink}$).
*   $[I]$ is the vector of currents flowing through the ports (averaged as $(I_{src} - I_{sink})/2$).
*   $[Z] = [R] + j\omega [L]$ is the complex impedance matrix.

**Key Implementation Details:**
1.  **Symmetry**: The solver explicitly enforces reciprocity, assuming the impedance matrix is symmetric ($Z_{ij} = Z_{ji}$). This reduces the number of unknowns solved for in the system.
2.  **Method**: The tool extracts voltage and current phasors from multiple simulation sweeps and solves for the unique elements of $[Z]$ using a least-squares fit.

The PEEC solver computes the full electromagnetic fields (electric and magnetic), capturing effects such as:
*   **Ohmic Losses**: Represented in the real part ($R$).
*   **Magnetic Coupling**: Inductive effects.
*   **Electric Coupling**: Capacitive effects (displacement currents).

In the frequency domain, inductive and capacitive reactances are combined into the imaginary part of the impedance ($X$). The extraction tool maps this total reactance to an effective inductance $L_{eff} = X / \omega$.

### Step-by-Step Mechanism

#### 1. Problem Definition (`problem.yaml`)
In the problem definition (e.g., `examples/microstrip/problem.yaml`), you define the **ports** and the **simulation sweeps**.

*   **Ports**: Defined as sources. For a multi-port device, you typically define one current source per port and a common reference (e.g., ground).
    ```yaml
    "source_def":
        "port_p1": { "source_type": "current", ... }
        "port_p2": { "source_type": "current", ... }
        "ground_ref": { "source_type": "voltage", ... }
    ```
*   **Sweeps**: You define a series of simulations. In each sweep, typically one port is excited (e.g., 1A current) while the others are left open (0A).
    ```yaml
    "sweep_solver":
        "sim_p1": { ... "port_p1": {"I_re": 1.0} ... } # Excite Port 1
        "sim_p2": { ... "port_p2": {"I_re": 1.0} ... } # Excite Port 2
    ```

#### 2. Data Extraction (`matrix.get_extract`)
After the solver runs, the `matrix.get_extract` function collects the raw voltage ($V$) and current ($I$) data for every defined terminal across all simulation sweeps.

*   **Input**: The solver solution object, a list of sweep names, and a list of terminal definitions (source/sink pairs).
*   **Output**: A dictionary containing matrices of currents (`I_mat`) and voltages (`V_mat`) with dimensions `(n_ports, n_sweeps)`.

#### 3. Impedance Matrix Calculation (`matrix.get_matrix`)
The function `matrix.get_matrix` (which calls `_get_matrix_solve`) computes the impedance matrix $Z$.

*   **Equation System**: Instead of assuming a simple $V/I$ ratio, it constructs a linear system $V = Z \cdot I$.
*   **Symmetry**: It assumes the device is reciprocal (passive), meaning the impedance matrix is symmetric ($Z_{ij} = Z_{ji}$). This reduces the number of unknowns.
*   **Least Squares**: It solves for the unique coefficients of $Z$ that best fit the measured $V$ and $I$ data from all sweeps. This allows for robust extraction even if the excitation patterns are complex (not strictly one-port-at-a-time).

#### 4. Parameter Decomposition (`_get_matrix_parse`)
Once the complex impedance matrix $Z$ is found, it is decomposed into circuit parameters:

*   **Resistance ($R$)**: Real part of $Z$ ($R = \text{Re}(Z)$).
*   **Inductance ($L$)**: Imaginary part of $Z$ divided by angular frequency ($L = \text{Im}(Z) / \omega$).
*   **Coupling ($k$)**: Derived from the self and mutual inductances.
    $$k_{ij} = \frac{|L_{ij}|}{\sqrt{L_{ii} L_{jj}}}$$

### Example Usage

In `examples/microstrip/run_matrix_extraction.py`, you can see this workflow explicitly:

```python
# 1. Define the sweeps and terminals
sweep_list = ["sim_p1", "sim_p2", "sim_p3", "sim_p4", "sim_p5"]
terminal_list = [
    {"src": "port_p1", "sink": "ground_ref"},
    # ... other ports ...
]

# 2. Extract raw V, I data
terminal_data = matrix.get_extract(solution, sweep_list, terminal_list)

# 3. Compute Z, R, L matrices
result_matrix = matrix.get_matrix(terminal_data)
```

## Interpreting the Extraction Report

When reviewing the output of the extraction tool, it is crucial to interpret the values based on the AC circuit model used.

### 1. Inductance Matrix (`L_mat`)
Calculated as $L_{ij} = \text{Im}(Z_{ij}) / \omega$.

*   **Positive Values**: Indicate **inductive behavior**. The magnetic field energy dominates the reactive power. This is typical for closed loops, grounded paths, or high-frequency interconnects where $\omega L > 1/(\omega C)$.
*   **Negative Values**: Indicate **capacitive behavior**. The electric field energy dominates. Since the tool fits the data to an inductive model ($j\omega L$), a net capacitive reactance ($1/j\omega C = -j/\omega C$) appears as a negative inductance.
    *   *Example*: An open-ended microstrip trace acts like a capacitor to ground. The extraction will report a large negative self-inductance.

### 2. Resistance Matrix (`R_mat`)
Calculated as $R_{ij} = \text{Re}(Z_{ij})$.

*   Represents the total effective resistance, including DC resistance, skin effect losses, and dielectric losses (if modeled with complex resistivity).
*   Off-diagonal terms ($R_{ij}$) represent the resistive coupling or common-impedance coupling between ports.

### 3. Coupling Coefficients (`k_L_mat`)
Calculated as $k_{ij} = \frac{|L_{ij}|}{\sqrt{L_{ii} L_{jj}}}$.

*   **Near 0%**: The ports are electromagnetically isolated (orthogonal fields or large distance).
*   **Near 100%**: The ports are extremely tightly coupled.
    *   *Note*: If two ports are placed on the **same electrical node** (e.g., two ends of a short trace), they effectively measure the same potential. This results in $Z_{ij} \approx Z_{ii} \approx Z_{jj}$, leading to a calculated coupling of ~100%.
