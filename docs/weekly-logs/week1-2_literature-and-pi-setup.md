# Week 1–2: Literature Review, C Code Analysis & Raspberry Pi Setup

**Dates:** Feb 1 – Feb 17, 2026

---

## Week 1 Deliverables

- Read MATLAB/CVX code implementation and understand C code implementation on GitLab (Phase 1 documentation)
- Setup and compile a simple C program locally to verify compilation works
- Run `simple_sdp.c` and `dcpf_sdp.c` locally to check compilation and outputs
- Read and document the Haghighi et al. paper and CSDP documentation

## Week 1: Tasks Completed

- Read project milestones and deliverables (Google Docs) — **Feb 2, 2026**
- Read *"Implicit Satisfaction of Battery Complementarity Constraints In Optimal Power Flow Problems"* paper — **Feb 3–4, 2026**
- Read CSDP Documentation — **Feb 3–4, 2026**
- Compiled a simple sorting/maximum-finding C program on laptop — **Feb 5, 2026**
- Compiled `simple_sdp.c` and `dcpf_sdp.c` locally — **Feb 5, 2026**
- Created notes on paper and CSDP understanding — **Feb 5, 2026**

**Problems:** None in Week 1.

---

## Paper Analysis: "Implicit Satisfaction of Battery Complementarity Constraints"

The paper solves an optimal power flow problem for battery energy storage by modelling charging/discharging powers and enforcing a nonconvex complementarity constraint. Key insight:

> If battery inefficiency penalties are included in the objective function with a positive cost coefficient, the nonconvex complementarity constraint is **implicitly satisfied** at the optimal point — no mixed-integer solver required.

The approach combines complementarity relaxation with standard SDP techniques for voltage constraints. The product `p_c(t) · p_d(t) = 0` (battery cannot charge and discharge simultaneously) is enforced implicitly by the penalty `λ = 1×10⁻⁴` in the objective.

---

## CSDP Documentation: C Code Structure Analysis

### 27×27 Matrix Layout (`dcpf_sdp.c`)

The full DC microgrid problem is encoded as a 27×27 PSD matrix X, where:

| Diagonal entries | Variable |
|-----------------|---------|
| 1–5 | DC bus voltages (V²) |
| 6–7 | Net power flows (P²) |
| 8–10 | Battery energy states (E²) |
| 11–13 | Charging power (p_c²) |
| 14–16 | Discharging power (p_d²) |
| 17–27 | Cross-coupling terms from SDP relaxation |

Non-diagonal entries encode relationships between variables: power flow (Kirchhoff's law), voltage-current (Ohm's law), etc.

### Key Data Structures

- **`Blockmatrix`** — primal variable X (to optimize), dual slack Z, cost matrix C
- **`Constraintmatrix`** — constraints in the form `A·X = b` (19 constraints for this problem)
- **`Sparseblock`** — sparse storage for the 27×27 matrix (only upper triangle stored due to symmetry)

### C Code Pipeline

1. MATLAB microgrid parameters → converted to C arrays stored in `file_to_write.h`
2. Cost matrix C allocated and filled
3. 19 constraints built from sparse blocks
4. `initsoln()` creates initial solver guess
5. `easy_sdp()` solves and prints optimized matrix X
6. `.dat-s` and `.sol` files written in CSDP format

### `simple_sdp.c` (2×2 toy problem)

Solves `min(C,X)` subject to `(A,X) = b` with N=2, K=3 constraints. Uses `ijtok()` for 1D array representation of 2D indices, dynamic `malloc()` for C matrix, and `free_prob()` for memory cleanup.

### `dcpf_sdp.c` (27×27 full problem)

Uses `negate_cost_matrix()` to convert `max(CX)` → `min(-CX)`. `dense_to_sparseblock()` converts the 27×27 dense matrix to CSDP sparse storage. 19 constraints (`constrain_idx++` loop) encode microgrid operating limits.

---

## Week 2 Deliverables

- Setup Raspberry Pi 5 to home WiFi network
- Setup SSH to the Raspberry Pi 5
- Build CSDP dependencies and gcc
- Run simple C programs on Raspberry Pi 5
- Transfer SDP project files to Raspberry Pi 5
- Duplicate Phase 1 results on Raspberry Pi

## Week 2: Tasks Completed

All completed **Feb 10–11, 2026**.

**Problem encountered:** WiFi connectivity to Raspberry Pi using `wpa_supplicant.conf` manual configuration failed after a full day of debugging. **Solution:** Reflash SD card using Raspberry Pi Imager with SSID and password entered in the imager directly.

---

## Raspberry Pi Setup Steps (Week 2)

### A. Network Discovery
```bash
# On laptop
ipconfig                          # check adapter IPs
arp -a                            # find Pi on network

# Pi address after successful setup: 192.168.1.22
ping 192.168.1.22                 # verify connectivity (TTL check)
```

### B. SSH Into Pi
```bash
ssh anurag@192.168.1.22           # password set in Raspberry Pi Imager
```

### C. Install CSDP Dependencies
```bash
sudo apt update
sudo apt install -y build-essential cmake git
sudo apt install -y libblas-dev liblapack-dev
git clone <CSDP-github-repo>
cd CSDP
make
make clean
```

### D. Transfer Project Files
```bash
# From WSL on laptop
scp -r . anurag@192.168.1.22:/home/anurag/sdp_energy_management/
```

### E. Run and Verify simple_sdp.c
```bash
gcc -o simple_sdp simple_sdp.c -L./lib -lsdp -llapack -lblas -lm
./simple_sdp
```
Output matched local WSL results (minor DIMACS/relative gap differences due to ARM vs x86 architecture).

### F. Run and Verify dcpf_sdp.c
```bash
gcc -o dcpf_sdp dcpf_sdp.c -L./lib -lsdp -llapack -lblas -lm
./dcpf_sdp
```
Output matched local WSL results. **Phase 1 results successfully replicated on Raspberry Pi.**

---

## Performance Comparison (Single Timestep)

| Platform | dcpf_sdp.c runtime |
|----------|-------------------|
| WSL (x86) | ~18 ms |
| Raspberry Pi 5 | ~20 ms |

Minor differences in DIMACS error metrics due to architectural differences (ARM vs x86 toolchain, compiler, latency).
