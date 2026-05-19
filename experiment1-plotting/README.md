# Experiment 1: Fixed-Parameter Optimization & Plotting Pipeline

## Files

### Python (Raspberry Pi Server)
- **`server_sdp.py`** — TCP server that runs all three solvers (CVXPY, CSDP, CVXPYgen) sequentially and returns JSON results.

### Python (MATLAB-Triggered Client)
- **`client_sdp_matlab_Plot_Data_Results.py`** — Loads `solar_power_data.mat`, builds per-unit payload, sends to Pi, saves `sdp_results_transfer.mat`.

### MATLAB (Laptop)
- **`plot_sdp_results.m`** — Main entry point. Calls the Python client, loads results, auto-generates 7 figures.

## Fixed Parameters
```
E_init = 0.01 p.u. (10% SOC, i.e. einit_pu = 0.01 × battery_energy_cap)
η_c = η_d = 0.99
T = 24 hourly timesteps
S_base = 5 MW
```

## Running

```bash
# On Raspberry Pi:
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
python3 server_sdp.py

# On MATLAB laptop:
>> plot_sdp_results
```

## Results (in `results/` folder)

| File | Description |
|------|-------------|
| `Battery_SOC_Trajectory.pdf` | SOC for Buses 3, 4, 5 over 24 hours |
| `Power_Generation_per_Bus.pdf` | Average 24h power per bus (AC Grid dominant) |
| `All_Battery_Buses_Dispatch_Overview.pdf` | Charge/discharge subplot per bus |
| `Bus_3_Battery_Dispatch.pdf` | Hourly charge + discharge, Bus 3 |
| `Bus_4_Battery_Dispatch.pdf` | Hourly charge + discharge, Bus 4 |
| `Bus_5_Battery_Dispatch.pdf` | Hourly charge + discharge, Bus 5 |
| `Solver_Benchmark.pdf` | CVXPY 1.084s vs CVXPYgen 0.043s (25× speedup) |

## Key Observation
The CSDP objective (`-2733.4`) differs from CVXPY/CVXPYgen (`~990.7`) because CSDP solves a single-timestep 27×27 formulation with a different cost structure (non-convex, without the battery usage penalty term). It is used here purely as a timing reference.
