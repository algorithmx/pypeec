# Microstrip Example Project Report

## Overview
The `examples/microstrip` project is a comprehensive mini-project within the PyPEEC ecosystem that simulates a 5-port microstrip structure on a dielectric substrate with a ground plane. It serves as a demonstration of PyPEEC's capabilities in modeling printed circuit board (PCB) features, frequency-dependent materials, and multi-port network parameter extraction.

## Capabilities

### 1. Parametric Geometry Generation
The project features a custom generator class, `SandwichMicrostripGenerator` (in `microstrip_yaml_generator.py`), which allows for the programmatic creation of microstrip geometries.
- **Automated Layering**: Automatically generates the substrate and ground plane layers based on the bounding box of the top-layer traces.
- **Domain Management**: Handles logical grouping of shapes (e.g., traces, ports) and manages conflict resolution rules to ensure correct voxelization priorities (e.g., conductors override dielectrics).
- **Flexible Layouts**: Supports defining arbitrary rectangular patterns, making it adaptable for various filter or coupler designs.

### 2. Advanced Material Modeling
The simulation demonstrates sophisticated material property definitions in `run_microstrip.py`:
- **Frequency-Dependent Dielectrics**: Models the substrate (e.g., FR4) using a complex resistivity model to account for displacement currents and dielectric losses ($\tan \delta$) across the frequency range.
- **Conductor Skin Effect**: Implements a resistivity model for copper that can be expanded to account for skin depth variations at higher frequencies.

### 3. Multi-Port Simulation & Matrix Extraction
The project is set up to perform full-wave PEEC simulations for a multi-port system:
- **Frequency Sweeps**: `run_microstrip.py` configures a sweep across multiple frequencies (1 MHz, 100 MHz, 1 GHz), adjusting material properties dynamically for each step.
- **Matrix Extraction**: `run_matrix_extraction.py` demonstrates how to extract the full Inductance ($L$) and Resistance ($R$) matrices for the 5-port network. It calculates self/mutual inductances and coupling coefficients ($k$).

### 4. Visualization
The workflow includes automated visualization steps using PyVista:
- **Geometry Inspection**: Visualizes the voxelized structure (traces, substrate, ground) to verify the mesh.
- **Field Plotting**: Plots solution quantities such as Current Density ($J$) and Potential ($V$) maps, aiding in the analysis of current return paths and potential distribution.

### 5. Verification
A separate script, `simulate_microstrip_lcapy.py`, provides a theoretical baseline using the `lcapy` library. It models the structure as a network of ideal transmission lines to calculate characteristic impedance ($Z_0$) and propagation delays, allowing for cross-verification of the PEEC simulation results.

## Project Structure

| File | Description |
|------|-------------|
| `run_microstrip.py` | Main driver script. Generates geometry, runs the solver, and visualizes results. |
| `microstrip_yaml_generator.py` | Logic for procedurally generating the microstrip geometry and YAML configuration. |
| `run_matrix_extraction.py` | Utility to extract L/R/Z matrices from the solver output. |
| `simulate_microstrip_lcapy.py` | Transmission line analytical model for verification. |
| `problem.yaml` | Defines the simulation setup (materials, ports, solver sweeps). |
| `geometry.yaml` | The generated geometry definition (output of the generator). |

## Usage
To run the full simulation pipeline:
```bash
python examples/microstrip/run_microstrip.py
```

To extract the inductance matrix after the simulation:
```bash
python examples/microstrip/run_matrix_extraction.py
```
