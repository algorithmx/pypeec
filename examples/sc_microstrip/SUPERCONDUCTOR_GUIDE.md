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

## Material Parameters
Common values for superconducting materials:

| Material | $T_c$ (K) | $\lambda_{L0}$ (nm) |
| :--- | :--- | :--- |
| **Aluminum (Al)** | 1.20 | ~50 |
| **Niobium (Nb)** | 9.20 | ~32-40 |
| **Tantalum (Ta)** | 4.45 | ~90 |
| **NbTiN** | 14.0 | ~300 |


## Mesh Resolution Warning

When simulating superconductors using volumetric PEEC, accurate results depend on the mesh resolution relative to the London penetration depth ($\lambda_L$) and the film thickness ($t$).

1.  **Thin Films ($t \approx \lambda_L$)**: If the film thickness is comparable to $\lambda_L$ (e.g., 100 nm), a single voxel layer in the Z-direction is usually sufficient if the bulk conductivity calculated above is applied. The current is effectively uniform.
2.  **Thick Films ($t \gg \lambda_L$)**: If the film is much thicker than $\lambda_L$, the current is confined to a thin surface layer (Meissner effect). Using a coarse volumetric mesh with bulk conductivity will **incorrectly distribution current uniformly**, leading to errors in inductance.
    *   **Mitigation**: Use a mesh resolution comparable to $\lambda_L$ near the surface (computationally expensive) OR use an effective resistivity normalized to the voxel thickness as described in advanced surface impedance formulations.

## Extracting Impedance and Inductance

`examples/sc_microstrip/run_superconducting_drude.py` now reports three complementary views of the port behavior. Together they explain why a short superconducting line can show $R_\text{in}\neq 50\,\Omega$ even though its characteristic impedance is still near 50 $\Omega$.

### 1. Raw Port Measurement
The solver provides terminal voltages and currents via `matrix.get_extract`. The code logs

$$ Z_\text{in} = \frac{V_{\text{src}} - V_{\text{gnd}}}{I_{\text{src}}} $$

for each sweep. This quantity reflects the entire launch: pad capacitance, short trace, and the 50 $\Omega$ termination at the far end. It is the right value to compare against a real coax probe or Thevenin source but it can differ by a few ohms from the intrinsic line impedance when the structure is electrically short.

### 2. Energy-Based Line Parameters
PyPEEC reports the integrated electric and magnetic energies (`W_electric`, `W_magnetic`) for every sweep. The script converts them into equivalent lumped values using

$$ L_\text{eq} = \frac{2 W_m}{|I|^2}, \qquad C_\text{eq} = \frac{2 W_e}{|V|^2}. $$

Dividing by the physical trace length (50 $\mu$m in the example) yields $L'$ and $C'$ in Si units, and

$$ Z_{0,\text{energy}} = \sqrt{\frac{L'}{C'}}. $$

Because energy is conserved regardless of the trace length, this method provides a stable characteristic impedance estimate even when the line is much shorter than $\lambda/10$.

### 3. Standard Two-Port / S-Parameter Extraction
A full two-port is formed by treating (`src`, `src_gnd`) as Port 1 and (`sink`, `sink_gnd`) as Port 2. The script now runs *two* sweeps at every frequency—first driving the source pad, then the sink pad—so the solver produces two linearly independent solutions that populate the 2×2 impedance matrix $Z$. With both sweeps available, `matrix.get_matrix` returns the full matrix and the script computes the scattering matrix for a 50 $\Omega$ reference:

$$ S = (Z - Z_0 I)(Z + Z_0 I)^{-1}. $$

The usual microwave relations then recover the characteristic impedance (and, if desired, $\gamma \ell$) without assuming long lines. The implementation uses

$$ Z_{0,\text{std}} = Z_0 \sqrt{\frac{(1 + S_{11})^2 - S_{21}^2}{(1 - S_{11})^2 - S_{21}^2}}, $$

which matches the textbook Nicolson–Ross–Weir extraction in the lossless limit. This provides a “standard VNA” view that can be compared directly to measurement or EM solvers geared toward S-parameters.

### 4. T-Network Extraction (Lumped Model)

For electrically short lines (length $\ll \lambda$), such as the superconducting traces often modeled here, a lumped T-network model provides a direct way to extract effective inductance and capacitance from the Z-matrix.

**Model Configuration:**
```
Port 1 ----[L]----+----[L]---- Port 2
                  |
                 [C]
                  |
                 GND
```
Where the horizontal arms are inductors of equal inductance $L$ and the vertical branch is a capacitor $C$.

**Derivation:**
For a symmetric T-network, the Z-matrix elements are related to $L$ and $C$ by:
$$ Z_{11} = Z_{22} = j\omega L + \frac{1}{j\omega C} $$
$$ Z_{12} = Z_{21} = \frac{1}{j\omega C} $$

**Extraction Formulas:**
From the measured Z-matrix at angular frequency $\omega$:

$$ C = -\frac{1}{\omega \cdot \text{Im}(Z_{12})} $$
$$ L = \frac{\text{Im}(Z_{11}) - \text{Im}(Z_{12})}{\omega} $$

**Note on Load Impedance:**
The extraction formulas above do *not* require manual subtraction of the 50 $\Omega$ load impedance. The function `matrix.get_matrix` mathematically de-embeds the Z-parameters of the structure from the external circuit. The resulting $Z_{11}$ and $Z_{12}$ values represent the intrinsic properties of the superconducting line itself, independent of the termination used during the simulation.

This method is particularly useful for verifying the kinetic inductance contribution in short superconducting structures where the distributed transmission line model might be overkill or harder to fit.

### Choosing the Right Metric

- Use $Z_\text{in}$ when you want to know what a practical source sees, including pad effects.
- Use the energy-derived $Z_0$ and $L'$ when modeling very short kinetic-inductance elements or when you need per-unit-length values for circuit synthesis.
- Use the two-port $Z_{0,\text{std}}$ (and associated $S$ parameters) when you need compatibility with RF measurement practice or when you want to de-embed the finite-length launch numerically.

All three numbers are printed per frequency sweep so you can verify that the superconductor remains low-loss (energy method) while understanding any residual mismatch (two-port method) and the actual drive conditions (raw port method).

### Implementation Notes

The reporting logic lives in `examples/sc_microstrip/run_superconducting_drude.py` after the call to `matrix.get_extract(...)`:

1. **Terminal extraction** – `terminal_list` includes both (`src`, `src_gnd`) and (`sink`, `sink_gnd`) so `matrix.get_extract` returns a 2×N matrix of currents and voltages for the paired source- and sink-driven sweeps. The script still prints the single-port $Z_\text{in}$ first because that best matches what Port 1 sees in measurement.
2. **Energy data access** – the solver packs field integrals into `solution["data_sweep"][tag]["integral_total"]`. The script simply grabs `W_electric` and `W_magnetic` from this dict; no additional API calls are required.
3. **Two-port computation path** – `matrix.get_matrix(terminal_data)` produces the 2×2 impedance matrix. The script inverts `(Z + Z_0 I)` using `numpy.linalg` (now imported as `lna`) to build the scattering matrix and then applies the Nicolson–Ross–Weir formula.
4. **Printing** – all three results are emitted inside the sweep loop so log lines for a given frequency appear grouped: (a) raw table row, (b) energy-based summary, (c) standard two-port summary. The solver now runs both excitations automatically, so the “skipped” message only appears if one of the sweeps fails or is filtered out (e.g., due to convergence issues at a specific frequency).

These snippets are intentionally compact so they can be adapted to other superconducting examples (e.g., coplanar waveguides) by copying the extraction loop into new scripts.
