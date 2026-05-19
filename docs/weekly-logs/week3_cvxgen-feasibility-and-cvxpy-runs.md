# Week 3: CVXGEN Feasibility Analysis & CVXPY Multi-Step Deployment

**Dates:** Feb 17 – Feb 23, 2026

---

## Deliverables

- Research CVXGEN implementation feasibility for SDP problem
- Run Ariana's multi-time step Python code (CVXPY) on WSL and Raspberry Pi
- Fix and re-run `simple_sdp.c` to match `simple_sdp.m` output

## Tasks Completed

- CVXGEN feasibility research — **Feb 15, 2026**
- Multi-time step DCPF_multi_convex.py on WSL and Raspberry Pi — **Feb 20, 2026**
- simple_sdp.c constraint debugging and fix — **Feb 18, 2026**

**Problem:** `simple_sdp.c` gave incorrect outputs compared to `simple_sdp.m`. Root cause: `constraints[3]` block defining A3 was incorrectly written. After re-reading and comparing both files, I rewrote that constraint block to produce the correct output `[10 4 4 5]`.

---

## CVXGEN Feasibility Analysis

### What CVXGEN Is

CVXGEN takes a high-level description of a convex optimization problem and automatically generates custom C code for a reliable, high-speed solver. It targets problems transformable (via DCP) to **convex quadratic programs (QPs)** of modest size.

Key features: branch-free predictable code, robust numerics (regularization + iterative refinement), speedup typically **20×** vs CVX (up to 10,000× for smallest problems). Only requires a C compiler.

### What CVXGEN Supports vs Does Not Support

| Supported | NOT Supported |
|-----------|--------------|
| Linear Programs (LPs) | Semidefinite Programming (SDP) |
| Convex QPs with *vector* variables | Matrix variables (V[t] ∈ ℝ^{5×5}) |
| Linear and quadratic constraints | PSD constraints (V[t] ⪰ 0) |
| ~2000 total coefficients max | Second-order / exponential cones |

### Why CVXGEN Cannot Work Here

Our multi-period DC microgrid OPF has:
```python
V = [cp.Variable((N, N), symmetric=True) for _ in range(T)]  # 24 matrix variables
constraints.append(V[t] >> 0)  # PSD constraint per timestep
```

**Problem scale:** 845 variables, 1667 constraints, 24× (5×5) PSD cones.

CVXGEN requires vector variables — it cannot represent `V[t]` as a matrix variable. The PSD constraint `V[t] >> 0` is structurally incompatible. Although the objective is linear (CVXGEN-compatible), the problem *class* is SDP, not QP/LP.

### Alternatives Considered

**Option 1 — Fixed Voltage (LP/QP compatible):** Fix all bus voltages at nominal (v = 1.0 p.u.), remove matrix variables, retain only p, p_c, p_d, E. Makes problem linear and CVXGEN-compatible, but loses voltage optimization entirely — the core benefit of the SDP approach.

**Option 2 — Linearized Voltage Constraints:** Taylor series approximation around nominal operating point. Approximate only, accuracy depends on deviation. Potentially CVXGEN-compatible but would require iterative refinement.

**Personal recommendation:** Continue with SDP + CSDP/CVXPYgen. The exact convex relaxation with rank-1 solutions is correct, deployable, and already meets real-time requirements (CSDP: ~20 ms, CVXPYgen target: <100 ms).

### CVXPYGEN as Alternative (Initial Research)

CVXPYgen generates C code from CVXPY problem descriptions (vs CVXGEN's own DSL). **Key difference:** CVXPYgen is also limited to QP/LP problems in isolation, but because it wraps CVXPY's full conic solver (Clarabel), it *can* handle SDP when the underlying solver supports it. This became the chosen path.

---

## Running DCPF_multi_convex.py on Raspberry Pi

```bash
# On Raspberry Pi
python3 DCPF_multi_convex.py
```

Uses `solar_power_data.mat` as input. Output matches the provided `output_txt` file.

### Performance on Raspberry Pi 5

| Component | Time |
|-----------|------|
| Python/CVXPY problem parsing | ~978 ms |
| Clarabel solver (pure) | ~62 ms |
| **Total** | **~1.04–1.14 s** |
| CSDP C binary (single timestep) | ~20 ms |

**Conclusion:** CVXPY is unsuitable for real-time embedded control due to the ~1 s Python overhead, even though the Clarabel solver itself is fast (62 ms). CSDP meets real-time requirements but only solves single-timestep (27×27 matrix) not multi-period.

---

## Next Steps

Debug the C code implementation of the multi-time step problem → CVXPYgen path.
