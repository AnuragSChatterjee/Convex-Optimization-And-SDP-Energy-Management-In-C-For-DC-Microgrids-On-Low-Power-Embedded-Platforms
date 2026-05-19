# Convex Optimization & SDP Energy Management in C for DC Microgrids
### Deployed on Low-Power Embedded Systems (Raspberry Pi 5)

[![Platform](https://img.shields.io/badge/Platform-Raspberry%20Pi%205-red)](https://www.raspberrypi.com/)
[![Solver](https://img.shields.io/badge/Solver-CVXPYGEN%20%7C%20CVXPY%20%7C%20CSDP-blue)]()
[![Language](https://img.shields.io/badge/Language-Python%20%7C%20MATLAB%20%7C%20C-green)]()
[![Status](https://img.shields.io/badge/Status-Complete-brightgreen)]()
[![Speedup](https://img.shields.io/badge/Speedup-25×%20faster-orange)]()

---

## Overview

As part of my advanced research projects course for my MS in Computer Engineering at Columbia University, I worked on a semester long spring research project with the Motor Drives And Power Electronics Lab (MPLab), which helps to translate a **Semidefinite Programming (SDP)-based multi-period DC microgrid optimal power flow (OPF) problem** from MATLAB/CVX into C, deploys it on a **Raspberry Pi 5** via a real-time Ethernet interface, and validates solver accuracy across **304 fixed parameter permutations**.

The core research question:

> *Can an SDP-based multi-period DC microgrid OPF problem be translated from MATLAB/CVX into C and deployed on a Raspberry Pi 5 while preserving optimality and achieving real-time performance?*

**Answer: Yes — with ~25× speedup and <0.012% objective error.**

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    5-Bus DC Microgrid                        │
│  Bus 1: AC Grid  │  Bus 2: Solar PV  │  Buses 3,4,5: Battery│
└──────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              │                               │
   ┌──────────▼──────────┐       ┌────────────▼────────────┐
   │   MATLAB Client     │       │   Raspberry Pi 5        │
   │   (Laptop)          │◄─────►│   (Server)              │
   │                     │  TCP  │                         │
   │  • Load solar data  │  IP   │  • CVXPY (Clarabel)     │
   │  • Build JSON payload│      │  • CVXPYGEN (C binary)  │
   │  • Trigger solver   │       │  • Return JSON results  │
   │  • Plot results     │       │                         │
   └─────────────────────┘       └─────────────────────────┘
```

---

## Key Results

| Metric | Value |
|--------|-------|
| Speedup (CVXPYGEN vs CVXPY on Pi) | **~25×** |
| CVXPY runtime (Raspberry Pi 5) | 1.084 s |
| CVXPYGEN runtime (Raspberry Pi 5) | 0.043 s |
| Objective difference (all 304 runs) | **< 0.012%** |
| Battery complementarity pᶜ × pᵈ | **≈ 0** (Theorem 1 validated) |
| Total permutations tested | **304 / 304 successful** |
| Parameter space | η_c, η_d ∈ {0.80, 0.85, 0.90, 0.95} × E_init ∈ [5%, 95%] |

---

## Background: The Energy Management Problem

The microgrid OPF problem involves:

- **Solar Intermittency:** PV generation varies hour-to-hour across T=24 timesteps
- **Battery Balancing:** Optimizing charge/discharge efficiencies η_c, η_d ∈ (0,1) at Buses 3, 4, 5 (500 kWh each)
- **Non-Convex Constraints:** Battery complementarity pᶜ(t)·pᵈ(t) = 0 (can't charge and discharge simultaneously)
- **DC Power Flow:** Voltage bilinearities (Ohm's law) make the full OPF non-convex

**Approach:** SDP relaxation via lifting and rank relaxation convexifies the problem. A penalty cost of 1×10⁻⁴ implicitly enforces complementarity (**Theorem 1** from Haghighi et al.), eliminating the need for expensive mixed-integer solvers.

---

## Repository Structure

```
mplab-sdp-energy-management/
│
├── README.md                        ← This file
│
├── matlab/
│   ├── plotting/
│   │   ├── plot_sdp_results.m       ← Main plotting script (7 auto-generated figures)
│   │   └── README_plotting.md       ← Plotting pipeline documentation
│   │
│   └── permutations/
│       ├── DCPF_permutation_script_simplified_fixed_from_supervisor_code.m
│       └── README_permutations.md   ← 304-run sweep documentation
│
├── python/
│   ├── server_sdp.py                ← Raspberry Pi server (CVXPY + CVXPYGEN)
│   ├── server_sdp_permutations_fixed_NEW.py   ← Permutation server
│   ├── server_sdp_permutations_fixed_NEW_V2.py
│   ├── generate_c_code.py           ← CVXPYGEN C code generation script
│   └── README_python.md             ← Python server documentation
│
├── docs/
│   ├── presentation.pdf             ← Final presentation (May 14, 2026)
│   ├── system_design.md             ← Architecture and design decisions
│   └── challenges_and_learnings.md  ← Technical retrospective
│
└── results/
    ├── experiment1_summary.md       ← Fixed-parameter experiment results
    └── experiment2_summary.md       ← 304-permutation statistical analysis
```

---

## Experiments

### Experiment 1: Fixed-Parameter Optimization Pipeline

**Setup:** E_init = 0.01 p.u., η_c = η_d = 0.99, T = 24 hours  
**Flow:** MATLAB → JSON over Ethernet → Raspberry Pi (CVXPY + CVXPYGEN) → JSON → MATLAB Plotter

Automatically generates 7 figures:
- Power Generation per Bus (bar chart)
- Battery SOC Trajectory over 24 hours
- Hourly Dispatch Overview (charge/discharge per bus)
- Solver Runtime Benchmark comparison

### Experiment 2: 304 Fixed Permutations Benchmark

**Parameter space:** η_c (4 values) × η_d (4 values) × E_init (19 values) = **304 total permutations**

```
η_c:   0.80, 0.85, 0.90, 0.95
η_d:   0.80, 0.85, 0.90, 0.95
E_init: 0.005 p.u. (5%) → 0.095 p.u. (95%), step 0.005
```

**Key findings:**
- ✅ Zero objective gap across all 304 runs
- ✅ Complementarity pᶜ × pᵈ ≈ 0 (confirms Theorem 1)
- ✅ Higher E_init → lower cost (battery displaces expensive AC grid power)
- ✅ CVXPYGEN objective cost consistently ≤ CVXPY (tighter C solver)

---

## Setup & Deployment

### Prerequisites

**On the Raspberry Pi 5:**
```bash
pip install cvxpy cvxpygen clarabel numpy
# Install LAPACK and BLAS for CVXPYGEN compilation
sudo apt-get install liblapack-dev libblas-dev cmake
```

**On the MATLAB client (laptop):**
- MATLAB R2024+ with Python integration
- Network connection to Raspberry Pi via Ethernet (static IP or link-local IPv6)

### Raspberry Pi Network Configuration

The Pi is configured as a TCP/IP server on port 5000. For Ethernet-direct connection (no router):
```bash
# Use IPv6 link-local if DHCP is unavailable
# Pi IP: 192.168.2.x (Ethernet static)
python server_sdp.py  # Start solver server
```

### Running Experiment 1

```matlab
% On MATLAB (laptop):
% 1. Start server_sdp.py on the Raspberry Pi
% 2. Run the MATLAB client:
run('matlab/plotting/plot_sdp_results.m')
```

### Running Experiment 2 (304 Permutations)

```matlab
% On MATLAB (laptop):
% 1. Start server_sdp_permutations_fixed_NEW_V2.py on the Pi
% 2. Run the permutation sweep:
run('matlab/permutations/DCPF_permutation_script_simplified_fixed_from_supervisor_code.m')
% Completes all 304 permutations, generates statistical plots
```

---

## CVXPYGEN: The Critical Bridge

CVXGEN (the traditional embedded solver tool) only handles QPs/LPs — it **cannot** handle matrix variables V[t] ⪰ 0 or PSD constraints required by SDP.

**CVXPYGEN** solves this by compiling CVXPY problem descriptions into standalone C solvers:

```python
from cvxpygen import cpg
# Generate C code from CVXPY problem
cpg.generate_code(prob, code_dir='cpg_solver', wrapper=True)
# wrapper=True is critical — ensures cp.Parameter() updates
# pass through correctly to the compiled binary
```

> ⚠️ **Important:** Setting `wrapper=True` in `generate_c_code.py` was the key fix that resolved stale objective values and 20% Clarabel failures, achieving 100% pass rate across all 304 permutations.

---

## Technical Challenges & Solutions

| Challenge | Root Cause | Solution |
|-----------|-----------|----------|
| Stale CVXPYGEN objectives (~30 gap) | `cp.Parameter()` not passing to compiled C solver | Set `wrapper=True` in `generate_c_code.py` |
| Raspberry Pi WiFi failure | Manual config issue | Reflash; switch to Ethernet |
| Ethernet discovery failure | No DHCP on direct link | Use IPv6 link-local addressing |
| CVXPYGEN build failure (`cpg_example`) | CMake linker order wrong | Fix: Clarabel → LAPACK → BLAS in `CMakeLists.txt` |
| 20% Clarabel solver failures | Numerical conditioning | Resolved by wrapper fix above |

---

## Theoretical Validation

**Theorem 1 (Haghighi et al.):** Battery complementarity constraints pᶜ(t)·pᵈ(t) = 0 are *implicitly satisfied* when small penalty costs (1×10⁻⁴) are added to the objective.

This project validates Theorem 1 empirically across all 304 parameter combinations:

```
Mean(pᶜ × pᵈ) ≈ 0    across all buses, all timesteps, all permutations
```

This eliminates the need for Mixed-Integer Programming (MIP) solvers entirely.

---

## Economic Insights

The optimization minimizes:
```
Cost = Σ(net power injections) − total load
     + Σ(grid power × electricity price)
     + battery usage penalty
```

**Key finding:** Higher initial battery SOC (E_init) → lower objective cost, because stored energy substitutes for expensive AC grid purchases at Bus 1. This monotonic inverse correlation was verified for 100% of the 304-run parameter sweep.

---

## Future Work

1. **Simulink HIL Integration:** C/S-Function wrappers for hardware-in-the-loop simulation
2. **Full η Sweep:** Reformulate DPP constraints to study true efficiency impact across broader η ranges
3. **Smaller Microcontrollers:** Investigate deployment on STM32 or similar ARM Cortex-M targets

---

## References

- Haghighi, A. et al. — *Battery complementarity constraints in DC microgrid OPF* (internal MPLab paper)
- [CVXPYGEN](https://github.com/cvxpy/cvxpygen) — C code generation from CVXPY
- [Clarabel Solver](https://github.com/oxfordcontrol/Clarabel.rs) — Interior-point conic solver
- [CSDP](https://github.com/coin-or/Csdp) — C library for SDP

---

## License

This research was conducted at Columbia University MPLab. Code is shared for academic and research purposes.

---

*Presented at MPLab Final Presentation, May 14, 2026*
