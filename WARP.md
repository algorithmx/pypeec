# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

PyPEEC is a 3D quasi-magnetostatic PEEC (Partial Element Equivalent Circuit) solver with FFT acceleration. It simulates magnetic components (inductors, transformers, coils, etc.) using voxel-based geometries and solves frequency-domain electromagnetic problems.

**Key Technologies:**
- Pure Python implementation (≥3.10)
- NumPy/SciPy for numerical computation
- FFT-accelerated matrix operations with optional GPU support
- PyVista/VTK for 3D visualization
- Shapely/Rasterio for geometry processing

## Common Commands

### Development Workflow
```bash
# Run code quality checks (linting and formatting)
./scripts/run_ruff.sh

# Run all integration tests
./scripts/run_tests.sh

# Run a specific test
python -m unittest tests/test_tutorial.py -v

# Build documentation and package
./scripts/run_build.sh

# Clean build artifacts
./scripts/run_clean.sh

# Generate test coverage report
./scripts/run_coverage.sh
```

### Testing Configuration
Tests use environment variables to control behavior:
```bash
export TEST_TOL="1e-4"     # Relative tolerance for test results
export TEST_CHECK="1"       # Enable result checking
export TEST_SET="0"         # Set to "1" to generate new reference results
export ALLOW_PLOTTING="true"  # Allow tests to run without display server
```

### Package Installation
```bash
# Install in development mode
pip install -e .

# Install with build dependencies
pip install -e ".[build]"
```

### Command Line Usage
```bash
# Mesh a geometry into voxels
pypeec mesher --geometry geometry.yaml --voxel voxel.pkl

# Visualize voxel structure
pypeec viewer --voxel voxel.pkl --viewer viewer.yaml

# Solve electromagnetic problem
pypeec solver --voxel voxel.pkl --problem problem.yaml --tolerance tolerance.yaml --solution solution.pkl

# Plot solution results
pypeec plotter --solution solution.pkl --plotter plotter.yaml
```

## Code Architecture

### Module Structure

The codebase follows a layered architecture with clear separation of concerns:

**Top-Level Entry Points:**
- `pypeec/__init__.py` - Main API exports (`run_mesher_data`, `run_solver_data`, etc.)
- `pypeec/script.py` - Command-line argument parsing
- `pypeec/main.py` - Entry point implementations (file I/O and data handling)

**Workflow Modules (`pypeec/run/`):**
These orchestrate the high-level workflows:
- `mesher.py` - Orchestrates geometry meshing into voxels
- `viewer.py` - Orchestrates voxel structure visualization
- `solver.py` - Orchestrates PEEC problem solving
- `plotter.py` - Orchestrates solution visualization

**Core Library Modules:**

1. **`lib_mesher/`** - Geometry to voxel conversion
   - `mesher_voxel.py` - Direct voxel index input
   - `mesher_shape.py` - 2D vector shapes (Shapely-based)
   - `mesher_png.py` - PNG image stacks (Pillow/Rasterio)
   - `mesher_stl.py` - 3D STL files (PyVista)
   - `voxel_*.py` - Post-processing (resampling, conflict resolution, integrity checks)

2. **`lib_solver/`** - PEEC electromagnetic solver
   - `voxel_geometry.py` - Voxel coordinates and incidence matrices
   - `problem_geometry.py` - Material and source assignment
   - `system_tensor.py` - Green function computation
   - `system_matrix.py` - Inductance, potential, and coupling matrices
   - `equation_system.py` - Assemble linear system
   - `equation_solver.py` - Solve linear system (direct or iterative)
   - `extract_solution.py` - Extract fields and terminal quantities
   - `sweep_joblib.py` - Parallel frequency sweeps

3. **`lib_matrix/`** - Matrix operations and FFT acceleration
   - `green_function.py` - Analytical Green functions
   - `multiply_fft.py` - FFT-based matrix multiplication (PEEC core)
   - `multiply_dense.py` - Dense matrix operations
   - `matrix_multiply.py` - High-level multiplication interface
   - `matrix_factorization.py` - LU/Cholesky factorization
   - `matrix_iterative.py` - Iterative solvers (GMRES, BiCGSTAB)
   - `matrix_condition.py` - Conditioning and preconditioning

4. **`lib_plot/`** - Visualization
   - `manage_pyvista.py` - PyVista 3D plotting
   - `manage_matplotlib.py` - Matplotlib 2D plotting
   - `manage_plotgui.py` - Interactive GUI management
   - `parse_*.py` - Parse visualization configurations

5. **`lib_check/`** - Input validation
   - JSON schema validation for all input data structures

6. **`utils/`** - Shared utilities
   - Helper functions used across modules

### Data Flow

1. **Meshing Phase:**
   - Input: Geometry definition (YAML/JSON)
   - Process: `mesher.py` → `lib_mesher/mesher_*.py` → `voxel_*.py`
   - Output: Voxel structure (domain definitions, coordinates, connectivity)

2. **Solving Phase:**
   - Input: Voxel structure + problem definition (materials, sources, frequencies)
   - Process: `solver.py` → `lib_solver/*.py` → `lib_matrix/*.py`
   - Output: Solution (currents, fields, terminal quantities)

3. **Visualization Phase:**
   - Input: Voxel structure or solution + plot configuration
   - Process: `viewer.py`/`plotter.py` → `lib_plot/*.py`
   - Output: Interactive plots or saved images/VTK files

### Key Design Patterns

**Lazy Module Loading:**
Heavy dependencies (PyVista, NumPy, SciPy) are imported inside functions, not at module level. This minimizes startup time and allows partial functionality without all dependencies.

**Data Structure Wrapping:**
All functions accept and return standardized dict structures with metadata:
```python
{
    "meta": {
        "name": "pypeec",
        "version": "x.x.x",
        "layout": "voxel/solution/etc",
        "date": "...",
        "duration": "...",
        "seconds": ...
    },
    "data": { ... }
}
```

**Schema Validation:**
All input data is validated using JSON schemas via the `scisave` library before processing.

**Logging:**
Comprehensive logging using `scilogger` with automatic timing blocks (`with LOGGER.BlockTimer("name")`).

## File Formats

- **Input:** YAML or JSON for configurations
- **Output (data):** JSON, MessagePack, or Pickle (gzipped)
- **Output (plots):** PNG images or VTK files for ParaView
- **Geometry:** STL, PNG, GERBER, or vector shapes

## Code Quality

**Linting/Formatting:**
- Uses `ruff` for both linting and formatting
- Configuration in `pyproject.toml`:
  - Line length: 160
  - Target: Python 3.10+
  - Selected rules: E, F, B, UP (with specific ignores)
  - Double quotes, space indentation

**Testing:**
- Integration tests using Python's `unittest` framework
- Test files in `tests/` directory match `test_*.py` pattern
- Tests validate against reference data with configurable tolerance
- All tests must pass before merging

## Important Notes

**Voxel Limitations:**
PyPEEC uses uniform voxel grids, which can be inefficient for certain geometries. Be mindful of memory usage and meshing resolution.

**FFT Acceleration:**
The core advantage of PyPEEC is FFT-accelerated matrix multiplication in `lib_matrix/multiply_fft.py`. This is critical for performance with large voxel counts.

**Optional Dependencies:**
GPU acceleration and advanced solvers may require additional libraries not in base dependencies. Check documentation for HPC options.

**Version Compatibility:**
The code includes version checking for data files. Mismatches trigger warnings but don't fail, allowing cross-version data usage with caution.
