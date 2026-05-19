# Experiment 2: 304 Fixed Permutations Benchmark

## Files

### Python (Raspberry Pi Server)
- **`server_sdp_permutations_fixed_NEW_V3.py`** — Parametric TCP server. Loads CVXPYgen Python wrapper **once** at startup, then updates `cp.Parameter()` objects per permutation. Logs `[CVXPY]`, `[CSDP]`, `[CVXPYgen]`, `[DIFF]`, and `[VERIFY]` per run.

### Python (MATLAB-Triggered Client)
- **`client_sdp_fixed_permutations_no_hardcoding.py`** — Reads ALL parameters from `temp_input.mat` (no hardcoding). Converts E_init fraction to p.u. energy. Sends JSON to Pi, saves `sdp_results_transfer.mat`.

### MATLAB (Laptop)
- **`DCPF_permutation_script_simplified_fixed_from_supervisor_code.m`** — Outer loop over 304 permutations. Saves `temp_input.mat` per iteration, calls `pyrunfile()`, accumulates results. Generates 4-panel statistical figure.

## Parameter Space

```matlab
eta_c_var = 0.80:0.05:0.95   % [0.80, 0.85, 0.90, 0.95]
eta_d_var = 0.80:0.05:0.95   % [0.80, 0.85, 0.90, 0.95]
Einit_var = 0.05:0.05:0.95   % 19 values (as SoC fraction, not p.u.)
% Total: 4 × 4 × 19 = 304 permutations
```

**Note on η:** Despite being swept in MATLAB, η_c and η_d are fixed at 1.0 in both solvers. `η_c × p_c` is bilinear (non-DPP), so η cannot be a `cp.Parameter()` in the compiled C binary. Only E_init, solar, and load vary genuinely.

## Running

```bash
# On Raspberry Pi:
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libopenblas.so \
    python3 server_sdp_permutations_fixed_NEW_V3.py

# On MATLAB laptop (same directory as solar_power_data.mat):
>> DCPF_permutation_script_simplified_fixed_from_supervisor_code
# Output: "Completed: 304/304 successful permutations."
```

## Results (in `results/` folder)

| File | Description |
|------|-------------|
| `Figure_1_13TH_MAY_RESULT.pdf` | 4-panel statistical figure (May 13, 2026) |
| `MATLAB_successful_runs_no_errors.txt` | MATLAB console output — all 304 permutations logged |

### Figure Description (4 panels)

| Panel | Content | Key Finding |
|-------|---------|-------------|
| Top-left | Optimal cost difference histogram | Concentrated at ~0, max < 0.012% |
| Top-right | CVXPYgen computation time (boxplot) | Median ~50 ms, IQR 50–58 ms |
| Bottom-left | Objective difference distribution | Effectively zero for all runs |
| Bottom-right | Battery charge × discharge amount | ≈ 1–5 × 10⁻⁵ (Theorem 1 validated) |

## Data Flow Per Permutation

```
MATLAB saves temp_input.mat
  ↓
pyrunfile() → client_sdp_fixed_permutations_no_hardcoding.py
  ↓
Reads temp_input.mat (eta_c, eta_d, Einit, S_base, PDmin, battery_energy_cap)
  ↓
Converts: einit_pu = current_Einit × battery_energy_cap
  ↓
TCP send to Pi (JSON: solar_pu, load_pu, einit_pu, eta_c, eta_d)
  ↓
Pi server: [CVXPY] → [CSDP] → [CVXPYgen] + [DIFF] + [VERIFY] logs
  ↓
TCP receive → saves sdp_results_transfer.mat
  ↓
MATLAB loads: cvxpy_rt, cpg_rt, cvxpy_obj, cpg_obj, p_c, p_d
  ↓
Appends to growing arrays (only successful runs — no NaN/zeros from failures)
```
