
import numpy as np
from lcapy import Circuit, s

# --- System Parameters ---
# From run_microstrip.py
w_trace = 4.0e-6      # Trace width (m)
h_sub = 4.0e-6        # Substrate thickness (m)
eps_r = 4.4           # FR4 permittivity
mu_r = 1.0
sigma_cu = 5.8e7      # Copper conductivity (S/m)

# --- Transmission Line Calculations ---
# Approximate Microstrip characteristic impedance and velocity
# Using standard Wheeler/Hammerstad formulas for w/h = 1
# Effective permittivity
eps_eff = (eps_r + 1)/2 + (eps_r - 1)/2 * (1/np.sqrt(1 + 12*(h_sub/w_trace)))
# Characteristic Impedance (Z0)
# For w/h = 1:
z0_approx = (60 / np.sqrt(eps_eff)) * np.log(8*(h_sub/w_trace) + (w_trace/h_sub)/4)

# Propagation velocity
c0 = 299792458
v_prop = c0 / np.sqrt(eps_eff)

print(f"Calculated Z0: {z0_approx:.2f} Ohms")
print(f"Calculated v_prop: {v_prop:.2e} m/s")

# Lengths derived from geometry
L_seg1 = 43.0e-6  # Start to stub junction
L_seg2 = 2.0e-6   # Junction to bottom trace end
L_seg3 = 36.0e-6  # Remaining top trace
L_stub = 42.0e-6  # Stub length (approximate)

# Delays
td1 = L_seg1 / v_prop
td2 = L_seg2 / v_prop
td3 = L_seg3 / v_prop
td_stub = L_stub / v_prop

# --- Circuit Definition ---
# We model the system using transmission lines (TL).
# Coupling is approximated by capacitor bridges for this simple model 
# (or ignored if focusing on connectivity).
# For a more accurate model, Lcapy's coupled line elements could be constructed from matrices.
# Here we build the topology with independent lines to represent the signal paths.

# Netlist String
# P1, P2, P3, P4, P5 are the ports.
# 0 is ground.
netlist = f"""
# Define Ports (50 Ohm terminations for S-param simulation equivalent)
P1 1 0 port
P2 2 0 port
P3 3 0 port
P4 4 0 port
P5 5 0 port

# --- Top Trace ---
# Segment 1: P1 to Junction (Node 10)
W1 1 0 10 0 Z0={z0_approx} delay={td1}

# Segment 2: Junction (Node 10) to Mid (Node 11)
W2 10 0 11 0 Z0={z0_approx} delay={td2}

# Segment 3: Mid (Node 11) to P2
W3 11 0 2 0 Z0={z0_approx} delay={td3}

# --- Stub ---
# Connected at Junction (Node 10) to P3
Wstub 10 0 3 0 Z0={z0_approx} delay={td_stub}

# --- Bottom Trace ---
# Segment 4: P4 to Mid-Junction (Node 40) - corresponds to Seg 1 length
W4 4 0 40 0 Z0={z0_approx} delay={td1}

# Segment 5: Mid-Junction (Node 40) to P5 - corresponds to Seg 2 length
W5 40 0 5 0 Z0={z0_approx} delay={td2}

# --- Coupling (Approximate) ---
# Capacitive coupling between parallel segments
# C_coupling approx 10% of line capacitance or derived from gap
# This is a placeholder for the crosstalk effect
C12 10 40 10f
"""

# Create Circuit
print("Building Circuit...")
cct = Circuit(netlist)

# --- Simulation ---
# Calculate Network parameters at 1 GHz
freq = 1e9
print(f"\nSimulating at {freq/1e9} GHz...")

# We can extract the admittance matrix (Y) or impedance matrix (Z)
# Since it's a multi-port, lcapy might require one-by-one excitation or finding the matrix.
# Note: lcapy's 'port' definition allows s-parameter extraction if setup correctly,
# but usually requires .ac analysis or matrix derivation.

# Let's print the Z matrix at s = j*omega
omega = 2 * np.pi * freq
try:
    # Lcapy calculates symbolic matrices, we substitute s
    Z = cct.Z
    Z_val = Z.evaluate(np.array([1j * omega]))
    
    print("\nZ-Matrix at 1 GHz (Real + Imag):")
    print(Z_val)
except Exception as e:
    print(f"Could not calculate Z-matrix directly: {e}")
    print("Attempting individual transfer functions...")

# Basic connectivity check / Transfer function P1 -> P2
try:
    H12 = cct.transfer('P1', 'P2')
    val = H12.evaluate(1j * omega)
    print(f"\nTransfer Function P1 -> P2 at 1 GHz: {20*np.log10(abs(val)):.2f} dB")
except Exception as e:
    print(f"Could not calculate transfer function: {e}")

