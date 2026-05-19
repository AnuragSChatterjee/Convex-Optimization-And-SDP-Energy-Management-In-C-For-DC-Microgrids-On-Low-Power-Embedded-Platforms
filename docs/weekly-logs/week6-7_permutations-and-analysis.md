# Weeks 6–7: 304 Fixed Permutations, Critical Analysis & Final Results

**Dates:** Mar 31 – May 1, 2026

---

## Deliverables

- Implement 304-permutation fixed scenario benchmarking
- Convex vs non-convex cost debugging
- Runtime graphs and statistical analysis
- Critical analysis and final documentation

---

## Experiment 2: 304 Fixed Permutations Design

### Parameter Space

```
η_c:    [0.80, 0.85, 0.90, 0.95]   — 4 values
η_d:    [0.80, 0.85, 0.90, 0.95]   — 4 values
E_init: [0.05, 0.10, ..., 0.95]    — 19 values (step 0.05)

Total: 4 × 4 × 19 = 304 permutations
```

### Important: E_init Parameter Conversion

`Einit_var` in the MATLAB script represents battery state of charge as a **fraction** (5%–95% full). The Python client converts this to actual per-unit energy:

```python
einit_pu = (ei * battery_energy_cap).tolist()
# where battery_energy_cap[2] = 500e3 / 5e6 = 0.1 p.u.
```

| MATLAB `e_val` (SoC fraction) | `einit_pu[2]` shown in server log |
|-------------------------------|----------------------------------|
| 0.05 (5% full) | 0.0050 p.u. |
| 0.10 (10% full) | 0.0100 p.u. |
| 0.50 (50% full) | 0.0500 p.u. |
| 0.95 (95% full) | 0.0950 p.u. |

### Critical Design Decision: η Fixed at 1.0

Despite η_c and η_d being swept in the MATLAB loop, **both solvers use η = 1.0 fixed**. This is because `η_c × p_c[i,t]` is a bilinear product of a parameter and a variable, which violates CVXPY's **Disciplined Parameterized Programming (DPP)** rules. A non-DPP problem cannot be compiled by CVXPYgen into a C binary with updateable parameters.

```python
# NOT DPP-compliant (fails):
eta_c_param * p_c[b, t]   # parameter × variable = bilinear

# DPP-compliant alternative (used):
# Fix eta at 1.0 in binary; only Einit, solar, load vary as cp.Parameter()
```

**Implication:** The 304-permutation sweep varies E_init, solar, and load genuinely. η values are received from MATLAB but not used in either solver. Future work requires constraint reformulation to enable a true η sweep.

---

## Server Architecture: V3 Parametric Server

The key architectural change from Experiment 1 is how CVXPYgen is called. Instead of running `cpg_example` as a subprocess (Experiment 1), the **Python wrapper** is loaded once at server startup:

```python
# Load CVXPYgen Python wrapper ONCE at startup
from DCPF_multi_c.cpg_solver import cpg_solve
with open(f'{PYTHON_CODE_DIR}/DCPF_multi_c/problem.pickle', 'rb') as f:
    cpg_prob = pickle.load(f)
cpg_params = {p.name(): p for p in cpg_prob.parameters()}
```

Then per permutation, parameters are updated **in-memory** (no file I/O):

```python
cpg_params['S_PGmax'].value = S_PGmax_val
cpg_params['S_PGmin'].value = S_PGmin_val
cpg_params['S_PLoad'].value = load_pu
cpg_params['price'].value   = np.full(T, ACprice_dollar)
cpg_params['Einit'].value   = np.array(einit_pu)

t0 = time.time()
cpg_solve(cpg_prob)
rt = time.time() - t0
```

This is the **wrapper=True** approach — the fix that resolved stale objectives and 20% Clarabel failures in earlier testing.

### Server Startup Command

```bash
cd ~/sdp_energy_management_c_implementation_2/Python\ Code
LD_PRELOAD=/usr/lib/aarch64-linux-gnu/libopenblas.so \
    python3 server_sdp_permutations_fixed_NEW_V3.py
```

`LD_PRELOAD` is required because the Python wrapper needs OpenBLAS to be pre-loaded before the C extension module is imported.

---

## MATLAB Client Flow (No Hardcoding)

```matlab
% Save all parameters for Python — no hardcoding in Python client
save('temp_input.mat', 'current_eta_c', 'current_eta_d', 'current_Einit', ...
     'S_base', 'PDmin', 'battery_energy_cap');

pyrunfile('client_sdp_fixed_permutations_no_hardcoding.py');
```

The Python client reads ALL values from `temp_input.mat`:

```python
inp    = scipy.io.loadmat('temp_input.mat')
ec     = inp['current_eta_c'].item()
ed     = inp['current_eta_d'].item()
ei     = inp['current_Einit'].item()
S_base = inp['S_base'].item()
PDmin  = inp['PDmin'].flatten()
battery_energy_cap = inp['battery_energy_cap'].flatten()

# Convert E_init fraction to actual p.u. energy
einit_pu = (ei * battery_energy_cap).tolist()
```

This ensures zero hardcoding in Python — all parameters flow from MATLAB.

---

## Server Verification Logs (Sample)

```
--- Permutation 167 ---
  Received  | eta_c=0.90 eta_d=0.80 (NOT used — fixed 1.0 in both solvers)
  Einit     | bus2=0.0700pu  bus3=0.0700pu  bus4=0.0700pu
  [CVXPY]    obj=963.6882  time=1.1906s  eta=1.0
  [CSDP]     obj=-2733.3962589  time=0.1001s
  [CVXPYgen] obj=963.6880  time=0.0537s  eta=1.0 (compiled)
  [DIFF]     |cvxpy - cpg| = 0.000177  ✓ ~0
  [VERIFY]   Einit(bus2)=0.0700pu | cvxpy=963.69 | cpg=963.69 |
             prev_cpg=965.94 | cpg_changed=✓ YES
  Sent.

--- Permutation 168 ---
  Einit     | bus2=0.0750pu ...
  [CVXPYgen] obj=961.4350  time=0.0533s
  [DIFF]     |cvxpy - cpg| = 0.000040  ✓ ~0
  [VERIFY]   cpg_changed=✓ YES   ← confirms parameter updates working
```

The `[VERIFY]` line proves `cp.Parameter()` updates are genuinely propagating to the compiled C solver — each permutation sees a different objective as E_init changes.

---

## Final Results: 304/304 Successful Permutations

```
Starting 304 Sequential Iterations...
Permutation 1/304 (c=0.80, d=0.80, e=0.05)
...
Permutation 304/304 (c=0.95, d=0.95, e=0.95)
Completed: 304/304 successful permutations.
```

### Statistical Outcomes

| Metric | Value |
|--------|-------|
| Pass rate | **304/304 (100%)** |
| Mean CVXPYgen runtime (Pi) | ~50 ms |
| IQR CVXPYgen runtime | 50–58 ms |
| Max CVXPYgen runtime (outliers) | ~80 ms |
| Mean objective difference (%) | < 0.001% |
| Max objective difference (%) | < 0.012% |
| Mean battery complementarity p_c × p_d | ≈ 1–5 × 10⁻⁵ |

### Economic Insight: E_init Effect

Higher initial battery SOC monotonically reduces total generation cost:

| E_init | Approx. Objective |
|--------|-----------------|
| 0.05 (5%) | ~993 |
| 0.50 (50%) | ~970 |
| 0.95 (95%) | ~952 |

Batteries substitute for expensive AC grid power (Bus 1, price = 30 × S_base/1e6). This trend held for 100% of permutations.

### Theorem 1 Empirical Validation

```
max(p_c × p_d) across all buses, timesteps, permutations ≈ 1–7 × 10⁻⁵
```

This is effectively zero. The penalty λ = 1×10⁻⁴ implicitly enforces battery complementarity without any integer variables — confirmed at scale across the full parameter space.
